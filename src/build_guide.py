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
IMG_DIR = pathlib.Path("img")


def data_uri(stem):
    """Inline one artwork as a base64 data: URI (no external request at runtime)."""
    p = IMG_DIR / (stem + ".webp")
    return "data:image/webp;base64," + base64.b64encode(p.read_bytes()).decode("ascii")

# Route: the four base points of the trip, in order.
ROUTE = [
    [34.632, 135.2239],   # Kobe Airport
    [34.6848, 135.5014],  # Osaka / Hommachi
    [34.9855, 135.7588],  # Kyoto Station
    [35.711, 139.7966],   # Tokyo / Asakusa
    [35.5494, 139.7798],  # Haneda
]
TRANSFERS = [
    {"lat": 34.6584, "lng": 135.3627, "label": "26 km · ≈55 min",
     "text": "Kobe Airport (UKB) → Osaka / Hommachi · Port Liner + train"},
    {"lat": 34.8352, "lng": 135.6301, "label": "41 km · ≈30 min",
     "text": "Osaka / Hommachi → Kyoto Station · JR / local train"},
    {"lat": 35.3483, "lng": 137.7777, "label": "376 km · ≈2h10–20",
     "text": "Kyoto Station → Tokyo / Asakusa · Nozomi Shinkansen"},
    {"lat": 35.6300, "lng": 139.7880, "label": "18 km · ≈45–60 min",
     "text": "Tokyo / Asakusa → Haneda Airport (HND) · metro / rail"},
]


# --- stops added on request -------------------------------------------------
EXTRA_STOPS = [
    {   # the only place in Japan actually listed as an izakaya named LIMA
        "day": 8, "date": "2026-10-24", "name": "LIMA \u2014 izakaya \U0001f37a",
        "city": "Tokyo", "category": "Food", "time": "21:00 \u2014 \u043f\u043e\u0437\u0434\u043d\u0438\u0439 \u0432\u0435\u0447\u0435\u0440",
        "notes": "\u041c\u0430\u043b\u0435\u043d\u044c\u043a\u0438\u0439 \u043f\u043e\u0434\u0432\u0430\u043b\u044c\u043d\u044b\u0439 \u0438\u0434\u0437\u0430\u043a\u0430\u044f-\u0431\u0430\u0440 \u0432 \u0413\u043e\u0442\u0430\u043d\u0434\u0435, \u0434\u0432\u0435 \u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043a\u0438 \u043e\u0442 \u0421\u0438\u0431\u0443\u0438 \u043f\u043e Yamanote. \u0420\u0430\u0431\u043e\u0442\u0430\u0435\u0442 \u0434\u043e 05:00, \u043d\u0435\u0434\u043e\u0440\u043e\u0433\u043e, \u0434\u0430\u0440\u0442\u0441 \u0438 \u043a\u0430\u0440\u0430\u043e\u043a\u0435, \u043c\u0435\u0441\u0442 \u043c\u0430\u043b\u043e.",
        "overnight": "", "lat": 35.6269487, "lng": 139.7255113,
        "gmaps_id": "ChIJ3W4tv_uKGGAR6n0Tzo-dG-4",
    },
    {   # global flagship, right next to the Ginza stop already on day 10
        "day": 10, "date": "2026-10-26", "name": "UNIQLO TOKYO \u2014 Ginza \U0001f6cd",
        "city": "Tokyo", "category": "Shopping", "time": "11:00\u201312:30",
        "notes": "\u0413\u043b\u043e\u0431\u0430\u043b\u044c\u043d\u044b\u0439 \u0444\u043b\u0430\u0433\u043c\u0430\u043d \u0432 Marronnier Gate Ginza 2, \u0447\u0435\u0442\u044b\u0440\u0435 \u044d\u0442\u0430\u0436\u0430, \u0441\u0432\u043e\u0438 \u043a\u043e\u043b\u043b\u0430\u0431\u043e\u0440\u0430\u0446\u0438\u0438 \u0438 \u043f\u0435\u0447\u0430\u0442\u044c \u043d\u0430 \u0432\u0435\u0449\u0430\u0445. \u0420\u044f\u0434\u043e\u043c \u2014 12-\u044d\u0442\u0430\u0436\u043d\u044b\u0439 Uniqlo Ginza. \u041e\u0442\u043a\u0440\u044b\u0442\u043e 11:00\u201321:00.",
        "overnight": "", "lat": 35.6737637, "lng": 139.7651281,
        "gmaps_id": "ChIJ4USUrOWLGGARi1DaZsGw4Ts",
    },
]
STOPS.extend(EXTRA_STOPS)

