#!/usr/bin/env python3
"""
zenkoku_hikkoshi_research.py
=============================

全国の市区町村について、転出届・転入届の公式ページURLと窓口情報を
Claude API (web_search ツール) を使って自動収集するバッチスクリプト。

【できること】
  - 全国の市区町村リストを Geolonia の住所オープンデータから自動取得
    （政令指定都市の「〇〇市△△区」はシティレベルに自動集約。東京23区はそのまま）
  - 1自治体につき1回の Claude API 呼び出しで「検索→URL抽出→JSON整形」を実行
  - 結果を data/city_data.json に逐次保存（中断してもそこから再開できる）
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
  - web_search ツールの type 文字列（"web_search_20260318"）は Anthropic 側で更新されることが
    あるため、実行前に https://docs.claude.com/en/docs/agents-and-tools/tool-use/web-search-tool
    で最新の値を確認してください。
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
import urllib.request
from pathlib import Path

import anthropic

MUNICIPALITY_LIST_URL = "https://geolonia.github.io/japanese-addresses/api/ja.json"

OUTPUT_DIR = Path("data")
OUTPUT_FILE = OUTPUT_DIR / "city_data.json"
REVIEW_FILE = OUTPUT_DIR / "city_data_review.json"

# 「〇〇市△△区」（政令指定都市の行政区）を「〇〇市」に丸めるための正規表現。
# 東京23区は「市」を含まない単独の「△△区」なのでこのパターンにはマッチせず、そのまま残る。
WARD_PATTERN = re.compile(r"^(.+?市)(.+区)$")

WEB_SEARCH_TOOL_TYPE = "web_search_20260318"  # 実行前に最新版か要確認

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


def fetch_municipality_list() -> list[dict]:
    """全国市区町村リストを取得し、政令市の行政区をシティレベルに統合する。"""
    with urllib.request.urlopen(MUNICIPALITY_LIST_URL) as res:
        data = json.loads(res.read().decode("utf-8"))

    seen = set()
    municipalities = []
    for pref, cities in data.items():
        for city in cities:
            m = WARD_PATTERN.match(city)
            normalized = m.group(1) if m else city
            key = (pref, normalized)
            if key in seen:
                continue
            seen.add(key)
            municipalities.append({"pref": pref, "city": normalized})
    return municipalities


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


def load_existing(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        records = json.load(f)
    return {f"{r['pref']}/{r['city']}": r for r in records}


def save_all(path: Path, records: dict):
    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list(records.values()), f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="全国自治体の転入・転出届ページを自動収集する")
    parser.add_argument("--start", type=int, default=0, help="開始インデックス")
    parser.add_argument("--limit", type=int, default=None, help="処理件数（省略時は全件）")
    parser.add_argument("--workers", type=int, default=4, help="並列実行数（控えめ推奨）")
    parser.add_argument(
        "--model",
        type=str,
        default="claude-haiku-4-5-20251001",
        help="使用するモデル（例: claude-haiku-4-5-20251001 / claude-sonnet-5）",
    )
    args = parser.parse_args()

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY を環境変数から自動取得

    all_municipalities = fetch_municipality_list()
    print(f"全国の市区町村: {len(all_municipalities)} 件（政令市の区をシティ単位に集約後）")

    target = (
        all_municipalities[args.start : args.start + args.limit]
        if args.limit
        else all_municipalities[args.start :]
    )

    existing = load_existing(OUTPUT_FILE)
    todo = [m for m in target if f"{m['pref']}/{m['city']}" not in existing]
    print(f"未処理: {len(todo)} 件（既存 {len(existing)} 件はスキップして続きから実行）")

    lock = threading.Lock()
    done_count = 0

    def worker(m: dict) -> tuple[dict, dict]:
        for attempt in range(3):
            try:
                result = research_city(client, m["pref"], m["city"], args.model)
                return m, result
            except anthropic.RateLimitError:
                time.sleep(5 * (attempt + 1))
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    return m, {"pref": m["pref"], "city": m["city"], "error": str(e)}
                time.sleep(2)
        return m, {"pref": m["pref"], "city": m["city"], "error": "retry_exhausted"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(worker, m) for m in todo]
        for future in concurrent.futures.as_completed(futures):
            m, result = future.result()
            key = f"{m['pref']}/{m['city']}"

            with lock:
                existing[key] = result
                done_count += 1
                if done_count % 10 == 0:
                    save_all(OUTPUT_FILE, existing)

            status = (
                "OK"
                if result.get("confidence") == "high"
                else ("要確認" if "error" not in result else f"失敗:{result.get('error')}")
            )
            print(f"[{done_count}/{len(todo)}] {m['pref']}{m['city']} … {status}")

    save_all(OUTPUT_FILE, existing)

    low_conf = [
        r for r in existing.values() if r.get("confidence") == "low" or "error" in r
    ]
    with open(REVIEW_FILE, "w", encoding="utf-8") as f:
        json.dump(low_conf, f, ensure_ascii=False, indent=2)

    print(f"\n完了。合計 {len(existing)} 件 → {OUTPUT_FILE}")
    print(f"要確認・失敗: {len(low_conf)} 件 → {REVIEW_FILE}")


if __name__ == "__main__":
    main()
