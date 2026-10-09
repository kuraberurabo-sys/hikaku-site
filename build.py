"""サイト生成スクリプト。標準ライブラリのみで動く。

環境変数 RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY があれば楽天市場商品検索APIから
価格を取得し、なければサンプルデータで生成する（動作確認用。noindex を付ける）。
取得したデータはファイルに保存せず、生成したHTMLにだけ反映する。
"""
import datetime
import html
import json
import os
import re
import shutil
import statistics
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
REQUEST_INTERVAL = 1.5  # 秒。1秒1回程度の制限に対する余裕

APP_ID = os.environ.get("RAKUTEN_APP_ID", "")
ACCESS_KEY = os.environ.get("RAKUTEN_ACCESS_KEY", "")
AFFILIATE_ID = os.environ.get("RAKUTEN_AFFILIATE_ID", "")
LIVE = bool(APP_ID and ACCESS_KEY)

SITE = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
JST = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime.now(JST)
STAMP = NOW.strftime("%Y年%m月%d日 %H:%M")

CREDIT = (
    '<!-- Rakuten Web Services Attribution Snippet FROM HERE -->\n'
    '<a href="https://webservice.rakuten.co.jp/" target="_blank"><img src="https://webservice.rakuten.co.jp/img/credit/200709/credit_22121.gif" border="0" alt="Rakuten Web Service Center" title="Rakuten Web Service Center" width="221" height="21"/></a>\n'
    '<!-- Rakuten Web Services Attribution Snippet TO HERE -->'
)

stats = {"ok": 0, "fail": 0}
_last_request = 0.0


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


# ---------- 商品名の照合 ----------

SEPARATORS = r"[\s\-‐ー_/]"


def norm(text):
    """全角半角と大文字小文字の違いを吸収する。"""
    # 商標記号は NFKC で "TM" になり型番の照合を壊すので先に消す
    return unicodedata.normalize("NFKC", re.sub("[™®©]", "", text)).upper()


def has_token(name, token):
    """空白やハイフンの有無を無視して token を探す（"RTX5070" は "RTX 5070" に一致）。

    別の語の一部には一致させない。"5KG" は "15KG" に、"B570" は "B570170K" に、
    "ARC" は "BARCO" に一致しない。
    """
    chars = re.sub(SEPARATORS, "", norm(token))
    before = ""
    if chars[:1].isdigit():
        before = r"(?<![\d.])"
    elif chars[:1].isascii() and chars[:1].isalpha() and len(chars) <= 4:
        # 長いトークンは "GEFORCERTX5070" のような連結表記を拾えるよう前方は縛らない
        before = r"(?<![A-Z])"
    after = r"(?![A-Z0-9])" if chars[-1:].isascii() and chars[-1:].isalnum() else ""
    pattern = before + (SEPARATORS + "*").join(re.escape(c) for c in chars) + after
    return re.search(pattern, name) is not None


WEIGHT = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:KG|キロ)")


def matches(item_name, must, exclude, single_size=False):
    """must は「いずれかを含む」グループのリスト。全グループを満たし、exclude を含まなければ一致。"""
    name = norm(item_name)
    # 複数の重量が書かれた出品は「選べる容量」で、表示価格が最小サイズのものなので外す
    if single_size and len({float(w) for w in WEIGHT.findall(name)}) > 1:
        return False
    if any(has_token(name, t) for t in exclude):
        return False
    return all(any(has_token(name, t) for t in group) for group in must)


# ---------- 楽天API ----------