# --- what has to be reserved, and by when -----------------------------------
# level: must = \u0431\u0435\u0437 \u0431\u0440\u043e\u043d\u0438 \u043d\u0435 \u043f\u043e\u043f\u0430\u0441\u0442\u044c; advise = \u0436\u0435\u043b\u0430\u0442\u0435\u043b\u044c\u043d\u043e; info = \u043f\u0440\u043e\u0441\u0442\u043e \u0443\u0447\u0435\u0441\u0442\u044c
BOOKING = {
    "Shibuya Sky": {
        "level": "must", "act": "2026-10-09",
        "when": "\u041f\u0440\u043e\u0434\u0430\u0436\u0438 \u043e\u0442\u043a\u0440\u044b\u0432\u0430\u044e\u0442\u0441\u044f \u0440\u043e\u0432\u043d\u043e \u0437\u0430 14 \u0434\u043d\u0435\u0439: 10 \u043e\u043a\u0442 00:00 JST = 9 \u043e\u043a\u0442 20:00 \u043f\u043e \u0410\u043b\u043c\u0430\u0442\u044b",
        "note": "\u0420\u0430\u043d\u044c\u0448\u0435 \u0437\u0430\u0431\u0440\u043e\u043d\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u043d\u0435\u043b\u044c\u0437\u044f \u2014 \u043e\u043a\u043d\u043e \u0441\u043a\u043e\u043b\u044c\u0437\u044f\u0449\u0435\u0435. \u0417\u0430\u043a\u0430\u0442\u043d\u044b\u0435 \u0441\u043b\u043e\u0442\u044b \u0440\u0430\u0437\u0431\u0438\u0440\u0430\u044e\u0442 \u0437\u0430 \u043c\u0438\u043d\u0443\u0442\u044b \u043f\u043e\u0441\u043b\u0435 \u043f\u043e\u043b\u0443\u043d\u043e\u0447\u0438. \u041e\u043d\u043b\u0430\u0439\u043d \u00a52\u2009500 \u043f\u0440\u043e\u0442\u0438\u0432 \u00a53\u2009000 \u043d\u0430 \u0432\u0445\u043e\u0434\u0435; \u043e\u0442\u043c\u0435\u043d\u0430 \u0431\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u0430 \u0434\u043e \u043a\u0430\u043d\u0443\u043d\u0430. \u0415\u0441\u043b\u0438 \u043e\u043d\u043b\u0430\u0439\u043d \u043f\u0443\u0441\u0442\u043e \u2014 \u043a\u0430\u0441\u0441\u0430 \u043d\u0430 \u043c\u0435\u0441\u0442\u0435 \u0442\u043e\u0436\u0435 \u043f\u0443\u0441\u0442\u0430.",
        "url": "https://www.shibuya-scramble-square.com/sky/",
    },
    "Hiroshima Peace Memorial Museum": {
        "level": "advise", "act": "2026-10-12",
        "when": "\u0417\u0430 1\u20132 \u043d\u0435\u0434\u0435\u043b\u0438",
        "note": "\u041e\u043d\u043b\u0430\u0439\u043d-\u0441\u043b\u043e\u0442 \u043d\u0430 \u0432\u0440\u0435\u043c\u044f \u0432\u0445\u043e\u0434\u0430. \u0412 \u043f\u0438\u043a (10:00\u201312:00) \u0431\u0435\u0437 \u0431\u0440\u043e\u043d\u0438 \u043e\u0447\u0435\u0440\u0435\u0434\u044c \u043d\u0430 30\u201360 \u043c\u0438\u043d\u0443\u0442. \u00a5200 \u0441 \u0447\u0435\u043b\u043e\u0432\u0435\u043a\u0430.",
        "url": "https://hpmmuseum.jp/?lang=eng",
    },
    "Kyoto Imperial Palace": {
        "level": "info", "act": "2026-10-20",
        "when": "\u0411\u0435\u0437 \u0431\u0440\u043e\u043d\u0438",
        "note": "\u0412\u0445\u043e\u0434 \u0441\u0432\u043e\u0431\u043e\u0434\u043d\u044b\u0439 \u0438 \u0431\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u044b\u0439, \u043d\u043e 22 \u043e\u043a\u0442 \u0438\u0437-\u0437\u0430 \u0414\u0437\u0438\u0434\u0430\u0439 \u041c\u0430\u0446\u0443\u0440\u0438 \u0447\u0430\u0441\u0442\u044c \u0442\u0435\u0440\u0440\u0438\u0442\u043e\u0440\u0438\u0438 \u0437\u0430\u043a\u0440\u044b\u0442\u0430 \u043f\u043e\u0434 \u0441\u0442\u0430\u0440\u0442 \u043f\u0440\u043e\u0446\u0435\u0441\u0441\u0438\u0438.",
        "url": "",
    },
    "Jidai Matsuri route": {
        "level": "advise", "act": "2026-09-30",
        "when": "\u041f\u043b\u0430\u0442\u043d\u044b\u0435 \u0442\u0440\u0438\u0431\u0443\u043d\u044b \u2014 \u0432 \u043f\u0440\u043e\u0434\u0430\u0436\u0435 \u0441 \u043d\u0430\u0447\u0430\u043b\u0430 \u0441\u0435\u043d\u0442\u044f\u0431\u0440\u044f",
        "note": "\u0421\u043c\u043e\u0442\u0440\u0435\u0442\u044c \u043c\u043e\u0436\u043d\u043e \u0431\u0435\u0441\u043f\u043b\u0430\u0442\u043d\u043e \u0432\u0434\u043e\u043b\u044c \u0432\u0441\u0435\u0433\u043e \u043c\u0430\u0440\u0448\u0440\u0443\u0442\u0430 \u2014 \u043c\u0435\u0441\u0442\u0430 \u043d\u0443\u0436\u043d\u044b \u0442\u043e\u043b\u044c\u043a\u043e \u0440\u0430\u0434\u0438 \u0441\u0438\u0434\u044f\u0447\u0435\u0433\u043e \u043c\u0435\u0441\u0442\u0430 \u0432 \u043f\u0435\u0440\u0432\u043e\u043c \u0440\u044f\u0434\u0443. \u041f\u0440\u043e\u0446\u0435\u0441\u0441\u0438\u044f \u0441\u0442\u0430\u0440\u0442\u0443\u0435\u0442 \u0432 12:00 \u043e\u0442 \u0418\u043c\u043f\u0435\u0440\u0430\u0442\u043e\u0440\u0441\u043a\u043e\u0433\u043e \u0434\u0432\u043e\u0440\u0446\u0430.",
        "url": "",
    },
    "LIMA \u2014 izakaya": {
        "level": "advise", "act": "2026-10-21",
        "when": "\u0421\u0442\u043e\u043b\u0438\u043a \u2014 \u0437\u0430 1\u20133 \u0434\u043d\u044f",
        "note": "\u041f\u043e\u0434\u0432\u0430\u043b\u044c\u043d\u044b\u0439 \u0431\u0430\u0440 \u043d\u0430 ~15 \u043c\u0435\u0441\u0442. \u0417\u0432\u043e\u043d\u043e\u043a \u0438\u043b\u0438 \u0447\u0435\u0440\u0435\u0437 \u043e\u0442\u0435\u043b\u044c; \u0432 \u0431\u0443\u0434\u043d\u0438 \u043f\u043e\u0441\u043b\u0435 22:00 \u043e\u0431\u044b\u0447\u043d\u043e \u0435\u0441\u0442\u044c \u043c\u0435\u0441\u0442\u0430.",
        "url": "",
    },
    "Pontocho & Kamo River": {
        "level": "advise", "act": "2026-10-15",
        "when": "\u0423\u0436\u0438\u043d \u2014 \u0437\u0430 2\u20135 \u0434\u043d\u0435\u0439",
        "note": "\u0412 \u043e\u043a\u0442\u044f\u0431\u0440\u0435 \u0443 \u0440\u0435\u043a\u0438 \u0432\u0441\u0451 \u0437\u0430\u043d\u044f\u0442\u043e \u0441 18:00. \u0411\u0435\u0437 \u0431\u0440\u043e\u043d\u0438 \u2014 \u0438\u0434\u0442\u0438 \u0434\u043e 17:30 \u0438\u043b\u0438 \u043f\u043e\u0441\u043b\u0435 21:00.",
        "url": "",
    },
    "Gion / Maruyama area": {
        "level": "advise", "act": "2026-10-14",
        "when": "\u0423\u0436\u0438\u043d \u2014 \u0437\u0430 3\u20137 \u0434\u043d\u0435\u0439",
        "note": "\u0417\u0430\u0432\u0435\u0434\u0435\u043d\u0438\u044f \u0432 \u0413\u0438\u043e\u043d\u0435 \u043c\u0430\u043b\u0435\u043d\u044c\u043a\u0438\u0435; \u043d\u0430 \u0447\u0435\u0442\u0432\u0435\u0440\u044b\u0445 \u0431\u0435\u0437 \u0431\u0440\u043e\u043d\u0438 \u0441\u043b\u043e\u0436\u043d\u043e.",
        "url": "",
    },
    "Osaka hotel area \u2013 Hommachi": {
        "level": "must", "act": "2026-09-25",
        "when": "\u0421\u0435\u0439\u0447\u0430\u0441, \u0435\u0441\u043b\u0438 \u0435\u0449\u0451 \u043d\u0435 \u0437\u0430\u0431\u0440\u043e\u043d\u0438\u0440\u043e\u0432\u0430\u043d",
        "note": "\u041e\u043a\u0442\u044f\u0431\u0440\u044c \u2014 \u043f\u0438\u043a \u0441\u0435\u0437\u043e\u043d\u0430 (\u043a\u043b\u0451\u043d\u044b + \u0431\u0438\u0437\u043d\u0435\u0441-\u043f\u043e\u0435\u0437\u0434\u043a\u0438). 3 \u043d\u043e\u0447\u0438, 17\u201319 \u043e\u043a\u0442.",
        "url": "",
    },
    "Kyoto hotel area \u2013 Kyoto Station": {
        "level": "must", "act": "2026-09-25",
        "when": "\u0421\u0435\u0439\u0447\u0430\u0441, \u0435\u0441\u043b\u0438 \u0435\u0449\u0451 \u043d\u0435 \u0437\u0430\u0431\u0440\u043e\u043d\u0438\u0440\u043e\u0432\u0430\u043d",
        "note": "\u041a\u0438\u043e\u0442\u043e \u0432 \u043e\u043a\u0442\u044f\u0431\u0440\u0435 \u0440\u0430\u0441\u043a\u0443\u043f\u0430\u044e\u0442 \u0440\u0430\u043d\u044c\u0448\u0435 \u0432\u0441\u0435\u0433\u043e, \u0430 22 \u043e\u043a\u0442 \u0435\u0449\u0451 \u0438 \u0414\u0437\u0438\u0434\u0430\u0439 \u041c\u0430\u0446\u0443\u0440\u0438. 3 \u043d\u043e\u0447\u0438, 20\u201322 \u043e\u043a\u0442.",
        "url": "",
    },
    "Tokyo hotel area \u2013 Asakusa": {
        "level": "must", "act": "2026-09-25",
        "when": "\u0421\u0435\u0439\u0447\u0430\u0441, \u0435\u0441\u043b\u0438 \u0435\u0449\u0451 \u043d\u0435 \u0437\u0430\u0431\u0440\u043e\u043d\u0438\u0440\u043e\u0432\u0430\u043d",
        "note": "4 \u043d\u043e\u0447\u0438, 23\u201326 \u043e\u043a\u0442. \u0410\u0441\u0430\u043a\u0443\u0441\u0430 \u0443\u0434\u043e\u0431\u043d\u0430 \u0434\u043b\u044f \u0432\u044b\u043b\u0435\u0442\u0430 \u0438\u0437 \u0425\u0430\u043d\u044d\u0434\u044b.",
        "url": "",
    },
    "UNIQLO TOKYO \u2014 Ginza": {
        "level": "info", "act": "2026-10-26",
        "when": "\u0411\u0440\u043e\u043d\u044c \u043d\u0435 \u043d\u0443\u0436\u043d\u0430",
        "note": "\u0414\u043b\u044f tax-free \u043d\u0443\u0436\u0435\u043d \u043f\u0430\u0441\u043f\u043e\u0440\u0442 \u0438 \u043e\u0442\u0434\u0435\u043b\u044c\u043d\u0430\u044f \u043a\u0430\u0441\u0441\u0430; \u043f\u043e\u0440\u043e\u0433 \u00a55\u2009500 \u0432 \u043e\u0434\u0438\u043d \u0447\u0435\u043a. \u041f\u0435\u0447\u0430\u0442\u044c \u043d\u0430 \u0444\u0443\u0442\u0431\u043e\u043b\u043a\u0430\u0445 \u0434\u0435\u043b\u0430\u044e\u0442 \u043f\u0440\u0438 \u0432\u0430\u0441, ~15 \u043c\u0438\u043d.",
        "url": "",
    },
    "Kobe Airport (UKB)": {
        "level": "info", "act": "2026-10-17",
        "when": "\u041f\u0440\u0438\u043b\u0451\u0442 17 \u043e\u043a\u0442, ~14:00",
        "note": "\u0414\u0430\u043b\u044c\u0448\u0435 Port Liner + \u043f\u043e\u0435\u0437\u0434 \u0434\u043e \u0425\u043e\u043c\u043c\u0430\u0442\u0438, ~55 \u043c\u0438\u043d. IC-\u043a\u0430\u0440\u0442\u0443 (Suica/ICOCA) \u0432\u044b\u043f\u0443\u0441\u0442\u0438\u0442\u044c \u0441\u0440\u0430\u0437\u0443 \u0432 \u0430\u044d\u0440\u043e\u043f\u043e\u0440\u0442\u0443.",
        "url": "",
    },
    "Haneda Airport (HND)": {
        "level": "info", "act": "2026-10-27",
        "when": "\u0412\u044b\u043b\u0435\u0442 27 \u043e\u043a\u0442, \u0432\u0435\u0447\u0435\u0440",
        "note": "\u0418\u0437 \u0410\u0441\u0430\u043a\u0443\u0441\u044b 45\u201360 \u043c\u0438\u043d. \u0412 \u0430\u044d\u0440\u043e\u043f\u043e\u0440\u0442\u0443 \u0431\u044b\u0442\u044c \u0437\u0430 3 \u0447\u0430\u0441\u0430; tax-free \u0447\u0435\u043a\u0438 \u0434\u0435\u0440\u0436\u0430\u0442\u044c \u043f\u043e\u0434 \u0440\u0443\u043a\u043e\u0439.",
        "url": "",
    },
}

