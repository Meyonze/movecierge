# 転シェルジュ（movecierge）

引っ越しの転出・転入手続きを、旧住所・新住所とあてはまる条件（国保・介護・子ども・車・犬など）だけで絞り込んでチェックリスト化するツールです。

**公開URL: https://meyonze.github.io/movecierge/**

## これは何か

- 転出届・転入届は全国共通ルールで処理し、市区町村ごとに違う「窓口の住所」「案内ページのURL」だけをデータとして持たせる構造になっています。
- 全国1,740市区町村を検索対象にしており、1,441件の窓口情報・公式案内URLを収録しています。未収録の自治体は全国共通ルールと公式サイト検索へのリンクで案内します。
- 収録データには自動調査の結果も含まれます。低信頼度の候補は公開用データと分離し、個別に確認してから反映します。

これはプロトタイプです。

## 構成

```
index.html            # 本体（UI・ロジック）
data/cities.json      # 全国の自治体一覧
data/city_data.json   # 収録済みの窓口情報・公式案内URL
data/city_data_review.json # 要確認の調査結果（公開用データには未反映）
scripts/validate-data.mjs  # データ構造・ID・URLの検証
zenkoku_hikkoshi_research.py  # 全国の自治体データをClaude APIで自動収集するバッチスクリプト
```

## データ検証

データを変更したら、公開前に次を実行します。GitHub Actionsでも同じ検証を行います。

```bash
node scripts/validate-data.mjs
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
