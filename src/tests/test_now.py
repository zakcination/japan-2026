"""The «Сейчас» tab: one screen, what's on now, what's next, when to leave."""


def at(app, time, day=2, **kw):
    return app(state={"prevDay": day, "prevTime": time, **kw.pop("state", {})}, **kw)


def fits_one_screen(page):
    """What matters is on the first screen without scrolling: now and next end above the tab bar."""
    # measured in one step inside the page, so a re-render (weather arriving) can't slip in between
    return page.evaluate("""() => { const bar = document.getElementById('tcTabs').getBoundingClientRect().top;
      return ['tcNow', 'tcNext'].map(id => document.getElementById(id)).filter(Boolean)
        .every(el => el.getBoundingClientRect().bottom <= bar + 0.5); }""")


def test_now_and_next_by_day(app):
    a = at(app, "13:24")
    now = a.page.inner_text("#tcNow")
    nxt = a.page.inner_text("#tcNext")
    assert "Oishi Park" in now and "до 15:45" in now
    assert "17:00" in nxt and "Кавагутико → Мисима" in nxt and "2 ч 51" in nxt
    assert fits_one_screen(a.page)
    for b in a.page.locator("#tcNext button, #tcNext a").all():
        assert b.bounding_box()["height"] >= 44
    assert a.errors == []


def test_time_to_leave_card_and_replan_note(app):
    a = at(app, "16:18", state={"delay": {"d2e7": 30}})
    card = a.page.inner_text("#tcNext")
    assert "Пора выходить" in card and "Начать маршрут" in card
    assert "План пересчитан" in a.page.inner_text("#todayBody")
    assert fits_one_screen(a.page)


def test_night_shows_big_clock(app):
    a = at(app, "19:30")
    assert a.page.get_attribute("#today", "data-th") == "dark"
    assert "19:30" in a.page.inner_text(".tc-bignow")


def test_day_finished(app):
    a = at(app, "23:55")
    assert "День завершён" in a.page.inner_text("#todayBody")


def test_now_empty_day(app):
    trip = {"schema": 1, "name": "Пусто", "travelers": 1, "start": "2026-10-17", "currency": "JPY", "rate": 1,
            "bookings": [], "days": [{"n": 1, "date": "2026-10-17", "city": "Токио", "label": "Токио", "wcity": "Tokyo",
                                      "sun": [35.6, 139.7], "summary": "", "konbini": "", "hotel": "", "ev": []}]}
    a = app(trip=trip, state={"prevDay": 1, "prevTime": "10:00"})
    assert "Нет пунктов" in a.page.inner_text("#todayBody")
    assert a.errors == []


def test_sun_widget_shows_the_next_sunrise_or_sunset(app):
    a = at(app, "13:24")                       # day 2 at Kawaguchiko: sunset ~17:07
    sun = a.page.inner_text("#tcSun")
    assert "ЗАКАТ" in sun.upper() and "17:0" in sun and "Восход:" in sun
    dot, arc = a.page.evaluate("""() => { const r = s => { const b = document.querySelector(s).getBoundingClientRect(); return {y: b.y, height: b.height}; };
      return [r('#tcSun .tc-sun-arc circle'), r('#tcSun .tc-sun-arc')]; }""")   # one step: a re-render can't detach them mid-check
    assert dot["y"] < arc["y"] + arc["height"] / 2          # early afternoon: the sun is high on the arc
    night = at(app, "21:00")
    assert "ВОСХОД" in night.page.inner_text("#tcSun").upper() and "Закат:" in night.page.inner_text("#tcSun")
    assert "down" in night.page.locator("#tcSun .tc-sun-arc circle").get_attribute("class")


HOURLY = {"hourly": {"time": [f"2026-10-18T{h:02d}:00" for h in range(24)],
                     "temperature_2m": [10 + h // 2 for h in range(24)],
                     "precipitation_probability": [70 if h >= 15 else 10 for h in range(24)],
                     "weather_code": [61 if h >= 15 else 2 for h in range(24)]}}


def test_weather_tile_hour_by_hour_with_rain_hint(app):
    import json as _j
    route = lambda r: r.fulfill(status=200, content_type="application/json", body=_j.dumps(HOURLY))
    a = at(app, "13:24", now="2026-10-10T12:00:00+09:00", routes={"https://api.open-meteo.com/v1/forecast?*hourly=*": route})
    from conftest import until
    until(a.page, "document.querySelectorAll('#tcWx .tc-wx-hours span').length === 4")
    wx = a.page.inner_text("#tcWx")
    assert "16°" in wx and "дождь с 15:00" in wx and "сейч." in wx
    sun = a.page.locator("#tcSun").bounding_box(); w = a.page.locator("#tcWx").bounding_box()
    assert abs(sun["y"] - w["y"]) < 1 and abs(sun["width"] - w["width"]) < 2      # side by side, same width
    assert fits_one_screen(a.page)


def test_weather_tile_before_the_forecast_shows_typical_weather(app):
    a = at(app, "13:24")                                  # 30.09: the 18th is beyond 16 days
    wx = a.page.locator("#tcWx")
    if wx.count():                                        # the climate data may be missing offline
        assert "по часам — с 02.10" in wx.inner_text()