# arrival / departure: short arcs pointing home towards Almaty
FLIGHTS = [
    {"kind": "arrival", "lat": 34.632, "lng": 135.2239,
     "label": "\u2708\ufe0f \u0438\u0437 \u0410\u043b\u043c\u0430\u0442\u044b \u00b7 17 \u043e\u043a\u0442",
     "text": "\u041f\u0440\u0438\u043b\u0451\u0442 \u0432 \u041a\u043e\u0431\u0435 (UKB) \u2014 17 \u043e\u043a\u0442\u044f\u0431\u0440\u044f, ~14:00. \u0414\u0430\u043b\u044c\u0448\u0435 Port Liner + \u043f\u043e\u0435\u0437\u0434 \u0434\u043e \u0425\u043e\u043c\u043c\u0430\u0442\u0438, \u224855 \u043c\u0438\u043d."},
    {"kind": "departure", "lat": 35.5494, "lng": 139.7798,
     "label": "\u2708\ufe0f \u0432 \u0410\u043b\u043c\u0430\u0442\u044b \u00b7 27 \u043e\u043a\u0442",
     "text": "\u0412\u044b\u043b\u0435\u0442 \u0438\u0437 \u0425\u0430\u043d\u044d\u0434\u044b (HND) \u2014 27 \u043e\u043a\u0442\u044f\u0431\u0440\u044f, \u0432\u0435\u0447\u0435\u0440. \u0418\u0437 \u0410\u0441\u0430\u043a\u0443\u0441\u044b 45\u201360 \u043c\u0438\u043d, \u0431\u044b\u0442\u044c \u0437\u0430 3 \u0447\u0430\u0441\u0430."},
]

