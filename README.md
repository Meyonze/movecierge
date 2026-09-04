# 転シェルジュ（movecierge）

引っ越しの転出・転入手続きを、旧住所・新住所とあてはまる条件（国保・介護・子ども・車・犬など）だけで絞り込んでチェックリスト化するツールです。

**公開URL: https://meyonze.github.io/movecierge/**

## これは何か

- 転出届・転入届は全国共通ルールで処理し、市区町村ごとに違う「窓口の住所」「案内ページのURL」だけをデータとして持たせる構造になっています。
- 全国1,740市区町村を検索対象にしており、1,441件の窓口情報・公式案内URLを収録しています。未収録の自治体は全国共通ルールと公式サイト検索へのリンクで案内します。
- 収録データには自動調査の結果も含まれます。低信頼度の候補は公開用データと分離し、個別に確認してから反映します。
- 完了にしたチェック項目は、その端末のブラウザ内に保存されます。住所ごとの手続きと全国共通の手続きを分けて保持し、外部には送信しません。
- 作成後は完了数を確認でき、必要なら「この端末の進捗をすべてリセット」から保存済みの進捗を消去できます。

これはプロトタイプです。

## 構成

```
index.html            # 本体（UI・ロジック）
data/cities.json      # 全国の自治体一覧
data/city_data.json   # 収録済みの窓口情報・公式案内URL
data/city_data_review.json # 要確認の調査結果（公開用データには未反映）
scripts/validate-data.mjs  # データ構造・ID・URLの検証
docs/DATA_QUALITY.md       # データ品質の基準と確認優先順位
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

# macOS / Linux
export ANTHROPIC_API_KEY=sk-ant-...

# PowerShell
$env:ANTHROPIC_API_KEY = 'sk-ant-...'

# まず少数で試す
python zenkoku_hikkoshi_research.py --limit 20

# 本番実行（中断しても再実行で続きから）
python zenkoku_hikkoshi_research.py --workers 4
```

スクリプトは `data/cities.json` の自治体IDを正として、画面が読むJSON形式のまま保存します。`confidence: high` かつ窓口・転出・転入の情報がそろった結果だけを `data/city_data.json` に入れ、それ以外は `data/city_data_review.json` に分離します。レビュー済みの候補を再調査する場合は `--retry-reviewed` を付けてください。
