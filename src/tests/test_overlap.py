import asyncio, json, pathlib
from playwright.async_api import async_playwright

FILE = pathlib.Path("Japan_Guide_2026.html").resolve().as_uri()

PROBE = """() => {
  const sel = {
    topbar: '.topbar', dayRail: '#dayChips', catRail: '#catChips',
    sheet: '#sheet.open', booking: '#booking.open', legend: '#legend.open',
    attrib: '.leaflet-control-attribution', scale: '.leaflet-control-scale',
    zoom: '.leaflet-control-zoom'
  };
  const boxes = {};
  for (const [k, s] of Object.entries(sel)) {
    const el = document.querySelector(s);
    if (!el) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    boxes[k] = { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  }
  const hits = [];
  const keys = Object.keys(boxes);
  for (let i = 0; i < keys.length; i++) for (let j = i + 1; j < keys.length; j++) {
    const a = boxes[keys[i]], b = boxes[keys[j]];
    const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
    const oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
    if (ox > 2 && oy > 2) hits.push(`${keys[i]} x ${keys[j]} (${ox}x${oy}px)`);
  }
  const de = document.documentElement;
  return { boxes, hits,
           hScroll: de.scrollWidth > de.clientWidth + 1,
           vw: window.innerWidth, vh: window.innerHeight };
}"""

async def main():
    out = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for w, h, mobile in [(360, 740, True), (390, 844, True), (414, 896, True),
                             (768, 1024, True), (820, 1180, True), (900, 700, False),
                             (1024, 768, False), (1280, 800, False), (1440, 900, False)]:
            ctx = await b.new_context(viewport={"width": w, "height": h}, is_mobile=mobile,
                                      has_touch=mobile)
            pg = await ctx.new_page()
            await pg.route("**/*open-meteo.com/**", lambda r: r.abort())
            await pg.goto(FILE, wait_until="load"); await pg.wait_for_timeout(1300)

            row = {"viewport": f"{w}x{h}"}
            # 1. nothing open
            row["idle"] = (await pg.evaluate(PROBE))["hits"]
            # 2. itinerary open
            await pg.click("#btnDays"); await pg.wait_for_timeout(500)
            r2 = await pg.evaluate(PROBE)
            row["days_open"] = r2["hits"]
            row["hscroll"] = r2["hScroll"]
            # 3. booking open
            await pg.click("#btnBook"); await pg.wait_for_timeout(500)
            row["booking_open"] = (await pg.evaluate(PROBE))["hits"]
            # 4. legend open
            await pg.click("#btnInfo"); await pg.wait_for_timeout(500)
            row["info_open"] = (await pg.evaluate(PROBE))["hits"]
            out.append(row)
            if w in (390, 1024):
                await pg.screenshot(path=f"ov_{w}.png")
            await ctx.close()
        await b.close()
    print(json.dumps(out, ensure_ascii=False, indent=1))

asyncio.run(main())
