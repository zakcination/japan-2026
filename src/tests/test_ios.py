"""iPhone extras: the .ics builder, Apple Maps, Calendar sheet, screen kept on at «Пора выходить», install hint."""
import re

from conftest import IPHONE_UA

WAKE = """
window.__wake = { req: 0, rel: 0 };
Object.defineProperty(navigator, 'wakeLock', { configurable: true, value: {
  request: () => { __wake.req++; return Promise.resolve({ release: () => { __wake.rel++; return Promise.resolve(); } }); } } });
"""


def unfold(txt):
    return txt.replace("\r\n ", "")


def test_ics_is_valid_and_alarms_at_leave_time(core):
    pg = core(("core.js", "ios.js"))
    txt = pg.evaluate("""Ios.ics({ name: 'Япония', dateISO: '2026-10-18', stamp: '20260929T120000Z', seq: 3, events: [
      { id: 'd2e9', t: 'Кавагутико → Мисима', ns: 17 * 60, ne: 18 * 60 + 40, leave: 16 * 60 + 15,
        loc: 'Kawaguchiko Sta. → Mishima Sta.', note: 'Купить билет; взять воду, перекус\\nВторая строка ' + 'длинная '.repeat(20) },
      { id: 'late', t: 'Ночной конбини', ns: 23 * 60 + 50, ne: 24 * 60 + 20 } ] })""")
    lines = txt.split("\r\n")
    assert txt.endswith("\r\n") and "\n" not in txt.replace("\r\n", "")
    assert all(len(l.encode()) <= 75 for l in lines)
    assert any(l.startswith(" ") for l in lines)               # the long note was folded
    u = unfold(txt)
    assert "BEGIN:VTIMEZONE\r\nTZID:Asia/Tokyo" in u
    assert u.count("BEGIN:VEVENT") == 2 and u.count("BEGIN:VALARM") == 2
    assert "UID:d2e9@japan-2026" in u and "SEQUENCE:3" in u
    assert "DTSTART;TZID=Asia/Tokyo:20261018T170000" in u and "DTEND;TZID=Asia/Tokyo:20261018T184000" in u
    assert "TRIGGER:-PT45M" in u and "Пора выходить: Кавагутико → Мисима" in u
    assert "DESCRIPTION:Купить билет\\; взять воду\\, перекус\\nВторая строка" in u
    assert "DTEND;TZID=Asia/Tokyo:20261019T002000" in u      # past midnight rolls to the next date
    assert "TRIGGER:-PT10M" in u


def test_fold_never_splits_a_character(core):
    pg = core(("core.js", "ios.js"))
    out = pg.evaluate("Ios.fold('SUMMARY:' + 'ё'.repeat(80))")
    parts = out.split("\r\n")
    assert all(len(p.encode()) <= 75 for p in parts)
    assert unfold(out) == "SUMMARY:" + "ё" * 80


def test_apple_route_and_ios_detection(core):
    pg = core(("core.js", "ios.js"))
    assert pg.evaluate("Ios.appleRoute({lat: 35.52, lng: 138.75})") == "https://maps.apple.com/?daddr=35.52,138.75&dirflg=r"
    assert "daddr=Oishi%20Park%20Japan" in pg.evaluate("Ios.appleRoute({lat: 'x\"', lng: 1, pname: 'Oishi Park'})")
    assert pg.evaluate(f"Ios.isIOS({IPHONE_UA!r}, 'iPhone', 5)") is True
    assert pg.evaluate("Ios.isIOS('Mozilla/5.0 (Macintosh)', 'MacIntel', 5)") is True     # iPad as desktop
    assert pg.evaluate("Ios.isIOS('Mozilla/5.0 (X11; Linux)', 'Linux', 0)") is False


def test_iphone_gets_apple_maps_and_calendar_sheet(app):
    a = app(state={"prevDay": 2, "prevTime": "13:24"}, ua=IPHONE_UA)
    a.page.click(".tc-tab[data-tab='day']")
    a.page.click(".tc-item.now .tc-open")
    s = a.page.locator("#tcSheet")
    assert "Apple Картах" in s.inner_text()
    assert s.locator("a[href^='https://maps.apple.com/?daddr=']").count() == 1
    s.locator("[data-cal]").click()
    assert "В Календарь" in s.inner_text()
    rows = s.locator("#tcCal .tc-calrow")
    assert rows.count() >= 8
    oishi = s.locator("#tcCal .tc-calrow", has_text="Oishi Park").inner_text()
    assert "13:00" in oishi and "12:30" in oishi
    assert "Календарь iPhone" in s.inner_text()


def test_desktop_downloads_ics(app):
    a = app(state={"prevDay": 2, "prevTime": "13:24"})
    a.page.click(".tc-tab[data-tab='day']")
    a.page.click(".tc-item.now .tc-open")
    a.page.click("#tcSheet [data-cal]")
    with a.page.expect_download() as d:
        a.page.click("#tcCalGo")
    body = open(d.value.path(), encoding="utf-8").read()
    assert body.startswith("BEGIN:VCALENDAR") and "UID:d2e7@japan-2026" in unfold(body)


def test_screen_stays_on_while_it_is_time_to_leave(app):
    a = app(state={"prevDay": 2, "prevTime": "16:18"})
    a.page.evaluate(WAKE)
    a.page.evaluate("window.dispatchEvent(new Event('japan2026:tick'))")
    a.page.wait_for_function("__wake.req === 1")
    a.page.click(".tc-tab[data-tab='day']")
    a.page.wait_for_function("__wake.rel === 1")


def test_install_hint_only_in_iphone_safari_and_hides_for_good(app):
    a = app(state={"prevDay": 2, "prevTime": "13:24"})
    assert a.page.locator("#tcInstall").count() == 0
    a = app(state={"prevDay": 2, "prevTime": "13:24"}, ua=IPHONE_UA)
    hint = a.page.locator("#tcInstall")
    assert hint.is_visible() and "На экран" in hint.inner_text()
    assert a.page.locator("#tcInstallX").bounding_box()["height"] >= 44
    a.page.click("#tcInstallX")
    assert a.page.locator("#tcInstall").count() == 0
    a.page.reload()
    a.page.wait_for_selector(".tc-tab")
    assert a.page.locator("#tcInstall").count() == 0
