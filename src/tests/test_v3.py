import asyncio, json, pathlib
from playwright.async_api import async_playwright

FILE = pathlib.Path("Japan_Guide_2026.html").resolve().as_uri()
DATES = [f"2026-10-{d}" for d in range(17, 28)]

def daily(with_code=True, nulls=False):
    n = len(DATES)
    d = {
        "time": DATES,
        "temperature_2m_max": [None] * n if nulls else [21.4 + i * .3 for i in range(n)],
        "temperature_2m_min": [None] * n if nulls else [13.2 + i * .2 for i in range(n)],
        "precipitation_sum": [0, 1.2, 0, 0, 4.8, 0, 0, 0, 2.1, 0, 0],
    }
    if with_code:
        d["weather_code"] = [0, 61, 2, 3, 63, 1, 0, 2, 51, 0, 1]
    return {"daily": d}

async def route_weather(page, mode):
    async def handler(route):
        url = route.request.url
        if "climate-api" in url:
            if mode == "offline":
                await route.abort()
            else:
                await route.fulfill(status=200, content_type="application/json",
                                    body=json.dumps(daily(with_code=False)))
        else:  # forecast
            if mode == "forecast":
                await route.fulfill(status=200, content_type="application/json",
                                    body=json.dumps(daily()))
            elif mode == "climate":
                await route.fulfill(status=200, content_type="application/json",
                                    body=json.dumps(daily(nulls=True)))
            else:
                await route.abort()
    await page.route("**/*open-meteo.com/**", handler)

async def scenario(browser, mode, shot=None):
    ctx = await browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                                    has_touch=True, device_scale_factor=3)
    pg = await ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await route_weather(pg, mode)
    await pg.goto(FILE, wait_until="load")
    await pg.wait_for_timeout(2200)

    out = {"mode": mode}
    await pg.locator("#btnDays").tap(); await pg.wait_for_timeout(500)
    out["wx_cells"] = await pg.locator(".wx-day").count()
    out["wx_note"] = (await pg.locator(".wx-note").first.inner_text()) if await pg.locator(".wx-note").count() else None
    out["wx_first"] = (await pg.locator(".wx-day").first.inner_text()).replace("\n", " ") if out["wx_cells"] else None
    if shot: await pg.screenshot(path=shot)
    out["errors"] = errs
    await ctx.close()
    return out

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        results = []
        results.append(await scenario(b, "forecast", "v3_wx_forecast.png"))
        results.append(await scenario(b, "climate"))
        results.append(await scenario(b, "offline"))

        # full feature pass with the forecast mock
        ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True,
                                  has_touch=True, device_scale_factor=3)
        pg = await ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await route_weather(pg, "forecast")
        await pg.goto(FILE, wait_until="load"); await pg.wait_for_timeout(2000)

        r = {}
        r["new_stops_present"] = await pg.evaluate(
            "DATA.places.filter(p => /LIMA|UNIQLO/.test(p.label)).map(p => p.label)")
        r["flight_labels"] = await pg.evaluate("[...document.querySelectorAll('.fl')].map(e=>e.textContent)")
        r["booking_places"] = await pg.evaluate("DATA.places.filter(p=>p.booking).length")

        # booking panel
        await pg.locator("#btnBook").tap(); await pg.wait_for_timeout(600)
        r["bk_items"] = await pg.locator(".bk-item").count()
        r["bk_sub"] = await pg.locator("#booking .sub").inner_text()
        r["bk_first"] = (await pg.locator(".bk-item").first.inner_text()).replace("\n", " | ")[:260]
        await pg.screenshot(path="v3_booking.png")

        # jump to Shibuya Sky from the booking list, check popup content
        await pg.locator(".bk-item", has_text="Shibuya Sky").locator(".stop-row").tap()
        await pg.wait_for_timeout(2200)
        r["popup_title"] = await pg.locator(".leaflet-popup .pop h4").first.inner_text()
        r["popup_has_booking_box"] = await pg.locator(".leaflet-popup .bkbox").count()
        r["popup_wx"] = (await pg.locator(".leaflet-popup .wxline").first.inner_text()) if await pg.locator(".leaflet-popup .wxline").count() else None
        r["gmaps_href"] = await pg.locator(".leaflet-popup .links a").first.get_attribute("href")
        r["dir_href"] = await pg.locator(".leaflet-popup .links a").nth(1).get_attribute("href")
        await pg.screenshot(path="v3_popup.png")

        # booking badges on pins
        await pg.evaluate("map.setView([35.66,139.70], 14)"); await pg.wait_for_timeout(1200)
        r["pins_with_ticket_badge"] = await pg.locator(".pin .bk").count()
        r["errors"] = errs
        results.append(r)

        # desktop
        pg2 = await (await b.new_context(viewport={"width": 1440, "height": 900})).new_page()
        await route_weather(pg2, "forecast")
        await pg2.goto(FILE, wait_until="load"); await pg2.wait_for_timeout(2000)
        await pg2.click("#btnBook"); await pg2.wait_for_timeout(600)
        await pg2.screenshot(path="v3_desktop_booking.png")
        await pg2.click("#btnDays"); await pg2.wait_for_timeout(600)
        await pg2.screenshot(path="v3_desktop_days.png")

        print(json.dumps(results, ensure_ascii=False, indent=1))
        await b.close()

asyncio.run(main())
