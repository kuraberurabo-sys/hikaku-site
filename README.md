# hikaku-site

楽天市場の商品検索APIの価格から、比較ページを毎日自動で作り直す静的サイト。3つのパターンを同じサイトに置き、どれが伸びるかを観察する。

| セクション | パス | 中身 | 楽天API |
|---|---|---|---|
| PCパーツ | `/pc/` | GPU・CPUのコスパとモデル別最安値、SSD・メモリ・HDD・電源の単価、モニターの最安 | 使う |
| ガジェット | `/gadget/` | microSD・モバイルバッテリーの単価、ゲーム機本体の最安 | 使う |
| 日用品・食品 | `/tanka/` | プロテイン、お米、水、トイレットペーパー、ティッシュ、おむつ、ペットフードの単価 | 使う |
| 電気代 | `/denki/` | 家電ごとの電気代早見表（`data/denki.json`） | 使わない |
| サイズ早見表 | `/size/` | モニターとテレビのインチ→cm | 使わない |
| 計算ツール | `/tools/` | ブラウザ内で動く計算機 | 使わない |

楽天APIを使うページは、`build.py` の `SECTIONS` に「データファイル名と種類」を並べて定義している。種類は3つ。

- `value`: スコア÷実質価格のランキング。モデルごとの最安値ページも作る（`models` を持つファイル）
- `unit`: 内容量あたりの単価のランキング。`amount` で内容量を固定するか、`amount_from` の正規表現で商品名から読む
- `cheapest`: 区分ごとに実質価格が安い順

## 仕組み

- `build.py` が `dist/` にHTMLを生成する。Python標準ライブラリだけで動く。
- `.github/workflows/deploy.yml` が毎日06:17（日本時間）に実行し、GitHub Pagesへ公開する。
- 楽天のキーが未設定のときはサンプルデータで生成し、価格ページに noindex と注意書きを付ける。
- 取得した価格はどこにも保存しない（楽天ウェブサービス規約への配慮）。生成したHTMLだけが公開される。

## セットアップ

1. GitHubでPublicリポジトリ `hikaku-site` を作り、このフォルダの中身をすべてアップロードする（`.github` フォルダを含む）。
2. `site.json` の `base_url` を `https://<ユーザー名>.github.io/hikaku-site/` に書き換える。`name` `operator` `contact` も実際の内容にする。
3. リポジトリの Settings → Pages → Source を「GitHub Actions」にする。
4. Actions タブで `build-and-deploy` を手動実行し、サンプル表示のサイトが開くことを確認する。
5. 楽天ウェブサービスでアプリを登録し、アプリケーションID・アクセスキー・アフィリエイトIDを取得する。アプリのURLと許可するサイトには手順2のURLを登録する。
6. Settings → Secrets and variables → Actions に次の3つを登録する。
   - `RAKUTEN_APP_ID`
   - `RAKUTEN_ACCESS_KEY`
   - `RAKUTEN_AFFILIATE_ID`
7. もう一度 `build-and-deploy` を手動実行し、実際の価格が出ることを確認する。
8. Google Search Console に「URLプレフィックス」でサイトを追加し、HTMLタグ方式の `content` の値を `site.json` の `search_console_verification` に入れる。確認後、`sitemap.xml` を送信する。

## データの直し方

- 「条件に合う出品が見つからなかった」と出るモデルは、`min_price` が高すぎるか、`must` の表記が出品名と合っていない。
- 違う商品が混ざるときは、`exclude` に除外したい語を足す。
- 新しいモデルや商品は、各JSONの `models` / `products` に1行足す。
- ベンチマークスコアは PassMark の公開値を手で写したもの。新製品が出たら更新する。

## 経過観察（月1回）

- Search Console の「ページ」フィルタで `/pc/` `/tanka/` `/tools/` ごとの表示回数とクリック数を見る。
- 楽天アフィリエイトの管理画面でクリック数と成果を見る。
- Actions の定期実行が止まっていないか確認する。GitHubは、リポジトリに60日間動きがないと定期実行を自動で無効にする（メールで通知が来る）。
- 6か月たっても表示回数がほぼ0のパターンは、やめるか題材を入れ替える。

## ローカルで試す

```bash
python build.py
python -m http.server 8765 --directory dist
```