# Place names for the built-in base map. "trip" cities are the ones on the route and are
# always drawn; the rest appear as you zoom in, so the country view stays readable.
PLACE_LABELS = [
    # name, lat, lng, min zoom, on the route
    ("Токио",     35.6762, 139.6503, 0, True),
    ("Осака",     34.6937, 135.5023, 0, True),
    ("Киото",     35.0116, 135.7681, 0, True),
    ("Хиросима",  34.3853, 132.4553, 0, True),
    ("Кобе",      34.6901, 135.1955, 6, True),
    ("Нара",      34.6851, 135.8048, 6, True),
    ("Миядзима",  34.2959, 132.3197, 7, True),
    ("Нагоя",     35.1815, 136.9066, 5, False),
    ("Иокогама",  35.4437, 139.6380, 7, False),
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
    "Osaka": "#e0483c", "Nara": "#e58a1f", "Hiroshima": "#2f9e44",
    "Miyajima": "#2f9e44", "Kyoto": "#8b5cf6", "Tokyo": "#2563eb",
    "Kobe": "#475569",
}
CAT_META = {
    "Attraction": {"emoji": "📍", "label": "Достопримечательности", "short": "Места"},
    "Nature":     {"emoji": "🌿", "label": "Природа и парки",       "short": "Природа"},
    "Food":       {"emoji": "🍜", "label": "Еда",                   "short": "Еда"},
    "Shopping":   {"emoji": "🛍", "label": "Шоппинг",               "short": "Шоппинг"},
    "Hotel":      {"emoji": "🏨", "label": "Отели",                 "short": "Отели"},
    "Airport":    {"emoji": "✈️", "label": "Аэропорты",             "short": "Аэропорты"},
}

