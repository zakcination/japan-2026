"""The shell: five tabs, the capsule, day segments, title and the sunset theme."""
DAY2 = {"prevDay": 2}


def at(app, time, **kw):
    return app(state={**DAY2, "prevTime": time}, **kw)


def test_five_tabs_and_switching(app):
    a = at(app, "13:24")
    tabs = a.page.locator(".tc-tab")
    assert tabs.count() == 5
    assert [t.inner_text().strip() for t in tabs.all()] == ["Сейчас", "День", "Брони", "Итоги", "Карта"]
    assert tabs.nth(0).get_attribute("aria-selected") == "true"
    tabs.nth(1).click()
    assert tabs.nth(1).get_attribute("aria-selected") == "true"
    for t in tabs.all():
        box = t.bounding_box()
        assert box["height"] >= 44 and box["width"] >= 44
    assert a.errors == []


def test_capsule_calm_soon_go(app):
    calm = at(app, "13:24").page
    assert calm.locator("#tcCap").get_attribute("class").split()[-1] == "calm"
    assert "17:00" in calm.inner_text("#tcCap") and "2:51" in calm.inner_text("#tcCap")
    soon = at(app, "16:05").page
    assert "soon" in soon.locator("#tcCap").get_attribute("class")
    go = at(app, "16:18").page
    assert "go" in go.locator("#tcCap").get_attribute("class")
    assert "Пора" in go.inner_text("#tcCap")


def test_capsule_hidden_after_last_event(app):
    a = at(app, "23:50")
    assert a.page.locator("#tcCap").count() == 0


def test_segments_and_title(app):
    a = at(app, "13:24")
    segs = a.page.locator(".tc-seg")
    assert segs.count() == 11
    assert "done" in segs.nth(0).get_attribute("class") and "cur" in segs.nth(1).get_attribute("class")
    title = a.page.inner_text(".tc-title")
    assert "Вс 18 · 2/11" in title


def test_theme_by_sunset_and_override(app):
    assert at(app, "13:24").page.get_attribute("#today", "data-th") == "light"
    assert at(app, "19:30").page.get_attribute("#today", "data-th") == "dark"
    forced = at(app, "13:24", settings={"travelers": 2, "start": "2026-10-17", "cur": "KZT", "rate": 2.81, "theme": "dark"})
    assert forced.page.get_attribute("#today", "data-th") == "dark"


def test_theme_switches_on_tick(app):
    from datetime import datetime
    a = app(now="2026-10-18T16:55:00+09:00")          # live: day 2, just before sunset (~17:07)
    assert a.page.get_attribute("#today", "data-th") == "light"
    a.page.clock.set_fixed_time(datetime.fromisoformat("2026-10-18T17:30:00+09:00"))
    a.page.evaluate("window.dispatchEvent(new Event('japan2026:tick'))")
    assert a.page.get_attribute("#today", "data-th") == "dark"
