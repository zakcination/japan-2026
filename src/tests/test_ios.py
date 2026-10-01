"""iPhone extras: the .ics builder, Apple Maps, Calendar sheet, screen kept on at «Пора выходить», install hint."""
import re

from conftest import IPHONE_UA, until

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
    assert s.locator("a[href^='https://maps.apple.com/?daddr='][href$='dirflg=r']").count() == 1          # transit
    assert s.locator("a[href^='https://maps.apple.com/?daddr='][href$='dirflg=w']").count() == 1          # «Пешком»
    s.locator("[data-cal]").click()
    assert "В Календарь" in s.inner_text()
    rows = s.locator("#tcCal .tc-calrow")
    assert rows.count() >= 8
    bus = s.locator("#tcCal .tc-calrow", has_text="Кавагутико → Мисима").inner_text()
    assert "17:00" in bus and "16:15" in bus                      # a departure: alarm at leave time
    oishi = s.locator("#tcCal .tc-calrow", has_text="Oishi Park").inner_text()
    assert "13:00" in oishi and "12:30" not in oishi              # a sight: no alarm
    assert s.locator("#tcCal .tc-calrow em svg").count() < rows.count()
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
    a.page.click(".tc-tab[data-tab='day']")
    a.page.click(".tc-tab[data-tab='now']")
    until(a.page, "__wake.req === 1")
    a.page.click(".tc-tab[data-tab='day']")
    until(a.page, "__wake.rel === 1")


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


def test_ics_escapes_a_lone_carriage_return(core):
    pg = core(("core.js", "ios.js"))
    txt = pg.evaluate("""() => Ios.ics({ name: 'x', dateISO: '2026-10-18', stamp: '20260929T120000Z', events: [
      { id: 'a', t: 'Стоп' + String.fromCharCode(13) + 'ATTENDEE:mailto:x@y', ns: 600, ne: 660 } ] })""")
    lines = txt.split("\r\n")
    assert not any(l.startswith("ATTENDEE") for l in lines)
    assert "\r" not in txt.replace("\r\n", "")
    assert "SUMMARY:Стоп\\nATTENDEE:mailto:x@y" in txt


SLOW_WAKE = """
window.__wake = { active: 0, req: 0, locks: [] };
Object.defineProperty(navigator, 'wakeLock', { configurable: true, value: {
  request: () => new Promise(res => setTimeout(() => {
    __wake.active++; __wake.req++;
    const l = { released: false, h: [], addEventListener(t, f) { this.h.push(f); },
      release() { if (!this.released) { this.released = true; __wake.active--; this.h.forEach(f => f()); } return Promise.resolve(); } };
    __wake.locks.push(l); res(l);
  }, 60)) } });
"""


def test_quick_renders_never_leak_a_wake_lock_and_it_comes_back_after_unlock(app):
    a = app(state={"prevDay": 2, "prevTime": "16:18"})
    a.page.evaluate(SLOW_WAKE)
    a.page.click(".tc-tab[data-tab='day']")
    a.page.click(".tc-tab[data-tab='now']")
    for _ in range(3):
        a.page.evaluate("window.dispatchEvent(new Event('japan2026:tick'))")
    a.page.wait_for_timeout(400)
    assert a.page.evaluate("__wake.active") == 1
    # Safari drops the lock when the phone locks; back on the page it is taken again
    a.page.evaluate("__wake.locks.at(-1).release(); document.dispatchEvent(new Event('visibilitychange'))")
    a.page.wait_for_timeout(300)
    assert a.page.evaluate("__wake.active") == 1 and a.page.evaluate("__wake.req") == 2
    a.page.click(".tc-tab[data-tab='day']")
    a.page.wait_for_timeout(300)
    assert a.page.evaluate("__wake.active") == 0
