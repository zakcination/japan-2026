import json, re
from conftest import ROOT, PHONE, IPHONE_UA

OWN = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
REAL = {"prevDay": 2, "prevTime": "13:24", "preview": False}


def home(app, now="2026-09-30T12:00:00+09:00", **kw):
    return app(trip=OWN, state=REAL, now=now, **kw)


def test_before_the_trip_countdown_first_thing_and_readiness_above_the_fold(app):
    a = home(app)
    assert "Япония" in a.page.inner_text(".tc-title h1") and "через 16 дней" in a.page.inner_text(".tc-title")   # 16.53 days, floored
    assert a.page.locator(".tc-segs").count() == 0 and a.page.locator("#tcCap").count() == 0
    assert "16 дней" in a.page.inner_text("#tcCount") and "MU 6042" in a.page.inner_text("#tcCount")   # same floor as the title, never disagree
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


def test_title_and_hero_countdown_never_disagree(app):
    def n_of(a):
        title_n = int(re.search(r"через (\d+)", a.page.inner_text(".tc-title")).group(1))
        hero_n = int(re.match(r"(\d+)", a.page.inner_text("#tcCount .tc-count-n")).group(1))
        return title_n, hero_n
    a = home(app, now="2026-09-30T12:00:00+09:00")               # 16.53 days to MU6042 — both floor to 16
    t, h = n_of(a)
    assert t == h == 16
    b = home(app, now="2026-10-14T12:00:00+09:00")                # ~2.53 days to MU6042 — both floor to 2
    t, h = n_of(b)
    assert t == h == 2


def test_no_flights_falls_back_to_dates(app):
    a = app(trip=dict(OWN, flights=[]), state=REAL, now="2026-09-30T12:00:00+09:00")
    a.page.evaluate("localStorage.setItem('japan2026.flights.v1', '[]'); renderShell()")
    assert "через 16 дней" in a.page.inner_text(".tc-title") and a.errors == []


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


PV = {"prevDay": 2, "prevTime": "13:24", "preview": True}


def test_a_stale_preview_never_hides_departure_or_the_end(app):
    d = app(trip=OWN, state=PV, now="2026-10-16T12:00:00+05:00")
    assert d.page.locator("#tcFlight").count() == 1 and d.page.locator("#tcNow").count() == 0
    p = app(trip=OWN, state=PV, now="2026-10-29T12:00:00+09:00")
    assert "Поездка завершена" in p.page.inner_text("#todayBody") and p.errors == []


def test_preview_has_an_exit_at_the_top(app):
    a = app(trip=OWN, state=PV)
    assert a.page.locator("#tcPvExitTop").is_visible() and a.page.locator("#tcPvExit").count() == 1
    a.page.click("#tcPvExitTop")
    assert a.page.locator("#tcCount").count() == 1 and a.page.locator("#tcPvExitTop").count() == 0


def test_readiness_above_the_fold_on_a_real_iphone(app):
    a = app(trip=OWN, state=REAL, ua=IPHONE_UA)
    assert a.page.locator("#tcInstall").count() == 1                      # the hint is there, just lower
    bar = a.page.locator("#tcTabs").bounding_box()["y"]
    for sel in ("#tcCount", "#tcFirst", "#tcReady"):
        b = a.page.locator(sel).bounding_box(); assert b["y"] + b["height"] <= bar


def test_transit_follows_the_flight(app):
    a = home(app, now="2026-10-17T19:30:00+08:00")                       # MU575 in the air
    cur = a.page.locator("#tcDay1 .now")
    assert cur.count() == 1 and "MU575" in re.sub(r"\s", "", cur.inner_text())
    assert "позади" in a.page.inner_text("#tcDay1")
    g = home(app, now="2026-10-17T10:35:00+08:00")                       # between two Shanghai stops
    assert g.page.locator("#tcDay1 .now").count() == 1
    hs = g.page.evaluate("[...document.querySelectorAll('#tcDay1 li b')].map(b => b.getBoundingClientRect().height)")
    assert hs and max(hs) < 30                                            # the time column never wraps (measured in one step)


def test_capsule_says_what_opens_and_opens_the_tickets(app):
    a = home(app, now="2026-10-10T01:00:00+09:00")
    t = a.page.inner_text("#tcCap")
    assert "продажи через" in t and "23 ч" in t
    a.page.click("#tcCap")
    assert a.page.locator("#tcSheet [data-group='tickets']").is_visible()


def test_hotel_tasks_say_book_not_buy(app):
    a = home(app)
    assert "Забронировать: отель в Киото, 18.10 → 20.10 (2 ночи)" in a.page.inner_text("#tcFirst b")


def test_overdue_task_color_is_readable(app):
    a = home(app, now="2026-10-05T12:00:00+09:00")                       # Kyoto hotel due 03.10 — already overdue
    assert "срок был 03.10" in a.page.inner_text("#tcFirst")
    color = a.page.eval_on_selector(".tc-late", "el => getComputedStyle(el).color")
    assert color == "rgb(215, 0, 21)"


def test_transit_header_has_no_day_segments_and_names_the_step(app):
    g = home(app, now="2026-10-17T10:35:00+08:00")                       # between two Shanghai stops
    assert g.page.locator(".tc-segs").count() == 0
    assert g.page.inner_text(".tc-title h1").strip() == "В пути"
    assert "Шанхае" in g.page.inner_text(".tc-title")
    a = home(app, now="2026-10-17T19:30:00+08:00")                       # MU575 in the air
    assert a.page.locator(".tc-segs").count() == 0
    assert a.page.inner_text(".tc-title h1").strip() == "В пути"
    assert "в полёте" in a.page.inner_text(".tc-title")


def test_countdown_skips_no_whole_day(app):
    def no_flights(now):
        a = app(trip=dict(OWN, flights=[]), state=REAL, now=now)
        a.page.evaluate("localStorage.setItem('japan2026.flights.v1', '[]'); renderShell()")
        return a
    assert "2 дня" in no_flights("2026-10-14T12:00:00+09:00").page.inner_text("#tcCount")     # 60 h before day 1
    assert "1 д 6 ч" in no_flights("2026-10-15T18:00:00+09:00").page.inner_text("#tcCount")   # 30 h before day 1
    assert "5:12" in no_flights("2026-10-16T18:48:00+09:00").page.inner_text("#tcCount")      # 5 h 12 min before day 1


def test_the_evening_before_departure_says_tomorrow(app):
    a = home(app, now="2026-10-15T22:00:00+05:00")       # 15.10 22:00 Almaty, MU6042 tomorrow 20:50
    assert "завтра" in a.page.inner_text(".tc-title") and "сегодня" not in a.page.inner_text(".tc-title")