DAY_NOTES = {
    1: "Прилёт в Кобе, заселение в Осаке, вечер в Дотонбори",
    2: "Дневная поездка в Нару, вечер в Осаке",
    3: "Хиросима и Миядзима одним днём",
    4: "Утро в Осаке, переезд в Киото, вечер в Гионе",
    5: "Главный день Киото: Фусими Инари и Киёмидзу-дэра",
    6: "Спокойный Киото + фестиваль Дзидай Мацури",
    7: "Арасияма утром, днём синкансэн в Токио",
    8: "Современный Токио: Синдзюку, Харадзюку, Сибуя",
    9: "Старый Токио: Асакуса, Уэно, Янака",
    10: "Цукидзи, Гиндза, Киёсуми — последний полный день",
    11: "Утро в Асакусе, вылет из Ханэды",
}

KZ_EMOJI = ("📍", "🌿", "🍜", "🛍", "🏨", "✈️", "🍺", "🍶")


def place_label(name: str) -> str:
    """Marker name minus its trailing category emoji — the join key for every side table."""
    for e in KZ_EMOJI:
        name = name.replace(e, "")
    return name.strip()


# Kazakh-Japanese fact layer: same keys as stops.json, joined on the stripped label.
KZ_RAW = json.loads(pathlib.Path("kz_facts.json").read_text(encoding="utf-8"))["places"]
KZ_FACTS = {place_label(k): v["facts"] for k, v in KZ_RAW.items()}

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
_kz_orphans = sorted(KZ_FACTS.keys() - {place_label(s["name"]) for s in STOPS})
assert not _kz_orphans, f"kz_facts.json keys with no stop: {_kz_orphans}"

