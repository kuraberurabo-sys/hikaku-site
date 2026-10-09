"""商品名の照合と内容量の読み取りのテスト。

    python tests/test_match.py

data/*.json に区分を足したり条件を変えたりしたら、実在しそうな商品名の例を cases に
足してから実行する。全件通らない変更は公開しない。
"""
import json
import os
import pathlib
import sys

proj = str(pathlib.Path(__file__).resolve().parent.parent)
sys.path.insert(0, proj)
os.chdir(proj)
import build as b


def spec(file, name):
    data = json.loads(pathlib.Path("data", file).read_text(encoding="utf-8"))
    for s in data["products"]:
        if s["name"] == name:
            return data, s
    raise KeyError(name)


def check(file, name, item):
    """(一致するか, 読み取った内容量) を返す。"""
    data, s = spec(file, name)
    exclude = data["exclude"] + s.get("exclude", [])
    ok = b.matches(item, s["must"], exclude, s.get("single_units"))
    ok = ok and not any(o is not s and b.matches(item, o["must"], o.get("exclude", [])) for o in data["products"])
    amount = b.parse_amount(item, s["amount_from"]) if "amount_from" in s else s.get("amount")
    return ok, amount


cases = [
    ("ssd.json", "M.2 NVMe 1TB", "Crucial P3 Plus 1TB M.2 NVMe SSD CT1000P3PSSD8", (True, 1)),
    ("ssd.json", "M.2 NVMe 1TB", "SSD 500GB 1TB 2TB 選べる NVMe M.2", (False, 1)),
    ("ssd.json", "M.2 NVMe 1TB", "外付け SSD 1TB NVMe ポータブル", (False, 1)),
    ("ssd.json", "2.5インチ SATA 1TB", "SanDisk SSD 1TB 2.5インチ SATA 内蔵", (True, 1)),
    ("memory.json", "DDR5 32GB（16GB×2枚）", "Crucial DDR5-5600 32GB(16GB×2枚) デスクトップ用メモリ", (True, 32)),
    ("memory.json", "DDR5 32GB（16GB×2枚）", "DDR5 64GB (32GB x2) メモリ", (False, 32)),
    ("memory.json", "DDR4 16GB（8GB×2枚）", "DDR4 16GB 8GBx2 SODIMM ノート用", (False, 16)),
    ("hdd.json", "3.5インチ 8TB", "WD Red Plus 8TB 3.5インチ 内蔵HDD NAS用 CMR", (True, 8)),
    ("sdcard.json", "microSD 256GB", "SanDisk microSDXC 256GB Extreme A2 V30 最大190MB/s", (True, 256)),
    ("sdcard.json", "microSD 256GB", "ドライブレコーダー 前後カメラ microSD 256GB対応", (False, 256)),
    ("psu.json", "750W GOLD", "玄人志向 電源ユニット 750W 80PLUS GOLD フルプラグイン ATX", (True, 750)),
    ("monitor.json", "24インチ前後 フルHD", "IODATA モニター 23.8インチ フルHD ADSパネル 100Hz", (True, None)),
    ("monitor.json", "24インチ前後 フルHD", "ゲーミングモニター 24.5インチ フルHD 180Hz", (False, None)),
    ("monitor.json", "24インチ前後 フルHD 144Hz以上", "ゲーミングモニター 24.5インチ フルHD 180Hz", (True, None)),
    ("monitor.json", "27インチ 4K", "モニターアーム 27インチ 4K モニター対応", (False, None)),
    ("battery.json", "10000mAh", "Anker モバイルバッテリー 10000mAh PSE認証 USB-C", (True, 10000)),
    ("battery.json", "10000mAh", "モバイルバッテリー 10000mAh / 20000mAh 選べる", (False, 10000)),
    ("console.json", "PlayStation 5", "PlayStation 5 本体 CFI-2000A01 PS5", (True, None)),
    ("console.json", "PlayStation 5", "PlayStation 5 Pro 本体 PS5", (False, None)),
    ("console.json", "PlayStation 5 Pro", "PlayStation 5 Pro 本体 PS5", (True, None)),
    ("console.json", "Nintendo Switch 2", "Nintendo Switch 2 本体 日本語・国内専用", (True, None)),
    ("console.json", "Nintendo Switch 2", "Nintendo Switch2 ケース カバー 本体保護", (False, None)),
    ("water.json", "水 500mlペットボトル", "サントリー 天然水 500ml×24本 ペットボトル 水", (True, 12.0)),
    ("water.json", "水 500mlペットボトル", "炭酸水 500ml 24本 強炭酸", (False, 12.0)),
    ("water.json", "水 2Lペットボトル", "い・ろ・は・す 天然水 2L 6本 水 ミネラルウォーター", (True, 12.0)),
    ("water.json", "炭酸水 500mlペットボトル", "ウィルキンソン 炭酸水 500ml × 24本", (True, 12.0)),
    ("paper.json", "ダブル", "トイレットペーパー ダブル 12ロール×8パック 96ロール", (True, 96.0)),
    ("paper.json", "ダブル", "トイレットペーパー ダブル 2倍巻 12ロール", (False, 12.0)),
    ("tissue.json", "ボックスティッシュ", "ティッシュペーパー 5箱×12パック 60箱 150組", (True, 60.0)),
    ("diaper.json", "パンツ Mサイズ", "メリーズ パンツ Mサイズ(6-12kg) 58枚×3個", (True, 174.0)),
    ("diaper.json", "パンツ Mサイズ", "ムーニーマン パンツ XLサイズ 38枚", (False, 38.0)),
    ("diaper.json", "テープ Sサイズ", "パンパース テープ Sサイズ 82枚", (True, 82.0)),
    ("petfood.json", "ドッグフード（ドライ）", "ドッグフード ドライ 成犬用 チキン 10kg", (True, 10.0)),
    ("petfood.json", "ドッグフード（ドライ）", "ドッグフード 3kg 6kg 10kg 選べる", (False, 3.0)),
    ("petfood.json", "キャットフード（ドライ）", "キャットフード ドライ 2kg×4袋", (True, 8.0)),
]
bad = []
for file, name, item, want in cases:
    got = check(file, name, item)
    if got[0] != want[0] or (want[0] and got[1] != want[1]):
        bad.append((name, item, got, want))
print("cases", len(cases) - len(bad), "/", len(cases))
for row in bad:
    print("  FAIL", row)
sys.exit(1 if bad else 0)
