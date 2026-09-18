import asyncio, json, pathlib
from playwright.async_api import async_playwright

FILE = pathlib.Path("Japan_Guide_2026.html").resolve().as_uri()

PICK = """(sel) => {
  const els=[...document.querySelectorAll(sel)];
  for (const el of els) { const r=el.getBoundingClientRect();
    if (r.y>200 && r.y < window.innerHeight-260 && r.x>40 && r.x<window.innerWidth-50) {
      const cx=r.x+r.width/2, cy=r.y+r.height/2;
      const hit=document.elementFromPoint(cx,cy);
      if (hit && hit.closest(sel)) return {cx, cy, text: el.textContent.trim()};
    } }
  return null;
}"""

async def main():
    r, errs = {}, []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await (await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                                        has_touch=True, device_scale_factor=3)).new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(FILE, wait_until="load"); await pg.wait_for_timeout(1600)

        r["1_zoom"] = await pg.evaluate("map.getZoom()")
        r["1_clusters"] = await pg.locator(".cl").count()
        r["1_loose_pins"] = await pg.locator(".pin").count()
        r["1_cluster_labels"] = await pg.evaluate("[...document.querySelectorAll('.cl')].map(e=>e.textContent.trim())")
        await pg.screenshot(path="cl_1_overview.png")

        # tap a cluster -> it should zoom to its bounds and decompose
        pt = await pg.evaluate(PICK, ".cl")
        await pg.touchscreen.tap(pt["cx"], pt["cy"]); await pg.wait_for_timeout(1600)
        r["2_tapped"] = pt["text"]
        r["2_zoom_after"] = await pg.evaluate("map.getZoom()")
        r["2_clusters"] = await pg.locator(".cl").count()
        r["2_pins"] = await pg.locator(".pin").count()
        await pg.screenshot(path="cl_2_decomposed.png")

        # zoom right in: everything should be individual pins
        await pg.evaluate("map.setView([34.9948,135.7700], 15)"); await pg.wait_for_timeout(1400)
        r["3_at_z15_clusters"] = await pg.locator(".cl").count()
        r["3_at_z15_pins"] = await pg.locator(".pin").count()
        await pg.screenshot(path="cl_3_street.png")

        # a stop that shares a point with others (hotel) -> spiderfy path via the list
        await pg.evaluate("map.setView([35.45,136.8], 6)"); await pg.wait_for_timeout(1200)
        await pg.locator("#btnDays").tap(); await pg.wait_for_timeout(500)
        await pg.locator(".stop-row").nth(2).tap(); await pg.wait_for_timeout(2200)
        r["4_jump_popup"] = await pg.locator(".leaflet-popup").count()
        r["4_jump_title"] = await pg.locator(".leaflet-popup .pop h4").first.inner_text() if await pg.locator(".leaflet-popup .pop h4").count() else None
        await pg.screenshot(path="cl_4_jump.png")

        # filters still drive the cluster
        await pg.locator("#btnDays").tap(); await pg.wait_for_timeout(300)
        await pg.locator("#dayChips .chip", has_text="Д3").first.tap(); await pg.wait_for_timeout(1400)
        r["5_day3_cluster_total"] = await pg.evaluate(
            "[...document.querySelectorAll('.cl b')].reduce((a,e)=>a+ +e.textContent,0) + document.querySelectorAll('.pin').length")
        await pg.screenshot(path="cl_5_day3.png")
        await pg.locator("#dayChips .chip", has_text="Все дни").first.tap(); await pg.wait_for_timeout(1200)
        for label in ["Отели", "Еда"]:
            await pg.locator("#catChips .chip", has_text=label).first.tap(); await pg.wait_for_timeout(300)
        r["6_after_two_cats_off"] = await pg.evaluate(
            "[...document.querySelectorAll('.cl b')].reduce((a,e)=>a+ +e.textContent,0) + document.querySelectorAll('.pin').length")

        r["errors"] = errs
        print(json.dumps(r, ensure_ascii=False, indent=1))

        pg2 = await (await b.new_context(viewport={"width": 1440, "height": 900})).new_page()
        await pg2.goto(FILE, wait_until="load"); await pg2.wait_for_timeout(1600)
        await pg2.screenshot(path="cl_6_desktop.png")
        await b.close()

asyncio.run(main())
