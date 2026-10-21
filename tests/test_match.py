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
    ("protein.json", "グロング ホエイプロテイン100 1kg", "GronG(グロング) プロテイン ホエイプロテイン100 ベーシック 風味付き 1kg 500g", (False, 1000)),
    ("protein.json", "グロング ホエイプロテイン100 1kg", "グロング プロテイン ホエイプロテイン 1kg スタンダード 風味付き ナチュラル ビタミン11種配合 GronG 置き換え ダイエット タンパク質 サプリメント アミノ酸スコア100 美味しい 送料無料 ポイント", (True, 1000)),
    ("wipes.json", "おしりふき", "おしりふき まとめ買い おしり拭き 水99.9 【送料無料】 ふんわり シート 80枚×20個 【1,600枚】【肌にやさしい】 レック ダイレクト お尻拭き お尻ふき ウエットシート", (True, 1600.0)),
    ("wipes.json", "おしりふき", "アカチャンホンポ 水99% おしりふき 90枚 16P アカチャン本舗 出産祝い ベビー お尻拭き 赤ちゃんお尻拭き 大容量 おしりふき 備蓄 ストック", (True, 1440.0)),
    ("wipes.json", "おしりふき", "900枚RICO★大人気/最新版★ 【Newおしりふき】RICO リコ　おしりふき　ベビーワイプ　900枚 100枚×9パック　【コストコ通販】カークランド 送料無料 りこ", (True, 900.0)),
    ("wipes.json", "おしりふき", "【レビューでプレゼント】おしりふき アメジスト やわらかタオルベビーローション入おしりふき 80枚入 36個セット(ケース)｜ 日本製 お尻拭き", (True, 2880.0)),
    ("wipes.json", "おしりふき", "【20個・36個セット】おしりふき 80枚20個 1,600枚 80枚×36個 2,880枚 送料無料 日本製 無香料 ノンアルコール 大容量 おしり拭き", (False, None)),
    ("wipes.json", "おしりふき", "【ネット限定】 ウェットシート ペット用 ウエットシート ペット用ウェットティッシュ 80枚 × 12個 （960枚） 犬 猫 ペット おしりふき まとめ買い", (False, 960.0)),
    ("wipes.json", "おしりふき", "おしりふき 厚手 単品 セット 90枚×6個 10枚×20個 新生児 肌にやさしい お尻拭き おしり拭き ウェットティッシュ 赤ちゃん", (False, 540.0)),
    ("wipes.json", "おしりふき", "おしりふき おしり拭き まとめ買い 水99.9 流せる シート【送料無料】60枚×15個【900枚】【肌にやさしい】お尻拭き お尻ふき 厚手 赤ちゃん", (False, 900.0)),
    ("wipes.json", "流せるおしりふき", "おしりふき おしり拭き まとめ買い 水99.9 流せる シート【送料無料】60枚×15個【900枚】【肌にやさしい】お尻拭き お尻ふき 厚手 赤ちゃん", (True, 900.0)),
    ("wipes.json", "流せるおしりふき", "おしり拭き 水99.9 おしりふき 流せる シート 【送料無料】【大容量2,880枚!】60枚×48個 まとめ買い レック ダイレクト", (True, 2880.0)),
    ("wipes.json", "流せるおしりふき", "おしりふき まとめ買い 水99.9 おしり拭き 厚手 シート 【送料無料】【大容量1,296枚!】 54枚×24個 レック ダイレクト", (False, 1296.0)),
    ("wipes.json", "流せるおしりふき", "大容量 大きめ おむつストッカー オムツストッカー おむつポーチ ボックス バッグ おむつ 小物 小物入れ ベビー用品 おしりふき おしゃれ", (False, None)),
    ("kandenchi.json", "単3形", "単3形 40本 三菱電機 アルカリ乾電池 LR6N/10S x4パック 水銀0 三菱 単3 アルカリ 電池 乾電池", (True, 40.0)),
    ("kandenchi.json", "単3形", "【1000円 ポッキリ ぽっきり】送料無料 アルカリ 単3 電池 単三 防災 備えに 乾電池 おすすめ ゆうパケット発送 MITSUBISHI 三菱 単3形 アルカリ乾電池 10本パック×3個 (計30本) LR6N/10S", (True, 30.0)),
    ("kandenchi.json", "単3形", "単3 アルカリ 乾電池 電池 30本[10本×3セット] 三菱電機【送料無料 防災 備蓄 地震 台風】(長持ち パック 単3電池 アルカリ乾電池", (True, 30.0)),
    ("kandenchi.json", "単3形", "パナソニック単3アルカリ乾電池24本【EVOLTA NEO LR6NJ/12SW x2点セット】Panasonicエボルタ アルカリ乾電池 単3 単3電池", (True, 24.0)),
    ("kandenchi.json", "単3形", "40本 単3形 x20本、 単4形 x20本ずつ 三菱電機 アルカリ乾電池 三菱 単3 単4 アルカリ 電池 乾電池", (False, 40.0)),
    ("kandenchi.json", "単3形", "【楽天一位 送料無料】単三形 単四形 アルカリ乾電池 電池 40本 10本単位 選べる セット まとめ買い 単3電池 単4電池 乾電池", (False, 40.0)),
    ("kandenchi.json", "単4形", "単4形 40本 三菱電機 アルカリ乾電池 LR03N/10S x4パック 水銀0 三菱 単4アルカリ 電池 乾電池", (True, 40.0)),
    ("kandenchi.json", "単4形", "アルカリ 乾電池 単4形 LR03XJ20SW パナソニック クリックポスト 送料無料 20本パック 10年保存可能 液漏れ防止製法 お買得パック", (True, 20.0)),
    ("kandenchi.json", "単4形", "＼1000円ポッキリ／【選べるセット】乾電池 単3 単4 40本セット 100本セット 単三 単四 電池 アルカリ乾電池 BIGCAPA basic セット", (False, 40.0)),
    ("kandenchi.json", "単4形", "東芝 アルカリ乾電池 単3形 20本まとめパック LR6AN 20MP", (False, 20.0)),
    ("wipes.json", "おしりふき", "手口ふき 赤ちゃん 80枚×15・36個 おしりふき 送料無料 手口拭き ウェットティッシュ ウエットティッシュ ケース ベビー 赤ちゃん", (True, 80.0)),
    ("wipes.json", "流せるおしりふき", "【70枚×15個・30個】おしりふき 流せる まとめ買い 送料無料 70枚×30個セット 流せるおしりふき ノンアルコール 大容量", (False, None)),
    ("wipes.json", "おしりふき", "パンパース おしりふき 肌へのいちばん(56枚*12個入*2セット)【パンパース 肌へのいちばん】", (True, 1344.0)),
    ("usbmemory.json", "USBメモリ 64GB", "USBメモリ USB 64GB SanDisk サンディスク Cruzer Glide USB3.0 海外リテール SDCZ600-064G-G35 ◆メ", (True, 64)),
    ("usbmemory.json", "USBメモリ 64GB", "【期間限定 最大20％OFF】USBメモリ 64GB USB3.2 Gen1 日本製【翌日配達送料無料】 KIOXIA TransMemory U301 キャップ式 ホワイト LU301W064GG4", (True, 64)),
    ("usbmemory.json", "USBメモリ 64GB", "USBメモリ フラッシュメモリ USBメモリー フラッシュドライブ Lexar 16GB 32GB 64GB 128GB USB2.0 スライド式キャップ USB Type-A タイプA Window", (False, 64)),
    ("usbmemory.json", "USBメモリ 64GB", "SDカード SD 64GB SDXC SanDisk サンディスク Extreme PRO Class10 UHS-I U3 V30 4K R:200MB/s W:90MB/s 海外リテール SDSDXXU-064G-G", (False, 64)),
    ("usbmemory.json", "USBメモリ 128GB", "USBメモリ USB 128GB SanDisk サンディスク Ultra Fit USB 3.1 Gen1 R:400MB/s 超小型設計 ブラック 海外リテール SDCZ430-128G-G46 ◆メ", (True, 128)),
    ("usbmemory.json", "USBメモリ 128GB", "シリコンパワー USBメモリ 128GB USB3.1 USB3.0 3.2 USB-A メモリー USBメモリー メモリスティック 外付けメモリ 容量不足 写真 データ転送 バックアップ フラッシュ データ キャップ式", (True, 128)),
    ("usbmemory.json", "USBメモリ 128GB", "USBメモリ usbフラッシュメモリ usb2.0 128gb タブレットPC カーオーディオ 小型 メモリースティック タブレットPC 1年保証 高性能 高い互換性 音楽プレーヤー用 高速 容量 お", (False, 128)),
    ("usbmemory.json", "USBメモリ 128GB", "マイクロSDカード 128GB microSDカード microSDXC SanDisk サンディスク Extreme UHS-I U3 V30 A2 R:190MB/s W:90MB/s Nintendo Switch", (False, 128)),
    ("usbmemory.json", "USBメモリ 256GB", "USBメモリ 256GB USB3.2 Gen1(USB3.0) KIOXIA キオクシア TransMemory U301 キャップ式 ホワイト 海外リテール LU301W256GG4 ◆メ", (True, 256)),
    ("usbmemory.json", "USBメモリ 256GB", "USBメモリ USB 256GB SanDisk サンディスク Ultra Fit USB 3.1 Gen1 R:400MB/s 超小型設計 ブラック 海外リテール SDCZ430-256G-G46 ◆メ", (True, 256)),
    ("usbmemory.json", "USBメモリ 256GB", "エイデータ USBメモリ 32GB/64GB/128GB/256GB/512GB UV128 USB3.2 Gen1 高速 大容量 AUV128-256G-RBE-I ブラック/ブルー(スナップ式)", (False, 256)),
    ("usbmemory.json", "USBメモリ 256GB", "マイクロSDカード microSD 256GB microSDカード microSDXC SanDisk サンディスク Ultra Class10 UHS-I A1 R:150MB/s Nintendo Switch動作", (False, 256)),
    ("usbmemory.json", "USBメモリ 512GB", "USBメモリ USB 512GB USB3.1 Gen1(USB3.0) SanDisk サンディスク Ultra Fit R:400MB/s 超小型 ブラック 海外リテール SDCZ430-512G-G46 ◆メ", (True, 512)),
    ("usbmemory.json", "USBメモリ 512GB", "USBメモリ USB 512GB USB3.0 SanDisk サンディスク Ultra Flair R:150MB/s 小型 金属製 海外リテール SDCZ73-512G-G46 ◆メ", (True, 512)),
    ("usbmemory.json", "USBメモリ 512GB", "ebamaz フラッシュドライブ USBメモリ2.0スティックマルチカラー 5個セット (512MB, 低容量, 512GBではない)", (False, 512)),
    ("usbmemory.json", "USBメモリ 512GB", "SanDisk USB3.1 Gen1 Type-A/C パッケージ サンディスク (USB3.0フラッシュメモリー) 32GB / 64GB / 128GB / 256GB / 512GB", (False, 512)),
    ("lifepo4.json", "12V 50Ah", "LiTime 12V 50Ah リン酸鉄リチウムイオンバッテリー 4000回以上ディープサイクル 容量640Wh 大幅な軽量化 LiFePO4 ボート マリン トローリング モーター キャンプ RV キャンプ シニアカー", (True, 50)),
    ("lifepo4.json", "12V 50Ah", "Redodo 12V 50Ah PRO リン酸鉄リチウムイオンバッテリー 640Wh 10年寿命 軽量 小型化12v LiFePO4 BMS保護 充放電サイクル4000回以上 RV キャンピングカー キャンプ ボート ア", (True, 50)),
    ("lifepo4.json", "12V 50Ah", "【魚探/電動リール用】LiTime 12V 50Ah リン酸鉄リチウムイオンバッテリー 14.6V10A専用充電器付き 内蔵BMS保護 4000回以上サイクル 長寿命 環境に優しいLiFePO4バッテリー ボート釣り用", (False, 50)),
    ("lifepo4.json", "12V 50Ah", "【船検適合品】LiTime 24V50Ah TM リン酸鉄リチウムバッテリー Bluetooth 低温保護 1280Wh 4000回以上サイクル スマート トローリングモーター エレキ 船 オフグリッド マリン ボート", (False, 50)),
    ("lifepo4.json", "12V 100Ah", "【ランキング1位】LiTime 12V 100Ah リン酸鉄リチウムイオンバッテリー グループ 31 内蔵100AのBMS 4000~15000サイクル回数 RV ソーラー 家庭用蓄電 バックアップ電源 オフグリッド ア", (True, 100)),
    ("lifepo4.json", "12V 100Ah", "Redodo 12V 100Ah リン酸鉄リチウムイオンバッテリー 1280Wh 10年寿命 充放電サイクル4000回以上 LiFePO4 BMS保護 容量拡張 車中泊 オフグリッド 防災対策 ソーラーシステム 推力30", (True, 100)),
    ("lifepo4.json", "12V 100Ah", "【Group24規格】LiTime 12V100Ah リン酸鉄リチウムイオンバッテリー Bluetooth機能付き BCI Group24サイズ 100A充放電電流 1280Wh 4000以上サイクル スマート LiFe", (True, 100)),
    ("lifepo4.json", "12V 100Ah", "【2SET】LiTime 12V 100Ah リン酸鉄リチウムイオンバッテリー グループ 31 内蔵100AのBMS 4000~15000サイクル回数 RV、ソーラー、バックアップ電源、オフグリッド アプリケーション、ボ", (False, 100)),
    ("lifepo4.json", "12V 100Ah", "Redodo 24V 100Ahリン酸鉄リチウムイオンバッテリー 2560Wh LiFePO4バッテリー 10年寿命 最大電力2560W BMS保護 充放電サイクル4000~15000回 容量拡張可能 RV キャンピング", (False, 100)),
    ("lifepo4.json", "12V 100Ah", "送料無料 LONG 12V100Ah 耐久性2倍 期待寿命10〜15年 密閉型ゲルバッテリー LGK100-12N 長寿命 密封型鉛蓄電池 ソーラー発電～キャンピングカーのサブバッテリー などに特に最適", (False, 100)),
    ("lifepo4.json", "12V 200Ah", "LiTime 12V 200Ah リン酸鉄リチウムイオンバッテリー 内蔵100AのBMS 最大2.56kWhエネルギー 15000回までサイクル可能 RV ソーラー マリン 監視設備 トローリングモーター 小型トラック", (True, 200)),
    ("lifepo4.json", "12V 200Ah", "【Grade-A電池セル-5年保証】LVYUAN 12.8V/200AH リン酸鉄リチウムイオンバッテリー 2.56KWH 大容量 12V 内蔵200A BMS LiFePO4バッテリー 並列直列接続可能 キャンピングカ", (True, 200)),
    ("lifepo4.json", "12V 200Ah", "【プライム感謝祭セール 自己加熱】RENOGY 12V 300Ah リン酸鉄リチウムイオンバッテリー 自己加熱 大容量 BMS保護 サイクル5000回以上 PSE技適認証取得 最大8台並列 発熱 寒冷地対応 レノジー C", (False, 200)),
    ("lifepo4.json", "12V 200Ah", "【蓄電池太陽光用最適】LiTime 51.2V 100Ah LiFePO4リチウムバッテリー グループ8D 内蔵100A BMS、グレードAセル、最大5120W 負荷電力 4000-15000 回サイクル&10", (False, 200)),
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
