"""サイト生成スクリプト。標準ライブラリのみで動く。

環境変数 RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY があれば楽天市場商品検索APIから
価格を取得し、なければサンプルデータで生成する（動作確認用。noindex を付ける）。
取得したデータはファイルに保存せず、生成したHTMLにだけ反映する。
"""
import datetime
import html
import json
import math
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

NAV = [("", "トップ"), ("pc/", "PCパーツ"), ("gadget/", "ガジェット"), ("tanka/", "日用品・食品"),
       ("denki/", "電気代"), ("size/", "サイズ早見表"), ("tools/", "計算ツール"), ("about/", "このサイトについて")]

# 楽天APIを使うセクション。(データファイル名, ページの種類) を並べる。
# value: スコア÷価格のランキング / unit: 単価のランキング / cheapest: 区分ごとの最安
SECTIONS = [
    ("pc/", "PCパーツの価格比較", "グラフィックボード、CPU、SSD、メモリなどを、楽天市場の実質価格で比べます。",
     [("gpu", "value"), ("cpu", "value"), ("ssd", "unit"), ("memory", "unit"), ("hdd", "unit"), ("psu", "unit"), ("monitor", "cheapest")]),
    ("gadget/", "ガジェットの価格比較", "microSDカード、モバイルバッテリー、ゲーム機本体を、楽天市場の実質価格で比べます。",
     [("sdcard", "unit"), ("battery", "unit"), ("console", "cheapest")]),
    ("tanka/", "日用品・食品の単価比較", "内容量の違う商品を、同じ量あたりの実質価格で比べます。",
     [("protein", "unit"), ("rice", "unit"), ("water", "unit"), ("paper", "unit"), ("tissue", "unit"), ("diaper", "unit"), ("petfood", "unit")]),
]

stats = {"ok": 0, "fail": 0}
_last_request = 0.0
PAGES = []


def load(name):
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


# ---------- 商品名の照合 ----------

SEPARATORS = r"[\s\-‐ー_/]"
UNIT_ALIASES = {"キロ": "KG", "リットル": "L"}


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


def distinct_sizes(name, units):
    """units の単位で書かれた量を重複なく集める（"5kg 10kg 選べる" → 2種類）。"""
    pattern = r"(?<![\d.])(\d+(?:\.\d+)?)\s*(" + "|".join(re.escape(u) for u in units) + r")(?![A-Z])"
    return {(float(number), UNIT_ALIASES.get(unit, unit)) for number, unit in re.findall(pattern, name)}


def matches(item_name, must, exclude, single_units=None, max_sizes=1):
    """must は「いずれかを含む」グループのリスト。全グループを満たし、exclude を含まなければ一致。"""
    name = norm(item_name)
    # 複数の容量が書かれた出品は「選べる容量」で、表示価格が最小サイズのものなので外す。
    # "58枚×3（174枚）" のように同じ商品で2通り書かれる単位は max_sizes=2 で許す
    if single_units and len(distinct_sizes(name, single_units)) > max_sizes:
        return False
    if any(has_token(name, t) for t in exclude):
        return False
    return all(any(has_token(name, t) for t in group) for group in must)


def parse_amount(item_name, rules):
    """商品名から内容量を読む。rules は [正規表現, 倍率] のリストで、最初に一致したものを使う。

    グループが2つある規則は掛け合わせる（"500ML×24本" → 500×24×倍率）。
    """
    compact = re.sub(r"\s", "", norm(item_name))
    for pattern, scale in rules:
        found = re.search(pattern, compact)
        if found:
            value = scale
            for group in found.groups():
                value *= float(group)
            return value
    return None


# ---------- 楽天API ----------

