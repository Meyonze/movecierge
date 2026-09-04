#!/usr/bin/env python3
"""
zenkoku_hikkoshi_research.py
=============================

全国の市区町村について、転出届・転入届の公式ページURLと窓口情報を
Claude API (web_search ツール) を使って自動収集するバッチスクリプト。

【できること】
  - data/cities.json の全国市区町村リストを対象に自動収集
  - 1自治体につき1回の Claude API 呼び出しで「検索→URL抽出→JSON整形」を実行
  - 高信頼度の結果を data/city_data.json、要確認結果を
    data/city_data_review.json に逐次保存（中断してもそこから再開できる）
  - 信頼度が低い（＝要目視確認）結果を data/city_data_review.json に分離

【使い方】
    pip install anthropic --break-system-packages   # 環境によっては不要
    export ANTHROPIC_API_KEY=sk-ant-...

    # まず10件だけ試す
    python zenkoku_hikkoshi_research.py --limit 10

    # 本番実行（再実行すると既存分をスキップして続きから進む）
    python zenkoku_hikkoshi_research.py --workers 4

【コスト目安（2026年7月時点の公開価格ベース）】
    web_search: $10 / 1,000回
    Claude Haiku 4.5: $1 / 100万入力トークン、$5 / 100万出力トークン
    → 全国約1,741自治体、1自治体あたり平均1.5検索・6,000入力/300出力トークン程度と仮定すると
      総額でおよそ 40〜60 ドル（数千円）程度。実際の検索回数は自治体ごとに変動するため、
      まず --limit 50 程度で試し、Anthropic Console の使用量画面で実コストを確認してから
      全件実行することを推奨。

【注意】
  - web_search ツールの type 文字列は "web_search_20250305"（基本版）を使用している。
    Haiku 4.5 はダイナミックフィルタリング版（"web_search_20260209"、Opus 4.8/4.7/4.6・
    Sonnet 5・Sonnet 4.6 のみ対応）を使えないため。モデルを変更する場合は対応する
    type 文字列も見直すこと。最新情報は
    https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-search-tool を参照。
  - 自動抽出したURL・窓口情報は完璧ではありません。confidence が "low" のものは
    data/city_data_review.json にまとまるので、公開前に目視で確認してください。
  - 極端に短時間で大量リクエストを送るとレート制限に当たることがあります。
    --workers は控えめ（3〜5程度）から始めてください。
"""

import argparse
import concurrent.futures
import json
import re
import threading
import time
from pathlib import Path

import anthropic

OUTPUT_DIR = Path("data")
CITY_LIST_FILE = OUTPUT_DIR / "cities.json"
OUTPUT_FILE = OUTPUT_DIR / "city_data.json"
REVIEW_FILE = OUTPUT_DIR / "city_data_review.json"

WEB_SEARCH_TOOL_TYPE = "web_search_20250305"  # Haiku 4.5はダイナミックフィルタリング版(web_search_20260209)非対応のため基本版を使用

SYSTEM_PROMPT = """あなたは日本の自治体の住民異動手続き（転出届・転入届）のページを調べる
リサーチアシスタントです。

与えられた市区町村について、web_search ツールを使って公式サイト
（多くは .lg.jp ドメイン、まれに独自ドメインの場合もある）から次の情報を調べ、
JSON以外は一切出力せず、次のスキーマだけを返してください。マークダウンの```は付けないこと。

{
  "office": "窓口の説明。区の有無・支所や出張所の構成など。100字程度、日本語で。",
  "out_url": "転出届の案内ページURL。見つからなければ null",
  "in_url": "転入届の案内ページURL。見つからなければ null",
  "mail_url": "郵送による転出届のページURL。見つからなければ null",
  "confidence": "\"high\" または \"low\"。
                 公式ドメインで転出届・転入届それぞれの専用ページを直接確認できた場合は high。
                 第三者サイトしか見つからない、情報が古い可能性がある、
                 該当ページが特定できない場合は low。",
  "notes": "特記事項。区制の有無、オンライン対応の可否など。40字程度。任意。"
}

公式サイト以外（引越し業者のまとめサイトや不動産会社のブログなど）の情報は、
参考にはしてよいが、URLとしては採用しないこと（office や notes の裏取りには使ってよい）。
"""


def load_city_list() -> list[dict]:
    """公開画面と同じ自治体ID・名称を持つローカル一覧を読み込む。"""
    with open(CITY_LIST_FILE, "r", encoding="utf-8") as f:
        cities = json.load(f)
    if not isinstance(cities, list):
        raise ValueError(f"{CITY_LIST_FILE} は自治体一覧の配列である必要があります")
    required = {"id", "name", "pref"}
    invalid = [city for city in cities if not required.issubset(city)]
    if invalid:
        raise ValueError(f"{CITY_LIST_FILE} に必須項目がない自治体があります: {invalid[0]}")
    return cities


