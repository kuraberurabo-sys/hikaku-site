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
    ok = b.matches(item, s["must"], exclude, s.get("single_units"), s.get("max_sizes", 1))
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
    ("battery.json", "20000mAh", "PDA工房 Tuna モバイルバッテリー 20000mAh BC104PD100EB 対応 Crystal Shield 保護 フィルム", (False, 20000)),
    ("hdd.json", "3.5インチ 8TB", "エレコム ELECOM ELD-HTV 3.5インチ HDD ハードディスクドライブ 8TB(ELD-HTV080UBK) 取り寄せ商品", (False, 8)),
    ("diaper.json", "パンツ Mサイズ", "【3個セット】ユニチャーム マミーポコパンツ ドラえもん 紙おむつ 6〜13kg 大きめ Mサイズ 74枚入 男女共用", (True, 222.0)),
    ("diaper.json", "テープ Mサイズ", "【4個セット】メリーズファストプレミアム テープ Mサイズ48枚×4 おむつ 花王", (True, 192.0)),
    ("paper.json", "シングル", "トイレットペーパー シングル 業務用 50m 96ロール(12ロール×8パック) 再生紙『送料無料（一部地域除く）』", (True, 96.0)),
    ("copypaper.json", "A4", "コピー用紙 A4 5000枚(500枚×10冊)ペーパーワン（PAPER ONE） 高白色 カーボンニュートラル", (True, 5000.0)),
    ("copypaper.json", "A4", "TANOSEE　PPC用紙　Pure　White　A4　フタ無し箱　1箱（5000枚：500枚×10冊） 【送料無料】", (True, 5000.0)),
    ("copypaper.json", "A4", "カウネット　「カウコレ」プレミアム スタンダード高白色タイプA4　500枚×10冊1箱", (False, 5000.0)),
    ("copypaper.json", "A4", "【法人限定】高白色 コピー用紙 EX A4 5000枚 500枚×10冊 Forestway", (False, 5000.0)),
    ("copypaper.json", "A4", "あす楽 色上質紙 特厚口 A4 500枚 国産 カラーペーパー 選べる 32色 カラーコピー用紙 両面印刷可", (False, 500.0)),
    ("copypaper.json", "A4", "『最安挑戦』コピー用紙 A3 2500枚(500枚×5冊)ペーパーワン(PAPER ONE) 高白色", (False, 2500.0)),
    ("copypaper.json", "A3", "コピー用紙 A3 1500枚 (500枚×3冊) 高白色 無地 PEFC認証 まとめ買い 箱買い", (True, 1500.0)),
    ("copypaper.json", "A3", "高白色 コピー用紙 EX A3 1000枚 500枚×2冊 Forestway", (True, 1000.0)),
    ("copypaper.json", "A3", "コピー用紙 A4 5000枚 高白色（500枚×10冊） 印刷用紙 白紙 用紙 A4サイズ PPC用紙 OA用紙", (False, 5000.0)),
    ("copypaper.json", "A3", "シュレッダー 家庭用 業務用 電動 アイリスオーヤマ A3 コピー用紙 対応", (False, None)),
    ("copypaper.json", "B5", "コピー用紙 B5 5000枚 高白色(500枚×10冊) 印刷用紙 白紙 用紙 B5サイズ PPC用紙 OA用紙", (True, 5000.0)),
    ("copypaper.json", "B5", "Forestway コピーペーパー ノルディック B5 500枚×10冊[代引不可]", (True, 5000.0)),
    ("copypaper.json", "B5", "コピー用紙 A4 2500枚 (500枚×5冊) グリーン購入法適合 再生紙 無地", (False, 2500.0)),
    ("copypaper.json", "B5", "【 法人限定 】 高白色 コピー用紙 EX B5 2500枚 500枚×5冊", (False, 2500.0)),
    ("dishtab.json", "フィニッシュ パワーキューブ", "特大100回分 フィニッシュ 凝縮 パワーキューブ 食洗機用 タブレット洗剤 L(100個入×3袋セット)【フィニッシュ】", (True, 300.0)),
    ("dishtab.json", "フィニッシュ パワーキューブ", "フィニッシュ タブレット 150粒 パワーキューブ", (True, 150.0)),
    ("dishtab.json", "フィニッシュ パワーキューブ", "フィニッシュオールインワンプレミアムパワーボールキューブM 42個入[食洗機　洗剤］", (False, 42.0)),
    ("dishtab.json", "フィニッシュ パワーキューブ", "フィニッシュ 食洗機庫内強力洗浄タブレット(17g×3個)【フィニッシュ】", (False, 3.0)),
    ("dishtab.json", "フィニッシュ ウルトラタブレット", "レキットベンキーザー フィニッシュ ウルトラタブレット M 35個入 食洗機専用 タブレット洗剤", (True, 35.0)),
    ("dishtab.json", "フィニッシュ ウルトラタブレット", "フィニッシュ ウルトラタブレット ジェル入り L 食洗機用洗剤(50個入×4セット(1個13g))【フィニッシュ】", (True, 200.0)),
    ("dishtab.json", "フィニッシュ ウルトラタブレット", "レキットベンキーザー フィニッシュ 濃縮 パワーキューブ 52個入 食洗機専用洗剤 タブレット洗剤", (False, 52.0)),
    ("dishtab.json", "フィニッシュ ウルトラタブレット", "フィニッシュ タブレット洗剤 オールインワン(58個入)【フィニッシュ】", (False, 58.0)),
    ("dishtab.json", "フィニッシュ オールインワン", "フィニッシュ タブレット洗剤 オールインワン(58個入×2袋セット)【フィニッシュ】", (True, 116.0)),
    ("dishtab.json", "フィニッシュ オールインワン", "フィニッシュ タブレット洗剤 プレミアムパワーボールキューブ オールインワン M 42個入 【フィニッシュ】 台所用洗剤", (True, 42.0)),
    ("dishtab.json", "フィニッシュ オールインワン", "【まとめ買い】フィニッシュ 食洗機 洗剤 タブレット パワーキューブ 100個入 ×2 袋 + 試供品付き (食洗機 洗剤 オールインワン プレミアム パワーボールキューブ 3個入)", (False, 200.0)),
    ("dishtab.json", "フィニッシュ オールインワン", "レキットベンキーザー フィニッシュ ウルトラタブレット L 50個入 食洗機専用 タブレット洗剤", (False, 50.0)),
    ("dishtab.json", "ジョイ ジェルタブ", "P&G ジョイジェルタブ 76個×3個セット | ジョイ ジェルタブ 76個 食洗機 洗剤 まとめ買い セット", (True, 228.0)),
    ("dishtab.json", "ジョイ ジェルタブ", "【今月のオススメ品】P&G ジョイ ジェルタブ PRO 76個入 大容量 食洗機用洗剤", (True, 76.0)),
    ("dishtab.json", "ジョイ ジェルタブ", "ジョイ ジェルタブ W除菌 食洗機用洗剤 【ジョイ(Joy)】 ジェルタブ クリスタル 76個入 / ジェルタブ 76個入 / ジェルタブ 100個入", (True, 76.0)),
    ("dishtab.json", "ジョイ ジェルタブ", "フィニッシュ タブレット 150粒 パワーキューブ", (False, 150.0)),
    ("dishtab.json", "ジョイ ジェルタブ", "食洗機用ジョイ 洗剤 粉末 オレンジピール成分入り つめかえ用 特大 930g", (False, None)),
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