for s in STOPS:
    key = GHIBLI.get(s["name"])
    s["img"] = data_uri(key) if key else None
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
            "lat": s["lat"], "lng": s["lng"], "img": s["img"],
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
    "days": [{"n": d, "date": DAY_DATES[d], "note": DAY_NOTES.get(d, "")} for d in DAYS],
    "categories": [{"key": k, **v} for k, v in CAT_META.items()],
    "cityColors": CITY_COLOR,
    # one representative point per city, for the weather sync
    "weatherSpots": [
        {"city": "Osaka",     "lat": 34.6848, "lng": 135.5014, "days": [1, 2, 3, 4]},
        {"city": "Kyoto",     "lat": 34.9855, "lng": 135.7588, "days": [4, 5, 6, 7]},
        {"city": "Tokyo",     "lat": 35.7110, "lng": 139.7966, "days": [7, 8, 9, 10, 11]},
        {"city": "Hiroshima", "lat": 34.3955, "lng": 132.4536, "days": [3]},
        {"city": "Nara",      "lat": 34.6851, "lng": 135.8048, "days": [2]},
    ],
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
<title>Япония 17–27 окт 2026</title>
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
</head>
<body>
<div id="map"></div>

<div class="topbar">
  <div class="title">🇯🇵 Япония · 17–27 окт 2026 · 4 чел.</div>
  <button class="btn" id="btnRoute" type="button">🧭<span class="lbl"> Маршрут</span></button>
  <button class="btn" id="btnDays" type="button">📋<span class="lbl"> Дни</span></button>
  <button class="btn" id="btnBook" type="button">🎫<span class="lbl"> Брони</span></button>
  <button class="btn" id="btnInfo" type="button">ℹ️<span class="lbl"> Инфо</span></button>
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
  <div class="row" style="color:var(--text)">✈️ Кобе → 🏨 Осака (3 ночи) → 🏨 Киото (3 ночи) → 🏨 Токио / Асакуса (4 ночи) → ✈️ Ханэда</div>
  <hr>
  <h3>Цвет метки — город</h3>
  <div class="row" id="legendCities"></div>
  <h3>Иконка — категория</h3>
  <div class="row" id="legendCats"></div>
  <div class="row">🎨 жёлтая обводка — есть Ghibli-версия места (17 точек)</div>
  <div class="row">🎫 значок на метке — место требует брони, детали в панели «Брони»</div>
  <div class="row">🛬 зелёная дуга — прилёт 17 окт, 🛫 красная — вылет 27 окт</div>
  <div class="row">В каждом попапе есть ссылки «Google Maps» (адрес места) и «Маршрут» (проезд на транспорте)</div>
  <hr>
  <h3>Ключевые переезды</h3>
  <dl>
    <dt>Осака ↔ Нара</dt><dd>≈45–50 мин</dd>
    <dt>Осака ↔ Хиросима</dt><dd>≈1 ч 25 мин, синкансэн</dd>
    <dt>Хиросима ↔ Миядзима</dt><dd>≈45–60 мин с паромом</dd>
    <dt>Осака → Киото</dt><dd>≈30 мин</dd>
    <dt>Киото → Токио</dt><dd>≈2 ч 10–20 мин, Nozomi</dd>
  </dl>
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

