import asyncio, json, pathlib
from playwright.async_api import async_playwright
FILE = pathlib.Path("Japan_Guide_2026.html").resolve().as_uri()

PROBE = open("test_overlap.py").read().split('PROBE = """')[1].split('"""')[0]

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        # --- everything external blocked, like the artifact sandbox ---
        ctx = await b.new_context(viewport={"width":1440,"height":900})
        pg = await ctx.new_page()
        errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.route("**://**", lambda r: r.abort() if r.request.url.startswith("http") else r.continue_())
        await pg.goto(FILE, wait_until="load"); await pg.wait_for_timeout(5200)
        r = {"mode":"all external blocked"}
        r["land_paths"] = await pg.evaluate("document.querySelectorAll('.leaflet-overlay-pane path').length")
        r["tile_imgs"] = await pg.evaluate("document.querySelectorAll('.leaflet-tile').length")
        r["map_bg"] = await pg.evaluate("document.getElementById('map').style.background")
        r["clusters"] = await pg.locator(".cl").count()
        # every Ghibli artwork must decode from the inlined data: URI with no network
        r["art_places"] = await pg.evaluate("DATA.places.filter(p=>p.img).length")
        r["art_all_data_uris"] = await pg.evaluate(
            "DATA.places.filter(p=>p.img).every(p=>p.img.startsWith('data:image/webp;base64,'))")
        r["art_decoded_ok"] = await pg.evaluate("""async () => {
            const urls = DATA.places.filter(p => p.img).map(p => p.img);
            const res = await Promise.all(urls.map(u => new Promise(ok => {
              const im = new Image();
              im.onload = () => ok(im.naturalWidth > 0 && im.naturalHeight > 0);
              im.onerror = () => ok(false);
              im.src = u;
            })));
            return res.filter(Boolean).length;
        }""")
        await pg.click("#btnDays"); await pg.wait_for_timeout(600)
        r["overlaps_days"] = (await pg.evaluate(PROBE))["hits"]
        await pg.click("#btnInfo"); await pg.wait_for_timeout(600)
        r["overlaps_info"] = (await pg.evaluate(PROBE))["hits"]
        await pg.screenshot(path="off_desktop.png")
        r["errors"]=errs
        print(json.dumps(r, ensure_ascii=False, indent=1))
        await ctx.close()

        # --- mobile, blocked ---
        ctx2 = await b.new_context(viewport={"width":390,"height":844}, is_mobile=True, has_touch=True, device_scale_factor=3)
        m = await ctx2.new_page()
        await m.route("**://**", lambda r: r.abort() if r.request.url.startswith("http") else r.continue_())
        await m.goto(FILE, wait_until="load"); await m.wait_for_timeout(5200)
        r2 = {"mode":"mobile blocked"}
        r2["land_paths"] = await m.evaluate("document.querySelectorAll('.leaflet-overlay-pane path').length")
        await m.click("#btnDays"); await m.wait_for_timeout(600)
        r2["overlaps_days"] = (await m.evaluate(PROBE))["hits"]
        await m.screenshot(path="off_mobile.png")
        print(json.dumps(r2, ensure_ascii=False, indent=1))

        # --- tiles available: fake a successful tile so the upgrade path runs ---
        png = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d4944415478da63fcffff3f0300050001a5f645400000000049454e44ae426082")
        ctx3 = await b.new_context(viewport={"width":1440,"height":900})
        t = await ctx3.new_page()
        async def tile(route):
            await route.fulfill(status=200, content_type="image/png", body=png)
        await t.route("**tile.openstreetmap.org/**", tile)
        await t.route("**open-meteo.com/**", lambda r: r.abort())
        await t.goto(FILE, wait_until="load"); await t.wait_for_timeout(3000)
        print(json.dumps({"mode":"tiles reachable",
              "tile_imgs": await t.evaluate("document.querySelectorAll('.leaflet-tile').length"),
              "land_removed": await t.evaluate("document.querySelectorAll('.leaflet-overlay-pane path').length")}, ensure_ascii=False, indent=1))
        await b.close()
asyncio.run(main())