def api_search(keyword, min_price, page=1, ng_keyword="", max_price=None, sort="+itemPrice"):
    global _last_request
    query = {
        "applicationId": APP_ID,
        "accessKey": ACCESS_KEY,
        "keyword": keyword,
        "format": "json",
        "formatVersion": 2,
        "hits": 30,
        "page": page,
        "sort": sort,
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
    """spec に一致する出品を、内容量あたりの実質価格が安い順に返す。取得失敗は None。

    siblings は同じ表に並ぶ他の spec。複数モデルから選ぶ形式の出品は、表示価格が
    最安モデルのものなので、他の spec にも一致する出品は外す。
    """
    exclude = common_exclude + spec.get("exclude", []) + ["ふるさと納税"]
    single_units = spec.get("single_units") or (["KG", "キロ"] if spec.get("single_size") else None)

    def is_other_model(name):
        return any(
            other is not spec and matches(name, other["must"], other.get("exclude", []))
            for other in siblings
        )

    ng_keyword = " ".join(filter(None, [ng_keyword, spec.get("ng_keyword", "")]))
    # 価格の安い順だと、まとめ売りのように「高いが単価は安い」出品を拾えない。
    # 内容量を読んで単価を比べる商品は、レビュー数順などで広く取ってから並べ直す
    sort = spec.get("sort", "+itemPrice")
    offers = []
    for page in range(1, spec.get("pages", 2) + 1):
        if LIVE:
            items = api_search(spec["keyword"], spec["min_price"], page, ng_keyword, spec.get("max_price"), sort)
        else:
            items = sample_items(spec) if page == 1 else []
        if items is None:
            return None
        for raw in items:
            item = raw.get("Item", raw)
            name = item.get("itemName", "")
            if not matches(name, spec["must"], exclude, single_units, spec.get("max_sizes", 1)) or is_other_model(name):
                continue
            # 商品名に「中古」と書かない買取店などは、店名で外す
            if any(word in item.get("shopName", "") for word in spec.get("exclude_shops", [])):
                continue
            if "amount_from" in spec:
                # 内容量を商品名から読む。読めない出品は単価を出せないので外す
                amount = parse_amount(name, spec["amount_from"])
                if amount is None and not LIVE:
                    amount = spec.get("sample_amount", 1)
                low, high = spec.get("amount_range", [0, float("inf")])
                if amount is None or not low <= amount <= high:
                    continue
            else:
                amount = spec.get("amount", 1)
            price = item["itemPrice"]
            points = price * int(item.get("pointRate") or 1) // 100
            offers.append({
                "name": name,
                "price": price,
                "points": points,
                "effective": price - points,
                "amount": amount,
                "unit_price": (price - points) / amount,
                "shop": item.get("shopName", ""),
                "url": item.get("affiliateUrl") or item.get("itemUrl", "#"),
                "postage_extra": item.get("postageFlag") == 1,
            })
        # 価格順なら、見つかった時点でそれより安い出品は無いので打ち切れる
        if len(items) < 30 or (offers and sort == "+itemPrice"):
            break
    if not offers:
        return []
    # 付属品の混入や内容量の読み違いを避けるため、中央値から大きく外れて安いものを落とす
    median = statistics.median(o["unit_price"] for o in offers)
    floor = median * spec.get("outlier", 0.6)
    offers = sorted((o for o in offers if o["unit_price"] >= floor), key=lambda o: o["unit_price"])
    # 同じ店が色違いや重複出品で並ぶので、店ごとに最安の1件だけ残す
    by_shop = {}
    for offer in offers:
        by_shop.setdefault(offer["shop"], offer)
    return list(by_shop.values())[:limit]


# ---------- HTML ----------

def esc(value):
    return html.escape(str(value), quote=True)


def yen(value):
    return f"{value:,}円"


def number(value, decimals=0):
    return f"{value:,.{decimals}f}"


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


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
    nav = "".join(f'<a href="{rel}{href}">{esc(label)}</a>' for href, label in NAV)
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


def table(headers, rows, left=(1,)):
    """left は左寄せにする列（0始まり）。それ以外は数値として右寄せ。"""
    def cells(tag, row):
        return "".join(f'<{tag}{" class=l" if i in left else ""}>{cell}</{tag}>' for i, cell in enumerate(row))
    head = cells("th", [esc(h) for h in headers])
    body = "".join(f"<tr>{cells('td', row)}</tr>" for row in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def offer_cells(offer):
    postage = ' <span class="tag">送料別</span>' if offer["postage_extra"] else ""
    link = f'<a href="{esc(offer["url"])}" rel="nofollow sponsored noopener" target="_blank">{esc(offer["shop"])}</a>'
    return [yen(offer["price"]) + postage, f'{offer["points"]:,}pt', f'<strong>{yen(offer["effective"])}</strong>', link]


def item_name(offer):
    name = offer["name"]
    return f'<span class="item">{esc(name[:70] + ("…" if len(name) > 70 else ""))}</span>'


def price_note():
    return (f'<p class="note">価格は{STAMP}時点で楽天市場の商品検索から取得したものです。'
            "ポイントは商品ごとの通常倍率のみで計算しており、キャンペーンや会員ランクによる上乗せは含みません。"
            "商品名から自動で照合しているため、条件と違う商品が混ざることがあります。"
            "最新の価格・送料・在庫・商品内容はリンク先でご確認ください。</p>")


def missing_note(missing, label):
    if not missing:
        return ""
    return f'<p class="note">現在、条件に合う出品が見つからなかった{label}: ' + esc("、".join(missing)) + "</p>"


def related_links(data):
    """data["related"] は [ページからの相対パス, 表示名] のリスト。"""
    links = "".join(f'<li><a href="{esc(href)}">{esc(label)}</a></li>' for href, label in data.get("related", []))
    return f"<h2>関連ページ</h2><ul>{links}</ul>" if links else ""


def cards(items):
    return '<div class="cards">' + "".join(
        f'<a class="card" href="{esc(href)}"><strong>{esc(title)}</strong><span>{esc(text)}</span></a>'
        for href, title, text in items) + "</div>"


# ---------- value: スコア÷価格のランキングと、モデル別の最安値ページ ----------

def build_value(path, data):
    rows, missing = [], []
    for spec in data["models"]:
        offers = offers_for(spec, data["exclude"], data.get("ng_keyword", ""), limit=5, siblings=data["models"])
        if not offers:
            missing.append(spec["name"] + ("（取得失敗）" if offers is None else ""))
            continue
        rows.append((spec["score"] / offers[0]["effective"] * 10000, spec, offers))
    rows.sort(key=lambda r: -r[0])

    table_rows = []
    for rank, (value, spec, offers) in enumerate(rows, 1):
        detail = slug(spec["name"]) + "/"
        table_rows.append([str(rank), f'<a href="{detail}">{esc(spec["name"])}</a>', f'{spec["score"]:,}',
                           *offer_cells(offers[0]), f"<strong>{value:,.0f}</strong>"])
        build_model_page(path + detail, data, spec, offers, value, rank, len(rows))

    body = f'<p>{esc(data["lead"])}</p>'
    body += table(["順位", "モデル", data["score_label"], "最安価格", "ポイント", "実質価格", "ショップ", "1万円あたりスコア"], table_rows)
    body += price_note()
    body += f'<p class="note">{esc(data["score_note"])}</p>'
    body += missing_note(missing, "モデル")
    body += related_links(data)
    page(path, data["title"], data["description"], body, uses_api=True)


def build_model_page(path, data, spec, offers, value, rank, total):
    best = offers[0]
    body = (f'<p>{esc(spec["name"])}の、楽天市場で在庫のある新品の出品を、ポイント還元を引いた実質価格が安い順に並べています。'
            f'最安は{esc(best["shop"])}の{yen(best["effective"])}（実質）です。</p>')
    body += table(["順位", "商品名", "価格", "ポイント", "実質価格", "ショップ"],
                  [[str(i), item_name(o), *offer_cells(o)] for i, o in enumerate(offers, 1)])
    body += (f'<h2>コスパ</h2><p>{esc(data["score_label"])}は{spec["score"]:,}で、実質価格1万円あたりのスコアは{value:,.0f}です。'
             f'<a href="../">{esc(data["title"])}</a>では{total}モデル中{rank}位です。</p>')
    body += price_note()
    body += f'<p class="note">{esc(data["score_note"])}</p>'
    page(path, f'{spec["name"]}の最安値（楽天市場）',
         f'{spec["name"]}を楽天市場のポイント込み実質価格が安い順に比較。毎日自動更新。', body, uses_api=True)


# ---------- unit: 内容量あたりの単価のランキング ----------

def build_unit(path, data):
    decimals = data.get("decimals", 0)
    rows, missing = [], []
    for spec in data["products"]:
        offers = offers_for(spec, data["exclude"], data.get("ng_keyword", ""), limit=spec.get("limit", 1), siblings=data["products"])
        if not offers:
            missing.append(spec["name"] + ("（取得失敗）" if offers is None else ""))
            continue
        rows += [(offer["unit_price"] * data["per"], spec, offer) for offer in offers]
    rows.sort(key=lambda r: r[0])
    table_rows = [
        [str(rank), esc(spec["name"]) + item_name(offer),
         number(offer["amount"], 0 if float(offer["amount"]).is_integer() else 1) + esc(data["unit"]),
         *offer_cells(offer), f"<strong>{number(unit_price, decimals)}円</strong>"]
        for rank, (unit_price, spec, offer) in enumerate(rows, 1)
    ]
    body = f'<p>{esc(data["lead"])}</p>'
    body += table(["順位", "商品", "内容量", "価格", "ポイント", "実質価格", "ショップ", data["per_label"]], table_rows)
    body += price_note()
    if data.get("note"):
        body += f'<p class="note">{esc(data["note"])}</p>'
    body += missing_note(missing, "商品")
    body += related_links(data)
    page(path, data["title"], data["description"], body, uses_api=True)


# ---------- cheapest: 区分ごとの最安 ----------

def build_cheapest(path, data):
    table_rows, missing = [], []
    for spec in data["products"]:
        offers = offers_for(spec, data["exclude"], data.get("ng_keyword", ""), limit=spec.get("limit", 3), siblings=data["products"])
        if not offers:
            missing.append(spec["name"] + ("（取得失敗）" if offers is None else ""))
            continue
        table_rows += [[esc(spec["name"]), item_name(offer), *offer_cells(offer)] for offer in offers]
    body = f'<p>{esc(data["lead"])}</p>'
    body += table(["区分", "商品名", "価格", "ポイント", "実質価格", "ショップ"], table_rows, left=(0, 1))
    body += price_note()
    if data.get("note"):
        body += f'<p class="note">{esc(data["note"])}</p>'
    body += missing_note(missing, "区分")
    body += related_links(data)
    page(path, data["title"], data["description"], body, uses_api=True)


BUILDERS = {"value": build_value, "unit": build_unit, "cheapest": build_cheapest}


# ---------- 計算ツール ----------

def build_tools():
    tools = []
    for source in sorted((ROOT / "tools").glob("*.html")):
        text = source.read_text(encoding="utf-8")
        meta = dict(re.findall(r"^<!--\s*(title|description):\s*(.+?)\s*-->$", text, re.M))
        page(f"tools/{source.stem}/", meta["title"], meta["description"], text)
        tools.append((f"{source.stem}/", meta["title"], meta["description"]))
    page("tools/", "計算ツール", "買い物や家計で使える無料の計算ツール集。", cards(tools))


# ---------- 家電の電気代早見表（楽天APIは使わない） ----------

def build_denki():
    data = load("denki.json")
    rate = data["rate"]
    items = []
    for item in data["items"]:
        watt = item["watt"]
        rows = []
        for hours, label in item["hours"]:
            day = watt / 1000 * hours * rate
            rows.append([esc(label), f"{day:,.1f}円", yen(round(day * 30)), yen(round(day * 365))])
        hour_cost = watt / 1000 * rate
        body = (f'<p>{esc(item["name"])}の消費電力を{watt:,}Wとすると、1時間あたりの電気代は約{hour_cost:,.1f}円です。'
                f'電気料金の単価は1kWhあたり{rate}円で計算しています。</p>')
        body += table(["使う時間", "1日", "1か月", "1年"], rows, left=(0,))
        body += f'<p class="note">{esc(item["note"])} {esc(data["note"])}</p>'
        body += f"""<h2>自分の機種で計算する</h2>
<div class="tool">
  <label for="watt">消費電力（W）</label>
  <input id="watt" type="number" inputmode="decimal" min="0" value="{watt}">
  <label for="hours">1日の使用時間（時間）</label>
  <input id="hours" type="number" inputmode="decimal" min="0" max="24" step="any" value="{round(item["hours"][0][0], 2)}">
  <label for="rate">電気料金の単価（円/kWh）</label>
  <input id="rate" type="number" inputmode="decimal" min="0" value="{rate}">
  <div class="result" id="result"></div>
</div>
<script>
const ids = ["watt", "hours", "rate"];
function update() {{
  const [watt, hours, rate] = ids.map(id => parseFloat(document.getElementById(id).value));
  const result = document.getElementById("result");
  if (!(watt > 0) || !(hours > 0) || !(rate > 0)) {{ result.textContent = ""; return; }}
  const day = watt / 1000 * hours * rate;
  const yen = v => Math.round(v).toLocaleString("ja-JP") + "円";
  result.innerHTML = `1日: <strong>${{day.toFixed(1)}}円</strong><br>1か月: <strong>${{yen(day * 30)}}</strong><br>1年: <strong>${{yen(day * 365)}}</strong>`;
}}
ids.forEach(id => document.getElementById(id).addEventListener("input", update));
update();
</script>"""
        title = f'{item["name"]}の電気代（1時間・1か月の目安）'
        description = f'{item["name"]}の電気代を、消費電力{watt:,}Wの場合で計算。1時間あたり約{hour_cost:,.1f}円。機種の消費電力を入れて計算し直せます。'
        page(f'denki/{item["slug"]}/', title, description, body)
        items.append((f'{item["slug"]}/', f'{item["name"]}の電気代', f"{watt:,}Wで1時間あたり約{hour_cost:,.1f}円"))
    page("denki/", "家電の電気代早見表", "ドライヤー、電気ケトル、ヒーターなど、家電ごとの電気代の目安を一覧に。",
         f'<p>家電ごとの電気代の目安です。電気料金の単価は1kWhあたり{rate}円で計算しています。</p>' + cards(items))


# ---------- 画面サイズ早見表（楽天APIは使わない） ----------

def screen_size(inches, ratio_w=16, ratio_h=9):
    diagonal = inches * 2.54
    scale = diagonal / math.hypot(ratio_w, ratio_h)
    return ratio_w * scale, ratio_h * scale


def build_size():
    formula = "対角のインチ数 × 2.54cm を、画面の縦横比で分けて計算しています。枠（ベゼル）やスタンドは含みません。"

    rows = []
    for inches, ratio in [(21.5, (16, 9)), (23.8, (16, 9)), (24, (16, 9)), (24.5, (16, 9)), (27, (16, 9)), (31.5, (16, 9)),
                          (32, (16, 9)), (34, (21, 9)), (38, (21, 9)), (43, (16, 9)), (49, (32, 9))]:
        width, height = screen_size(inches, *ratio)
        rows.append([f"{inches}インチ", f"{ratio[0]}:{ratio[1]}", f"{width:.1f}cm", f"{height:.1f}cm"])
    body = "<p>モニターの画面サイズ（インチ）を、横幅と高さのセンチに直した早見表です。机に置けるかの確認に使えます。</p>"
    body += table(["サイズ", "縦横比", "画面の横幅", "画面の高さ"], rows, left=(0,))
    body += f'<p class="note">{formula}</p>'
    page("size/monitor/", "モニターのサイズ早見表（インチ→cm）", "21.5〜49インチのモニターの横幅と高さをセンチで一覧に。ウルトラワイドにも対応。", body)

    rows = []
    for inches in (24, 32, 40, 43, 50, 55, 65, 75, 85):
        width, height = screen_size(inches)
        rows.append([f"{inches}型", f"{width:.1f}cm", f"{height:.1f}cm", f"約{height * 1.5 / 100:.1f}m", f"約{height * 3 / 100:.1f}m"])
    body = "<p>テレビの画面サイズ（型）を、横幅と高さのセンチに直した早見表です。視聴距離の目安も付けています。</p>"
    body += table(["サイズ", "画面の横幅", "画面の高さ", "視聴距離（4K）", "視聴距離（フルHD）"], rows, left=(0,))
    body += (f'<p class="note">{formula} 視聴距離は、一般に言われる「4Kは画面の高さの約1.5倍、フルHDは約3倍」という目安で計算しています。'
             "好みや部屋の条件で変わるので、参考としてください。</p>")
    page("size/tv/", "テレビのサイズ早見表（型→cm・視聴距離）", "24〜85型のテレビの横幅・高さと、4K・フルHDの視聴距離の目安を一覧に。", body)

    page("size/", "サイズ早見表", "モニターとテレビの画面サイズを、インチからセンチに直した早見表。", cards([
        ("monitor/", "モニターのサイズ早見表", "21.5〜49インチの横幅と高さ"),
        ("tv/", "テレビのサイズ早見表", "24〜85型の横幅・高さと視聴距離の目安"),
    ]))


# ---------- 全体 ----------

def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copy(ROOT / "assets" / "style.css", DIST / "style.css")
    print("mode:", "live" if LIVE else "sample")

    home = []
    for section_path, title, description, entries in SECTIONS:
        section_cards = []
        for name, kind in entries:
            data = load(name + ".json")
            BUILDERS[kind](f"{section_path}{name}/", data)
            section_cards.append((f"{name}/", data["title"], data["description"]))
            print(f"  built {section_path}{name}/  api ok: {stats['ok']}  fail: {stats['fail']}", flush=True)
        page(section_path, title, description, cards(section_cards))
        home.append((section_path, title, description))

    build_denki()
    build_size()
    build_tools()
    home += [
        ("denki/", "家電の電気代早見表", "家電ごとの電気代の目安を一覧に。"),
        ("size/", "サイズ早見表", "モニターとテレビのサイズを、インチからセンチに。"),
        ("tools/", "計算ツール", "単価、電気代、実質価格をその場で計算できます。"),
    ]

    about = (ROOT / "about.html").read_text(encoding="utf-8").replace("{{operator}}", esc(SITE["operator"])).replace("{{contact}}", esc(SITE["contact"]))
    page("about/", "このサイトについて", "運営者情報、広告、免責事項について。", about)
    page("", SITE["tagline"], SITE["description"], cards(home))

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
