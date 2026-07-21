# 転シェルジュ（movecierge）

引っ越しの転出・転入手続きを、旧住所・新住所とあてはまる条件（国保・介護・子ども・車・犬など）だけで絞り込んでチェックリスト化するツールです。

**公開URL: https://meyonze.github.io/movecierge/**

## これは何か

- 転出届・転入届は全国共通ルールで処理し、市区町村ごとに違う「窓口の住所」「案内ページのURL」だけをデータとして持たせる構造になっています。
- 対応都市：東京23区＋政令指定都市＋県庁所在地クラス＋主要都市 計94都市。すべて実データ収録済みで、それ以外の市区町村は全国共通ルール＋検索リンクで代替表示されます。
- 全国1,741自治体のうち、現時点で実データがあるのは94のみです。

これはプロトタイプです。

## 構成

```
index.html            # 本体（UI・ロジック）
data/city_data.json   # 94都市分の窓口情報・URL（index.htmlがfetchで読み込む）
zenkoku_hikkoshi_research.py  # 全国の自治体データをClaude APIで自動収集するバッチスクリプト
```

## ローカルでの確認方法

`data/city_data.json` を `fetch` で読み込む構成になっているため、`index.html` を直接ブラウザで開く（`file://`）とCORSの制限で読み込めません。簡易HTTPサーバーを立てて確認してください。

```bash
python3 -m http.server 8000
# ブラウザで http://localhost:8000/ を開く
```

## データの追加・更新

```bash
pip install anthropic --break-system-packages
export ANTHROPIC_API_KEY=sk-ant-...

# まず少数で試す
python zenkoku_hikkoshi_research.py --limit 20

# 本番実行（中断しても再実行で続きから）
python zenkoku_hikkoshi_research.py --workers 4
```

`confidence: low` の結果は `data/city_data_review.json` に分離されます。目視確認してから `data/city_data.json` に反映してください。詳細は `CLAUDE.md` を参照。