function popupHtml(p) {
  const img = p.img
    ? `<img src="${esc(p.img)}" alt="Ghibli-версия: ${esc(p.label)}" loading="lazy"
            onerror="this.style.display='none';this.nextElementSibling.style.display='none';">
       <div class="cap">🎨 Ghibli-версия места</div>`
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
    ${kzHtml(p)}
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

function kzHtml(p) {
  const list = p.kz || [];
  if (!list.length) return '';
  const head = list.slice(0, 2).map(kzItem).join('');
  const rest = list.slice(2);
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

const markers = DATA.places.map((p, i) => {
  const m = L.marker([p.lat, p.lng], {
    icon: L.divIcon({
      className: 'pin-wrap',
      html: `<div class="pin${p.img ? ' art' : ''}" style="background:${p.color}">${p.emoji}${
        p.booking && p.booking.level !== 'info' ? '<i class="bk">🎫</i>' : ''}</div>`,
      iconSize: [28, 28], iconAnchor: [14, 14], popupAnchor: [0, -14]
    }),
    title: p.label,
    riseOnHover: true
  // built on open, not on load: the weather arrives later and the popup must show it
  }).bindPopup(() => popupHtml(p), { maxWidth: 286, maxHeight: popupMaxH(),
      autoPanPaddingTopLeft: [16, 136], autoPanPaddingBottomRight: [16, 28] });
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
    color: f.kind === 'arrival' ? '#2f9e44' : '#e0483c',
    weight: 3, opacity: .75, dashArray: '2 6', lineCap: 'round'
  }).addTo(flightLayer);
  line.bindPopup(`<div class="pop"><h4>${f.kind === 'arrival' ? '🛬 Прилёт' : '🛫 Вылет'}</h4>
    <p class="notes">${esc(f.text)}</p></div>`);
  L.marker(end, {
    icon: L.divIcon({ className: 'fl-wrap', html: `<div class="fl">${esc(f.label)}</div>`, iconSize: [null, null] })
  }).bindPopup(`<div class="pop"><h4>${f.kind === 'arrival' ? '🛬 Прилёт' : '🛫 Вылет'}</h4>
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
      if (m._place.img) art++;
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
  const artCount = new Set(visible.filter(({ s }) => s.img).map(({ i }) => i)).size;

  let html = `<h2>Маршрут по дням</h2>
    <div class="sub">${activeDay === 'all'
        ? `${new Set(visible.map(v => v.i)).size} мест · ${visible.length} остановок`
        : `день ${activeDay} · ${visible.length} ${plural(visible.length)}`} · 🎨 ${artCount} с Ghibli-версией</div><!--WX-->`;

  days.forEach(d => {
    const meta = DATA.days.find(x => x.n === d) || {};
    html += `<div class="day-block"><div class="day-head"><b>День ${d}</b><span>${esc(meta.date || '')} · ${esc(meta.note || '')}</span></div>`;
    visible.filter(({ x }) => x.day === d).forEach(({ s, i, x }) => {
      const times = x.times.join(' · ');
      html += `<button class="stop-row" type="button" data-idx="${i}">
        <span class="dot" style="background:${s.color}">${s.emoji}</span>
        <span><span class="nm">${esc(s.label)}</span>${s.img ? ' <span class="art-tag">🎨</span>' : ''}
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
      cluster.zoomToShowLayer(m, () => m.openPopup());
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
const WX_CACHE = 'japan2026.wx.v1';

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
      fetch(`https://api.open-meteo.com/v1/forecast?${q(sp)}${daily}`)
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
      const rank = l => (l === 'must' ? 0 : l === 'advise' ? 1 : 2);
      return rank(a.p.booking.level) - rank(b.p.booking.level) ||
             a.p.booking.act.localeCompare(b.p.booking.act);
    });
  const musts = items.filter(x => x.p.booking.level === 'must').length;
  let html = `<h2>Что нужно забронировать</h2>
    <div class="sub">${musts} обязательных · ${items.length} пунктов всего</div>`;
  items.forEach(({ p, i }) => {
    const d = daysUntil(p.booking.act);
    const due = p.booking.level === 'info' ? ''
      : d < 0 ? `<div class="bk-due past">срок ориентира прошёл — проверьте наличие</div>`
      : `<div class="bk-due${d <= 14 ? ' soon' : ''}">действовать ${d === 0 ? 'сегодня' : 'через ' + d + ' дн.'} · ${p.booking.act}</div>`;
    html += `<div class="bk-item">
      <div class="bk-head"><span class="nm">${p.emoji} ${esc(p.label)}</span>
        <span class="bk-lvl ${p.booking.level}">${
          p.booking.level === 'must' ? 'обязательно' : p.booking.level === 'advise' ? 'желательно' : 'к сведению'}</span></div>
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
    cluster.zoomToShowLayer(m, () => m.openPopup());
  }));
}

/* ---------- view helpers ---------- */
function viewPad() {
  const topChrome = 128;                                   // top bar + both filter rails
  const sheetOpen = sheetEl.classList.contains('open');
  const wide = window.matchMedia('(min-width: 900px)').matches;
  if (wide) {
    // on a wide screen the itinerary is a left-hand panel, so it eats width, not height
    const left = sheetOpen ? sheetEl.offsetWidth + 28 : 40;
    return { paddingTopLeft: [left, topChrome], paddingBottomRight: [40, 60] };
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
    cluster.zoomToShowLayer(m, () => m.openPopup());
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
</body>
</html>
"""

out = (HTML
       .replace("__LEAFLET_CSS__", LEAFLET_CSS + "\n" + CLUSTER_CSS)
       .replace("__LEAFLET_JS__", LEAFLET_JS + "\n" + CLUSTER_JS)
       .replace("__DATA__", json.dumps(payload, ensure_ascii=False))
       .replace("__BASEMAP__", BASEMAP))
open("Japan_Guide_2026.html", "w", encoding="utf-8").write(out)
# len(out) counts characters; the page is mostly Cyrillic, so UTF-8 on disk is far
# larger. Report what the phone actually downloads.
_size = pathlib.Path("Japan_Guide_2026.html").stat().st_size
print(f"written: {_size} bytes ({_size / 1024:.0f} KiB), {len(out)} chars")
print("places:", len(payload["places"]), "| visits:", len(payload["visits"]),
      "| places with art:", sum(1 for s in payload["places"] if s["img"]))
_kz_n = sum(len(s["kz"]) for s in payload["places"])
print("kz facts:", _kz_n,
      "| places covered:", sum(1 for s in payload["places"] if s["kz"]), "/", len(payload["places"]),
      "| games:", sum(1 for s in payload["places"] for f in s["kz"] if "game" in f))
