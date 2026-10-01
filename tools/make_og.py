"""python3 tools/make_og.py → og-<trip>.jpg link previews (1200×630), rendered in Chromium from the trip illustrations.
Text sits in the middle so WhatsApp's square crop still shows it."""
import base64, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
CARDS = {
    "og-miras-aikosh.jpg": dict(img="fushimi.webp", kicker="SHF Power Trip", title="Japan 2026",
                                sub="17–28 октября · Токио · Фудзи · Киото · Нагоя · Шанхай", pill="План поездки, билеты и кто куда едет"),
    "og-v2.jpg": dict(img="arashiyama.webp", kicker="Приложение поездки", title="Япония за 11 дней",
                      sub="Токио · Фудзи · Киото · Нагоя", pill="Что сейчас, что дальше — офлайн, на iPhone"),
}
HTML = """<html><body style="margin:0"><div style="position:relative;width:1200px;height:630px;overflow:hidden;font-family:-apple-system,'SF Pro Display','Helvetica Neue',sans-serif">
<img src="data:image/webp;base64,{b64}" style="position:absolute;inset:0;width:1200px;height:630px;object-fit:cover;object-position:center 60%">
<div style="position:absolute;inset:0;background:radial-gradient(ellipse at center,rgba(0,0,0,.62) 0%,rgba(0,0,0,.38) 55%,rgba(0,0,0,.18) 100%)"></div>
<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;color:#fff;gap:14px;padding:0 60px">
  <div style="font:600 30px/1.2 -apple-system,'SF Pro Display','Helvetica Neue',sans-serif;letter-spacing:.02em;opacity:.95">{kicker}</div>
  <div style="font:800 112px/1.02 -apple-system,'SF Pro Display','Helvetica Neue',sans-serif;letter-spacing:-.02em;text-shadow:0 4px 30px rgba(0,0,0,.45)">{title}</div>
  <div style="font:500 32px/1.3 -apple-system,'SF Pro Display','Helvetica Neue',sans-serif;opacity:.95">{sub}</div>
  <div style="margin-top:14px;font:600 28px/1 -apple-system,'SF Pro Display','Helvetica Neue',sans-serif;background:#FFCC00;color:#000;border-radius:999px;padding:16px 30px">{pill}</div>
</div></div></body></html>"""

with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1200, "height": 630})
    for out, c in CARDS.items():
        b64 = base64.b64encode((ROOT / "src" / "img" / c["img"]).read_bytes()).decode()
        pg.set_content(HTML.format(b64=b64, **{k: v for k, v in c.items() if k != "img"}))
        pg.wait_for_timeout(200)
        pg.screenshot(path=str(ROOT / out), type="jpeg", quality=84, clip={"x": 0, "y": 0, "width": 1200, "height": 630})
        print(out, (ROOT / out).stat().st_size // 1024, "KB")
    b.close()