def api_search(keyword, min_price, page=1, ng_keyword="", max_price=None):
    global _last_request
    query = {
        "applicationId": APP_ID,
        "accessKey": ACCESS_KEY,
        "keyword": keyword,
        "format": "json",
        "formatVersion": 2,
        "hits": 30,
        "page": page,
        "sort": "+itemPrice",
        "availability": 1,
        "minPrice": min_price,
    }
    if AFFILIATE_ID:
        query["affiliateId"] = AFFILIATE_ID
    if ng_keyword:
        query["NGKeyword"] = ng_keyword
    if max_price:
        query["maxPrice"] = max_price
    parts = urllib.parse.urlsplit(SITE["base_url"])
    origin = f"{parts.scheme}://{parts.netloc}"
    request = urllib.request.Request(
        ENDPOINT + "?" + urllib.parse.urlencode(query),
        # 楽天側の「許可されたWebサイト」と照合されるので、公開サイトのURLを名乗る
        headers={"Referer": SITE["base_url"], "Origin": origin, "User-Agent": "hikaku-site-builder"},
    )
    for attempt in range(3):
        wait = REQUEST_INTERVAL - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                stats["ok"] += 1
                return json.loads(response.read().decode("utf-8")).get("Items", [])
        except urllib.error.HTTPError as error:
            if error.code == 404:  # 該当なし
                stats["ok"] += 1
                return []
            # URLにはキーが含まれるので出さない。応答本文のエラー内容だけを出す
            detail = error.read().decode("utf-8", "replace")[:200].replace("\n", " ")
            print(f"  API error {error.code} ({keyword}) attempt {attempt + 1}: {detail}", file=sys.stderr)
            if error.code not in (429, 500, 503):
                break
            time.sleep(5 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError) as error:
            print(f"  network error ({keyword}): {type(error).__name__}", file=sys.stderr)
            time.sleep(5)
    stats["fail"] += 1
    if stats["ok"] == 0 and stats["fail"] >= 3:
        # 認証や設定の問題なので、残りを試さずに止める（前回の公開内容が残る）
        sys.exit("first API requests all failed; aborting so the previous deployment stays")
    return None