def research_city(client: anthropic.Anthropic, pref: str, city: str, model: str) -> dict:
    message = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[{"type": WEB_SEARCH_TOOL_TYPE, "name": "web_search"}],
        messages=[
            {
                "role": "user",
                "content": f"{pref}{city} の転入届・転出届の手続きページを調べてください。",
            }
        ],
    )

    text_blocks = [block.text for block in message.content if block.type == "text"]
    raw = "\n".join(text_blocks).strip()
    raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"error": "json_parse_failed", "raw": raw}

    parsed["pref"] = pref
    parsed["city"] = city
    return parsed


def load_records(path: Path) -> dict:
    """公開用スキーマ（自治体IDをキーにしたオブジェクト）を読み込む。"""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)
    if not isinstance(records, dict):
        raise ValueError(
            f"{path} は自治体IDをキーにしたJSONオブジェクトである必要があります。"
            " 旧形式の配列は data/city_data_legacy.json などへ退避してから実行してください。"
        )
    return records


def save_records(path: Path, records: dict):
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
        f.write("\n")


def is_http_url(value: object) -> bool:
    return isinstance(value, str) and value.startswith(("https://", "http://"))


def to_public_record(result: dict) -> dict:
    """APIの生データを画面・検証スクリプトが読むスキーマへ変換する。"""
    office = result.get("office")
    office = office.strip() if isinstance(office, str) else ""
    links = {
        "out": result.get("out_url") if is_http_url(result.get("out_url")) else None,
        "in": result.get("in_url") if is_http_url(result.get("in_url")) else None,
        "mail": result.get("mail_url") if is_http_url(result.get("mail_url")) else None,
    }
    record = {
        "hasData": bool(office or any(links.values())),
        "office": office,
        "links": links,
        "confidence": "high" if result.get("confidence") == "high" else "low",
    }
    if isinstance(result.get("notes"), str) and result["notes"].strip():
        record["notes"] = result["notes"].strip()
    if result.get("error"):
        record["error"] = str(result["error"])
    return record


def main():
    parser = argparse.ArgumentParser(description="全国自治体の転入・転出届ページを自動収集する")
    parser.add_argument("--start", type=int, default=0, help="開始インデックス")
    parser.add_argument("--limit", type=int, default=None, help="処理件数（省略時は全件）")
    parser.add_argument("--workers", type=int, default=4, help="並列実行数（控えめ推奨）")
    parser.add_argument(
        "--retry-reviewed",
        action="store_true",
        help="レビュー用データにある自治体も再調査する（公開済みデータは常にスキップ）",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-haiku-4-5-20251001",
        help="使用するモデル（例: claude-haiku-4-5-20251001 / claude-sonnet-5）",
    )
    args = parser.parse_args()

    all_municipalities = load_city_list()
    print(f"全国の市区町村: {len(all_municipalities)} 件（data/cities.json）")

    target = (
        all_municipalities[args.start : args.start + args.limit]
        if args.limit
        else all_municipalities[args.start :]
    )

    public_records = load_records(OUTPUT_FILE)
    review_records = load_records(REVIEW_FILE)
    todo = [
        m for m in target
        if m["id"] not in public_records
        and (args.retry_reviewed or m["id"] not in review_records)
    ]
    print(
        f"未処理: {len(todo)} 件（公開済み {len(public_records)} 件、"
        f"レビュー済み {len(review_records)} 件はスキップして続きから実行）"
    )

    if not todo:
        print("対象の未処理自治体はありません。")
        return

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY を環境変数から自動取得

    lock = threading.Lock()
    done_count = 0

    def worker(m: dict) -> tuple[dict, dict]:
        for attempt in range(3):
            try:
                result = research_city(client, m["pref"], m["name"], args.model)
                return m, result
            except anthropic.RateLimitError:
                time.sleep(5 * (attempt + 1))
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    return m, {"pref": m["pref"], "city": m["name"], "error": str(e)}
                time.sleep(2)
        return m, {"pref": m["pref"], "city": m["name"], "error": "retry_exhausted"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(worker, m) for m in todo]
        for future in concurrent.futures.as_completed(futures):
            m, result = future.result()
            record = to_public_record(result)

            with lock:
                if record["confidence"] == "high" and record["office"] and record["links"]["out"] and record["links"]["in"]:
                    public_records[m["id"]] = record
                    review_records.pop(m["id"], None)
                else:
                    review_records[m["id"]] = record
                done_count += 1
                if done_count % 10 == 0:
                    save_records(OUTPUT_FILE, public_records)
                    save_records(REVIEW_FILE, review_records)

            status = (
                "OK"
                if result.get("confidence") == "high"
                else ("要確認" if "error" not in result else f"失敗:{result.get('error')}")
            )
            print(f"[{done_count}/{len(todo)}] {m['pref']}{m['name']} … {status}")

    save_records(OUTPUT_FILE, public_records)
    save_records(REVIEW_FILE, review_records)

    print(f"\n完了。公開用: {len(public_records)} 件 → {OUTPUT_FILE}")
    print(f"要確認・失敗: {len(review_records)} 件 → {REVIEW_FILE}")


if __name__ == "__main__":
    main()
