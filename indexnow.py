"""公開後に、更新したページのURLを IndexNow（Bing など）へ知らせる。

公開中の sitemap.xml を読み、そのURL一覧を送る。Google は IndexNow に対応していないので、
Google 向けには Search Console に登録した sitemap.xml が使われる。
"""
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SITE = json.loads((Path(__file__).parent / "site.json").read_text(encoding="utf-8"))
KEY = SITE.get("indexnow_key", "")
BASE = SITE["base_url"]


def main():
    if not KEY:
        sys.exit("indexnow_key is not set in site.json")
    with urllib.request.urlopen(BASE + "sitemap.xml", timeout=30) as response:
        urls = re.findall(r"<loc>(.*?)</loc>", response.read().decode("utf-8"))
    payload = {
        "host": urllib.parse.urlsplit(BASE).netloc,
        "key": KEY,
        # サブディレクトリ公開なので、鍵ファイルの場所を明示する
        "keyLocation": f"{BASE}{KEY}.txt",
        "urlList": urls,
    }
    request = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            print(f"IndexNow: {response.status} for {len(urls)} URLs")
    except urllib.error.HTTPError as error:
        # 通知の失敗でサイトの公開は止めない。理由だけ記録する
        print(f"IndexNow failed: {error.code} {error.read().decode('utf-8', 'replace')[:200]}")


if __name__ == "__main__":
    main()
