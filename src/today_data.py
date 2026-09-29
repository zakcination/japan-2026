# -*- coding: utf-8 -*-
"""The trip, hour by hour — one source for the TODAY screen and for the map pins.

    python3 today_data.py        -> writes today.json and stops.json

Statuses: fixed (booked or immovable), planned (the recommended route), flex (drop it when
tired or late), input (waiting for the travellers' data). Fixed events are never moved by
the replanner; flex time is cut first, then planned.

Costs are yen for the two of us together. A "~" in the note marks an estimate.
Nothing private goes in here: no ticket numbers, phones or card data — tickets are
attached on the phone and stay on the device.
"""
import json

FX = 2.81          # ₸ per ¥, National Bank of Kazakhstan, 29.09.2026
DATES = {n: f"2026-10-{16 + n}" for n in range(1, 12)}

# place -> (lat, lng, map stop name or None, map category)
PL = {
    "hnd":      (35.5494, 139.7798, "Haneda Airport (HND) ✈️", "Airport"),
    "sansuiso": (35.6262, 139.7236, "Sansuiso – Gotanda 🏨", "Hotel"),
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
}

# ---------------------------------------------------------------------------------------
# Bookings: shown on the TODAY screen for the days they belong to; a ticket photo/PDF is
# attached on the phone and kept offline in the browser.
BOOKINGS = [
    dict(id="flight_in", days=[1], t="Рейс MU575 Шанхай → Ханэда", when="17.10.2026 · 17:15 → 21:20", st="fixed", cost=None),
    dict(id="h_sansuiso", days=[1, 2], t="Рёкан Sansuiso, Готанда", when="17.10 → 18.10 · заезд до 23:30", st="fixed", cost=15039),
    dict(id="bus18", days=[2], t="Автобус Keio: Busta → Kawaguchiko Sta.", when="18.10 · 06:45 · рейс 1431", st="fixed", cost=4400),
    dict(id="bus_mishima", days=[2], t="Автобус Fujikyu: Кавагутико → Мисима", when="18.10 · 17:00 → 18:40", st="input", cost=5400),
    dict(id="shin18", days=[2], t="Синкансэн Мисима → Киото", when="18.10 · после 19:00", st="input", cost=21000),
    dict(id="h_kyoto", days=[2, 3, 4], t="Отель в Киото", when="18.10 → 20.10 · 2 ночи", st="input", cost=None),
    dict(id="shin20", days=[4], t="Синкансэн Киото → Нагоя", when="20.10 · ~18:30", st="input", cost=11800),
    dict(id="h_nagoya", days=[4, 5, 6], t="Отель в Нагое", when="20.10 → 22.10 · 2 ночи", st="input", cost=None),
    dict(id="judo", days=[5], t="Пара-дзюдо PJU06, финалы", when="21.10 · 16:00 · Aichi Budokan", st="input", cost=4000),
    dict(id="shin22", days=[6], t="Синкансэн Нагоя → Токио", when="22.10 · 18:00–19:00", st="input", cost=22600),
    dict(id="h_tokyo", days=[6, 7, 8, 9, 10, 11], t="Отель в Токио", when="22.10 → 27.10 · 5 ночей", st="input", cost=None),
    dict(id="disney", days=[8], t="Tokyo Disneyland", when="24.10 · 09:00–21:00", st="input", cost=24800),
    dict(id="sky", days=[9], t="Shibuya Sky", when="25.10 · ~16:30", st="input", cost=6800),
    dict(id="teamlab", days=[10], t="teamLab Borderless", when="26.10", st="input", cost=7200),
    dict(id="flight_out", days=[11], t="Рейс MU540 Ханэда → Шанхай", when="27.10.2026 · 20:15", st="fixed", cost=None),
]

HOTEL = {1: "Рёкан Sansuiso, Готанда", 2: "Отель в Киото (не выбран)", 3: "Отель в Киото (не выбран)",
         4: "Отель в Нагое (не выбран)", 5: "Отель в Нагое (не выбран)", 6: "Отель в Токио (не выбран)",
         7: "Отель в Токио (не выбран)", 8: "Отель в Токио (не выбран)", 9: "Отель в Токио (не выбран)",
         10: "Отель в Токио (не выбран)", 11: "— вылет 20:15"}

