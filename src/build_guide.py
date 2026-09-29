#!/usr/bin/env python3
"""Build a lean, self-contained Leaflet trip guide from the extracted stop data."""
import base64
import hashlib
import json
import pathlib
import re

STOPS = json.load(open("stops.json", encoding="utf-8"))

# --- vendored Leaflet (from the npm tarball) so the page needs no external JS/CSS ---
DIST = pathlib.Path("package/dist")
LEAFLET_JS = DIST.joinpath("leaflet.js").read_text(encoding="utf-8")
LEAFLET_CSS = DIST.joinpath("leaflet.css").read_text(encoding="utf-8")


def inline_css_images(css: str) -> str:
    """Replace url(images/foo.png) with base64 data URIs."""
    def repl(m):
        name = m.group(1)
        path = DIST / "images" / name
        if not path.exists():
            return m.group(0)
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'url(data:image/png;base64,{b64})'
    return re.sub(r'url\(images/([\w.\-]+)\)', repl, css)


LEAFLET_CSS = inline_css_images(LEAFLET_CSS)

# Coastline of the trip's region, clipped and simplified from Natural Earth (world-atlas).
# It is the base map: the page must draw a real map with no network at all, because the
# hosted/sandboxed environments block tile servers outright.
BASEMAP = pathlib.Path("japan_basemap.json").read_text(encoding="utf-8")

# Climate-model numbers for the trip window, fetched once at build time (Open-Meteo climate
# API). They ship inside the file so the guide shows weather with no network at all; a live
# forecast replaces them from about 16 days before the trip, when one starts to exist.
WX_BAKED = json.loads(pathlib.Path("wx_baked.json").read_text(encoding="utf-8"))

# Leaflet.markercluster: standard clustering — groups dense markers and splits them
# back apart as you zoom in, with spiderfy for markers that share a point.
CLUSTER_JS = DIST.joinpath("leaflet.markercluster.js").read_text(encoding="utf-8")
CLUSTER_CSS = DIST.joinpath("MarkerCluster.css").read_text(encoding="utf-8")

# Ghibli-style artwork: place name -> local .webp in img/. The files are inlined
# as data: URIs so the guide shows them with no network request at all.
GHIBLI = {
    "Todai-ji 📍": "todaiji",
    "Fushimi Inari Taisha 📍": "fushimi",
    "Senso-ji / Asakusa 📍": "sensoji",
    "Itsukushima Shrine & Torii 🌿": "itsukushima",
    "Arashiyama Bamboo Grove 🌿": "arashiyama",
    "Nara Park 🌿": "narapark",
    "Dotonbori 🍜": "dotonbori",
    "Pontocho & Kamo River 🍜": "pontocho",
    "Tsukiji Outer Market 🍜": "tsukiji",
    "Sannenzaka / Ninenzaka 🛍": "sannenzaka",
    "Gion / Hanamikoji 🛍": "gion",
    "Ginza 🛍": "ginza",
    "Osaka hotel area – Hommachi 🏨": "hommachi",
    "Kyoto hotel area – Kyoto Station 🏨": "kyotostation",
    "Tokyo hotel area – Asakusa 🏨": "asakusa",
    "Kobe Airport (UKB) ✈️": "kobe",
    "Haneda Airport (HND) ✈️": "haneda",
}
# The Hiroshima memorials are deliberately not stylised: a Ghibli-style illustration
# of an atomic bombing memorial would be tasteless. These are restrained documentary
# views, and the card labels them differently so the two registers never get confused.
DOCUMENTARY = {
    "Atomic Bomb Dome 📍": "abdome",
    "Hiroshima Peace Memorial Park 📍": "peacepark",
    "Hiroshima Peace Memorial Museum 📍": "peacemuseum",
}

IMG_DIR = pathlib.Path("img")


def data_uri(stem):
    """Inline one artwork as a base64 data: URI (no external request at runtime)."""
    p = IMG_DIR / (stem + ".webp")
    return "data:image/webp;base64," + base64.b64encode(p.read_bytes()).decode("ascii")

# Route: the bases of the trip, in the order they are travelled.
ROUTE = [
    [35.5494, 139.7798],   # Haneda
    [35.6262, 139.7236],   # first night near Gotanda Station
    [35.6887, 139.7003],   # Busta Shinjuku
    [35.4985, 138.7690],   # Kawaguchiko
    [35.1260, 138.9110],   # Mishima
    [34.9855, 135.7588],   # Kyoto
    [35.1709, 136.8815],   # Nagoya
    [35.711, 139.7966],    # Tokyo, Asakusa/Ueno
    [35.5494, 139.7798],   # Haneda
]
TRANSFERS = [
    {"lat": 35.5700, "lng": 139.8600, "label": "≈30 мин · Keikyu",
     "text": "Ханэда → Готанда · 17 окт вечером"},
    {"lat": 35.6700, "lng": 139.2300, "label": "06:45 → 08:30 · автобус",
     "text": "Busta Синдзюку → Кавагутико · автобус Keio, 18 окт (куплен)"},
    {"lat": 35.3100, "lng": 138.8200, "label": "17:00 → 18:40 · автобус",
     "text": "Кавагутико → Мисима · Fujikyu, 18 окт"},
    {"lat": 34.9500, "lng": 137.9500, "label": "~2 ч · синкансэн",
     "text": "Мисима → Киото · 18 окт вечером"},
    {"lat": 35.0780, "lng": 136.3200, "label": "34 мин · Nozomi",
     "text": "Киото → Нагоя · 20 окт ~18:30"},
    {"lat": 35.3300, "lng": 137.7500, "label": "1 ч 40 мин · Nozomi",
     "text": "Нагоя → Токио · 22 окт 18:00–19:00"},
]


# --- what has to be reserved, and by when -----------------------------------
# level: must = без брони не попасть; advise = желательно; info = просто учесть
_NOW = "2026-09-28"
_HOTEL = "Сейчас, если ещё не забронирован"
BOOKING = {
    "Hotel – Gotanda": {
        "level": "must", "act": "2026-10-01",
        "when": "Первая ночь у станции Готанда — поздний заезд после прилёта",
        "note": "От Готанды утром — 15 минут по JR Яманотэ до Busta Синдзюку. Предупредить о заезде после 22:00 и спросить про отправку чемоданов курьером.",
        "url": "",
    },
    "Busta Shinjuku": {
        "level": "must", "act": "2026-09-18",
        "when": "Автобус Синдзюку → Кавагутико, 06:45 — продажа открывается за месяц",
        "note": "highwaybus.com → Shinjuku – Fujigoko / Mt. Fuji 5th Station → Outbound → выход Kawaguchiko Sta. (не конечная). Места Front / Window.",
        "url": "https://www.highwaybus.com/",
    },
    "Mishima Station": {
        "level": "must", "act": _NOW,
        "when": "Автобус Кавагутико → Мисима 18 окт 17:00 и синкансэн Мисима → Киото после 19:00",
        "note": "Автобус Fujikyu ¥2 700 на человека. Синкансэн — Smart EX.",
        "url": "https://bus.fujikyu.co.jp/en/highway/mishima/",
    },
    "Kyoto hotel area – Kyoto Station": {
        "level": "must", "act": _NOW, "when": _HOTEL,
        "note": "2 ночи, 18–20 окт, заезд ~22:00. Должен принять чемоданы от курьера из Токио.",
        "url": "",
    },
    "World Currency Shop – Kyoto": {
        "level": "info", "act": "2026-10-19",
        "when": "Без брони · пн–пт 10:00–17:00",
        "note": "Меняем, только если курс не ниже ¥155 за $1. Иначе снимать в 7-Bank.",
        "url": "https://www.tokyo-card.co.jp/wcs/wcs-shop-e.php",
    },
    "Nagoya hotel area – Nagoya Station": {
        "level": "must", "act": _NOW, "when": _HOTEL,
        "note": "2 ночи, 20–22 окт (ещё обсуждается: можно уехать в Токио сразу после финалов 21-го). В городе Asian Para Games — номера уйдут быстро.",
        "url": "",
    },
    "Aichi Budokan": {
        "level": "must", "act": _NOW,
        "when": "Пара-дзюдо PJU06, финалы 21 окт 16:00 · ¥2 000 на человека",
        "note": "От вокзала Нагоя: Aonami line до Кохоку (港北) 12 мин + 15 мин пешком.",
        "url": "https://lp-apg.tickets-aichi-nagoya2026.org/pdf/guide_ja-6.pdf",
    },
    "Tokyo hotel area – Asakusa": {
        "level": "must", "act": _NOW, "when": _HOTEL,
        "note": "5 ночей, 22–27 окт: Уэно / Окатимати или Асакуса. Keikyu до Ханэды без пересадок.",
        "url": "",
    },
    "Tokyo Disneyland": {
        "level": "must", "act": _NOW,
        "when": "24 окт, 09:00–21:00 · ¥12 400 на человека, билет на дату",
        "note": "Только официальный сайт. Суббота — много людей; альтернатива — DisneySea в будний день.",
        "url": "https://www.tokyodisneyresort.jp/en/tdl/daily/calendar/20261024/",
    },
    "Shibuya Sky": {
        "level": "must", "act": "2026-10-10",
        "when": "25 окт ~16:30 · продажа за 14 дней: 11 окт 00:00 JST = 10 окт 20:00 по Алматы",
        "note": "Закатные слоты уходят за минуты. Онлайн ¥3 400 на человека по текущим ценам.",
        "url": "https://www.shibuya-scramble-square.com/sky/ticket/",
    },
    "teamLab Borderless": {
        "level": "advise", "act": "2026-10-12",
        "when": "26 окт · билет на время",
        "note": "Азабудай Хиллз.",
        "url": "https://www.teamlab.art/e/tokyo/",
    },
    "Origami Kaikan": {
        "level": "advise", "act": "2026-10-16",
        "when": "23 окт, урок 13:30 — записаться по телефону 03-3811-4025",
        "note": "Пн–сб, ¥2 500 на человека.",
        "url": "https://origamikaikan.co.jp/",
    },
    "UNIQLO TOKYO — Ginza": {
        "level": "info", "act": "2026-10-26",
        "when": "Бронь не нужна · 11:00–21:00",
        "note": "Tax-free от ¥5 000 в один чек, с паспортом. Рядом 12-этажный Uniqlo Ginza.",
        "url": "",
    },
    "Haneda Airport (HND)": {
        "level": "info", "act": "2026-10-27",
        "when": "Прилёт 17 окт 21:20 · вылет 27 окт 20:15",
        "note": "Время — из шаблона, впишите свои рейсы в «Сегодня → ⚙». В аэропорту быть за 2 часа.",
        "url": "",
    },
}

# arrival and departure are both Haneda, so one arc points home towards Almaty
FLIGHTS = [
    {"kind": "both", "lat": 35.5494, "lng": 139.7798,
     "label": "✈️ Ханэда · прилёт и вылет",
     "text": "Шаблон: прилёт в Ханэду 17 окт вечером, вылет 27 окт 20:15. Из центра выехать к 17:30."},
]

# Place names for the built-in base map. "trip" cities are the ones on the route and are
# always drawn; the rest appear as you zoom in, so the country view stays readable.
PLACE_LABELS = [
    # name, lat, lng, min zoom, on the route
    ("Токио",     35.6762, 139.6503, 0, True),
    ("Киото",     35.0116, 135.7681, 0, True),
    ("Нагоя",     35.1815, 136.9066, 0, True),
    ("Кавагутико", 35.5006, 138.7597, 0, True),
    ("Мисима",    35.1260, 138.9110, 7, True),
    ("Хаконэ",    35.2324, 139.1069, 7, False),
    ("Осака",     34.6937, 135.5023, 6, False),
    ("Камакура",  35.3192, 139.5467, 7, False),
    ("Нара",      34.6851, 135.8048, 7, False),
    ("Иокогама",  35.4437, 139.6380, 7, False),
    ("Хиросима",  34.3853, 132.4553, 5, False),
    ("Фукуока",   33.5904, 130.4017, 5, False),
    ("Саппоро",   43.0618, 141.3545, 5, False),
    ("Сендай",    38.2682, 140.8694, 5, False),
    ("Канадзава", 36.5613, 136.6562, 6, False),
    ("Окаяма",    34.6551, 133.9195, 6, False),
    ("Сидзуока",  34.9756, 138.3828, 6, False),
    ("Химедзи",   34.8154, 134.6854, 7, False),
    ("Вакаяма",   34.2260, 135.1675, 7, False),
    ("Ниигата",   37.9161, 139.0364, 6, False),
    ("Мацуяма",   33.8416, 132.7657, 6, False),
    ("Тояма",     36.6953, 137.2113, 7, False),
    ("Аомори",    40.8246, 140.7406, 6, False),
    ("Кагосима",  31.5966, 130.5571, 6, False),
    ("Сеул",      37.5665, 126.9780, 5, False),
    ("Пусан",     35.1796, 129.0756, 6, False),
]

