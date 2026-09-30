import json, re
from conftest import ROOT, PHONE

OWN = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
REAL = {"prevDay": 2, "prevTime": "13:24", "preview": False}


def home(app, now="2026-09-30T12:00:00+09:00", **kw):
    return app(trip=OWN, state=REAL, now=now, **kw)


def test_before_the_trip_countdown_first_thing_and_readiness_above_the_fold(app):
    a = home(app)
    assert "Япония" in a.page.inner_text(".tc-title h1") and "через 17 дней" in a.page.inner_text(".tc-title")   # 16.5 days, rounded up
    assert a.page.locator(".tc-segs").count() == 0 and a.page.locator("#tcCap").count() == 0
    assert "17 дней" in a.page.inner_text("#tcCount") and "MU 6042" in a.page.inner_text("#tcCount")
    first = a.page.inner_text("#tcFirst")
    assert a.page.inner_text("#tcFirst b").strip() and "ещё" in first
    ready = a.page.locator("#tcReady [data-ready]")
    assert [b.get_attribute("data-ready") for b in ready.all()] == ["tickets", "phone", "money", "packing"]
    bar = a.page.locator("#tcTabs").bounding_box()["y"]
    for sel in ("#tcCount", "#tcFirst", "#tcReady"):
        b = a.page.locator(sel).bounding_box(); assert b["y"] + b["height"] <= bar
    assert a.page.locator("#tcWx, #tcSun, #tcNow, #tcNext, .tc-preview").count() == 0      # no weather before T-7, no fake time
    ready.first.click()
    assert a.page.locator("#tcSheet [data-group='tickets']").is_visible()
    assert a.errors == []


def test_week_before_shows_weather_and_capsule_before_sales_open(app):
    a = home(app, now="2026-10-10T01:00:00+09:00")            # Shibuya Sky sales in < 48 h; departure in 6 days
    assert a.page.locator("#tcCap").count() == 1 and "Shibuya Sky" in a.page.inner_text("#tcCap")
    assert a.page.locator("#tcDay1").count() == 1
    assert a.page.locator("#tcSun").count() == 1 and a.errors == []          # T-7: the sun (and weather) row is back


def test_departure_transit_live_post(app):
    d = home(app, now="2026-10-16T12:00:00+05:00")           # Almaty, departure day
    assert "MU 6042" in d.page.inner_text("#tcFlight") and d.page.locator("#tcFirst").count() == 0
    assert d.page.locator(".tc-segs").count() == 0 and "вылет сегодня" in d.page.inner_text(".tc-title")
    t = home(app, now="2026-10-17T09:00:00+08:00")           # Shanghai morning
    day1 = t.page.inner_text("#tcDay1")
    assert "по Шанхаю" in day1 and t.page.locator("#tcDay1 .now").count() == 1
    l = home(app, now="2026-10-18T13:24:00+09:00")           # in Japan
    assert "Oishi Park" in l.page.inner_text("#tcNow")
    p = home(app, now="2026-10-29T12:00:00+09:00")
    assert "Поездка завершена" in p.page.inner_text("#todayBody")


def test_no_flights_falls_back_to_dates(app):
    a = app(trip=dict(OWN, flights=[]), state=REAL, now="2026-09-30T12:00:00+09:00")
    a.page.evaluate("localStorage.setItem('japan2026.flights.v1', '[]'); renderShell()")
    assert "через 17 дней" in a.page.inner_text(".tc-title") and a.errors == []


def test_preview_lives_on_day_tab(app):
    a = home(app)
    a.page.click(".tc-tab[data-tab='day']")
    a.page.click(".tc-daypick >> nth=1")
    a.page.click("#tcPreviewDay")
    assert a.page.locator("#tcNow").count() == 1 and "Предпросмотр" in a.page.inner_text("#todayBody")
    a.page.click("#tcPvExit")
    assert a.page.locator("#tcCount").count() == 1


def test_shanghai_stops_show_local_time_on_day_tab(app):
    a = home(app)
    a.page.click(".tc-tab[data-tab='day']")
    a.page.click(".tc-daypick >> nth=0")
    row = a.page.locator(".tc-item", has_text="Маглев до").inner_text()
    assert "07:00" in row and "по Шанхаю" in row


def test_a_left_over_preview_does_not_hide_the_transit_screen(app):
    a = app(trip=OWN, state={"prevDay": 2, "prevTime": "13:24", "preview": True}, now="2026-10-17T09:00:00+08:00")
    assert a.page.locator("#tcDay1 .now").count() == 1 and a.errors == []