# ---------------------------------------------------------------------------------------
def E(s, e, t, place, cat, st, **kw):
    ev = dict(s=s, e=e, t=t, place=place, cat=cat, st=st)
    ev.update(kw)
    return ev

DAYS = [
 dict(n=1, city="Токио", label="Токио", wcity="Tokyo", sun=(35.55, 139.78), summary="Прилёт в Ханэду в 21:20, ночь в рёкане Sansuiso в Готанде",
      konbini="Конбини у станции Готанда: вода и завтрак на раннее утро 18-го",
      ev=[
   E("21:20", "22:00", "Прилёт MU575, паспортный контроль и багаж", "hnd", "transport", "fixed", mode="Самолёт", num="MU575", frm="Шанхай", to="Ханэда T3", bk="flight_in",
     note="Сразу: наличные в банкомате 7-Bank, настроить Suica в Wallet."),
   E("22:00", "22:35", "Ханэда → Готанда", "gotanda", "transport", "planned", mode="Keikyu + Toei Asakusa", frm="Ханэда T3", to="Готанда", walk=5, cost=1000,
     note="Часть поездов Keikyu идёт по линии Asakusa без пересадки; иначе пересадка в Сэнгакудзи. ~¥500 на человека."),
   E("22:40", "23:00", "Заселение в рёкан Sansuiso", "sansuiso", "hotel", "fixed", walk=5, bk="h_sansuiso",
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
   E("06:45", "08:30", "Автобус Синдзюку → Кавагутико", "kwgk", "transport", "fixed", mode="Автобус Keio", num="рейс 1431 (места — в билете)", frm="Busta Shinjuku", to="Kawaguchiko Sta. (не конечная!)",
     plat="номер выхода — на табло Busta", buf=15, cost=4400, bk="bus18",
     note="Автобус идёт до Mt. Fuji 5th Station — выходить на «Kawaguchiko Sta.», Fuji-Q Highland раньше. Билет показывать при посадке и выходе. Отмена — до 06:35."),
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
   E("17:00", "18:40", "Кавагутико → Мисима", "mishima", "transport", "input", mode="Автобус Fujikyu", frm="Kawaguchiko Sta.", to="Mishima Sta.", ride=25, walk=5, buf=15, cost=5400, bk="bus_mishima",
     link="https://bus.fujikyu.co.jp/en/highway/mishima/", note="Нужно купить билет. От Oishi Park до станции — ретро-автобус ~25 мин."),
   E("19:46", "21:49", "Мисима → Киото", "kyoto_st", "transport", "input", mode="Синкансэн (Kodama + пересадка или Hikari)", frm="Мисима", to="Киото", walk=5, buf=15, cost=21000, bk="shin18",
     link="https://smart-ex.jp/en/", note="Точный поезд выбрать в Smart EX. Место E справа. ~¥10 500 на человека."),
   E("22:00", "22:20", "Заселение в Киото", "kyoto_h", "hotel", "input", walk=5, bk="h_kyoto", note="Отель ещё не выбран. Предупредить о позднем заезде."),
   E("22:30", "22:45", "Конбини", "kyoto_h", "konbini", "flex", cost=1500),
 ]),
 dict(n=3, city="Киото", label="Киото", wcity="Kyoto", sun=(35.0, 135.76),
      summary="Фусими-Инари на рассвете, Киёмидзу, обмен валюты, Нисики, вечерний Гион",
      konbini="Lawson на рассвете: кофе перед Фусими-Инари",
      ev=[
   E("06:00", "06:15", "Киото → Инари", "fushimi", "transport", "planned", mode="JR Нара-лайн", frm="Киото", to="Инари", walk=10, cost=300),
   E("06:15", "08:15", "Фусими-Инари: тысяча ворот до толп", "fushimi", "activity", "planned", km=4.0,
     note="Подъём до вершины и обратно ~2 ч. Можно повернуть на полпути у смотровой Ёцуцудзи."),
   E("08:30", "09:15", "Завтрак", "fushimi", "food", "planned", cost=2000),
   E("09:30", "11:15", "Киёмидзу-дэра", "kiyomizu", "activity", "planned", ride=20, walk=10, mode="Такси / автобус", cost=2500, km=1.5,
     note="Вход ¥500 на человека."),
   E("11:15", "12:15", "Санэндзака, Нинэндзака, Starbucks в доме-матия", "sannen", "activity", "flex", walk=5, cost=1500, km=1.0),
   E("12:30", "13:30", "Обед", "gion", "food", "planned", walk=10, cost=3000),
   E("13:45", "14:30", "Обмен: World Currency Shop (только если ≥ ¥155 за $1)", "wcs", "money", "planned", ride=10, walk=10, mode="Метро / пешком",
     note="Пн–пт 10:00–17:00, 1-й этаж MUFG Bank у метро Сидзё, паспорт. Если курс ниже — снимать в 7-Bank."),
   E("14:30", "16:00", "Рынок Нисики", "nishiki", "food", "flex", walk=5, cost=2000, km=1.0),
   E("16:30", "18:30", "Гион и Ханамикодзи в сумерках", "gion", "activity", "planned", walk=15, km=2.0),
   E("19:00", "20:30", "Ужин (халяль: Sudaku по брони)", "gion", "food", "planned", cost=8000),
   E("21:00", "21:20", "Обратно в отель", "kyoto_h", "transport", "planned", walk=5, mode="Метро / такси", cost=500),
 ]),
 dict(n=4, city="Киото → Нагоя", label="Киото → Нагоя", wcity="Kyoto", sun=(35.0, 135.76),
      summary="Арасияма на рассвете, Тэнрю-дзи, Кинкаку-дзи; вечером синкансэн в Нагою",
      konbini="FamilyMart у вокзала Киото — завтрак в поезд до Сага-Арасиямы",
      transfer=dict(frm="Киото", to="Нагоя", s="18:30", e="19:04", how="Синкансэн Nozomi", dur="34 мин",
                    after=["Заселение в отель", "Ужин", "Конбини", "Сон"]),
      ev=[
   E("06:30", "06:50", "Киото → Сага-Арасияма", "bamboo", "transport", "planned", mode="JR Сагано-лайн", frm="Киото", to="Сага-Арасияма", walk=10, cost=480),
   E("07:00", "08:15", "Бамбуковая роща до толп", "bamboo", "activity", "planned", walk=10, km=1.5),
   E("08:30", "09:30", "Тэнрю-дзи, сад дзен", "tenryuji", "activity", "planned", walk=5, cost=1000, km=0.8),
   E("09:30", "10:00", "Мост Тогэцукё", "togetsu", "activity", "flex", walk=5, km=0.5),
   E("10:15", "10:45", "Завтрак-обед у реки", "togetsu", "food", "planned", cost=2500),
   E("11:15", "12:30", "Кинкаку-дзи, Золотой павильон", "kinkaku", "activity", "planned", ride=25, walk=5, mode="Такси / автобус", cost=2500, km=1.0),
   E("13:00", "16:30", "Свободное время: кимоно, Удзи или отдых", "kyoto_h", "activity", "flex", ride=25, mode="Автобус / такси",
     note="Можно отдать под фотосессию в кимоно у Ясака или отдых перед переездом."),
   E("17:15", "17:45", "Забрать вещи из отеля", "kyoto_h", "hotel", "planned"),
   E("18:30", "19:04", "Киото → Нагоя", "nagoya_st", "transport", "input", mode="Синкансэн Nozomi", frm="Киото", to="Нагоя", walk=10, buf=20, cost=11800, bk="shin20",
     link="https://smart-ex.jp/en/", note="Чемодан больше 160 см по сумме сторон — место с багажной зоной."),
   E("19:20", "19:40", "Заселение в Нагое", "nagoya_h", "hotel", "input", walk=10, bk="h_nagoya"),
   E("20:00", "21:00", "Ужин (Yamamotoya — халяль)", "nagoya_h", "food", "planned", cost=4000),
 ]),
 dict(n=5, city="Нагоя", label="Нагоя / Para Judo", wcity="Nagoya", sun=(35.17, 136.88),
      summary="Замок Нагоя, Осу, обед; в 16:00 финалы пара-дзюдо",
      konbini="7-Eleven у вокзала Нагоя: вода и снеки на арену",
      ev=[
   E("09:00", "10:45", "Замок Нагоя", "ncastle", "activity", "planned", ride=15, walk=10, mode="Метро", cost=1500, km=2.0),
   E("11:15", "13:00", "Квартал Осу: винтаж, Mandarake", "osu", "activity", "flex", ride=15, walk=5, mode="Метро", km=2.0),
   E("13:00", "14:00", "Обед: Yamamotoya Ookute (халяль)", "osu", "food", "planned", cost=3000),
   E("14:15", "15:00", "Отдых в отеле, взять флаг", "nagoya_h", "hotel", "flex", ride=15, mode="Метро"),
   E("16:00", "18:30", "Финалы пара-дзюдо PJU06 — болеем за Казахстан", "budokan", "event", "fixed", ride=12, walk=20, buf=25,
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
     link="https://smart-ex.jp/en/", note="~¥11 300 на человека. Время выбрать в Smart EX."),
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
   E("09:00", "21:00", "Tokyo Disneyland", "tdl", "event", "fixed", cost=24800, bk="disney", km=10.0,
     note="Билет на дату (ещё не куплен). Свою еду проносить нельзя; халяля почти нет — снеки. Мираса укачивает на симуляторах."),
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
                    after=["Регистрация на MU540", "Tax-free покупки — под рукой", "Вылет 20:15"]),
      ev=[
   E("08:00", "10:00", "Завтрак, сборы, выселение, вещи на хранение", "tokyo_h", "hotel", "planned"),
   E("10:00", "12:00", "Асакуса / Каппабаси — последние покупки", "sensoji", "activity", "flex", walk=10, km=2.0),
   E("12:00", "13:00", "Обед", "sensoji", "food", "planned", cost=3000),
   E("13:30", "16:00", "Акихабара или отдых", "akiba", "activity", "flex", ride=10, km=1.5),
   E("16:30", "17:00", "Забрать вещи из отеля", "tokyo_h", "hotel", "planned", ride=10),
   E("17:15", "18:00", "Отель → Ханэда", "hnd", "transport", "planned", mode="Keikyu / Toei Asakusa", frm="Отель", to="Ханэда T3", walk=5, buf=15, cost=1200),
   E("18:00", "18:15", "В аэропорту за 2 часа: регистрация", "hnd", "routine", "fixed"),
   E("20:15", "22:40", "Вылет MU540 в Шанхай", "hnd", "transport", "fixed", mode="Самолёт", num="MU540", frm="Ханэда T3", to="Шанхай", bk="flight_out",
     note="Ночь в Шанхае, домой MU6041 28.10 в 15:45."),
 ]),
]

# ---------------------------------------------------------------------------------------
def build():
    days = []
    for d in DAYS:
        evs = []
        for i, ev in enumerate(d["ev"]):
            lat, lng, stop, mcat = PL[ev["place"]]
            x = dict(id=f'd{d["n"]}e{i}', lat=lat, lng=lng, **ev)
            x.setdefault("walk", 0); x.setdefault("ride", 0); x.setdefault("buf", 0)
            evs.append(x)
        days.append(dict(n=d["n"], date=DATES[d["n"]], city=d["city"], label=d["label"], wcity=d["wcity"],
                         sun=list(d["sun"]), summary=d["summary"], konbini=d["konbini"], hotel=HOTEL[d["n"]],
                         transfer=d.get("transfer"), ev=evs))
    today = dict(fx=FX, bookings=BOOKINGS, days=days)
    json.dump(today, open("today.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # the map pins come from the same schedule: every event at a named place is a visit
    stops, seen = [], set()
    for d in DAYS:
        for ev in d["ev"]:
            lat, lng, stop, mcat = PL[ev["place"]]
            if not stop or (d["n"], stop) in seen and ev["cat"] != "hotel":
                continue
            seen.add((d["n"], stop))
            night = ""
            if ev["cat"] == "hotel" and ev["s"] >= "19:00" or (ev["cat"] == "hotel" and d["n"] == 1):
                night = HOTEL[d["n"]]
            stops.append(dict(day=d["n"], date=DATES[d["n"]], name=stop, city=d["wcity"], category=mcat,
                              time=f'{ev["s"]}–{ev["e"]}' if ev.get("e") else ev["s"], notes=(ev["t"] + (". " + ev["note"] if ev.get("note") else "")),
                              overnight=night, lat=lat, lng=lng))
    json.dump(stops, open("stops.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(days), "days,", sum(len(d["ev"]) for d in days), "events,", len(stops), "map visits")


if __name__ == "__main__":
    build()