CITY_COLOR = {
    "Tokyo": "#2563eb", "Fuji": "#2f9e44", "Kawaguchiko": "#2f9e44", "Nagoya": "#e58a1f",
    "Kyoto": "#8b5cf6",
}
CAT_META = {
    "Attraction": {"emoji": "📍", "label": "Достопримечательности", "short": "Места"},
    "Event":      {"emoji": "🏟", "label": "Спорт и события",       "short": "События"},
    "Nature":     {"emoji": "🌿", "label": "Природа и парки",       "short": "Природа"},
    "Food":       {"emoji": "🍜", "label": "Еда",                   "short": "Еда"},
    "Shopping":   {"emoji": "🛍", "label": "Шоппинг и винтаж",      "short": "Шоппинг"},
    "Transit":    {"emoji": "🚌", "label": "Транспорт",             "short": "Транспорт"},
    "Money":      {"emoji": "💴", "label": "Обмен валюты",          "short": "Обмен"},
    "Hotel":      {"emoji": "🏨", "label": "Отели",                 "short": "Отели"},
    "Airport":    {"emoji": "✈️", "label": "Аэропорт",              "short": "Аэропорт"},
}

# PERSONAL=1 builds our own copy with the private trip preloaded (never committed);
# the default build is the public, universal template.
import os
PERSONAL = os.environ.get("PERSONAL") == "1"
TODAY = json.loads(pathlib.Path("../survey/trip_miras_aikosh.json" if PERSONAL else "today.json").read_text(encoding="utf-8"))
DAY_NOTES = {d["n"]: d["summary"] for d in TODAY["days"]}
KONBINI = {d["n"]: d["konbini"] for d in TODAY["days"]}

KZ_EMOJI = ("📍", "🏟", "💴", "🏪", "🚌", "🌿", "🍜", "🛍", "🏨", "✈️", "🍺", "🍶")


def place_label(name: str) -> str:
    """Marker name minus its trailing category emoji — the join key for every side table."""
    for e in KZ_EMOJI:
        name = name.replace(e, "")
    return name.strip()


# Kazakh-Japanese fact layer: same keys as stops.json, joined on the stripped label.
KZ_RAW = json.loads(pathlib.Path("kz_facts.json").read_text(encoding="utf-8"))["places"]
KZ_FACTS = {place_label(k): v["facts"] for k, v in KZ_RAW.items()}
# the fact pack outlives any one route: places dropped from the route keep their facts
# in the file and simply aren't shipped
_ON_ROUTE = {place_label(s["name"]) for s in STOPS}
KZ_DROPPED = sorted(KZ_FACTS.keys() - _ON_ROUTE)
KZ_FACTS = {k: v for k, v in KZ_FACTS.items() if k in _ON_ROUTE}

# "Find it on the spot" tasks are ticked off and the tick is remembered on the device,
# so each one needs an id that survives a rebuild. Hashing place+text means reordering
# the list keeps every tick, while rewriting a task correctly retires the old one.
KZ_SPOTS = 0
for _label, _facts in KZ_FACTS.items():
    for _f in _facts:
        _g = _f.get("game")
        if _g and _g.get("type") == "spot":
            _g["id"] = hashlib.sha1(
                (_label + "|" + _g["task"]).encode("utf-8")).hexdigest()[:10]
            KZ_SPOTS += 1


for s in STOPS:
    key = GHIBLI.get(s["name"]) or DOCUMENTARY.get(s["name"])
    s["img"] = data_uri(key) if key else None
    s["img_style"] = "doc" if s["name"] in DOCUMENTARY else ("art" if key else None)
    s["color"] = CITY_COLOR.get(s["city"], "#475569")
    s["emoji"] = CAT_META.get(s["category"], {}).get("emoji", "📍")
    # strip the trailing emoji from the display name — the marker carries it
    s["label"] = place_label(s["name"])

DAYS = sorted({s["day"] for s in STOPS})
DAY_DATES = {s["day"]: s["date"] for s in STOPS}

# one marker per physical place; every day it is used becomes a "visit"
places, index = [], {}
for s in STOPS:
    key = (s["label"], round(s["lat"], 5), round(s["lng"], 5))
    if key not in index:
        index[key] = len(places)
        places.append({
            "label": s["label"], "city": s["city"], "category": s["category"],
            "lat": s["lat"], "lng": s["lng"], "img": s["img"], "imgStyle": s["img_style"],
            "color": s["color"], "emoji": s["emoji"], "days": [], "visits": [],
            "kz": KZ_FACTS.get(s["label"], []),
        })
    pl = places[index[key]]
    if s.get("gmaps_id"):
        pl["gmaps_id"] = s["gmaps_id"]
    if s["day"] not in pl["days"]:
        pl["days"].append(s["day"])
    pl["visits"].append({"day": s["day"], "date": s["date"], "time": s["time"],
                         "notes": s["notes"], "overnight": s["overnight"]})

visits = []
for s in STOPS:
    key = (s["label"], round(s["lat"], 5), round(s["lng"], 5))
    visits.append({"p": index[key], "day": s["day"], "time": s["time"],
                   "notes": s["notes"], "overnight": s["overnight"]})
visits.sort(key=lambda v: v["day"])

# booking requirements hang off the place label
for pl in places:
    bk = BOOKING.get(pl["label"])
    if bk:
        pl["booking"] = bk

payload = {
    "places": places,
    "visits": visits,
    "flights": FLIGHTS,
    "route": ROUTE,
    "transfers": TRANSFERS,
    "days": [{"n": d, "date": DAY_DATES[d],
              "note": DAY_NOTES.get(d, "") + (" · 🏪 " + KONBINI[d] if d in KONBINI else "")}
             for d in DAYS],
    "categories": [{"key": k, **v} for k, v in CAT_META.items()],
    "cityColors": CITY_COLOR,
    # one representative point per city, for the weather sync
    "weatherSpots": [
        {"city": "Tokyo",       "lat": 35.7110, "lng": 139.7966, "days": [1, 7, 8, 9, 10, 11]},
        {"city": "Kawaguchiko", "lat": 35.5006, "lng": 138.7597, "days": [2]},
        {"city": "Kyoto",       "lat": 34.9855, "lng": 135.7588, "days": [3, 4]},
        {"city": "Nagoya",      "lat": 35.1709, "lng": 136.8815, "days": [5, 6]},
    ],
    "today": TODAY,
    "labels": [{"n": n, "lat": la, "lng": ln, "z": z, "trip": t} for n, la, ln, z, t in PLACE_LABELS],
    "wxBaked": WX_BAKED,
    "kzSpots": KZ_SPOTS,
    "tripStart": "2026-10-17",
    "tripEnd": "2026-10-27",
}

HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<title>Япония за 11 дней</title>
<style>__LEAFLET_CSS__</style>
<style>
  :root {
    --bg: #ffffff;
    --surface: rgba(255,255,255,.97);
    --text: #14161a;
    --muted: #64707d;
    --line: #e4e8ec;
    --chip: #f1f3f6;
    --chip-on: #14161a;
    --chip-on-text: #ffffff;
    --shadow: 0 6px 24px rgba(15,23,42,.16);
    --warn-bg: #fff0d4; --warn-fg: #9a5b00;
    --kz-bg: #eef7f1; --kz-line: #cbe4d6; --kz-fg: #17663f;
    --radius: 14px;
    --safe-t: env(safe-area-inset-top, 0px);
    --safe-b: env(safe-area-inset-bottom, 0px);
  }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) {
      --bg: #0e1116; --surface: rgba(20,24,31,.97); --text: #eef1f5;
      --muted: #97a3b2; --line: #262d38; --chip: #1c222c;
      --chip-on: #eef1f5; --chip-on-text: #11151b;
      --shadow: 0 6px 24px rgba(0,0,0,.5);
      --warn-bg: #4a3512; --warn-fg: #ffd08a;
      --kz-bg: #10201a; --kz-line: #204034; --kz-fg: #7fd3a6;
    }
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body { height: 100%; margin: 0; background: var(--bg); color: var(--text);
    font: 15px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    -webkit-text-size-adjust: 100%; overscroll-behavior: none; }
  #map { position: absolute; inset: 0; background: var(--bg); }

  /* ---------- top bar ---------- */
  .topbar { position: fixed; top: calc(8px + var(--safe-t)); left: 8px; right: 8px; z-index: 1000;
    display: flex; gap: 8px; align-items: center; padding: 8px 10px;
    background: var(--surface); border: 1px solid var(--line);
    border-radius: var(--radius); box-shadow: var(--shadow);
    backdrop-filter: saturate(160%) blur(12px); }
  .topbar .title { flex: 1; min-width: 0; font-size: 14px; font-weight: 650; letter-spacing: -.01em;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .btn { border: 0; border-radius: 10px; padding: 8px 12px; font-size: 13px; font-weight: 600;
    background: var(--chip); color: var(--text); cursor: pointer; white-space: nowrap; }
  .btn:active { transform: scale(.97); }
  .btn.on { background: var(--chip-on); color: var(--chip-on-text); }
  @media (max-width: 560px) { .btn .lbl { display: none; } .btn { padding: 8px 10px; font-size: 15px; } }

  /* ---------- filter rail ---------- */
  .rail { position: fixed; left: 0; right: 0; z-index: 999;
    top: calc(64px + var(--safe-t)); padding: 0 8px;
    display: flex; flex-direction: column; gap: 6px; pointer-events: none; }
  .scroller { display: flex; gap: 6px; overflow-x: auto; padding: 2px 0;
    scrollbar-width: none; pointer-events: auto; }
  .scroller::-webkit-scrollbar { display: none; }
  .chip { flex: 0 0 auto; border: 1px solid var(--line); border-radius: 999px;
    padding: 6px 11px; font-size: 12.5px; font-weight: 600; background: var(--surface);
    color: var(--text); cursor: pointer; box-shadow: 0 2px 8px rgba(15,23,42,.08); }
  .chip.on { background: var(--chip-on); color: var(--chip-on-text); border-color: var(--chip-on); }
  .chip.off { opacity: .45; }

  /* ---------- itinerary sheet ---------- */
  .sheet { position: fixed; left: 8px; right: 8px; bottom: calc(26px + var(--safe-b)); z-index: 1001;
    max-height: min(52vh, 500px); overflow: auto; -webkit-overflow-scrolling: touch;
    background: var(--surface); border: 1px solid var(--line); border-radius: 18px;
    box-shadow: var(--shadow); padding: 14px 14px 10px; display: none;
    backdrop-filter: saturate(160%) blur(12px); }
  .sheet.open { display: block; }
  .sheet h2 { margin: 0 0 2px; font-size: 15px; font-weight: 700; letter-spacing: -.01em; }
  .sheet .sub { color: var(--muted); font-size: 12.5px; margin-bottom: 10px; }
  .day-block { border-top: 1px solid var(--line); padding: 10px 0 2px; }
  .day-block:first-of-type { border-top: 0; }
  .day-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px; }
  .day-head b { font-size: 13.5px; white-space: nowrap; }
  .day-head span { color: var(--muted); font-size: 12px; }
  .stop-row { display: flex; gap: 9px; align-items: flex-start; width: 100%;
    background: none; border: 0; padding: 6px 4px; border-radius: 9px;
    color: var(--text); text-align: left; font: inherit; cursor: pointer; }
  .stop-row:hover, .stop-row:focus-visible { background: var(--chip); outline: none; }
  .stop-row .dot { flex: 0 0 auto; width: 22px; height: 22px; border-radius: 50%;
    display: grid; place-items: center; font-size: 11px; margin-top: 1px; }
  .stop-row .nm { font-size: 13.5px; font-weight: 600; }
  .stop-row .mt { color: var(--muted); font-size: 12px; }
  .art-tag { font-size: 11px; }
  .bk-tag { font-size: 10.5px; padding: 1px 5px; border-radius: 5px; margin-left: 2px;
    background: var(--warn-bg); color: var(--warn-fg); font-weight: 700; }

  /* ---------- booking ---------- */
  .bk-item { border-top: 1px solid var(--line); padding: 10px 0; }
  .bk-item:first-of-type { border-top: 0; }
  .bk-head { display: flex; gap: 7px; align-items: baseline; }
  .bk-head .nm { font-size: 13.5px; font-weight: 650; }
  .bk-lvl { font-size: 10.5px; font-weight: 700; padding: 1.5px 6px; border-radius: 6px; white-space: nowrap; }
  .bk-lvl.must { background: var(--warn-bg); color: var(--warn-fg); }
  .bk-lvl.advise { background: var(--chip); color: var(--muted); }
  .bk-lvl.done { background: var(--kz-bg); color: var(--kz-fg); }
  .bk-lvl.info { background: transparent; color: var(--muted); border: 1px solid var(--line); }
  .bk-when { font-size: 12.5px; margin: 3px 0 0; }
  .bk-note { font-size: 12px; color: var(--muted); margin: 3px 0 0; }
  .bk-due { font-size: 11.5px; font-weight: 700; margin-top: 4px; }
  .bk-due.soon { color: var(--warn-fg); }
  .bk-due.past { color: var(--muted); font-weight: 600; }
  .bk-item a { color: inherit; font-size: 12px; }

  /* ---------- weather ---------- */
  .wx { display: flex; gap: 6px; overflow-x: auto; padding: 2px 0 6px; scrollbar-width: none; }
  .wx::-webkit-scrollbar { display: none; }
  .wx-day { flex: 0 0 auto; min-width: 62px; text-align: center; padding: 6px 7px;
    border: 1px solid var(--line); border-radius: 10px; background: var(--chip); }
  .wx-day .d { font-size: 10.5px; color: var(--muted); font-weight: 600; }
  .wx-day .ic { font-size: 17px; line-height: 1.25; }
  .wx-day .t { font-size: 12px; font-weight: 700; }
  .wx-day .t small { font-weight: 600; color: var(--muted); }
  .wx-note { font-size: 11.5px; color: var(--muted); margin: 0 0 8px; }
  .wx-inline { font-size: 12px; color: var(--muted); margin-left: 6px; white-space: nowrap; }

  /* ---------- legend ---------- */
  .legend { position: fixed; left: 8px; bottom: calc(26px + var(--safe-b)); z-index: 1000;
    width: min(330px, calc(100vw - 16px)); max-height: 54vh; overflow: auto;
    background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
    box-shadow: var(--shadow); padding: 12px 13px; display: none; font-size: 12.5px;
    backdrop-filter: saturate(160%) blur(12px); }
  .legend.open { display: block; }
  @media (min-width: 900px) {
    .sheet { left: 12px; right: auto; width: 392px; top: calc(142px + var(--safe-t));
      bottom: 14px; max-height: none; }
    #booking { left: 12px; right: auto; width: 392px; }
    .legend { left: auto; right: 12px; bottom: 14px; width: 352px; max-height: calc(100vh - 170px); }
    /* keep Leaflet's own controls out from under whichever panel is open */
    body.pl-left .leaflet-bottom.leaflet-left { margin-left: 408px; }
    body.pl-right .leaflet-bottom.leaflet-right { margin-right: 372px; }
  }
  .legend h3 { margin: 0 0 6px; font-size: 13px; }
  .legend .row { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-bottom: 8px; color: var(--muted); }
  .legend .row span { display: inline-flex; align-items: center; gap: 5px; }
  .legend .sw { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
  .legend hr { border: 0; border-top: 1px solid var(--line); margin: 9px 0; }
  .legend dl { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: 3px 10px; color: var(--muted); }
  .legend dt { font-weight: 600; color: var(--text); white-space: nowrap; }
  .legend dd { margin: 0; }
  .legend details.tip { border-top: 1px solid var(--line); padding: 7px 0; }
  .legend details.tip summary { cursor: pointer; font-weight: 650; color: var(--text); }
  .legend details.tip ul { margin: 6px 0 2px; padding-left: 16px; color: var(--muted);
    display: flex; flex-direction: column; gap: 5px; line-height: 1.4; }
  .legend details.tip b { color: var(--text); }

  /* ---------- markers ---------- */
  .pin { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%;
    border: 2px solid #fff; font-size: 14px; line-height: 1;
    box-shadow: 0 2px 6px rgba(15,23,42,.35); transition: transform .12s ease; }
  .pin.art { border-color: #ffd43b; box-shadow: 0 0 0 2px rgba(255,212,59,.55), 0 2px 6px rgba(15,23,42,.35); }
  .pin:hover { transform: scale(1.14); }
  .pin-wrap { background: none !important; border: 0 !important; overflow: visible; }
  .pin { position: relative; }
  .pin .bk { position: absolute; top: -7px; right: -8px; font-size: 10px; line-height: 1;
    background: var(--warn-bg); color: var(--warn-fg); border-radius: 6px; padding: 1.5px 3px;
    border: 1px solid #fff; font-style: normal; }
  .cl { display: grid; place-items: center; width: 100%; height: 100%; border-radius: 50%;
    border: 2px solid #fff; color: #fff; font-weight: 700; line-height: 1;
    box-shadow: 0 3px 10px rgba(15,23,42,.32); cursor: pointer;
    background: var(--cl-bg, #475569); transition: transform .12s ease; }
  .cl:hover { transform: scale(1.08); }
  .cl b { font-size: 14px; }
  .cl i { font-style: normal; font-size: 9px; margin-top: 1px; opacity: .9; }
  .cl.art { border-color: #ffd43b; box-shadow: 0 0 0 2px rgba(255,212,59,.5), 0 3px 10px rgba(15,23,42,.32); }
  .cl-wrap { background: none !important; border: 0 !important; }
  .tlabel { background: var(--surface); border: 1px solid var(--line); border-radius: 8px;
    padding: 3px 7px; font-size: 11px; font-weight: 600; color: var(--text);
    white-space: nowrap; box-shadow: 0 2px 6px rgba(15,23,42,.18); }
  .tlabel-wrap { background: none !important; border: 0 !important; }

  /* ---------- popup ---------- */
  .leaflet-popup-content-wrapper { border-radius: 14px; background: var(--surface); color: var(--text); }
  .leaflet-popup-tip { background: var(--surface); }
  .leaflet-popup-content { margin: 12px 13px; font-size: 13px; line-height: 1.45; width: 260px !important; }
  .pop h4 { margin: 0 0 1px; font-size: 14.5px; letter-spacing: -.01em; }
  .pop .meta { color: var(--muted); font-size: 12px; margin-bottom: 8px; }
  .pop img { width: 100%; border-radius: 10px; display: block; margin: 0 0 8px;
    background: var(--chip); aspect-ratio: 1 / 1; object-fit: cover; }
  .pop .cap { color: var(--muted); font-size: 11px; margin: -5px 0 8px; }
  .pop .notes { margin: 0; }
  .pop .sched { display: flex; flex-direction: column; gap: 5px; }
  .pop .vrow { display: flex; gap: 8px; align-items: baseline; }
  .pop .vrow b { flex: 0 0 auto; font-size: 11.5px; padding: 1px 6px; border-radius: 6px;
    background: var(--chip); color: var(--text); }
  .pop .vrow span { font-size: 12.5px; color: var(--muted); }
  .pop .links { display: flex; gap: 6px; margin: 9px 0 0; }
  .pop .links a { flex: 1; text-align: center; text-decoration: none; font-size: 12px; font-weight: 650;
    padding: 7px 6px; border-radius: 9px; background: var(--chip); color: var(--text); }
  .pop .bkbox { margin: 9px 0 0; padding: 8px 9px; border-radius: 9px;
    background: var(--warn-bg); color: var(--warn-fg); font-size: 12px; }
  .pop .bkbox b { display: block; font-size: 12px; margin-bottom: 2px; }
  .pop .bkbox span { display: block; opacity: .85; margin-top: 3px; font-size: 11.5px; }
  .pop .wxline { margin: 8px 0 0; font-size: 12px; color: var(--muted); }

  /* ---------- Kazakh-Japanese layer ---------- */
  .pop .kzbox { margin: 9px 0 0; padding: 8px 9px; border-radius: 10px;
    background: var(--kz-bg); border: 1px solid var(--kz-line); }
  .pop .kzhead { display: flex; align-items: center; gap: 5px; margin-bottom: 7px;
    font-size: 11.5px; font-weight: 750; color: var(--kz-fg); letter-spacing: .01em; }
  .pop .kzhead i { font-style: normal; font-size: 10px; font-weight: 700; padding: 1px 6px;
    border-radius: 999px; background: var(--kz-fg); color: var(--kz-bg); }
  .pop .kzi { margin: 0 0 8px; }
  .pop .kzi:last-child, .pop .kzrest .kzi:last-child { margin-bottom: 0; }
  .pop .kzi b { display: block; font-size: 12px; font-weight: 700; margin-bottom: 2px; }
  .pop .kzi span { display: block; font-size: 11.5px; line-height: 1.5; color: var(--muted); }
  .pop .kzrest { display: none; }
  .pop .kzbox.open .kzrest { display: block; }
  .pop .kzbox.open .kzmore { display: none; }
  .pop .kzmore, .pop .kzbtn { border: 0; cursor: pointer; font: inherit; font-weight: 650;
    border-radius: 8px; background: var(--chip); color: var(--text); }
  .pop .kzmore { width: 100%; margin-top: 2px; font-size: 11.5px; padding: 7px 6px; }
  .pop .kzbtn { margin-top: 6px; font-size: 11.5px; padding: 5px 11px; }
  .pop .kzg { border: 1px dashed var(--kz-line); border-radius: 9px;
    padding: 7px 9px; margin: 0 0 8px; }
  .pop .kzg > b { display: block; font-size: 10px; font-weight: 750; letter-spacing: .05em;
    text-transform: uppercase; color: var(--kz-fg); margin-bottom: 3px; }
  .pop .kzg p { margin: 0; font-size: 11.5px; line-height: 1.5; color: var(--text); }
  .pop .kzab { display: block; margin-top: 3px; font-size: 11.5px; color: var(--muted); }
  .pop .kzrev { display: none; margin-top: 6px; padding-top: 6px; font-size: 11.5px;
    line-height: 1.5; color: var(--text); border-top: 1px solid var(--kz-line); }
  .pop .kzg.open .kzrev { display: block; }
  .pop .kzg.open .kzbtn { display: none; }
  .pop .kzbtn.kzdone { background: transparent; border: 1px solid var(--kz-line);
    color: var(--kz-fg); margin-left: 6px; }
  .pop .kzbtn.kzdone.on { background: var(--kz-fg); color: var(--kz-bg); border-color: var(--kz-fg); }
  .pop .kzg.open .kzbtn.kzdone { display: inline-block; margin-left: 0; }

  /* ---------- task list in the info panel ---------- */
  .legend .bingo-n { font-size: 11px; font-weight: 700; padding: 1px 7px; border-radius: 999px;
    background: var(--chip); color: var(--muted); margin-left: 5px; }
  .legend .bingo-n.full { background: var(--kz-fg); color: var(--kz-bg); }
  .legend .bingo-row { display: flex; align-items: flex-start; gap: 4px; }
  .legend .bingo-tick { flex: 1; display: flex; gap: 8px; align-items: flex-start; text-align: left;
    border: 0; background: none; font: inherit; color: var(--text); cursor: pointer;
    padding: 7px 5px; border-radius: 8px; min-height: 44px; }
  .legend .bingo-tick:hover { background: var(--chip); }
  .legend .bingo-tick .box { flex: 0 0 auto; width: 18px; height: 18px; margin-top: 1px;
    border-radius: 5px; border: 1.5px solid var(--line); display: inline-block; }
  .legend .bingo-row.done .box { background: var(--kz-fg); border-color: var(--kz-fg); }
  .legend .bingo-row.done .box::after { content: "✓"; display: block; text-align: center;
    line-height: 15px; font-size: 12px; font-weight: 800; color: var(--kz-bg); }
  .legend .bingo-tick span { font-size: 12px; line-height: 1.4; color: var(--muted); }
  .legend .bingo-tick span b { display: block; font-size: 11.5px; font-weight: 650; color: var(--text); }
  .legend .bingo-row.done .bingo-tick span { opacity: .45; text-decoration: line-through; }
  .legend .bingo-go { flex: 0 0 auto; width: 34px; min-height: 44px; border: 0; cursor: pointer;
    background: none; color: var(--muted); font: inherit; font-size: 15px; border-radius: 8px; }
  .legend .bingo-go:hover { background: var(--chip); color: var(--text); }
  .legend .bingo-note { font-size: 11.5px; color: var(--warn-fg); background: var(--warn-bg);
    border-radius: 8px; padding: 6px 8px; margin-top: 6px; }

  /* ---------- place card as a panel ----------
     Same markup as the popup, more room to read it. Under 900px it becomes a nearly
     full-height sheet, which is also the answer to "make the blocks bigger" on a phone;
     from 900px it is a right-hand column and the map keeps the left. */
  .cardpanel { position: fixed; z-index: 1002; display: none; overflow: auto;
    -webkit-overflow-scrolling: touch; padding: 12px 14px 16px;
    left: 8px; right: 8px; top: calc(140px + var(--safe-t)); bottom: calc(26px + var(--safe-b));
    background: var(--surface); border: 1px solid var(--line); border-radius: 18px;
    box-shadow: var(--shadow); backdrop-filter: saturate(160%) blur(12px); }
  .cardpanel.open { display: block; }
  .cardpanel .cardclose { float: right; margin: -2px -4px 4px 10px; border: 0; cursor: pointer;
    width: 36px; height: 36px; border-radius: 11px; background: var(--chip);
    color: var(--text); font: inherit; font-size: 16px; }
  .cardpanel .pop { font-size: 13.5px; line-height: 1.5; }
  .cardpanel .pop h4 { font-size: 19px; margin-bottom: 2px; }
  .cardpanel .pop .meta { font-size: 13px; margin-bottom: 10px; }
  .cardpanel .pop img { aspect-ratio: 16 / 10; max-height: 320px; }
  .cardpanel .pop .vrow span { font-size: 13.5px; }
  .cardpanel .pop .wxline, .cardpanel .pop .bkbox { font-size: 13px; }
  .cardpanel .pop .links a { font-size: 13.5px; padding: 11px 6px; }
  .cardpanel .pop .kzi b { font-size: 14px; }
  .cardpanel .pop .kzi span, .cardpanel .pop .kzg p,
  .cardpanel .pop .kzab, .cardpanel .pop .kzrev { font-size: 13px; }
  .cardpanel .pop .kzbtn { font-size: 13px; padding: 7px 13px; }
  @media (min-width: 900px) {
    .cardpanel { left: auto; right: 12px; top: calc(142px + var(--safe-t)); bottom: 14px;
      width: clamp(360px, 36vw, 560px); }
  }

  /* ---------- flights ---------- */
  .lbl { font-size: 11px; font-weight: 600; color: #6b7785; white-space: nowrap;
    text-shadow: 0 0 3px var(--bg), 0 0 3px var(--bg), 0 0 5px var(--bg);
    transform: translate(-50%, -50%); pointer-events: none; }
  .lbl.trip { font-size: 12.5px; font-weight: 750; color: var(--text); letter-spacing: .01em; }
  .lbl-wrap { background: none !important; border: 0 !important; }
  .fl { background: var(--surface); border: 1px solid var(--line); border-radius: 999px;
    padding: 3px 9px; font-size: 11px; font-weight: 650; color: var(--text);
    white-space: nowrap; box-shadow: 0 2px 6px rgba(15,23,42,.18); }
  .fl-wrap { background: none !important; border: 0 !important; }
  .leaflet-container { font: inherit; }
  .leaflet-control-zoom { margin-bottom: 26px !important; }
  .leaflet-control-scale { margin-bottom: 2px !important; }
  .leaflet-control-attribution { font-size: 10px; }
  .pin.dim { opacity: .25; pointer-events: none; }
</style>
<style>__TODAY_CSS__</style>
</head>
<body>
<div id="map"></div>

<div class="topbar">
  <div class="title" id="tripTitle">🇯🇵 Япония за 11 дней</div>
  <button class="btn" id="btnToday" type="button">🗓<span class="lbl"> Сегодня</span></button>
  <button class="btn" id="btnRoute" type="button">🧭<span class="lbl"> Маршрут</span></button>
  <button class="btn" id="btnDays" type="button">📋<span class="lbl"> Дни</span></button>
  <button class="btn" id="btnBook" type="button">🎫<span class="lbl"> Брони</span></button>
  <button class="btn" id="btnInfo" type="button">ℹ️<span class="lbl"> Инфо</span></button>
  <button class="btn" id="btnCard" type="button" title="Карточки места в боковой панели"
    >◧<span class="lbl"> Панель</span></button>
</div>

<aside class="cardpanel" id="cardPanel"></aside>

<div id="today" role="region" aria-label="Сегодня"><div class="td-wrap" id="todayBody"></div></div>
<div class="td-ticket" id="tdTicket" hidden role="dialog" aria-label="Билет">
  <div class="hold"></div><p id="tdTicketCap"></p>
  <button class="td-btn" type="button" id="tdTicketClose">Закрыть</button>
</div>

<div class="rail">
  <div class="scroller" id="dayChips"></div>
  <div class="scroller" id="catChips"></div>
</div>

<div class="sheet" id="sheet"></div>
<div class="sheet" id="booking"></div>

<div class="legend" id="legend">
  <h3>🎯 Задания «Степной след»<span class="bingo-n" id="bingoCount">0 / 0</span></h3>
  <div id="bingoList"></div>
  <hr>
  <h3>Базы проживания</h3>
  <div class="row" style="color:var(--text)">✈️ Ханэда → 🏨 Готанда (1 ночь) → 🗻 Кавагутико (день) → 🚌 Мисима → 🏨 Киото (2 ночи) → 🏨 Нагоя (2 ночи, 21-го финалы дзюдо) → 🏨 Токио (5 ночей) → ✈️ Ханэда</div>
  <hr>
  <h3>Цвет метки — город</h3>
  <div class="row" id="legendCities"></div>
  <h3>Иконка — категория</h3>
  <div class="row" id="legendCats"></div>
  <div class="row">🎨 жёлтая обводка — есть Ghibli-версия места</div>
  <div class="row">🎫 значок на метке — место требует брони, детали в панели «Брони»</div>
  <div class="row">✈️ дуга из Ханэды — прилёт и вылет (время из шаблона, свои рейсы — в «Сегодня → ⚙»)</div>
  <div class="row">В каждом попапе есть ссылки «Google Maps» (адрес места) и «Маршрут» (проезд на транспорте)</div>
  <hr>
  <h3>Ключевые переезды</h3>
  <dl>
    <dt>Готанда → Синдзюку</dt><dd>≈15 мин, JR Яманотэ</dd>
    <dt>Синдзюку → Кавагутико</dt><dd>≈1 ч 45 мин, автобус Keio</dd>
    <dt>Кавагутико → Мисима</dt><dd>≈1 ч 40 мин, автобус Fujikyu</dd>
    <dt>Мисима → Киото</dt><dd>≈2 ч, синкансэн</dd>
    <dt>Киото → Сага-Арасияма</dt><dd>≈15 мин, JR Сагано</dd>
    <dt>Киото → Нагоя</dt><dd>34 мин, Nozomi</dd>
    <dt>Нагоя → Aichi Budokan</dt><dd>12 мин Aonami + 15 мин пешком</dd>
    <dt>Нагоя → Токио</dt><dd>≈1 ч 40 мин, Nozomi</dd>
    <dt>Уэно → Майхама (Disney)</dt><dd>≈35 мин, JR Keiyo</dd>
    <dt>Асакуса → Ханэда</dt><dd>≈40 мин, Keikyu</dd>
  </dl>
  <hr>
  <h3>Лайфхаки</h3>
  <details class="tip" open><summary>🇰🇿 Из опыта казахстанцев (podeshevle.kz)</summary>
    <ul>
      <li><b>APA Hotel</b> — сеть среднего сегмента, есть почти везде, часто с завтраком. Кровать в номере «Double» узкая (около 1,2–1,4 м, в статье пишут и ~1 м) — паре лучше номер побольше или twin. Проверить при брони Киото и Синдзюку.</li>
      <li><b>Bic Camera</b> (8–9 этажей): техника, часы, оптика, косметика, игрушки, продукты, дополнительный чемодан. Купон Tourist Privilege (до 10%) + tax-free (10%) + кешбэк по карте — в сумме до ~26%. Пример из статьи: Garmin за ~190 000 ₸ вместо ~360 000 ₸ дома. Оправы — ещё Owndays. По плану — вечер 25-го у отеля в Синдзюку.</li>
      <li><b>Карта Freedom</b> — до 6% кешбэка за покупки за границей (проверить условия). Apple Pay / Google Pay принимают почти везде, но в маленьких местах нужна наличка.</li>
      <li><b>Наличных нужно немного:</b> в статье на всю поездку хватило $300. Остальное — картой и снятием в 7-Bank в любом 7-Eleven.</li>
      <li><b>Усталость от 20–30 тыс. шагов:</b> в статье советуют Q&amp;P Kowa Alpha Drink (7-Eleven или аптека) — витаминный напиток с экстрактами трав, не классический энергетик. Перед покупкой проверить состав: на аллергию и для халяля — アルコール (алкоголь) и ゼラチン (желатин) в списке.</li>
      <li><b>Такси — приложение GO</b>, работает с казахстанским номером. Нужно, например, на рассвет к Тюрэйто.</li>
      <li><b>Интернет:</b> eSIM MobiMatter или Airalo. Если не ловит — включить роуминг для eSIM в настройках.</li>
      <li><b>Uniqlo:</b> размеры одинаковые во всех магазинах — подошёл L, берите L. Heattech ~6 000 ₸, самый тонкий — для города, потолще — для гор (у Фудзи ночью ~8°C).</li>
      <li><b>Чемодан «матрёшкой»:</b> ручную кладь положить в большой чемодан — обратно он заполнится покупками.</li>
      <li>Фрукты и овощи с собой не везти — большие штрафы. Громко в метро не говорят, чаевых нет. На эскалаторах в Токио стоят слева.</li>
    </ul>
  </details>
  <details class="tip"><summary>💴 Деньги и обмен</summary>
    <ul>
      <li><b>Меняем только в World Currency Shop и только если курс не ниже ¥155 за $1.</b> Иначе не меняем, а снимаем иены с карты.</li>
      <li>Отделения работают по будням: Киото (MUFG у метро Сидзё, пн–пт 10–17) — по плану 20 окт; Нагоя (Хирокодзи, пн–пт 10–18); Токио: Синдзюку-Нисигути и Сибуя (пн–пт 10–18), Гиндза в Matsuya (11–18). В выходные почти всё закрыто.</li>
      <li>Банкоматы 7-Bank в любом 7-Eleven и Japan Post принимают Visa и Mastercard 24/7. Снимать реже и крупнее — комиссия берётся за каждое снятие.</li>
      <li>Если банкомат или терминал предлагает «оплатить в вашей валюте» — отказываться и платить в иенах. Их курс заметно хуже.</li>
      <li>Наличные нужны для храмов, маленьких винтажных лавок, рынков и Costco. Предупредить свой банк о поездке, иначе карту могут заблокировать.</li>
    </ul>
  </details>
  <details class="tip"><summary>🚃 Suica и проезд</summary>
    <ul>
      <li><b>iPhone:</b> Wallet → «+» → проездная карта → Suica. Пополнять через Apple Pay. Работает с Visa и Mastercard, но казахстанскую карту стоит проверить до вылета.</li>
      <li><b>Android или если Wallet не принял карту:</b> пластиковая Welcome Suica для туристов. Продаётся в Ханэде, в терминале 3, в JR East Travel Service Center и в автоматах, без депозита, действует 28 дней. Остаток не возвращают — потратить в конбини.</li>
      <li>Suica работает в Киото и Нагое наравне с местными ICOCA и manaca, а ещё в конбини, автоматах и камерах хранения.</li>
      <li>Синкансэн — в приложении Smart EX с зарубежной картой. JR Pass на этом маршруте не окупается: отдельные билеты выходят около ¥35 000, пасс стоит ~¥50 000.</li>
    </ul>
  </details>
  <details class="tip"><summary>🧾 Tax-free — законные приёмы</summary>
    <ul>
      <li>Порог — ¥5 000 без налога в одном магазине за один день. Покупки за день в одном магазине можно собрать в один чек на кассе tax-free. Паспорт нужен оригинал.</li>
      <li>Еда и косметика запечатываются в пакет, открывать его до вылета нельзя. Одежду и технику можно носить сразу.</li>
      <li>Крупные покупки собрать на последние дни (Гиндза 27 окт), чтобы не возить их по стране.</li>
      <li>На вылете покупки могут попросить показать на таможне. Держать их в ручной клади или сверху в чемодане.</li>
      <li>Правила tax-free меняются с ноября 2026 года. До 27 октября действует нынешняя система со скидкой прямо на кассе — проверить перед поездкой.</li>
    </ul>
  </details>
  <details class="tip"><summary>🧳 Чемоданы между городами</summary>
    <ul>
      <li><b>18 окт утром чемоданы едут из Готанды в Киото сами</b> — курьерской доставкой (такъюбин, Yamato или Sagawa). Отдать на ресепшене, доставка на следующий день, 19-го — к вашему заселению. Около ¥2 500–3 500 за чемодан в зависимости от размера (проверить). Лимит — 3 измерения в сумме до 200 см, до 30 кг.</li>
      <li>Если ресепшен не отправляет — любой 7-Eleven принимает Yamato (такъюбин) на кассе, бланк заполнят вместе с вами. Адрес получателя — отель в Киото, латиницей и японскими иероглифами (скопировать с сайта отеля), дата заезда и ваше имя как в брони.</li>
      <li>Заранее написать отелю в Киото: «багаж придёт 19-го до нашего заселения» — почти все принимают.</li>
      <li>С собой на 2 дня у Фудзи — рюкзак: одежда, зарядки, лекарства, паспорт. В рёкане дадут юкату.</li>
      <li>Камеры хранения на вокзалах (в т. ч. в Синдзюку) — только если вечером вернуться; нам не подходит. 24 окт то же самое: утром чемоданы из Киото курьером в токийский отель, приедут 25-го.</li>
    </ul>
  </details>
  <details class="tip"><summary>🚌 Автобус Busta Синдзюку → Кавагутико</summary>
    <ul>
      <li><b>Бронь:</b> highwaybus.com (есть английская версия) → откуда Shinjuku (Busta) → куда Kawaguchiko Station → 18 окт → рейс 6:45 (✅ уже забронирован) → схема салона → место → оплата картой. Билет приходит на почту, показать водителю с телефона. Продажа открывается за месяц — уже идёт.</li>
      <li><b>Места:</b> брать слева по ходу, у окна. Фудзи появляется слева на подъезде к Фудзиёсиде. Два места рядом — в одном ряду слева.</li>
      <li>Busta — 4-й этаж прямо над New South Gate (新南改札) JR Синдзюку. Из Готанды: подъём 5:15, выход 5:55, Яманотэ ~15 мин, на Busta к 6:30, автобус 6:45. Выход на посадку указан на табло.</li>
      <li>Наш рейс 06:45 идёт до Mt. Fuji 5th Station, поэтому Кавагутико для него не конечная. Выходить на остановке «Kawaguchiko Sta.» (河口湖駅); перед ней будет Fuji-Q Highland — там не выходить. Билет показать водителю при посадке и выходе.</li>
      <li>В воскресенье утром на трассе Тюо бывают пробки — поэтому первый рейс. Туалет в автобусе обычно есть, но лучше сходить на Busta.</li>
      <li>Если все места проданы: поезд Fuji Excursion из Синдзюку (бронь в JR East eki-net), ~2 часа, без пересадок.</li>
    </ul>
  </details>
  <details class="tip"><summary>🗻 Как поймать Фудзи</summary>
    <ul>
      <li><b>Утро — главное.</b> До 10:00 шансы увидеть гору намного выше, к обеду её закрывают облака. В октябре гора видна целиком примерно в каждый третий день — это ориентир, а не статистика.</li>
      <li>За 3–5 дней смотреть облачность на tenki.jp или Windy и живые камеры Кавагутико. У Фудзи вы только утром 18-го — поэтому первый автобус. Если обещают сплошные тучи, всё равно ехать: гора часто открывается в разрывах, а Тюрэйто и Хоммати красивы и так.</li>
      <li>Запасные шансы: 18-го из синкансэна после Мисимы (место E справа), бесплатная смотровая мэрии Токио у отеля в Синдзюку утром 25–26-го (часы проверить), Shibuya Sky 25-го — солнце садится примерно в 6° правее Фудзи, гора встаёт силуэтом в закате.</li>
      <li>Первый снег на вершине обычно ложится к концу октября — есть шанс на белую шапку.</li>
    </ul>
  </details>
  <details class="tip"><summary>🏷 Скидки и брони</summary>
    <ul>
      <li>У Don Quijote, Bic Camera, Yodobashi и Matsumoto Kiyoshi есть купоны для туристов, обычно 5–10% поверх tax-free. Их показывают на кассе с экрана телефона — проверить актуальные.</li>
      <li>Uniqlo и MUJI — в будний день к открытию. В Uniqlo стоит заглянуть на полку «limited offer»: там цены снижены на неделю.</li>
      <li>Tokyo Disney — только на официальном сайте, билеты на дату; Klook/KKday иногда дешевле для прочих билетов (проверить условия отмены). Shibuya Sky — только на официальном сайте, так дешевле, чем у касс.</li>
      <li>Отели бронировать с бесплатной отменой, а за 1–2 недели проверить цену заново и перебронировать, если стало дешевле.</li>
    </ul>
  </details>
  <details class="tip"><summary>🛒 Costco</summary>
    <ul>
      <li>Вход только для членов. Членство Gold Star — ¥5 280 в год, оформляется на месте с паспортом (проверить, требуют ли японский адрес).</li>
      <li><b>Взнос возвращают полностью при отказе от членства.</b> Купить, сделать покупки, отказаться — и вернуть взнос. Повторно оформиться можно только через год.</li>
      <li>Член клуба проводит с собой до двух взрослых без карты, поэтому членство нужно одно на пару. Семейная карта бесплатная, но только для человека с тем же адресом.</li>
      <li>Членство Costco из другой страны действует и в Японии. Чужую карту одолжить нельзя: на ней фото, на входе сверяют.</li>
      <li>Платить только наличными иенами или Mastercard, Visa не принимают.</li>
    </ul>
  </details>
</div>

<script>__LEAFLET_JS__</script>
<script>
const DATA = __DATA__;

/* ---------- map ---------- */
// maxZoom/minZoom live on the map, not on the tile layer: the tile layer may never be
// added (blocked or offline) and markercluster refuses to work without a maxZoom.
const map = L.map('map', { zoomControl: false, preferCanvas: false, tap: true,
                           minZoom: 4, maxZoom: 19 })
  .setView([35.45, 136.8], 6);
/* ---------- base map ----------
   The built-in layer is vector coastline shipped inside this file, so the map draws
   with no network. Tiles are an upgrade: probed first, added only if they really load
   (sandboxed pages and offline phones never get them). */
const BASE_GEO = __BASEMAP__;
const landLayer = L.geoJSON(BASE_GEO, {
  interactive: false,
  style: { color: '#b9c4d0', weight: 1, fillColor: '#eef1f4', fillOpacity: 1 }
}).addTo(map);
map.attributionControl.addAttribution('Контуры: Natural Earth');

function paintSea() {
  const dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  document.getElementById('map').style.background = dark ? '#0b1016' : '#dfe8ef';
  landLayer.setStyle(dark
    ? { color: '#3a4653', fillColor: '#171d25' }
    : { color: '#b9c4d0', fillColor: '#eef1f4' });
}
paintSea();
window.matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', paintSea);

const tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
});
(function probeTiles() {
  const img = new Image();
  let settled = false;
  const give = ok => {
    if (settled) return;
    settled = true;
    if (!ok) return;                       // stay on the vector base
    tiles.addTo(map);
    tiles.once('load', () => {
      map.removeLayer(landLayer);
      map.removeLayer(labelLayer);          // tiles carry their own place names
      document.getElementById('map').style.background = '';
    });
  };
  img.onload = () => give(true);
  img.onerror = () => give(false);
  setTimeout(() => give(false), 4000);     // slow or blocked counts as absent
  img.src = 'https://a.tile.openstreetmap.org/5/28/12.png';
})();
L.control.scale({ imperial: false, position: 'bottomleft' }).addTo(map);
if (window.matchMedia('(min-width: 768px)').matches) L.control.zoom({ position: 'bottomright' }).addTo(map);

/* ---------- route ---------- */
const routeLine = L.polyline(DATA.route, {
  color: '#14161a', weight: 4, opacity: .55, dashArray: '1 7', lineCap: 'round'
}).addTo(map);

const transferLayer = L.layerGroup();   // shown only while the route view is on
DATA.transfers.forEach(t => {
  L.marker([t.lat, t.lng], {
    icon: L.divIcon({ className: 'tlabel-wrap', html: `<div class="tlabel">${t.label}</div>`,
                      iconSize: [null, null] }),
    interactive: true, keyboard: false
  }).bindPopup(`<div class="pop"><h4>Переезд</h4><p class="notes">${t.text}</p></div>`)
    .addTo(transferLayer);
});

/* ---------- markers (all visible by default) ---------- */
const esc = s => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

function popupHtml(p, all) {
  const doc = p.imgStyle === 'doc';
  const img = p.img
    ? `<img src="${esc(p.img)}" alt="${doc ? 'Документальный вид' : 'Ghibli-версия'}: ${esc(p.label)}" loading="lazy"
            onerror="this.style.display='none';this.nextElementSibling.style.display='none';">
       <div class="cap">${doc ? 'Документальный вид места' : '🎨 Ghibli-версия места'}</div>`
    : '';
  const rows = p.visits.map(v => `<div class="vrow"><b>Д${v.day}</b>
      <span>${esc(v.time)}${v.notes ? ' — ' + esc(v.notes) : ''}${v.overnight ? ' 🌙 ' + esc(v.overnight) : ''}</span>
    </div>`).join('');
  const bk = p.booking ? `<div class="bkbox">
      <b>${bkTitle(p.booking.level)}</b>${esc(p.booking.when)}
      <span>${esc(p.booking.note)}</span>
      ${p.booking.url ? `<span><a href="${esc(p.booking.url)}" target="_blank" rel="noopener">Официальный сайт ↗</a></span>` : ''}
    </div>` : '';
  const wx = wxLineFor(p);
  return `<div class="pop">
    <h4>${p.emoji} ${esc(p.label)}</h4>
    <div class="meta">${esc(p.city)} · ${esc(catLabel(p.category))}</div>
    ${img}
    <div class="sched">${rows}</div>
    ${wx}
    ${bk}
    ${kzHtml(p, all)}
    <div class="links">
      <a href="${gmapsPlace(p)}" target="_blank" rel="noopener">📍 Google Maps</a>
      <a href="${gmapsDir(p)}" target="_blank" rel="noopener">🧭 Маршрут</a>
    </div>
  </div>`;
}
/* ---------- Kazakh-Japanese layer ----------
   Facts carry an honesty level and are glyphed by it, so a joke can never read as
   history. Built with the popup, on open — never at load. */
const KZ_GLYPH = { fact: '✅', parallel: '🔗', joke: '😄', note: '⚠️' };

/* Ticked-off tasks live on this device only — there is no account and no sync, so
   each of the four keeps their own progress. Safari in private mode throws on every
   localStorage call, so the probe decides up front whether ticks will survive a
   reload; either way they keep working in memory for the current session. */
const KZ_DONE_KEY = 'japan2026.kzdone.v1';
const KZ_STORAGE_OK = (() => {
  try {
    localStorage.setItem('japan2026.probe', '1');
    localStorage.removeItem('japan2026.probe');
    return true;
  } catch (e) { return false; }
})();
let KZ_DONE = {};
function kzLoadDone() {
  try {
    const raw = localStorage.getItem(KZ_DONE_KEY);
    KZ_DONE = raw ? (JSON.parse(raw) || {}) : {};
  } catch (e) { KZ_DONE = {}; }
}
function kzSaveDone() {
  try { localStorage.setItem(KZ_DONE_KEY, JSON.stringify(KZ_DONE)); } catch (e) { /* private mode */ }
}
function kzToggleDone(id) {
  if (KZ_DONE[id]) delete KZ_DONE[id]; else KZ_DONE[id] = Date.now();
  kzSaveDone();
}
const KZ_GAME_TITLE = { tf: '🎲 Верю / не верю', order: '🎲 Что было раньше',
                        guess: '🎲 Угадай', spot: '📸 Задание на месте' };

function kzGame(g) {
  let body = '', reveal = '';
  if (g.type === 'tf') {
    body = `<p>${esc(g.q)}</p>`;
    reveal = (g.answer ? 'Правда. ' : 'Неправда. ') + g.reveal;
  } else if (g.type === 'order') {
    body = `<p>Что было раньше?</p><span class="kzab">A — ${esc(g.a)}</span>` +
           `<span class="kzab">B — ${esc(g.b)}</span>`;
    reveal = 'Раньше — ' + (g.answer === 'a' ? 'A. ' : 'B. ') + g.reveal;
  } else if (g.type === 'guess') {
    body = `<p>${esc(g.q)}</p>` +
           (g.options || []).map(o => `<span class="kzab">· ${esc(o)}</span>`).join('');
    reveal = 'Ответ: ' + (g.options || [])[g.answer] + '. ' + g.reveal;
  } else if (g.type === 'spot') {
    const on = !!KZ_DONE[g.id];
    body = `<p>${esc(g.task)}</p>
      <button class="kzbtn kzdone${on ? ' on' : ''}" type="button" data-kzdone="${esc(g.id)}"
        >${on ? '✓ Сделано' : 'Отметить'}</button>`;
    reveal = 'Чем закрывается: ' + g.proof;
  } else {
    return '';
  }
  return `<div class="kzg"><b>${esc(KZ_GAME_TITLE[g.type] || 'Игра')}</b>${body}
    <button class="kzbtn" type="button" data-kzrev>${g.type === 'spot' ? 'Что засчитывается' : 'Показать ответ'}</button>
    <div class="kzrev">${esc(reveal)}</div></div>`;
}

function kzItem(f) {
  if (f.game) return kzGame(f.game);
  return `<div class="kzi"><b>${KZ_GLYPH[f.level] || '•'} ${esc(f.title)}</b>
    <span>${esc(f.text)}</span></div>`;
}

function kzHtml(p, all) {
  const list = p.kz || [];
  if (!list.length) return '';
  // in the panel there is room, so nothing hides behind a button
  const head = (all ? list : list.slice(0, 2)).map(kzItem).join('');
  const rest = all ? [] : list.slice(2);
  const more = rest.length
    ? `<button class="kzmore" type="button" data-kzmore>Ещё ${rest.length} ${plural2(rest.length)} ↓</button>
       <div class="kzrest">${rest.map(kzItem).join('')}</div>`
    : '';
  return `<div class="kzbox">
    <div class="kzhead">🇰🇿 Степной след <i>${list.length}</i></div>
    ${head}${more}</div>`;
}

function plural2(n) {
  const a = n % 10, b = n % 100;
  if (a === 1 && b !== 11) return 'факт';
  if (a >= 2 && a <= 4 && (b < 12 || b > 14)) return 'факта';
  return 'фактов';
}

function kzSpotTasks() {
  const out = [];
  DATA.places.forEach((p, i) => (p.kz || []).forEach(f => {
    if (f.game && f.game.type === 'spot') out.push({ p, i, g: f.game });
  }));
  return out;
}

function renderBingo() {
  const list = document.getElementById('bingoList');
  const cnt = document.getElementById('bingoCount');
  if (!list || !cnt) return;
  const tasks = kzSpotTasks();
  const done = tasks.filter(t => KZ_DONE[t.g.id]).length;
  cnt.textContent = done + ' / ' + tasks.length;
  cnt.classList.toggle('full', tasks.length > 0 && done === tasks.length);
  list.innerHTML = tasks.map(t => `
    <div class="bingo-row${KZ_DONE[t.g.id] ? ' done' : ''}">
      <button class="bingo-tick" type="button" data-kzdone="${esc(t.g.id)}">
        <i class="box"></i><span><b>${esc(t.p.label)}</b>${esc(t.g.task)}</span></button>
      <button class="bingo-go" type="button" data-kzgo="${t.i}"
        aria-label="Показать на карте">→</button>
    </div>`).join('') +
    (KZ_STORAGE_OK ? '' :
      `<div class="bingo-note">Браузер не разрешает локальное хранилище — в приватном
        режиме Safari отметки живут только до перезагрузки.</div>`);
}

function catLabel(k) { return (DATA.categories.find(c => c.key === k) || {}).label || k; }
function bkTitle(l) {
  return l === 'must' ? '🎫 Нужна бронь · ' : l === 'advise' ? '🎫 Лучше забронировать · ' : 'ℹ️ ';
}

/* ---------- Google Maps ----------
   The point's own coordinates are the query, so Maps opens exactly this spot and
   shows its real address; where a Google place id is known it is passed too, which
   pins the official listing (hours, phone, reviews) instead of a bare coordinate. */
function gmapsPlace(p) {
  const q = encodeURIComponent(p.lat + ',' + p.lng);
  const id = p.gmaps_id ? '&query_place_id=' + encodeURIComponent(p.gmaps_id) : '';
  return `https://www.google.com/maps/search/?api=1&query=${q}${id}`;
}
function gmapsDir(p) {
  const d = encodeURIComponent(p.lat + ',' + p.lng);
  const id = p.gmaps_id ? '&destination_place_id=' + encodeURIComponent(p.gmaps_id) : '';
  return `https://www.google.com/maps/dir/?api=1&destination=${d}${id}&travelmode=transit`;
}

/* Leave room for the top bar, the two chip rails and the tip, then give the rest of
   the screen to the card: on a 844px phone that is ~580px instead of a fixed cap. */
function popupMaxH() { return Math.max(300, window.innerHeight - 264); }

// built on open, not on load: the weather arrives later and the card must show it
function bindCard(m, p) {
  m.bindPopup(() => popupHtml(p), { maxWidth: 286, maxHeight: popupMaxH(),
    autoPanPaddingTopLeft: [16, 136], autoPanPaddingBottomRight: [16, 28] });
}

const markers = DATA.places.map((p, i) => {
  const m = L.marker([p.lat, p.lng], {
    icon: L.divIcon({
      className: 'pin-wrap',
      html: `<div class="pin${p.imgStyle === 'art' ? ' art' : ''}" style="background:${p.color}">${p.emoji}${
        p.booking && p.booking.level !== 'info' ? '<i class="bk">🎫</i>' : ''}</div>`,
      iconSize: [28, 28], iconAnchor: [14, 14], popupAnchor: [0, -14]
    }),
    title: p.label,
    riseOnHover: true
  });
  bindCard(m, p);
  // in panel mode the popup is unbound, so the tap has to be handled here
  m.on('click', () => { if (PANEL_MODE) showCard(p); });
  m._place = p; m._idx = i;
  return m;
});


/* ---------- place names for the built-in base map ---------- */
const labelLayer = L.layerGroup().addTo(map);
const labelMarkers = DATA.labels.map(l => ({
  z: l.z,
  m: L.marker([l.lat, l.lng], {
    icon: L.divIcon({ className: 'lbl-wrap',
      html: `<div class="lbl${l.trip ? ' trip' : ''}">${esc(l.n)}</div>`, iconSize: [null, null] }),
    interactive: false, keyboard: false, zIndexOffset: -1000
  })
}));
function syncLabels() {
  const z = map.getZoom();
  labelMarkers.forEach(o => {
    const show = z >= o.z;
    if (show && !labelLayer.hasLayer(o.m)) labelLayer.addLayer(o.m);
    if (!show && labelLayer.hasLayer(o.m)) labelLayer.removeLayer(o.m);
  });
}
map.on('zoomend', syncLabels);

/* ---------- arrival and departure, drawn towards home ---------- */
const flightLayer = L.layerGroup().addTo(map);
const flightEnds = [];
DATA.flights.forEach(f => {
  // a short arc pointing WNW, the bearing of Almaty, so the direction reads at a glance
  const end = [f.lat + 0.34, f.lng - 0.95];
  const ctrl = [(f.lat + end[0]) / 2 + 0.26, (f.lng + end[1]) / 2];
  const pts = [];
  for (let t = 0; t <= 1.0001; t += 0.05) {
    const u = 1 - t;
    pts.push([
      u * u * f.lat + 2 * u * t * ctrl[0] + t * t * end[0],
      u * u * f.lng + 2 * u * t * ctrl[1] + t * t * end[1]
    ]);
  }
  const line = L.polyline(f.kind === 'arrival' ? pts.slice().reverse() : pts, {
    color: f.kind === 'arrival' ? '#2f9e44' : f.kind === 'both' ? '#475569' : '#e0483c',
    weight: 3, opacity: .75, dashArray: '2 6', lineCap: 'round'
  }).addTo(flightLayer);
  line.bindPopup(`<div class="pop"><h4>${f.kind === 'arrival' ? '🛬 Прилёт' : f.kind === 'both' ? '🛬 Прилёт · 🛫 Вылет' : '🛫 Вылет'}</h4>
    <p class="notes">${esc(f.text)}</p></div>`);
  L.marker(end, {
    icon: L.divIcon({ className: 'fl-wrap', html: `<div class="fl">${esc(f.label)}</div>`, iconSize: [null, null] })
  }).bindPopup(`<div class="pop"><h4>${f.kind === 'arrival' ? '🛬 Прилёт' : f.kind === 'both' ? '🛬 Прилёт · 🛫 Вылет' : '🛫 Вылет'}</h4>
    <p class="notes">${esc(f.text)}</p></div>`).addTo(flightLayer);
  flightEnds.push(end);
});

/* ---------- clustering: dense areas group up, and split apart as you zoom in ---------- */
const cluster = L.markerClusterGroup({
  maxClusterRadius: z => (z <= 7 ? 90 : z <= 10 ? 60 : 40),  // tighter groups the closer you get
  spiderfyOnMaxZoom: true,          // markers sharing one point fan out instead of hiding
  showCoverageOnHover: false,
  zoomToBoundsOnClick: true,
  disableClusteringAtZoom: 15,      // at street level every stop stands on its own
  spiderLegPolylineOptions: { weight: 1.4, color: '#64707d', opacity: .6 },
  spiderfyDistanceMultiplier: 1.3,  // finger-sized spacing when a point fans out
  // keep the zoom-to-cluster result clear of the fixed top bar and the itinerary sheet
  fitBoundsOptions: { paddingTopLeft: [40, 142], paddingBottomRight: [40, 64], maxZoom: 16 },
  iconCreateFunction(c) {
    const kids = c.getAllChildMarkers();
    const n = kids.length;
    // colour the cluster by the city that dominates it; flag it if it holds Ghibli art
    const tally = {};
    let art = 0;
    kids.forEach(m => {
      tally[m._place.color] = (tally[m._place.color] || 0) + 1;
      if (m._place.imgStyle === 'art') art++;
    });
    const color = Object.entries(tally).sort((a, b) => b[1] - a[1])[0][0];
    const size = n < 5 ? 38 : n < 12 ? 46 : 54;
    return L.divIcon({
      className: 'cl-wrap',
      html: `<div class="cl${art ? ' art' : ''}" style="--cl-bg:${color}">
               <b>${n}</b>${art ? '<i>🎨 ' + art + '</i>' : ''}
             </div>`,
      iconSize: [size, size]
    });
  }
});
map.addLayer(cluster);

function plural(n) {
  const a = n % 10, b = n % 100;
  if (a === 1 && b !== 11) return 'точка';
  if (a >= 2 && a <= 4 && (b < 10 || b > 20)) return 'точки';
  return 'точек';
}

/* the four inter-city transfer labels belong to the route view, not the everyday map */
let routeView = false;
function syncZoomLayers() {
  const show = routeView && map.getZoom() <= 10;   // they overlap the pins once you zoom in
  if (show && !map.hasLayer(transferLayer)) map.addLayer(transferLayer);
  if (!show && map.hasLayer(transferLayer)) map.removeLayer(transferLayer);
  document.getElementById('btnRoute').classList.toggle('on', routeView);
}
map.on('zoomend', syncZoomLayers);

/* ---------- filters ---------- */
let activeDay = 'all';
const activeCats = new Set(DATA.categories.map(c => c.key));

function applyFilters() {
  const keep = markers.filter(m => {
    const p = m._place;
    if (!activeCats.has(p.category)) return false;
    return activeDay === 'all' || p.days.includes(activeDay);
  });
  cluster.clearLayers();
  cluster.addLayers(keep);
  syncZoomLayers();
  renderSheet();
}

function buildChips() {
  const dayBox = document.getElementById('dayChips');
  const mk = (text, on, onClick) => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'chip' + (on ? ' on' : ''); b.textContent = text;
    b.addEventListener('click', onClick);
    return b;
  };
  dayBox.appendChild(mk('Все дни', true, e => {
    activeDay = 'all';
    [...dayBox.children].forEach(c => c.classList.remove('on'));
    e.currentTarget.classList.add('on');
    applyFilters(); fitAll();
  }));
  DATA.days.forEach(d => {
    dayBox.appendChild(mk('Д' + d.n, false, e => {
      activeDay = d.n;
      [...dayBox.children].forEach(c => c.classList.remove('on'));
      e.currentTarget.classList.add('on');
      applyFilters(); fitDay(d.n);
    }));
  });

  const catBox = document.getElementById('catChips');
  DATA.categories.forEach(c => {
    const b = mk(c.emoji + ' ' + c.short, true, e => {
      if (activeCats.has(c.key)) { activeCats.delete(c.key); e.currentTarget.classList.add('off'); }
      else { activeCats.add(c.key); e.currentTarget.classList.remove('off'); }
      applyFilters();
    });
    catBox.appendChild(b);
  });
}

/* ---------- itinerary sheet ---------- */
function renderSheet() {
  const sheet = document.getElementById('sheet');
  // merge repeat visits to the same place inside one day into a single row
  const merged = [];
  DATA.visits.forEach(v => {
    const p = DATA.places[v.p];
    if (!activeCats.has(p.category)) return;
    if (activeDay !== 'all' && v.day !== activeDay) return;
    const prev = merged.find(x => x.day === v.day && x.p === v.p);
    if (prev) {
      prev.times.push(v.time);
      if (v.notes && !prev.notes.includes(v.notes)) prev.notes.push(v.notes);
      if (v.overnight) prev.overnight = v.overnight;
    } else {
      merged.push({ day: v.day, p: v.p, times: [v.time],
                    notes: v.notes ? [v.notes] : [], overnight: v.overnight });
    }
  });
  const visible = merged.map(x => ({ s: DATA.places[x.p], i: x.p, x }));
  const days = [...new Set(visible.map(({ x }) => x.day))].sort((a, b) => a - b);
  const artCount = new Set(visible.filter(({ s }) => s.imgStyle === 'art').map(({ i }) => i)).size;
  const docCount = new Set(visible.filter(({ s }) => s.imgStyle === 'doc').map(({ i }) => i)).size;

  let html = `<h2>Маршрут по дням</h2>
    <div class="sub">${activeDay === 'all'
        ? `${new Set(visible.map(v => v.i)).size} мест · ${visible.length} остановок`
        : `день ${activeDay} · ${visible.length} ${plural(visible.length)}`}${
        artCount ? ` · 🎨 ${artCount} с Ghibli-версией` : ''}${
        docCount ? ` · ${docCount} документальных` : ''}</div><!--WX-->`;

  days.forEach(d => {
    const meta = DATA.days.find(x => x.n === d) || {};
    html += `<div class="day-block"><div class="day-head"><b>День ${d}</b><span>${esc(meta.date || '')} · ${esc(meta.note || '')}</span></div>`;
    visible.filter(({ x }) => x.day === d).forEach(({ s, i, x }) => {
      const times = x.times.join(' · ');
      html += `<button class="stop-row" type="button" data-idx="${i}">
        <span class="dot" style="background:${s.color}">${s.emoji}</span>
        <span><span class="nm">${esc(s.label)}</span>${s.imgStyle === 'art' ? ' <span class="art-tag">🎨</span>' : ''}
        <br><span class="mt">${esc(times)} · ${esc(s.city)}${x.overnight ? ' · 🌙 ' + esc(x.overnight) : ''}</span></span></button>`;
    });
    html += `</div>`;
  });
  html = html.replace('<!--WX-->', wxStrip());
  sheet.innerHTML = html;
  sheet.querySelectorAll('.stop-row').forEach(btn => {
    btn.addEventListener('click', () => {
      const m = markers[+btn.dataset.idx];
      if (!cluster.hasLayer(m)) return;
      // zoomToShowLayer expands whatever cluster is hiding the marker, then opens it
      cluster.zoomToShowLayer(m, () => openPlace(m));
      if (window.matchMedia('(max-width: 767px)').matches) toggleSheet(false);
    });
  });
}

/* ---------- weather: live forecast when the trip is close, climate model before that ----------
   Open-Meteo needs no key and allows browser requests. The forecast API only reaches
   ~16 days out, so until then the page falls back to the climate API, and always says
   which of the two it is showing. Results are cached so the guide still shows numbers
   with no signal. */
const WX = { byCity: JSON.parse(JSON.stringify(DATA.wxBaked)), source: 'climate',
             fetchedAt: null, error: null, baked: true };
const WX_CACHE = 'japan2026.wx.v2';   // v2: new route, new cities

const WX_ICON = c =>
  c === 0 ? '☀️' : c <= 2 ? '🌤️' : c === 3 ? '☁️' :
  c <= 48 ? '🌫️' : c <= 57 ? '🌦️' : c <= 67 ? '🌧️' :
  c <= 77 ? '🌨️' : c <= 82 ? '🌧️' : c <= 86 ? '🌨️' : '⛈️';

function wxLoadCache() {
  try {
    const raw = localStorage.getItem(WX_CACHE);
    if (!raw) return false;
    const c = JSON.parse(raw);
    if (!c || !c.byCity) return false;
    Object.assign(WX, c);
    return true;
  } catch (e) { return false; }
}
function wxSaveCache() {
  try { localStorage.setItem(WX_CACHE, JSON.stringify(WX)); } catch (e) { /* private mode */ }
}

async function wxFetch() {
  const s = DATA.tripStart, e = DATA.tripEnd;
  const daily = 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum';
  const q = sp => `latitude=${sp.lat}&longitude=${sp.lng}&start_date=${s}&end_date=${e}` +
                  `&timezone=Asia%2FTokyo&daily=`;
  try {
    const live = await Promise.all(DATA.weatherSpots.map(sp =>
      fetch(`https://api.open-meteo.com/v1/forecast?${q(sp)}${daily},precipitation_probability_max`)
        .then(r => r.ok ? r.json() : null).catch(() => null)));
    if (live.every(r => r && r.daily && r.daily.time && r.daily.time.length &&
                        r.daily.temperature_2m_max.some(v => v !== null))) {
      DATA.weatherSpots.forEach((sp, i) => { WX.byCity[sp.city] = live[i].daily; });
      WX.source = 'forecast';
      WX.baked = false;
    } else {
      const clim = await Promise.all(DATA.weatherSpots.map(sp =>
        fetch(`https://climate-api.open-meteo.com/v1/climate?${q(sp)}` +
              `temperature_2m_max,temperature_2m_min,precipitation_sum&models=MRI_AGCM3_2_S`)
          .then(r => r.ok ? r.json() : null).catch(() => null)));
      if (clim.every(r => r && r.daily && r.daily.time)) {
        DATA.weatherSpots.forEach((sp, i) => { WX.byCity[sp.city] = clim[i].daily; });
        WX.source = 'climate';
        WX.baked = false;
      } else { throw new Error('no data'); }
    }
    WX.fetchedAt = new Date().toISOString();
    WX.error = null;
    wxSaveCache();
  } catch (err) {
    WX.error = 'offline';      // the baked numbers stay on screen
  }
  renderSheet();
  const open = document.getElementById('booking');
  if (open.classList.contains('open')) renderBooking();
  window.dispatchEvent(new Event('japan2026:wx'));
}

function wxCityForDay(day) {
  const sp = DATA.weatherSpots.find(x => x.days[0] === day) ||
             DATA.weatherSpots.find(x => x.days.includes(day));
  return sp ? sp.city : null;
}
function wxFor(city, dateISO) {
  const d = WX.byCity[city];
  if (!d || !d.time) return null;
  const i = d.time.indexOf(dateISO);
  if (i < 0) return null;
  const hi = d.temperature_2m_max?.[i], lo = d.temperature_2m_min?.[i];
  if (hi == null) return null;
  const rain = d.precipitation_sum?.[i];
  let code = d.weather_code ? d.weather_code[i] : null;
  if (code == null && rain != null) code = rain > 8 ? 63 : rain > 1 ? 61 : rain > 0.05 ? 3 : 1;
  return { hi: Math.round(hi), lo: lo == null ? null : Math.round(lo), code, rain };
}
function wxLineFor(p) {
  const day = p.days[0];
  const v = wxFor(p.city, (DATA.days.find(d => d.n === day) || {}).date);
  if (!v) return '';
  return `<p class="wxline">${v.code != null ? WX_ICON(v.code) + ' ' : '🌡️ '}${v.hi}°${
    v.lo != null ? ' / ' + v.lo + '°' : ''}${v.rain ? ' · осадки ' + v.rain.toFixed(1) + ' мм' : ''}
    <span style="opacity:.7">· ${WX.source === 'forecast' ? 'прогноз' : 'климатическая норма'}</span></p>`;
}
function wxStrip() {
  if (!Object.keys(WX.byCity).length) return `<p class="wx-note">🌡️ Погода загружается…</p>`;
  const days = activeDay === 'all' ? DATA.days : DATA.days.filter(d => d.n === activeDay);
  const cells = days.map(d => {
    const city = wxCityForDay(d.n);
    const v = city && wxFor(city, d.date);
    if (!v) return '';
    return `<div class="wx-day"><div class="d">Д${d.n} · ${city.slice(0, 3)}</div>
      <div class="ic">${v.code != null ? WX_ICON(v.code) : '🌡️'}</div>
      <div class="t">${v.hi}°${v.lo != null ? ' <small>/ ' + v.lo + '°</small>' : ''}</div></div>`;
  }).join('');
  if (!cells) return '';
  const src = WX.source === 'forecast'
    ? 'Прогноз Open-Meteo, обновлён только что'
    : 'Климатическая модель Open-Meteo, зашита в файл ' +
      (WX.error ? '· живой прогноз недоступен (нет сети или запросы запрещены)'
                : '· прогноз появится за ~16 дней до поездки');
  return `<div class="wx">${cells}</div><p class="wx-note">${src}</p>`;
}

/* ---------- booking panel ---------- */
function daysUntil(iso) {
  const ms = new Date(iso + 'T00:00:00') - new Date(new Date().toDateString());
  return Math.round(ms / 86400000);
}
function renderBooking() {
  const el = document.getElementById('booking');
  const items = DATA.places
    .filter(p => p.booking)
    .map((p, i) => ({ p, i: DATA.places.indexOf(p) }))
    .sort((a, b) => {
      const rank = l => (l === 'must' ? 0 : l === 'advise' ? 1 : l === 'done' ? 3 : 2);
      return rank(a.p.booking.level) - rank(b.p.booking.level) ||
             a.p.booking.act.localeCompare(b.p.booking.act);
    });
  const musts = items.filter(x => x.p.booking.level === 'must').length;
  const done = items.filter(x => x.p.booking.level === 'done').length;
  let html = `<h2>Что нужно забронировать</h2>
    <div class="sub">${musts} обязательных · ✅ ${done} готово · ${items.length} пунктов всего</div>`;
  items.forEach(({ p, i }) => {
    const d = daysUntil(p.booking.act);
    const due = (p.booking.level === 'info' || p.booking.level === 'done') ? ''
      : d < 0 ? `<div class="bk-due past">срок ориентира прошёл — проверьте наличие</div>`
      : `<div class="bk-due${d <= 14 ? ' soon' : ''}">действовать ${d === 0 ? 'сегодня' : 'через ' + d + ' дн.'} · ${p.booking.act}</div>`;
    html += `<div class="bk-item">
      <div class="bk-head"><span class="nm">${p.emoji} ${esc(p.label)}</span>
        <span class="bk-lvl ${p.booking.level}">${
          p.booking.level === 'must' ? 'обязательно' : p.booking.level === 'advise' ? 'желательно' : p.booking.level === 'done' ? '✅ забронировано' : 'к сведению'}</span></div>
      <p class="bk-when">${esc(p.booking.when)}</p>
      <p class="bk-note">${esc(p.booking.note)}</p>
      ${p.booking.url ? `<a href="${esc(p.booking.url)}" target="_blank" rel="noopener">Сайт бронирования ↗</a>` : ''}
      ${due}
      <button class="stop-row" type="button" data-idx="${i}" style="margin-top:4px">
        <span class="dot" style="background:${p.color}">${p.emoji}</span>
        <span><span class="mt">показать на карте · день ${p.days.join(', ')}</span></span></button>
    </div>`;
  });
  el.innerHTML = html;
  el.querySelectorAll('.stop-row').forEach(btn => btn.addEventListener('click', () => {
    const m = markers[+btn.dataset.idx];
    if (!cluster.hasLayer(m)) {              // hidden by a filter — clear it first
      activeDay = 'all';
      [...document.getElementById('dayChips').children].forEach((c, i) => c.classList.toggle('on', i === 0));
      DATA.categories.forEach(c => activeCats.add(c.key));
      [...document.getElementById('catChips').children].forEach(c => c.classList.remove('off'));
      applyFilters();
    }
    if (window.matchMedia('(max-width: 899px)').matches) showPanel(bookEl, false);
    cluster.zoomToShowLayer(m, () => openPlace(m));
  }));
}

/* ---------- place card: popup or side panel ----------
   One content function serves both. The popup is for a glance, the panel for reading:
   in the panel every fact is expanded and the image gets a wider crop. The choice is
   remembered per device, like the task ticks. */
const CARD_MODE_KEY = 'japan2026.cardpanel.v1';
let PANEL_MODE = false;

function openPlace(m) {
  if (PANEL_MODE) showCard(m._place); else m.openPopup();
}

function showCard(p) {
  // the panel lives on the right, so whatever else sits there has to go first
  if (window.matchMedia('(max-width: 899px)').matches) {
    PANELS.forEach(x => { if (x.el.classList.contains('open')) showPanel(x.el, false); });
  } else if (legendEl.classList.contains('open')) {
    showPanel(legendEl, false);
  }
  cardEl.innerHTML =
    '<button class="cardclose" type="button" data-cardclose aria-label="Закрыть">✕</button>' +
    popupHtml(p, true);
  cardEl.scrollTop = 0;
  cardEl.classList.add('open');
  document.body.classList.add('pl-right');
}

function closeCard() {
  if (!cardEl.classList.contains('open')) return;
  cardEl.classList.remove('open');
  cardEl.innerHTML = '';
  document.body.classList.remove('pl-right');
}

function setPanelMode(on, remember) {
  PANEL_MODE = on;
  btnCard.classList.toggle('on', on);
  if (on) {
    map.closePopup();
    markers.forEach(m => m.unbindPopup());
  } else {
    closeCard();
    markers.forEach((m, i) => { if (!m.getPopup()) bindCard(m, DATA.places[i]); });
  }
  if (remember) {
    try { localStorage.setItem(CARD_MODE_KEY, on ? '1' : '0'); } catch (e) { /* private mode */ }
  }
}

/* ---------- view helpers ---------- */
function viewPad() {
  const topChrome = 128;                                   // top bar + both filter rails
  const sheetOpen = sheetEl.classList.contains('open');
  const wide = window.matchMedia('(min-width: 900px)').matches;
  if (wide) {
    // on a wide screen the itinerary is a left-hand panel, so it eats width, not height
    const left = sheetOpen ? sheetEl.offsetWidth + 28 : 40;
    const right = cardEl.classList.contains('open') ? cardEl.offsetWidth + 28 : 40;
    return { paddingTopLeft: [left, topChrome], paddingBottomRight: [right, 60] };
  }
  const bottomChrome = sheetOpen ? Math.min(window.innerHeight * 0.62, 560) + 24 : 40;
  return { paddingTopLeft: [40, topChrome], paddingBottomRight: [40, bottomChrome + 14] };
}
function fitAll() {
  sheetShift = 0;
  map.fitBounds(L.latLngBounds(DATA.places.map(s => [s.lat, s.lng]).concat(flightEnds)), viewPad());
}
function fitDay(n) {
  const pts = DATA.places.filter(s => s.days.includes(n) && activeCats.has(s.category)).map(s => [s.lat, s.lng]);
  if (pts.length) { sheetShift = 0; map.fitBounds(L.latLngBounds(pts), { ...viewPad(), maxZoom: 14 }); }
}

/* ---------- ui wiring ---------- */
const sheetEl = document.getElementById('sheet');
const bookEl = document.getElementById('booking');
const legendEl = document.getElementById('legend');
const cardEl = document.getElementById('cardPanel');
const btnCard = document.getElementById('btnCard');
const btnDays = document.getElementById('btnDays');
const btnBook = document.getElementById('btnBook');
const btnInfo = document.getElementById('btnInfo');

const PANELS = [
  { el: sheetEl, btn: btnDays },
  { el: bookEl, btn: btnBook },
  { el: legendEl, btn: btnInfo },
];
function showPanel(target, force) {
  const entry = PANELS.find(x => x.el === target);
  const open = force === undefined ? !entry.el.classList.contains('open') : force;
  PANELS.forEach(x => {
    const on = x === entry && open;
    x.el.classList.toggle('open', on);
    x.btn.classList.toggle('on', on);
  });
  // the card panel shares the right edge on wide screens and the whole screen on a phone
  if (open && (target === legendEl || window.matchMedia('(max-width: 899px)').matches)) closeCard();
  document.body.classList.toggle('pl-left', open && (target === sheetEl || target === bookEl));
  document.body.classList.toggle('pl-right', open && target === legendEl);
  if (open && target === bookEl) renderBooking();
  shiftForSheet();
}
/* On a phone the panels are bottom sheets covering the middle of the map, so the map is
   nudged up while one is open and back down when they all close. Zoom and pan are kept. */
let sheetShift = 0;
function shiftForSheet() {
  if (!window.matchMedia('(max-width: 899px)').matches) {
    if (sheetShift) { map.panBy([0, -sheetShift], { animate: false }); sheetShift = 0; }
    return;
  }
  const openPanel = PANELS.find(x => x.el.classList.contains('open'));
  const want = openPanel ? Math.round(openPanel.el.getBoundingClientRect().height / 2) : 0;
  if (want === sheetShift) return;
  map.panBy([0, want - sheetShift], { animate: true, duration: .25 });
  sheetShift = want;
}
function toggleSheet(force) { showPanel(sheetEl, force); }
btnDays.addEventListener('click', () => showPanel(sheetEl));
btnBook.addEventListener('click', () => showPanel(bookEl));
btnInfo.addEventListener('click', () => showPanel(legendEl));
btnCard.addEventListener('click', () => setPanelMode(!PANEL_MODE, true));
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeCard(); });
document.getElementById('btnRoute').addEventListener('click', () => {
  routeView = !routeView;
  if (routeView) map.fitBounds(routeLine.getBounds(), viewPad());
  syncZoomLayers();
});

/* legend swatches */
const lc = document.getElementById('legendCities');
Object.entries(DATA.cityColors).forEach(([city, color]) => {
  const s = document.createElement('span');
  s.innerHTML = `<i class="sw" style="background:${color}"></i>${city}`;
  lc.appendChild(s);
});
const lcat = document.getElementById('legendCats');
DATA.categories.forEach(c => {
  const s = document.createElement('span');
  s.textContent = c.emoji + ' ' + c.label;
  lcat.appendChild(s);
});

/* ---------- boot ---------- */
buildChips();
applyFilters();
if (window.matchMedia('(min-width: 900px)').matches) toggleSheet(true);

/* Popups are destroyed and rebuilt on every open and the task list is re-rendered on
   every tick, so both are driven by one delegated listener instead of per-node handlers. */
document.addEventListener('click', e => {
  if (e.target.closest('[data-cardclose]')) { closeCard(); return; }

  const tick = e.target.closest('[data-kzdone]');
  if (tick) {
    const id = tick.dataset.kzdone;
    kzToggleDone(id);
    const on = !!KZ_DONE[id];
    if (tick.classList.contains('kzdone')) {           // the button inside a popup
      tick.classList.toggle('on', on);
      tick.textContent = on ? '✓ Сделано' : 'Отметить';
    }
    renderBingo();                                     // the panel may be open behind it
  }

  const go = e.target.closest('[data-kzgo]');
  if (go) {
    const m = markers[+go.dataset.kzgo];
    if (!cluster.hasLayer(m)) {            // hidden by a filter — clear it first, as the
      activeDay = 'all';                   // booking panel does, so the jump never dead-ends
      [...document.getElementById('dayChips').children].forEach((c, i) => c.classList.toggle('on', i === 0));
      DATA.categories.forEach(c => activeCats.add(c.key));
      [...document.getElementById('catChips').children].forEach(c => c.classList.remove('off'));
      applyFilters();
    }
    if (window.matchMedia('(max-width: 899px)').matches) showPanel(legendEl, false);
    cluster.zoomToShowLayer(m, () => openPlace(m));
    return;
  }

  const more = e.target.closest('[data-kzmore]');
  if (more) {
    const box = more.closest('.kzbox');
    if (box) box.classList.add('open');
  }
  const rev = e.target.closest('[data-kzrev]');
  if (rev) {
    const g = rev.closest('.kzg');
    if (g) g.classList.add('open');
  }
  if (more || rev) {
    // NB: popup.update() re-runs the content function and would wipe the state we
    // just set. Re-measure and re-pan only, so the grown card stays on screen.
    const pop = map._popup;
    if (pop && pop._updateLayout) pop._updateLayout();
    if (pop && pop._adjustPan) pop._adjustPan();
  }
});

map.on('popupopen', e => {
  const h = popupMaxH();
  if (e.popup.options.maxHeight === h) return;
  e.popup.options.maxHeight = h;
  if (e.popup._updateLayout) e.popup._updateLayout();
  if (e.popup._adjustPan) e.popup._adjustPan();
});

function boot() {
  map.invalidateSize({ animate: false });
  kzLoadDone();
  renderBingo();
  try { if (localStorage.getItem(CARD_MODE_KEY) === '1') setPanelMode(true, false); } catch (e) {}
  fitAll();
  syncZoomLayers();
  syncLabels();
  if (wxLoadCache()) renderSheet();   // show last known weather instantly
  wxFetch();                          // then refresh in the background
}
map.whenReady(() => requestAnimationFrame(boot));
window.addEventListener('resize', () => map.invalidateSize({ animate: false }));
window.addEventListener('orientationchange', () => setTimeout(boot, 250));
</script>
<script>__TODAY_JS__</script>
</body>
</html>
"""

# The TODAY screen ships as modules under src/today/, glued into one closure in this order.
TODAY_MODULES = ["core.js", "store.js", "trips.js", "ios.js", "ui/shell.js", "ui/now.js", "ui/day.js",
                 "ui/bookings.js", "ui/stats.js", "ui/settings.js", "legacy.js", "boot.js"]
TODAY_STYLES = ["theme.css", "components.css"]


def today_js():
    parts = [pathlib.Path("today", m).read_text(encoding="utf-8") for m in TODAY_MODULES if pathlib.Path("today", m).exists()]
    return "(function () {\n'use strict';\n" + "\n".join(parts) + "\n})();"


def today_css():
    parts = [pathlib.Path("today", m).read_text(encoding="utf-8") for m in TODAY_STYLES if pathlib.Path("today", m).exists()]
    legacy = pathlib.Path("today.css")
    return (legacy.read_text(encoding="utf-8") if legacy.exists() else "") + "\n".join(parts)


out = (HTML
       .replace("__LEAFLET_CSS__", LEAFLET_CSS + "\n" + CLUSTER_CSS)
       .replace("__LEAFLET_JS__", LEAFLET_JS + "\n" + CLUSTER_JS)
       .replace("__DATA__", json.dumps(payload, ensure_ascii=False))
       .replace("__BASEMAP__", BASEMAP)
       .replace("__TODAY_CSS__", today_css())
       .replace("__TODAY_JS__", today_js()))
if PERSONAL:
    out = out.replace("<title>Япония за 11 дней</title>", "<title>" + TODAY["name"] + "</title>", 1)
OUT_FILE = "../survey/guide_personal.html" if PERSONAL else "Japan_Guide_2026.html"
open(OUT_FILE, "w", encoding="utf-8").write(out)
# len(out) counts characters; the page is mostly Cyrillic, so UTF-8 on disk is far
# larger. Report what the phone actually downloads.
_size = pathlib.Path(OUT_FILE).stat().st_size
print(f"written: {_size} bytes ({_size / 1024:.0f} KiB), {len(out)} chars")
print("places:", len(payload["places"]), "| visits:", len(payload["visits"]),
      "| with illustration:", sum(1 for s in payload["places"] if s["img"]),
      "(art:", sum(1 for s in payload["places"] if s["imgStyle"] == "art"),
      "| documentary:", sum(1 for s in payload["places"] if s["imgStyle"] == "doc"), ")")
_kz_n = sum(len(s["kz"]) for s in payload["places"])
print("kz facts:", _kz_n,
      "| places covered:", sum(1 for s in payload["places"] if s["kz"]), "/", len(payload["places"]),
      "| games:", sum(1 for s in payload["places"] for f in s["kz"] if "game" in f))
