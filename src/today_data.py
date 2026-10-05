# -*- coding: utf-8 -*-
"""The trip, hour by hour — one source for the TODAY screen and for the map pins.

    python3 today_data.py        -> writes ../trips/{template,miras-aikosh,index}.json and stops.json

Statuses: fixed (booked or immovable), planned (the recommended route), flex (drop it when
tired or late), input (waiting for the travellers' data). Fixed events are never moved by
the replanner; flex time is cut first, then planned.

Costs are yen for the two of us together. A "~" in the note marks an estimate.
Nothing private goes in here: no ticket numbers, phones or card data — tickets are
attached on the phone and stay on the device.
"""
import json
import pathlib

FX = 2.81          # ₸ per ¥, National Bank of Kazakhstan, 29.09.2026


# Our own trip (trips/miras-aikosh.json) is public by the owners' choice: names, flights, the first
# hotel and what is bought. Ticket numbers, seats, addresses, phones and card data never go here —
# tickets are attached on the phone and stay on the device.


class P:
    """A value that differs between our own trip and the public template:
    `own` is ours, `tpl` is what everyone else gets."""
    def __init__(self, own, tpl):
        self.own, self.tpl = own, tpl


def resolve(x, personal):
    if isinstance(x, P):
        return resolve(x.own if personal else x.tpl, personal)
    if isinstance(x, dict):
        return {k: resolve(v, personal) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return type(x)(resolve(v, personal) for v in x) if isinstance(x, list) else tuple(resolve(v, personal) for v in x)
    return x
DATES = {n: f"2026-10-{16 + n}" for n in range(1, 13)}       # day 12 (28.10, Shanghai) is our trip only

# place -> (lat, lng, map stop name or None, map category)
PL = {
    "hnd":      (35.5494, 139.7798, "Haneda Airport (HND) ✈️", "Airport"),
    "sansuiso": (35.6262, 139.7236, "Hotel – Gotanda 🏨", "Hotel"),
    "gotanda":  (35.6262, 139.7236, None, None),
    "busta":    (35.6887, 139.7003, "Busta Shinjuku 🚌", "Transit"),
    "kwgk":     (35.4985, 138.7690, None, None),
    "lawson":   (35.4989, 138.7622, "Lawson Kawaguchiko Station 🏪", "Attraction"),
    "ropeway":  (35.5009, 138.7680, "Kachi Kachi Ropeway 🌿", "Nature"),
    "cruise":   (35.5013, 138.7686, None, None),
    "oishi":    (35.5221, 138.7481, "Oishi Park 🌿", "Nature"),
    "mishima":  (35.1260, 138.9110, "Mishima Station 🚌", "Transit"),
    "kyoto_st": (34.9855, 135.7588, None, None),
    "kyoto_h":  (34.9855, 135.7588, "Kyoto hotel area – Kyoto Station 🏨", "Hotel"),
    "fushimi":  (34.9671, 135.7727, "Fushimi Inari Taisha 📍", "Attraction"),
    "kiyomizu": (34.9949, 135.7851, "Kiyomizu-dera 📍", "Attraction"),
    "sannen":   (34.9963, 135.7814, "Sannenzaka / Ninenzaka 🛍", "Shopping"),
    "wcs":      (35.0040, 135.7596, "World Currency Shop – Kyoto 💴", "Money"),
    "nishiki":  (35.0050, 135.7649, "Nishiki Market 🍜", "Food"),
    "gion":     (35.0036, 135.7767, "Gion / Hanamikoji 🛍", "Shopping"),
    "bamboo":   (35.0176, 135.6671, "Arashiyama Bamboo Grove 🌿", "Nature"),
    "tenryuji": (35.0158, 135.6737, "Tenryu-ji 📍", "Attraction"),
    "togetsu":  (35.0154, 135.6761, "Togetsukyo Bridge 🌿", "Nature"),
    "kinkaku":  (35.0394, 135.7292, "Kinkaku-ji 📍", "Attraction"),
    "nagoya_st":(35.1709, 136.8815, None, None),
    "nagoya_h": (35.1709, 136.8815, "Nagoya hotel area – Nagoya Station 🏨", "Hotel"),
    "noritake": (35.1802, 136.8783, "Noritake Garden 🏺", "Attraction"),
    "oasis21":  (35.1709, 136.9094, "Oasis 21 🌆", "Attraction"),
    "ncastle":  (35.1856, 136.8991, "Nagoya Castle 📍", "Attraction"),
    "osu":      (35.1596, 136.9020, "Osu shopping district 🛍", "Shopping"),
    "budokan":  (35.1171972, 136.8699389, "Aichi Budokan 🏟", "Event"),
    "atsuta":   (35.1279, 136.9087, "Atsuta Jingu 📍", "Attraction"),
    "toyota":   (35.1830, 136.8775, "Toyota Commemorative Museum 📍", "Attraction"),
    "tokyo_st": (35.6812, 139.7671, None, None),
    "tokyo_h":  (35.711, 139.7966, "Tokyo hotel area – Asakusa 🏨", "Hotel"),
    "sensoji":  (35.7148, 139.7967, "Senso-ji / Asakusa 📍", "Attraction"),
    "ameyoko":  (35.7087, 139.7745, "Ueno / Ameyoko 🍜", "Food"),
    "akiba":    (35.6984, 139.7731, "Akihabara 🛍", "Shopping"),
    "origami":  (35.7028798, 139.7654497, "Origami Kaikan 🛍", "Shopping"),
    "tdl":      (35.6329, 139.8804, "Tokyo Disneyland 📍", "Attraction"),
    "meiji":    (35.6764, 139.6993, "Meiji Jingu 📍", "Attraction"),
    "harajuku": (35.6687, 139.7057, "Harajuku / Cat Street 🛍", "Shopping"),
    "shimokita":(35.6617, 139.6680, "Shimokitazawa 🛍", "Shopping"),
    "camii":    (35.66806, 139.67639, "Tokyo Camii 📍", "Attraction"),
    "sky":      (35.658, 139.7016, "Shibuya Sky 📍", "Attraction"),
    "teamlab":  (35.6605, 139.7406, "teamLab Borderless 📍", "Attraction"),
    "ttower":   (35.6586, 139.7454, "Tokyo Tower 📍", "Attraction"),
    "uniqlo":   (35.6737637, 139.7651281, "UNIQLO TOKYO — Ginza 🛍", "Shopping"),
    "muji":     (35.6746, 139.7668, "MUJI Ginza 🛍", "Shopping"),
    "roastery": (35.6497, 139.6934, "Starbucks Reserve Roastery Tokyo ☕", "Food"),
    "shmuseum": (31.2283, 121.4752, None, None),
    "nanjing":  (31.2366, 121.4807, None, None),
    "nbund":    (31.2475, 121.4985, None, None),
    "stower":   (31.2335, 121.5055, None, None),
    "lujiazui": (31.2397, 121.4998, None, None),
    "pvg":      (31.1443, 121.8083, None, None),
    "maglev":   (31.2034, 121.5578, None, None),
    "bund":     (31.2400, 121.4900, None, None),
    "yuyuan":   (31.2272, 121.4921, None, None),
}

# ---------------------------------------------------------------------------------------
# Bookings: shown on the TODAY screen for the days they belong to; a ticket photo/PDF is
# attached on the phone and kept offline in the browser.
# Our flights (China Eastern via Shanghai). Times are local at each airport; the app knows the
# time zones and counts down to the next departure. Other travellers enter their own on the phone.
FLIGHTS = [
    dict(no="MU6042", date="2026-10-16", frm="ALA", dep="20:50", to="PVG", arr="05:30"),
    dict(no="MU575", date="2026-10-17", frm="PVG", dep="17:15", to="HND", arr="21:20"),
    dict(no="MU540", date="2026-10-27", frm="HND", dep="20:15", to="PVG", arr="22:40"),
    dict(no="MU6041", date="2026-10-28", frm="PVG", dep="15:45", to="ALA", arr="19:35"),
]

# Buying recipes (spec appendix A). Hosts' own booking details (seats, numbers) are NOT here — only in Supabase.
RECIPES = [
    dict(bk="bus18", what="Автобус Keio, Busta Shinjuku → Kawaguchiko Sta., 18.10, 06:45", site="Highway Bus",
         url="https://www.highwaybus.com/", opens=None, opens_note="за месяц — уже открыты", buy_by="2026-10-10", price_pp=2200,
         tips="Выходить на Kawaguchiko Sta. — это не конечная. Утренние места уходят первыми."),
    dict(bk="bus_mishima", what="Автобус Fujikyu, Kawaguchiko Sta. → Mishima Sta., 18.10, 17:00 → 18:40", site="Fujikyu",
         url="https://bus.fujikyu.co.jp/en/highway/mishima/", opens=None, opens_note="проверить, нужна ли бронь", buy_by="2026-10-15", price_pp=2700,
         tips="От Oishi Park до станции — ретро-автобус ~25 мин."),
    dict(bk="shin18", what="Синкансэн Мисима → Киото, 18.10, после 19:00 (план 19:46)", site="Smart EX",
         url="https://smart-ex.jp/en/", opens=None, opens_note="обычно за месяц — проверить", buy_by="2026-10-15", price_pp=10500,
         tips="Место E — справа. Возьмите тот же поезд, что у хозяев."),
    dict(bk="h_kyoto", what="Отель в Киото, 18.10 → 20.10 (2 ночи): выбрать и забронировать", site="Booking.com",
         url="https://www.booking.com/searchresults.ru.html?ss=Kyoto&checkin=2026-10-18&checkout=2026-10-20",
         opens=None, opens_note="", buy_by="2026-10-03", price_pp=None,
         tips="Ближе к станции Киото — удобно с чемоданами и на Инари."),
    dict(bk="shin20", what="Синкансэн Киото → Нагоя, 20.10, ~14:10", site="Smart EX",
         url="https://smart-ex.jp/en/", opens=None, opens_note="проверить", buy_by="2026-10-18", price_pp=5900,
         tips="Чемодан больше 160 см по сумме сторон — место с багажной зоной. Дешевле (проверить цену): обычные поезда JR через Майбару (Special Rapid + пересадка), ~2 ч 10 мин и ~¥2 600 вместо ~35 мин и ~¥5 900, вдоль озера Бива; билет в кассе или по Suica, бронь не нужна. Приедете ~на 1,5 ч позже — сад Noritake сдвинется."),
    dict(bk="h_nagoya", what="Отель в Нагое, 20.10 → 22.10 (2 ночи): выбрать и забронировать", site="Booking.com",
         url="https://www.booking.com/searchresults.ru.html?ss=Nagoya&checkin=2026-10-20&checkout=2026-10-22",
         opens=None, opens_note="", buy_by="2026-10-06", price_pp=None,
         tips="У вокзала Нагоя: синкансэн и заезд с 15:00."),
    dict(bk="judo", what="Финалы пара-дзюдо PJU06, 21.10, 16:00, Aichi Budokan", site="Aichi-Nagoya 2026",
         url="https://lp-apg.tickets-aichi-nagoya2026.org/pdf/guide_ja-6.pdf", opens=None, opens_note="проверить", buy_by="2026-10-19", price_pp=2000,
         tips="Болеем за Казахстан."),
    dict(bk="shin22", what="Синкансэн Нагоя → Токио, 22.10, 18:00–19:00", site="Smart EX",
         url="https://smart-ex.jp/en/", opens=None, opens_note="проверить", buy_by="2026-10-20", price_pp=11300,
         tips="Дешевле (проверить цену): Kodama по акции «Platt Kodama» (JR Central Tours, бронь заранее, напиток в подарок) — ~3 ч вместо ~1 ч 40 мин, примерно на ¥2 500 дешевле; заселение в Токио тогда ~на 1,5 ч позже. Ночной/вечерний автобус — 5–6 ч, ~¥3 000–5 000, для этого вечера слишком долго."),
    dict(bk="h_tokyo", what="Отель в Токио, 22.10 → 27.10 (5 ночей): выбрать и забронировать", site="Booking.com",
         url="https://www.booking.com/searchresults.ru.html?ss=Tokyo&checkin=2026-10-22&checkout=2026-10-27",
         opens=None, opens_note="", buy_by="2026-10-09", price_pp=None,
         tips="Уэно / Окатимати или Асакуса — удобно до Ханэды в день вылета."),
    dict(bk="disney", what="Tokyo Disneyland, 24.10, билет на дату", site="Tokyo Disney Resort",
         url="https://www.tokyodisneyresort.jp/en/tdl/daily/calendar/20261024/", opens=None, opens_note="проверить", buy_by="2026-10-17", price_pp=12400,
         tips="Свою еду проносить нельзя; халяля почти нет."),
    dict(bk="sky", what="Shibuya Sky, 25.10, ~16:30 (закат ~16:50)", site="Shibuya Sky",
         url="https://www.shibuya-scramble-square.com/sky/ticket/", opens="2026-10-11T00:00+09:00",
         opens_note="11.10 00:00 по Японии = 10.10 20:00 по Алматы", buy_by="2026-10-11", price_pp=3400,
         tips="Слоты на закат уходят быстро."),
    dict(bk="h_shanghai", what="Шанхай, ночь 27.10 → 28.10, у Бунда: выбрать и забронировать", site="Booking.com",
         url="https://www.booking.com/searchresults.ru.html?ss=The+Bund%2C+Shanghai&checkin=2026-10-27&checkout=2026-10-28&group_adults=5&no_rooms=3&order=price",
         opens=None, opens_note="", buy_by="2026-10-20", price_pp=None,
         tips="Самое дешёвое у Бунда / Нанкин-лу — сетевые отели (Hanting, Home Inn, Jinjiang Inn), ориентир ¥250–400 юаней за номер (проверить). Только с бесплатной отменой: решите гулять всю ночь — отмените. Заезд около 02:00 — предупредить отель. Нужен ли отель — решите вместе."),
    dict(bk="teamlab", what="teamLab Borderless, 26.10, билет на время", site="teamLab",
         url="https://www.teamlab.art/e/tokyo/", opens=None, opens_note="проверить", buy_by="2026-10-20", price_pp=3600, tips=""),
]
GROUP = {"url": "https://ajpiptdkybhtkaoozqet.supabase.co", "anon": "sb_publishable_b6RTQ3rUOXTNwWxnEd98dg_feX9DPJi",
         "vapid": "BNlAOijvMWi2Hj9DYyuQBorTg-ZEtk1-UwtrnovgBNUCDri8007svbuj6epux66aVjwYqwGn-bORPlmFFKXRzw0"}   # publishable key: safe in the page; RLS + guarded RPCs do the rest

# Preparation checklist (spec appendix B). PREP is shared by both trips; PREP_OWN (Shanghai layover
# items) is ours only. `due`/`from` are ISO dates; `auto` marks an item the app can detect on its own.
PREP = [
    dict(id="p-home", group="phone", title="Приложение на экране «Домой»", auto="installed", note="Поделиться → На экран «Домой». Сделайте до того, как прикреплять билеты."),
    dict(id="p-suica", group="phone", title="Suica в Wallet", note="Wallet → + → Проездной → Suica. Проверьте казахстанскую карту заранее."),
    dict(id="p-esim", group="phone", title="eSIM или роуминг", due="2026-10-14"),
    dict(id="p-maps", group="phone", title="Офлайн-карты Токио, Киото, Нагои", due="2026-10-15"),
    dict(id="p-translate", group="phone", title="Google Переводчик: японский офлайн", due="2026-10-15"),
    dict(id="p-passport", group="money", title="Паспорт и японская виза на руках", due="2026-10-14"),
    dict(id="p-insurance", group="money", title="Страховка", due="2026-10-14"),
    dict(id="p-card", group="money", title="Карта работает за границей", note="Предупредите банк; проверьте оплату в иенах.", due="2026-10-14"),
    dict(id="p-cash", group="money", title="Наличные: план на первые дни", note="Менять в World Currency Shop, только если ≥ ¥155 за $1; иначе — 7-Bank."),
    dict(id="p-vjw", group="money", title="Visit Japan Web: QR иммиграции и таможни", url="https://www.vjw.digital.go.jp/", **{"from": "2026-10-11"}, due="2026-10-15",
         note="Заполнить за 1–6 дней до прилёта — проверить сроки."),
    dict(id="p-offline", group="money", title="Брони сохранены офлайн", note="Скриншоты или PDF — во вкладке «Брони»."),
    dict(id="p-adapter", group="packing", title="Переходник тип A"),
    dict(id="p-powerbank", group="packing", title="Пауэрбанк ≤ 100 Wh — в ручной клади"),
    dict(id="p-shoes", group="packing", title="Удобная обувь"),
    dict(id="p-umbrella", group="packing", title="Зонт или дождевик"),
    dict(id="p-warm", group="packing", title="Тёплый слой", note="Ночью у Фудзи около 8°."),
    dict(id="p-meds", group="packing", title="Лекарства"),
    dict(id="p-snacks", group="packing", title="Халяль-перекус"),
    dict(id="p-space", group="packing", title="Место для покупок / курьер чемоданов"),
]
PREP_OWN = [
    dict(id="p-sh-bags", group="money", title="Шанхай: уточнить, сквозной ли багаж до Ханэды", due="2026-10-10"),
    dict(id="p-sh-visa", group="money", title="Шанхай: безвиз для граждан РК — проверить", due="2026-10-10"),
    dict(id="p-sh-pay", group="money", title="Шанхай: юани или Alipay/WeChat Pay с иностранной картой", due="2026-10-14"),
]

BOOKINGS = [
    dict(id="flight_in", days=[1], t=P("Рейс MU575 Шанхай → Ханэда", "Прилёт в Ханэду"), when=P("17.10.2026 · 17:15 → 21:20", "17.10 · 21:20 (пример — впишите свой рейс)"), st=P("fixed", "input"), cost=None),
    dict(id="h_sansuiso", days=[1, 2], t=P("Рёкан Sansuiso, Готанда", "Отель у ст. Готанда, 1 ночь"), when=P("17.10 → 18.10 · заезд до 23:30", "17.10 → 18.10 · заезд поздно — предупредить"), st=P("fixed", "input"), cost=P(15039, None)),
    dict(id="bus18", days=[2], t="Автобус Keio: Busta → Kawaguchiko Sta.", when=P("18.10 · 06:45 · рейс 1431", "18.10 · 06:45 · highwaybus.com"), st=P("fixed", "input"), cost=4400),
    dict(id="bus_mishima", days=[2], t="Автобус Fujikyu: Кавагутико → Мисима", when=P("18.10 · 17:00 → 18:30 · рейс 0122, до Северного выхода", "18.10 · 17:00 → 18:40"), st=P("fixed", "input"), cost=P(5000, 5400)),
    dict(id="shin18", days=[2], t="Синкансэн Мисима → Киото", when="18.10 · после 19:00", st="input", cost=21000),
    dict(id="h_kyoto", days=[2, 3, 4], t="Отель в Киото", when="18.10 → 20.10 · 2 ночи", st="input", cost=None),
    dict(id="shin20", days=[4], t="Синкансэн Киото → Нагоя", when="20.10 · ~14:10", st="input", cost=11800),
    dict(id="h_nagoya", days=[4, 5, 6], t="Отель в Нагое", when="20.10 → 22.10 · 2 ночи", st="input", cost=None),
    dict(id="judo", days=[5], t="Пара-дзюдо PJU06, финалы", when="21.10 · 16:00 · Aichi Budokan", st="input", cost=4000),
    dict(id="shin22", days=[6], t="Синкансэн Нагоя → Токио", when="22.10 · 18:00–19:00", st="input", cost=22600),
    dict(id="h_tokyo", days=[6, 7, 8, 9, 10, 11], t="Отель в Токио", when="22.10 → 27.10 · 5 ночей", st="input", cost=None),
    dict(id="disney", days=[8], t="Tokyo Disneyland", when="24.10 · 09:00–21:00", st="input", cost=24800),
    dict(id="sky", days=[9], t="Shibuya Sky", when="25.10 · ~16:30", st="input", cost=6800),
    dict(id="teamlab", days=[10], t="teamLab Borderless", when="26.10", st="input", cost=7200),
    dict(id="h_shanghai", days=[12], t="Шанхай: отель на ночь у Бунда (по желанию)", when="27.10 → 28.10 · ночь", st="input", cost=None, only="own"),
    dict(id="flight_out", days=[11], t=P("Рейс MU540 Ханэда → Шанхай", "Вылет из Ханэды"), when=P("27.10.2026 · 20:15", "27.10 · 20:15 (пример — впишите свой рейс)"), st=P("fixed", "input"), cost=None),
]

HOTEL = {1: P("Рёкан Sansuiso, Готанда", "Отель у ст. Готанда"), 2: "Отель в Киото (не выбран)", 3: "Отель в Киото (не выбран)",
         4: "Отель в Нагое (не выбран)", 5: "Отель в Нагое (не выбран)", 6: "Отель в Токио (не выбран)",
         7: "Отель в Токио (не выбран)", 8: "Отель в Токио (не выбран)", 9: "Отель в Токио (не выбран)",
         10: "Отель в Токио (не выбран)", 11: "— вылет 20:15", 12: "Шанхай: отель у Бунда или прогулка"}

# the place in the local script, for «Показать по-японски» (taxi drivers, passers-by, Maps search).
# Names only — no street addresses: a famous place's name is what a driver needs, and a wrong address is worse than none.
# Hotels are left out until chosen (their address lives in the booking, never here). Shanghai stops are in Chinese.
LOC = {
    "hnd": "羽田空港", "gotanda": "五反田駅", "busta": "バスタ新宿", "kwgk": "河口湖駅",
    "ropeway": "河口湖〜富士山パノラマロープウェイ", "cruise": "河口湖遊覧船", "oishi": "大石公園", "mishima": "三島駅",
    "kyoto_st": "京都駅", "fushimi": "伏見稲荷大社", "kiyomizu": "清水寺", "sannen": "産寧坂（三年坂）・二寧坂",
    "nishiki": "錦市場", "gion": "祇園・花見小路", "bamboo": "嵐山 竹林の小径", "tenryuji": "天龍寺", "togetsu": "渡月橋",
    "kinkaku": "金閣寺（鹿苑寺）", "nagoya_st": "名古屋駅", "noritake": "ノリタケの森", "oasis21": "オアシス21",
    "ncastle": "名古屋城", "osu": "大須商店街", "atsuta": "熱田神宮", "toyota": "トヨタ産業技術記念館",
    "tokyo_st": "東京駅", "sensoji": "浅草寺", "ameyoko": "アメ横", "akiba": "秋葉原", "origami": "おりがみ会館",
    "tdl": "東京ディズニーランド", "meiji": "明治神宮", "harajuku": "原宿・キャットストリート", "shimokita": "下北沢",
    "camii": "東京ジャーミイ", "sky": "渋谷スカイ（渋谷スクランブルスクエア）", "teamlab": "チームラボボーダレス（麻布台ヒルズ）",
    "ttower": "東京タワー", "roastery": "スターバックス リザーブ ロースタリー 東京（中目黒）", "uniqlo": "ユニクロ 銀座", "muji": "無印良品 銀座",
    "pvg": ("浦东国际机场", "zh"), "maglev": ("龙阳路站", "zh"), "bund": ("外滩", "zh"), "yuyuan": ("豫园", "zh"),
    "shmuseum": ("上海博物馆（人民广场）", "zh"), "nanjing": ("南京东路步行街", "zh"), "nbund": ("北外滩滨江", "zh"),
    "stower": ("上海中心大厦", "zh"), "lujiazui": ("陆家嘴滨江", "zh"),
}

# ---------------------------------------------------------------------------------------
def E(s, e, t, place, cat, st, only=None, **kw):
    ev = dict(s=s, e=e, t=t, place=place, cat=cat, st=st)
    if only is not None:
        ev["only"] = only
    ev.update(kw)
    return ev

DAYS = [
 dict(n=1, city="Токио", label="Токио", wcity="Tokyo", sun=(35.55, 139.78), summary=P("Прилёт в Ханэду в 21:20, ночь в рёкане Sansuiso в Готанде", "Прилёт в Ханэду вечером, ночь у станции Готанда"),
      konbini="Конбини у станции Готанда: вода и завтрак на раннее утро 18-го",
      ev=[
   E("05:30", "06:45", "Шанхай: прилёт, паспортный контроль, выход в город", "pvg", "transport", "fixed", off=480, only="own",
     mode="Самолёт MU6042", note="Безвиз для граждан РК до 30 дней — проверить. Уточнить, сквозной ли багаж до Ханэды."),
   E("07:00", "07:30", "Маглев до Longyang Rd", "maglev", "transport", "planned", off=480, only="own", mode="Maglev",
     note="Ходит с 06:45, ~50 юаней — проверить."),
   E("07:30", "08:15", "Метро до Бунда", "bund", "transport", "planned", off=480, only="own", mode="Метро, линия 2", walk=10),
   E("08:15", "09:15", "Бунд утром, пока пусто", "bund", "activity", "planned", off=480, only="own", km=1.5),
   E("09:15", "10:00", "Пешком к Народной площади, завтрак", "shmuseum", "food", "planned", off=480, only="own", walk=25, km=2.0),
   E("10:00", "11:45", "Шанхайский музей: бронза, фарфор, каллиграфия", "shmuseum", "activity", "planned", off=480, only="own",
     note="Вход бесплатный, по паспорту; может понадобиться онлайн-бронь — проверить. По понедельникам закрыт (17.10 — суббота)."),
   E("11:45", "13:00", "Нанкин-лу Восточная: обувь", "nanjing", "activity", "flex", off=480, only="own", walk=10, km=1.0,
     note="Флагманы спортивных брендов, Li-Ning и Anta; магазины с 10:00. Платить Alipay или картой — проверить."),
   E("13:00", "13:45", "Обратно в Пудун: метро линия 2 + маглев", "pvg", "transport", "planned", off=480, only="own", mode="Метро + Maglev"),
   E("14:15", "17:15", "В аэропорту: регистрация MU575, досмотр, посадка", "pvg", "transport", "fixed", off=480, only="own",
     note="Не позже 14:15 — вылет в 17:15, международный рейс."),
   E("21:20", "22:00", P("Прилёт MU575, паспортный контроль и багаж", "Прилёт в Ханэду, паспортный контроль и багаж"), "hnd", "transport", P("fixed", "input"), mode="Самолёт", num=P("MU575", ""), frm=P("Шанхай", "—"), to="Ханэда T3", bk="flight_in",
     note="Сразу: наличные в банкомате 7-Bank, настроить Suica в Wallet."),
   E("22:00", "22:35", "Ханэда → Готанда", "gotanda", "transport", "planned", mode="Keikyu + Toei Asakusa", frm="Ханэда T3", to="Готанда", walk=5, cost=1000,
     note="Часть поездов Keikyu идёт по линии Asakusa без пересадки; иначе пересадка в Сэнгакудзи. ~¥500 на человека."),
   E("22:40", "23:00", P("Заселение в рёкан Sansuiso", "Заселение в отель у ст. Готанда"), "sansuiso", "hotel", P("fixed", "input"), walk=5, bk="h_sansuiso",
     note="Заселение до 23:30. Сразу оформить курьерскую отправку чемоданов в Киото и договориться о раннем выходе."),
   E("23:00", "23:20", "Конбини: вода и завтрак на 5 утра", "gotanda", "konbini", "flex", walk=5, cost=1500),
 ]),
 dict(n=2, city="Фудзи → Киото", label="Фудзи → Киото", wcity="Kawaguchiko", sun=(35.50, 138.76),
      summary="Busta 06:45 → Кавагутико: Lawson, канатная дорога, Oishi Park; вечером через Мисиму в Киото",
      konbini="Lawson у станции Кавагутико — тот самый; халяльных мест у Фудзи мало",
      transfer=dict(frm="Фудзи", to="Киото", s="17:00", e="21:49", how="Автобус до Мисимы + синкансэн", dur="4 ч 49 мин",
                    after=["Заселение в отель", "Ужин / конбини", "Сон — чемоданы приедут завтра"]),
      ev=[
   E("05:15", "05:40", "Подъём, завтрак из конбини", "sansuiso", "routine", "planned"),
   E("05:55", "06:15", "Готанда → Синдзюку", "busta", "transport", "planned", mode="JR Яманотэ", frm="Готанда", to="Синдзюку, New South Gate", walk=5, cost=420,
     note="Выход через New South Gate (新南改札), Busta прямо над ним, 4-й этаж."),
   E("06:45", "08:30", "Автобус Синдзюку → Кавагутико", "kwgk", "transport", P("fixed", "input"), mode="Автобус Keio", num=P("рейс 1431 (места — в билете)", ""), frm="Busta Shinjuku", to="Kawaguchiko Sta. (не конечная!)",
     plat="номер выхода — на табло Busta", buf=15, cost=4400, bk="bus18",
     note="Автобус идёт до Mt. Fuji 5th Station — выходить на «Kawaguchiko Sta.», Fuji-Q Highland раньше. Билет показывать при посадке и выходе. Бронь — highwaybus.com, продажа за месяц."),
   E("08:40", "09:10", "Lawson с Фудзи над крышей", "lawson", "activity", "planned", walk=5, km=0.8,
     note="Утром свет сбоку — лучший кадр. Жилой квартал: дорогу не перебегать."),
   E("09:25", "10:40", "Канатная дорога Kachi Kachi (Panorama Ropeway)", "ropeway", "activity", "planned", walk=15, cost=2000, km=1.0,
     note="~¥1 000 туда-обратно на человека (проверить). Если гора в облаках — сократить."),
   E("10:45", "11:15", "Катер по озеру Кавагутико", "cruise", "activity", "flex", walk=3, cost=2000,
     note="~20 мин, ~¥1 000 на человека. Первое, что убрать при усталости."),
   E("11:30", "12:30", "Обед у станции", "kwgk", "food", "planned", walk=10, cost=3000,
     note="Хото бывает на свином бульоне — спрашивать. Надёжнее конбини."),
   E("13:00", "15:45", "Oishi Park: Фудзи за озером", "oishi", "activity", "planned", ride=25, walk=5, mode="Ретро-автобус Red Line", cost=3000, km=2.0,
     note="Проездной на автобусы у озёр ¥1 500 на человека в день."),
   E("15:45", "16:15", "Свободное время у озера / кофе", "oishi", "activity", "flex", km=0.5,
     note="Запас перед автобусом. При задержке сокращается первым."),
   E("17:00", P("18:30", "18:40"), "Кавагутико → Мисима", "mishima", "transport", P("fixed", "input"), mode="Автобус Fujikyu", frm="Kawaguchiko Sta.", to=P("Mishima Sta. North Exit", "Mishima Sta."), ride=25, walk=5, buf=15, cost=P(5000, 5400), bk="bus_mishima",
     link="https://bus.fujikyu.co.jp/en/highway/mishima/", note=P("Куплено: рейс 0122, до Северного выхода Мисимы. Билет — на странице брони Fujiyama Connect (сохраните скриншот). От Oishi Park до станции — ретро-автобус ~25 мин.",
                                                                 "Нужно купить билет. От Oishi Park до станции — ретро-автобус ~25 мин.")),
   E("19:46", "21:49", "Мисима → Киото", "kyoto_st", "transport", "input", mode="Синкансэн (Kodama + пересадка или Hikari)", frm="Мисима", to="Киото", walk=5, buf=15, cost=21000, bk="shin18",
     link="https://smart-ex.jp/en/", note="Точный поезд выбрать в Smart EX. Место E справа. ~¥10 500 на человека."),
   E("22:00", "22:20", "Заселение в Киото", "kyoto_h", "hotel", "input", walk=5, bk="h_kyoto", note="Отель ещё не выбран. Предупредить о позднем заезде."),
   E("22:30", "22:45", "Конбини", "kyoto_h", "konbini", "flex", cost=1500),
 ]),
 dict(n=3, city="Киото", label="Киото", wcity="Kyoto", sun=(35.0, 135.76),
      summary="Арасияма на рассвете, Тэнрю-дзи, Кинкаку-дзи, обмен валюты, Нисики, вечерний Гион",
      konbini="FamilyMart у вокзала Киото — завтрак с собой к рассвету в Арасияме",
      ev=[
   E("05:40", "06:00", "Киото → Сага-Арасияма", "bamboo", "transport", "planned", mode="JR Сагано-лайн", frm="Киото", to="Сага-Арасияма", walk=10, cost=480),
   E("06:05", "07:15", "Бамбуковая роща на рассвете", "bamboo", "activity", "planned", walk=10, km=1.5,
     note="Восход ~06:05 — до 8:00 в роще почти никого."),
   E("07:15", "08:15", "Мост Тогэцукё, завтрак у реки", "togetsu", "food", "planned", walk=10, cost=1500, km=0.8,
     note="Кафе в это время почти закрыты — завтрак из конбини на набережной."),
   E("08:30", "09:30", "Тэнрю-дзи, сад дзен", "tenryuji", "activity", "planned", walk=10, cost=1000, km=0.8,
     note="Сад открывается в 8:30."),
   E("10:00", "11:15", "Кинкаку-дзи, Золотой павильон", "kinkaku", "activity", "planned", ride=25, walk=5, mode="Такси / автобус", cost=2500, km=1.0),
   E("11:45", "12:45", "Обед в центре", "nishiki", "food", "planned", ride=25, mode="Автобус / такси", cost=3000),
   E("13:00", "13:45", "Обмен: World Currency Shop (только если ≥ ¥155 за $1)", "wcs", "money", "planned", walk=10,
     note="Пн–пт 10:00–17:00, 1-й этаж MUFG Bank у метро Сидзё, паспорт. Если курс ниже — снимать в 7-Bank."),
   E("14:00", "15:30", "Рынок Нисики", "nishiki", "food", "flex", walk=5, cost=2000, km=1.0),
   E("15:30", "16:30", "Отдых в отеле", "kyoto_h", "activity", "flex", ride=15, mode="Метро / такси",
     note="Ранний подъём — час отдыха перед вечером."),
   E("16:45", "18:30", "Гион и Ханамикодзи в сумерках", "gion", "activity", "planned", ride=15, walk=10, km=2.0),
   E("19:00", "20:30", "Ужин (халяль: Sudaku по брони)", "gion", "food", "planned", cost=8000),
   E("21:00", "21:20", "Обратно в отель", "kyoto_h", "transport", "planned", walk=5, mode="Метро / такси", cost=500),
 ]),
 dict(n=4, city="Киото → Нагоя", label="Киото → Нагоя", wcity="Kyoto", sun=(35.0, 135.76),
      summary="Фусими-Инари на рассвете, Киёмидзу; днём синкансэн в Нагою, вечером Oasis 21",
      konbini="Lawson на рассвете: кофе перед Фусими-Инари",
      transfer=dict(frm="Киото", to="Нагоя", s="14:10", e="14:45", how="Синкансэн Nozomi", dur="35 мин",
                    after=["Заселение в отель", "Сад Noritake или отдых", "Oasis 21 на закате", "Ужин"]),
      ev=[
   E("06:15", "06:30", "Киото → Инари", "fushimi", "transport", "planned", mode="JR Нара-лайн", frm="Киото", to="Инари", walk=10, cost=300),
   E("06:30", "08:30", "Фусими-Инари: тысяча ворот до толп", "fushimi", "activity", "planned", km=4.0,
     note="Подъём до вершины и обратно ~2 ч. Можно повернуть на полпути у смотровой Ёцуцудзи."),
   E("08:45", "09:30", "Завтрак", "fushimi", "food", "planned", cost=2000),
   E("09:45", "11:15", "Киёмидзу-дэра", "kiyomizu", "activity", "planned", ride=20, walk=10, mode="Такси / автобус", cost=2500, km=1.5,
     note="Вход ¥500 на человека."),
   E("11:15", "12:00", "Санэндзака, Нинэндзака, Starbucks в доме-матия", "sannen", "activity", "flex", walk=5, cost=1500, km=1.0),
   E("12:15", "13:00", "Обед", "gion", "food", "planned", walk=10, cost=3000),
   E("13:30", "13:50", "Забрать вещи из отеля", "kyoto_h", "hotel", "planned", ride=20, mode="Такси"),
   E("14:10", "14:45", "Киото → Нагоя", "nagoya_st", "transport", "input", mode="Синкансэн Nozomi", frm="Киото", to="Нагоя", walk=10, buf=20, cost=11800, bk="shin20",
     link="https://smart-ex.jp/en/", note="Чемодан больше 160 см по сумме сторон — место с багажной зоной. Дешевле: обычные JR через Майбару, ~2 ч 10 мин, ~¥2 600 (проверить)."),
   E("15:00", "15:30", "Заселение в Нагое", "nagoya_h", "hotel", "input", walk=10, bk="h_nagoya",
     note="Обычное время заезда — с 15:00."),
   E("15:30", "17:00", "Сад Noritake или отдых", "noritake", "activity", "flex", walk=15, cost=1000,
     note="Бывшая фабрика фарфора Noritake: сад и кирпичные печи бесплатно, мастерская (можно расписать тарелку) ~¥500. Закрывается ~17:00."),
   E("17:15", "18:30", "Oasis 21 на закате", "oasis21", "activity", "flex", ride=15, mode="Метро Хигасияма до Сакаэ", cost=500, km=1.0,
     note="Бесплатно: прогулка по стеклянной крыше с водой на высоте 14 м, вид на телебашню. Закат ~17:20."),
   E("19:00", "20:00", "Ужин (Yamamotoya — халяль)", "nagoya_h", "food", "planned", ride=15, cost=4000),
 ]),
 dict(n=5, city="Нагоя", label="Нагоя / Para Judo", wcity="Nagoya", sun=(35.17, 136.88),
      summary="Замок Нагоя, Осу, обед; в 16:00 финалы пара-дзюдо",
      konbini="7-Eleven у вокзала Нагоя: вода и снеки на арену",
      ev=[
   E("09:00", "10:45", "Замок Нагоя", "ncastle", "activity", "planned", ride=15, walk=10, mode="Метро", cost=1500, km=2.0),
   E("11:15", "13:00", "Квартал Осу: винтаж, Mandarake", "osu", "activity", "flex", ride=15, walk=5, mode="Метро", km=2.0),
   E("13:00", "14:00", "Обед: Yamamotoya Ookute (халяль)", "osu", "food", "planned", cost=3000),
   E("14:15", "15:00", "Отдых в отеле, взять флаг", "nagoya_h", "hotel", "flex", ride=15, mode="Метро"),
   E("16:00", "18:30", P("Финалы пара-дзюдо PJU06 — болеем за Казахстан", "Финалы пара-дзюдо PJU06, Asian Para Games 2026"), "budokan", "event", "fixed", bound="2026-10-21", ride=12, walk=20, buf=25,
     mode="Aonami line до Кохоку (港北) + 15 мин пешком", frm="вокзал Нагоя", to="Aichi Budokan", cost=4000, bk="judo",
     link="https://aichi-budo.sakura.ne.jp/access.html", note="Билеты ещё не куплены (¥2 000 на человека). Время окончания — оценка."),
   E("18:45", "19:30", "Обратно к вокзалу Нагоя", "nagoya_st", "transport", "planned", walk=15, mode="Aonami line", cost=540),
   E("19:45", "21:00", "Ужин", "nagoya_h", "food", "planned", cost=4000),
 ]),
 dict(n=6, city="Нагоя → Токио", label="Нагоя → Токио", wcity="Nagoya", sun=(35.17, 136.88),
      summary="Ацута-дзингу, музей Toyota; вечером синкансэн в Токио",
      konbini="FamilyMart у вокзала Нагоя — перекус в поезд",
      transfer=dict(frm="Нагоя", to="Токио", s="18:00", e="19:40", how="Синкансэн Nozomi", dur="1 ч 40 мин",
                    after=["Метро до отеля", "Заселение", "Конбини", "Сон"]),
      ev=[
   E("09:00", "10:30", "Святилище Ацута-дзингу", "atsuta", "activity", "planned", ride=15, walk=10, mode="Метро / Meitetsu", cost=500, km=1.5),
   E("11:00", "13:00", "Музей Toyota (Commemorative Museum)", "toyota", "activity", "flex", ride=20, walk=5, mode="Meitetsu", cost=2000, km=1.5),
   E("13:00", "14:00", "Обед", "toyota", "food", "planned", cost=3000),
   E("14:30", "17:00", "Свободное время / отдых", "nagoya_h", "activity", "flex", ride=15),
   E("17:15", "17:40", "Забрать вещи", "nagoya_h", "hotel", "planned"),
   E("18:00", "19:40", "Нагоя → Токио", "tokyo_st", "transport", "input", mode="Синкансэн Nozomi", frm="Нагоя", to="Токио", walk=10, buf=20, cost=22600, bk="shin22",
     link="https://smart-ex.jp/en/", note="~¥11 300 на человека. Время выбрать в Smart EX. Дешевле: Kodama по «Platt Kodama», ~3 ч, ~на ¥2 500 меньше (проверить)."),
   E("20:15", "20:45", "Заселение в Токио", "tokyo_h", "hotel", "input", ride=20, walk=5, mode="Метро", cost=400, bk="h_tokyo",
     note="Уэно / Окатимати или Асакуса — отель ещё не выбран."),
   E("21:00", "21:20", "Конбини", "tokyo_h", "konbini", "flex", cost=1500),
 ]),
 dict(n=7, city="Токио", label="Токио", wcity="Tokyo", sun=(35.68, 139.76),
      summary="Сэнсо-дзи утром, Уэно и Амэёко, Акихабара, урок оригами",
      konbini="7-Eleven у отеля: наличные в 7-Bank",
      ev=[
   E("07:00", "08:30", "Сэнсо-дзи и Накамисэ до толп", "sensoji", "activity", "planned", walk=10, km=1.5),
   E("08:30", "09:30", "Завтрак (халяль-рамен Naritaya открывается в 10:00)", "sensoji", "food", "planned", cost=2000),
   E("10:00", "12:00", "Уэно и рынок Амэёко", "ameyoko", "activity", "planned", ride=15, walk=10, mode="Метро Гиндза", cost=400, km=2.5),
   E("12:00", "13:00", "Обед: Ayam-Ya (халяль)", "ameyoko", "food", "planned", cost=2500),
   E("13:30", "15:30", "Урок в Origami Kaikan", "origami", "activity", "flex", ride=10, walk=10, cost=5000,
     note="Запись по телефону 03-3811-4025, пн–сб. ¥2 500 на человека."),
   E("15:45", "18:30", "Акихабара", "akiba", "activity", "flex", walk=10, km=2.0),
   E("19:00", "20:30", "Ужин", "tokyo_h", "food", "planned", ride=10, cost=4000),
 ]),
 dict(n=8, city="Токио", label="Disneyland", wcity="Tokyo", sun=(35.63, 139.88),
      summary="Tokyo Disneyland весь день",
      konbini="7-Eleven до Майхамы: плотный завтрак",
      ev=[
   E("07:30", "08:15", "Отель → Майхама", "tdl", "transport", "planned", mode="JR Keiyo", frm="Отель", to="Майхама", walk=10, buf=10, cost=900),
   E("08:30", "09:00", "Очередь на вход", "tdl", "routine", "planned"),
   E("09:00", "21:00", "Tokyo Disneyland", "tdl", "event", P("fixed", "planned"), cost=24800, bk="disney", km=10.0,
     note="Билет на дату (ещё не куплен). Свою еду проносить нельзя; халяля почти нет — снеки. Если укачивает — избегать симуляторов."),
   E("21:00", "22:00", "Обратно в отель", "tokyo_h", "transport", "planned", walk=10, mode="JR", cost=900),
 ]),
 dict(n=9, city="Токио", label="Токио / Shibuya", wcity="Tokyo", sun=(35.66, 139.70),
      summary="Мэйдзи-дзингу, Омотэсандо, Симокитадзава, Tokyo Camii, закат на Shibuya Sky",
      konbini="FamilyMart в Сибуе",
      ev=[
   E("07:00", "08:15", "Мэйдзи-дзингу", "meiji", "activity", "planned", ride=30, walk=10, mode="Метро / JR", cost=500, km=2.0),
   E("08:30", "10:30", "Харадзюку и архитектура Омотэсандо", "harajuku", "activity", "planned", walk=10, km=2.0),
   E("11:30", "13:45", "Симокитадзава: винтаж + обед", "shimokita", "activity", "flex", ride=15, walk=5, mode="Keio Inokashira", cost=3500, km=2.0),
   E("14:30", "15:30", "Tokyo Camii: экскурсия и халяль-маркет", "camii", "activity", "flex", ride=5, walk=10, mode="Odakyu", cost=400, km=0.5,
     note="Экскурсии только по выходным."),
   E("16:30", "17:30", "Shibuya Sky — закат", "sky", "event", "input", ride=10, walk=10, buf=15, mode="Odakyu / такси", cost=6800, bk="sky",
     note="Продажа открывается 10.10 в 20:00 по Алматы. Закат ~16:50."),
   E("18:00", "19:30", "Ужин: Gyumon (халяль-рамен)", "sky", "food", "planned", walk=10, cost=4000),
   E("19:45", "21:15", "Starbucks Reserve Roastery Tokyo, Накамэгуро", "roastery", "food", "flex", ride=5, walk=12, mode="Tokyu Toyoko: Сибуя → Накамэгуро",
     cost=4000, km=1.0, note="Четыре этажа обжарки и кофе, вечером — вдоль реки Мэгуро. Работает примерно до 22:00–23:00 (проверить); в выходные бывает очередь по номеркам у входа."),
 ]),
 dict(n=10, city="Токио", label="Токио / teamLab", wcity="Tokyo", sun=(35.66, 139.74),
      summary="teamLab Borderless, Токийская башня, Uniqlo и MUJI в Гиндзе",
      konbini="Lawson — сладости на вечер",
      ev=[
   E("10:00", "12:30", "teamLab Borderless (Азабудай Хиллз)", "teamlab", "event", "input", ride=25, walk=10, buf=10, mode="Метро", cost=7200, bk="teamlab", km=2.0,
     note="Билет на время — ещё не куплен."),
   E("12:30", "13:30", "Обед", "teamlab", "food", "planned", cost=3000),
   E("13:45", "14:45", "Токийская башня", "ttower", "activity", "flex", walk=10, km=1.0),
   E("15:15", "16:45", "UNIQLO TOKYO и 12-этажный Uniqlo Ginza", "uniqlo", "activity", "planned", ride=15, walk=5, mode="Метро", km=1.5,
     note="Tax-free от ¥5 000 в один чек, паспорт."),
   E("16:45", "17:45", "MUJI Ginza", "muji", "activity", "planned", walk=5, km=0.5),
   E("18:30", "20:00", "Ужин", "tokyo_h", "food", "planned", ride=20, cost=4000),
 ]),
 dict(n=11, city="Токио → Ханэда", label="Токио → Ханэда", wcity="Tokyo", sun=(35.55, 139.78),
      summary="Последнее утро, покупки, в 17:15 выезд в Ханэду, вылет 20:15",
      konbini="Последний 7-Eleven: снеки домой, остаток Suica",
      transfer=dict(frm="Токио", to="Ханэда", s="17:15", e="18:00", how="Keikyu / метро", dur="~45 мин",
                    after=[P("Регистрация на MU540", "Регистрация на рейс"), "Tax-free покупки — под рукой", "Вылет 20:15"]),
      ev=[
   E("08:00", "10:00", "Завтрак, сборы, выселение, вещи на хранение", "tokyo_h", "hotel", "planned"),
   E("10:00", "12:00", "Асакуса / Каппабаси — последние покупки", "sensoji", "activity", "flex", walk=10, km=2.0),
   E("12:00", "13:00", "Обед", "sensoji", "food", "planned", cost=3000),
   E("13:30", "16:00", "Акихабара или отдых", "akiba", "activity", "flex", ride=10, km=1.5),
   E("16:30", "17:00", "Забрать вещи из отеля", "tokyo_h", "hotel", "planned", ride=10),
   E("17:15", "18:00", "Отель → Ханэда", "hnd", "transport", "planned", mode="Keikyu / Toei Asakusa", frm="Отель", to="Ханэда T3", walk=5, buf=15, cost=1200),
   E("18:00", "18:15", "В аэропорту за 2 часа: регистрация", "hnd", "routine", "planned"),
   E("20:15", "22:40", P("Вылет MU540 в Шанхай", "Вылет из Ханэды"), "hnd", "transport", P("fixed", "input"), mode="Самолёт", num=P("MU540", ""), frm="Ханэда T3", to=P("Шанхай", "—"), bk="flight_out",
     note=P("Ночь в Шанхае, домой MU6041 28.10 в 15:45.", "Впишите свой рейс и время.")),
 ]),
 dict(n=12, own=True, city="Шанхай", label="Шанхай · ночь и утро", wcity="Shanghai", sun=(31.23, 121.47),
      summary="Ночь в Шанхае: Северный Бунд, отель или прогулка, рассвет на Бунде, Shanghai Tower, в 15:45 домой",
      konbini="FamilyMart и Lawson открыты круглосуточно",
      ev=[
   E("00:00", "00:30", "Пудун: паспортный контроль, большие сумки — в камеру хранения", "pvg", "transport", "fixed", off=480,
     note="Прилёт MU540 в 22:40. Камера хранения в аэропорту — проверить, что работает ночью. С собой — рюкзак и паспорта."),
   E("00:30", "01:20", "Такси / DiDi в город", "nbund", "transport", "planned", off=480, mode="Такси / DiDi", frm="Пудун", to="Северный Бунд",
     note="Маглев и метро ночью не ходят. ~¥200–250 юаней за машину ночью (проверить); на пятерых — две машины. DiDi — через Alipay."),
   E("01:20", "02:00", "Северный Бунд: вид на Лудзяцзуй (рядом Raffles City The Bund)", "nbund", "activity", "planned", off=480, km=1.0),
   E("02:00", "05:30", "Ночь: отель у Бунда или прогулка по городу", "bund", "hotel", "flex", off=480, bk="h_shanghai",
     note="Отель — бронь в «Делах», с бесплатной отменой. Если гуляете: Нанкин-лу и набережная, еда допоздна вокруг Хуанхэ-лу у Народной площади; халяль — лапша Ланьчжоу; FamilyMart/Lawson круглосуточно. Держитесь вместе."),
   E("05:30", "07:00", "Рассвет на Бунде, тайцзи на набережной", "bund", "activity", "planned", off=480, km=1.5, note="Рассвет около 06:00."),
   E("07:00", "08:15", "Халяль-завтрак, метро линия 2 в Лудзяцзуй", "lujiazui", "food", "planned", off=480, mode="Метро, линия 2"),
   E("08:30", "10:30", "Shanghai Tower, 118 этаж — город с 546 м", "stower", "activity", "planned", off=480,
     note="~¥180–200 юаней на человека (проверить), открытие ~08:30–09:00. В дымку — лучше просто набережная."),
   E("10:30", "12:00", "Набережная Лудзяцзуй, обед", "lujiazui", "food", "flex", off=480, km=1.5),
   E("12:00", "13:15", "В Пудун: метро линия 2 + маглев, забрать сумки", "pvg", "transport", "planned", off=480, mode="Метро + Maglev"),
   E("13:15", "15:45", "В аэропорту: регистрация MU6041, посадка", "pvg", "transport", "fixed", off=480, num="MU6041",
     note="Вылет в Алматы 15:45, прилёт 19:35."),
 ]),
]

# ---------------------------------------------------------------------------------------
def _find_idx(ev, bk=None, title=None):
    """Index of the first event matching bk or title, in a built day's ev list."""
    for i, e in enumerate(ev):
        if (bk is not None and e.get("bk") == bk) or (title is not None and e.get("t") == title):
            return i
    raise ValueError(f"event not found in day: bk={bk!r} title={title!r}")


def build_parts(days):
    """Parts of the trip people join as a whole (spec §5), built from the real stop ids of the
    already-built `days` — never hardcoded id ranges, so a day's events can be reordered safely.
    Every stop of days 1-11 ends up in exactly one part (owners' ruling, 2026-09-30):
      arrive = day 1. fuji = day 2 up to & incl. the Kawaguchiko→Mishima bus (bk=bus_mishima).
      kyoto = day 2 from the Mishima→Kyoto Shinkansen (bk=shin18) onward, all of day 3, day 4 up
      to & incl. "Забрать вещи из отеля". nagoya = day 4 from the Kyoto→Nagoya train (bk=shin20)
      onward, all of day 5, day 6 up to & incl. "Забрать вещи". tokyo = day 6 from the
      Nagoya→Tokyo train (bk=shin22) onward, all of days 7-11.
    """
    by_n = {d["n"]: d for d in days}

    def ids(n, lo=0, hi=None):
        ev = by_n[n]["ev"]
        return [e["id"] for e in ev[lo:None if hi is None else hi]]

    d2, d4, d6 = by_n[2]["ev"], by_n[4]["ev"], by_n[6]["ev"]
    i_mishima = _find_idx(d2, bk="bus_mishima")
    i_shin18 = _find_idx(d2, bk="shin18")
    i_kyoto_checkout = _find_idx(d4, title="Забрать вещи из отеля")
    i_shin20 = _find_idx(d4, bk="shin20")
    i_nagoya_checkout = _find_idx(d6, title="Забрать вещи")
    i_shin22 = _find_idx(d6, bk="shin22")

    def stop_days(stops):
        """The days a part's stops are on, e.g. d4e7 -> 4 (a stop id is d{n}e{i})."""
        return sorted({int(s[1:s.index("e")]) for s in stops})

    parts = [
        dict(id="arrive", title="Прилёт, Токио", stops=ids(1)),
        dict(id="fuji", title="Фудзи / Кавагутико", stops=ids(2, 0, i_mishima + 1)),
        dict(id="kyoto", title="Киото",
             stops=ids(2, i_shin18) + ids(3) + ids(4, 0, i_kyoto_checkout + 1)),
        dict(id="nagoya", title="Нагоя и дзюдо",
             stops=ids(4, i_shin20) + ids(5) + ids(6, 0, i_nagoya_checkout + 1)),
        dict(id="tokyo", title="Токио",
             stops=ids(6, i_shin22) + [i for n in range(7, 12) for i in ids(n)]),
    ]
    for p in parts:
        p["days"] = stop_days(p["stops"])
    return parts


def trip(personal):
    days = []
    for d in DAYS:
        if d.get("own") and not personal:                       # our Shanghai night is not part of the template
            continue
        d = resolve(d, personal)
        evs = []
        for ev in d["ev"]:
            if ev.get("only") == "tpl" and personal:
                continue
            if ev.get("only") == "own" and not personal:
                continue
            ev = {k: v for k, v in ev.items() if k != "only"}
            lat, lng, stop, mcat = PL[ev["place"]]
            x = dict(id=f'd{d["n"]}e{len(evs)}', lat=lat, lng=lng, **ev)
            if ev["place"] in LOC and ev.get("cat") != "hotel":   # hotels: the address is in the booking
                v = LOC[ev["place"]]; x["loc"], x["locLang"] = (v, "ja") if isinstance(v, str) else v
            x.setdefault("walk", 0); x.setdefault("ride", 0); x.setdefault("buf", 0)
            if x.get("cost"):
                x["cost"] = round(x["cost"] / 2)          # the schedule is written for two; stored per person
            evs.append(x)
        days.append(dict(n=d["n"], date=DATES[d["n"]], city=d["city"], label=d["label"], wcity=d["wcity"],
                         sun=list(d["sun"]), summary=d["summary"], konbini=d["konbini"],
                         hotel=resolve(HOTEL[d["n"]], personal), transfer=d.get("transfer"), ev=evs))
    bks = []
    for b in resolve(BOOKINGS, personal):
        b = dict(b)
        if b.pop("only", None) == "own" and not personal:
            continue
        if b.get("cost"):
            b["cost"] = round(b["cost"] / 2)
        bks.append(b)
    return dict(schema=1, name="SHF Power Trip Japan 2026" if personal else "Япония за 11 дней · шаблон",
                template="japan-11d-2026", travelers=2, start=DATES[1], currency="KZT", rate=FX,
                bookings=bks, flights=FLIGHTS if personal else [], days=days,
                parts=build_parts(days) if personal else [], recipes=RECIPES if personal else [],
                group=GROUP if personal else None, prep=PREP + (PREP_OWN if personal else []))


TRIPS = pathlib.Path(__file__).resolve().parent.parent / "trips"      # served next to index.html


def write_trip(tid, data):
    """trips/<id>.json; `updated` moves only when the content does, so rebuilding changes nothing."""
    import datetime
    path = TRIPS / f"{tid}.json"
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    stamp = old.get("updated")
    if {k: v for k, v in old.items() if k != "updated"} != data or not stamp:
        stamp = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5))).isoformat(timespec="minutes")
    path.write_text(json.dumps({**data, "updated": stamp},
                               ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


PAGES = "https://zakcination.github.io/japan-2026/"
SHARE_PAGE = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>{name}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="План поездки 17–28 октября: что сейчас, куда едем и какие билеты купить. Откройте ссылку и выберите себя.">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Япония 2026">
<meta property="og:locale" content="ru_RU">
<meta property="og:title" content="{name}">
<meta property="og:description" content="План поездки 17–28 октября: что сейчас, куда едем и какие билеты купить. Откройте ссылку и выберите себя.">
<meta property="og:url" content="{base}t/{id}.html">
<meta property="og:image" content="{base}og-{id}.jpg?v=2">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Тории Фусими-Инари и надпись «SHF Power Trip · Japan 2026»">
<meta name="twitter:card" content="summary_large_image">
<link rel="apple-touch-icon" href="../apple-touch-icon.png">
<script>(function () {{ var q = new URLSearchParams(location.search); q.set('trip', '{id}');
  location.replace('../?' + q.toString() + location.hash); }})();</script>
<noscript><meta http-equiv="refresh" content="0;url=../?trip={id}"></noscript>
</head><body style="font:17px -apple-system,sans-serif;padding:24px"><a href="../?trip={id}">Открыть план поездки</a></body></html>
"""


def build():
    TRIPS.mkdir(exist_ok=True)
    tpl, own = trip(False), trip(True)
    tpl["id"], own["id"] = "template", "miras-aikosh"
    write_trip("template", tpl)
    write_trip("miras-aikosh", own)
    # a Home Screen app has its own storage, so each trip gets a manifest that opens that trip
    base = json.loads((TRIPS.parent / "manifest.webmanifest").read_text(encoding="utf-8"))
    for t in (own,):
        m = dict(base, id=f"./?trip={t['id']}", start_url=f"./?trip={t['id']}", name=t["name"], short_name="Япония")
        (TRIPS.parent / f"manifest-{t['id']}.webmanifest").write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # each shared trip gets its own short page for link previews (WhatsApp, iMessage): its own title and picture,
    # then straight into the app with the invite code and any #link kept
    share = TRIPS.parent / "t"; share.mkdir(exist_ok=True)
    for t in (own,):
        (share / f"{t['id']}.html").write_text(SHARE_PAGE.format(id=t["id"], name=t["name"], base=PAGES), encoding="utf-8")
    (TRIPS / "index.json").write_text(json.dumps([dict(id="template", name=tpl["name"]), dict(id="miras-aikosh", name=own["name"])],
                                                 ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # the map pins come from the template schedule: every event at a named place is a visit
    stops, seen = [], set()
    for d in tpl["days"]:
        src = next(x for x in DAYS if x["n"] == d["n"])
        raw_ev = [e for e in src["ev"] if e.get("only") != "own"]         # template drops own-only (Shanghai) events too
        for ev, raw in zip(d["ev"], raw_ev):
            lat, lng, stop, mcat = PL[raw["place"]]
            if not stop or (d["n"], stop) in seen and ev["cat"] != "hotel":
                continue
            seen.add((d["n"], stop))
            night = d["hotel"] if ev["cat"] == "hotel" and (ev["s"] >= "19:00" or d["n"] == 1) else ""
            stops.append(dict(day=d["n"], date=d["date"], name=stop, city=d["wcity"], category=mcat,
                              time=f'{ev["s"]}–{ev["e"]}' if ev.get("e") else ev["s"],
                              notes=(ev["t"] + (". " + ev["note"] if ev.get("note") else "")),
                              overnight=night, lat=lat, lng=lng))
    json.dump(stops, open("stops.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(tpl["days"]), "days,", sum(len(d["ev"]) for d in tpl["days"]), "events,", len(stops), "map visits;",
          "trips/template.json, trips/miras-aikosh.json, trips/index.json")


if __name__ == "__main__":
    build()