def sample_items(spec):
    """APIキーがないときの仮データ。実在の価格ではない。"""
    price = int(spec["min_price"] * 1.7 // 10 * 10)
    name = spec["name"] + " " + " ".join(g[0] for g in spec["must"])
    return [{"itemName": name, "itemPrice": price, "pointRate": 1, "postageFlag": 0,
             "shopName": "サンプル店", "itemUrl": "#", "mediumImageUrls": []}]


def offers_for(spec, common_exclude, ng_keyword="", limit=1, siblings=()):
    """spec に一致する出品を、ポイント込みの実質価格が安い順に返す。取得失敗は None。

    siblings は同じ表に並ぶ他の spec。複数モデルから選ぶ形式の出品は、表示価格が
    最安モデルのものなので、他の spec にも一致する出品は外す。
    """
    exclude = common_exclude + spec.get("exclude", []) + ["ふるさと納税"]

    def is_other_model(name):
        return any(
            other is not spec and matches(name, other["must"], other.get("exclude", []))
            for other in siblings
        )

    ng_keyword = " ".join(filter(None, [ng_keyword, spec.get("ng_keyword", "")]))
    found = []
    for page in (1, 2):
        if LIVE:
            items = api_search(spec["keyword"], spec["min_price"], page, ng_keyword, spec.get("max_price"))
        else:
            items = sample_items(spec) if page == 1 else []
        if items is None:
            return None
        for raw in items:
            item = raw.get("Item", raw)
            name = item.get("itemName", "")
            if matches(name, spec["must"], exclude, spec.get("single_size", False)) and not is_other_model(name):
                found.append(item)
        if found or len(items) < 30:
            break
    if not found:
        return []
    # 付属品や部品の混入を避けるため、中央値から大きく外れて安いものを落とす
    median = statistics.median(i["itemPrice"] for i in found)
    offers = []
    for item in found:
        price = item["itemPrice"]
        if price < median * 0.6:
            continue
        points = price * int(item.get("pointRate") or 1) // 100
        offers.append({
            "name": item.get("itemName", ""),
            "price": price,
            "points": points,
            "effective": price - points,
            "shop": item.get("shopName", ""),
            "url": item.get("affiliateUrl") or item.get("itemUrl", "#"),
            "postage_extra": item.get("postageFlag") == 1,
        })
    offers.sort(key=lambda o: o["effective"])
    return offers[:limit]


# ---------- HTML ----------

def esc(value):
    return html.escape(str(value), quote=True)


def yen(value):
    return f"{value:,}円"


def page(path, title, description, body, uses_api=False):
    """path は dist からの相対ディレクトリ（"" がトップ）。"""
    depth = len([p for p in path.split("/") if p])
    rel = "../" * depth
    head_extra = ""
    if SITE.get("search_console_verification"):
        head_extra += f'<meta name="google-site-verification" content="{esc(SITE["search_console_verification"])}">\n'
    notices = ""
    if uses_api:
        notices += '<p class="notice">本ページはアフィリエイト広告を利用しています。</p>\n'
        if not LIVE:
            head_extra += '<meta name="robots" content="noindex">\n'
            notices += '<p class="notice warn">表示中の価格はサンプルデータです。実在の価格ではありません。</p>\n'
    nav = "".join(
        f'<a href="{rel}{href}">{esc(label)}</a>'
        for href, label in [("", "トップ"), ("pc/", "PCパーツ"), ("tanka/", "単価比較"), ("tools/", "計算ツール"), ("about/", "このサイトについて")]
    )
    credit = f'<div class="credit">{CREDIT}</div>' if uses_api else ""
    document = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} | {esc(SITE["name"])}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(SITE["base_url"] + path)}">
{head_extra}<link rel="stylesheet" href="{rel}style.css">
</head>
<body>
<header><a class="brand" href="{rel}">{esc(SITE["name"])}</a><nav>{nav}</nav></header>
<main>
<h1>{esc(title)}</h1>
{notices}{body}
</main>
<footer>{credit}<p>&copy; {NOW.year} {esc(SITE["name"])}</p></footer>
</body>
</html>
"""
    target = DIST / path
    target.mkdir(parents=True, exist_ok=True)
    (target / "index.html").write_text(document, encoding="utf-8")
    PAGES.append(path)


def table(headers, rows):
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def offer_cells(offer):
    postage = ' <span class="tag">送料別</span>' if offer["postage_extra"] else ""
    link = f'<a href="{esc(offer["url"])}" rel="nofollow sponsored noopener" target="_blank">{esc(offer["shop"])}</a>'
    return [yen(offer["price"]) + postage, f'{offer["points"]:,}pt', f'<strong>{yen(offer["effective"])}</strong>', link]


def price_note():
    return (f'<p class="note">価格は{STAMP}時点で楽天市場の商品検索から取得したものです。'
            "ポイントは商品ごとの通常倍率のみで計算しており、キャンペーンや会員ランクによる上乗せは含みません。"
            "最新の価格・送料・在庫はリンク先でご確認ください。</p>")


def cards(items):
    return '<div class="cards">' + "".join(
        f'<a class="card" href="{esc(href)}"><strong>{esc(title)}</strong><span>{esc(text)}</span></a>'
        for href, title, text in items) + "</div>"


# ---------- パターンA: PCパーツのコスパ ----------

def build_value_ranking(path, data):
    rows, missing = [], []
    for spec in data["models"]:
        offers = offers_for(spec, data["exclude"], data.get("ng_keyword", ""), siblings=data["models"])
        if not offers:
            missing.append(spec["name"] + ("（取得失敗）" if offers is None else ""))
            continue
        offer = offers[0]
        rows.append((spec["score"] / offer["effective"] * 10000, spec, offer))
    rows.sort(key=lambda r: -r[0])
    table_rows = [
        [str(rank), esc(spec["name"]), f'{spec["score"]:,}', *offer_cells(offer), f"<strong>{value:,.0f}</strong>"]
        for rank, (value, spec, offer) in enumerate(rows, 1)
    ]
    body = f'<p>{esc(data["lead"])}</p>'
    body += table(["順位", "モデル", data["score_label"], "最安価格", "ポイント", "実質価格", "ショップ", "1万円あたりスコア"], table_rows)
    body += price_note()
    body += f'<p class="note">{esc(data["score_note"])}</p>'
    if missing:
        body += '<p class="note">現在、条件に合う出品が見つからなかったモデル: ' + esc("、".join(missing)) + "</p>"
    page(path, data["title"], data["description"], body, uses_api=True)


# ---------- パターンB: 消耗品の単価 ----------

def build_unit_price(path, data):
    rows, missing = [], []
    for spec in data["products"]:
        offers = offers_for(spec, data["exclude"], data.get("ng_keyword", ""), limit=spec.get("limit", 1), siblings=data["products"])
        if not offers:
            missing.append(spec["name"] + ("（取得失敗）" if offers is None else ""))
            continue
        for offer in offers:
            rows.append((offer["effective"] / spec["amount"] * data["per"], spec, offer))
    rows.sort(key=lambda r: r[0])
    table_rows = [
        [str(rank), esc(spec["name"]), f'{spec["amount"]:,}{esc(data["unit"])}', *offer_cells(offer), f"<strong>{unit_price:,.0f}円</strong>"]
        for rank, (unit_price, spec, offer) in enumerate(rows, 1)
    ]
    body = f'<p>{esc(data["lead"])}</p>'
    body += table(["順位", "商品", "内容量", "価格", "ポイント", "実質価格", "ショップ", data["per_label"]], table_rows)
    body += price_note()
    if missing:
        body += '<p class="note">現在、条件に合う出品が見つからなかった商品: ' + esc("、".join(missing)) + "</p>"
    page(path, data["title"], data["description"], body, uses_api=True)


# ---------- パターンC: 計算ツール ----------

def build_tools():
    tools = []
    for source in sorted((ROOT / "tools").glob("*.html")):
        text = source.read_text(encoding="utf-8")
        meta = dict(re.findall(r"^<!--\s*(title|description):\s*(.+?)\s*-->$", text, re.M))
        page(f"tools/{source.stem}/", meta["title"], meta["description"], text)
        tools.append((f"{source.stem}/", meta["title"], meta["description"]))
    page("tools/", "計算ツール", "買い物や家計で使える無料の計算ツール集。", cards(tools))


# ---------- 全体 ----------

PAGES = []


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copy(ROOT / "assets" / "style.css", DIST / "style.css")
    print("mode:", "live" if LIVE else "sample")

    gpu, cpu = load("gpu.json"), load("cpu.json")
    build_value_ranking("pc/gpu/", gpu)
    build_value_ranking("pc/cpu/", cpu)
    page("pc/", "PCパーツのコスパ比較", "グラフィックボードとCPUを、楽天市場の実質価格とベンチマークスコアからコスパ順に並べます。",
         cards([("gpu/", gpu["title"], gpu["description"]), ("cpu/", cpu["title"], cpu["description"])]))

    protein, rice = load("protein.json"), load("rice.json")
    build_unit_price("tanka/protein/", protein)
    build_unit_price("tanka/rice/", rice)
    page("tanka/", "消耗品の単価比較", "内容量の違う商品を、同じ量あたりの実質価格で比べます。",
         cards([("protein/", protein["title"], protein["description"]), ("rice/", rice["title"], rice["description"])]))

    build_tools()

    about = (ROOT / "about.html").read_text(encoding="utf-8").replace("{{operator}}", esc(SITE["operator"])).replace("{{contact}}", esc(SITE["contact"]))
    page("about/", "このサイトについて", "運営者情報、広告、免責事項について。", about)
    page("", SITE["tagline"], SITE["description"], cards([
        ("pc/", "PCパーツのコスパ比較", "GPUとCPUを、ポイント込みの実質価格あたりの性能で並べます。"),
        ("tanka/", "消耗品の単価比較", "プロテインやお米を、同じ量あたりの価格で比べます。"),
        ("tools/", "計算ツール", "単価、電気代、実質価格をその場で計算できます。"),
    ]))

    if LIVE and stats["ok"] == 0:
        # 全滅したときは空のサイトで上書きしない（前回の公開内容が残る）
        sys.exit("all API requests failed; aborting so the previous deployment stays")

    urls = "".join(f"<url><loc>{esc(SITE['base_url'] + p)}</loc></url>" for p in sorted(PAGES))
    (DIST / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>', encoding="utf-8")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE['base_url']}sitemap.xml\n", encoding="utf-8")
    print(f"pages: {len(PAGES)}  api ok: {stats['ok']}  api fail: {stats['fail']}")


if __name__ == "__main__":
    main()
