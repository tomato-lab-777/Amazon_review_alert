# Amazonレビュー監視 → スマホ通知

Amazon商品ページのレビューを定期チェックし、新着があればntfy.sh経由でスマホに通知します。
GitHub Actionsで無料・PC不要で動きます。

## 仕組み

1. GitHub Actionsが3時間おきに起動
2. `config.json` に書いたASINごとにレビューページを取得
3. 前回チェック時(`state.json`)になかったレビューIDを「新着」と判定
4. 新着があれば ntfy.sh に通知を送信 → スマホのntfyアプリに届く
5. チェック結果を `state.json` に保存してリポジトリにコミット(次回チェックの基準になる)

## セットアップ手順

### 1. スマホにntfyアプリを入れる

- iOS/Android共に「ntfy」というアプリがあります
- アプリを開いて、好きな「トピック名」を決めて購読(Subscribe)します
  - 例: `crafty-tiger-reviews-8x3k` のように、他人に推測されにくいランダムな文字列を含めるのがおすすめです
  - (ntfy.shは誰でもトピック名を知っていれば購読・投稿できる公開サーバーのため)

### 2. このフォルダをGitHubリポジトリにする

```bash
cd amazon-review-watcher
git init
git add .
git commit -m "init"
gh repo create amazon-review-watcher --private --source=. --push
# ghコマンドが無ければGitHub上で新規リポジトリを作ってpushしてください
```

### 3. GitHub Secretsを設定

リポジトリの Settings → Secrets and variables → Actions → New repository secret

| Name | 値 |
|---|---|
| `NTFY_TOPIC` | 手順1で決めたトピック名 |
| `PROXY_URL` | (任意・後述) |

### 4. `config.json` を編集

監視したい商品のASIN(Amazon商品ページURLの `/dp/XXXXXXXXXX/` の部分)を記入します。

```json
{
  "products": [
    { "asin": "実際のASIN", "name": "本棚 ブラック" }
  ]
}
```

編集したらcommit & pushしてください。

### 5. 動作確認

GitHubリポジトリの Actions タブ → "Amazon Review Watcher" → "Run workflow" で手動実行できます。
初回実行時は既存レビューを「記録」するだけで通知は送られません(2回目以降のチェックで新着があれば通知されます)。

## 重要な注意点

- **Amazonはスクレイピングを禁止(利用規約違反)しています。** 個人利用の範囲でも、Amazon側の検知でブロックされたりCAPTCHAが出るとチェックが失敗する可能性があります。GitHub Actionsのサーバー(AWS上)からのアクセスは特にブロックされやすい傾向があります。
- ブロックが頻発する場合の対策:
  - チェック頻度を下げる(cronを `0 */6 * * *` などに変更)
  - スクレイピング用プロキシサービス(ScraperAPI, Bright Data等)を契約し、`PROXY_URL` Secretに設定する
  - GitHub Actionsではなく自宅PCから定期実行する(データセンターIPではないためブロックされにくい)
- Amazon側のページ構造(HTML)が変わると、レビュー取得部分(`scrape_reviews.py` 内のCSSセレクタ)の調整が必要になることがあります。

## ファイル構成

```
amazon-review-watcher/
├── .github/workflows/check-reviews.yml  # 定期実行の設定
├── scrape_reviews.py                     # レビュー取得・通知本体
├── config.json                           # 監視するASINのリスト
├── state.json                            # 通知済みレビューの記録(自動更新)
└── README.md
```
