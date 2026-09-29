"""The «Сейчас» tab: one screen, what's on now, what's next, when to leave."""


def at(app, time, day=2, **kw):
    return app(state={"prevDay": day, "prevTime": time, **kw.pop("state", {})}, **kw)


def fits_one_screen(page):
    return page.evaluate("(() => { const r = document.getElementById('today'); return r.scrollHeight <= r.clientHeight + 1; })()")


def test_now_and_next_by_day(app):
    a = at(app, "13:24")
    now = a.page.inner_text("#tcNow")
    nxt = a.page.inner_text("#tcNext")
    assert "Oishi Park" in now and "до 15:45" in now
    assert "17:00" in nxt and "Кавагутико → Мисима" in nxt and "2:51" in nxt
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
