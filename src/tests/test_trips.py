"""Trips as files: ?trip=<id>, network first with an offline copy, local edits win, hostile files do nothing."""
import json
import re

from playwright.sync_api import expect

from conftest import ROOT

OURS = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
NIGHT = {"prevDay": 2, "prevTime": "13:24"}


def fulfil(trip):
    body = json.dumps(trip, ensure_ascii=False)
    return lambda route: route.fulfill(status=200, content_type="application/json", body=body)


def abort(route):
    route.abort()


def settings_text(a):
    a.page.click("#tcGear")
    t = a.page.inner_text("#tcSheet")
    a.page.keyboard.press("Escape")
    return t


def test_link_opens_our_trip_and_is_remembered(app, site):
    a = app(state=NIGHT, url=site, url_suffix="?trip=miras-aikosh")
    expect(a.page).to_have_title(re.compile('Мирас'))
    a.page.click(".tc-tab[data-tab='tix']")
    assert "MU575" in a.page.text_content("#todayBody")
    assert "версия от" in settings_text(a)
    a.page.goto(site)                                   # no ?trip= any more
    expect(a.page).to_have_title(re.compile('Мирас'))
    assert a.errors == []


def test_no_network_uses_the_saved_copy(app, site):
    a = app(state=NIGHT, url=site, url_suffix="?trip=miras-aikosh")
    expect(a.page).to_have_title(re.compile('Мирас'))
    a.page.route("**/trips/*.json", abort)
    a.page.reload()
    a.page.wait_for_selector(".tc-tab")
    assert "Мирас" in a.page.title()
    a.page.wait_for_timeout(300)
    assert "без сети" in settings_text(a)


def test_first_open_without_network_shows_the_template(app, site):
    a = app(state=NIGHT, url=site, url_suffix="?trip=miras-aikosh", routes={"**/trips/*.json": abort})
    a.page.wait_for_timeout(400)
    assert "шаблон" in a.page.title()
    assert "ещё не загружена" in settings_text(a)


def test_a_newer_shared_version_arrives_and_keeps_marks(app, site):
    a = app(state=NIGHT, url=site, url_suffix="?trip=miras-aikosh")
    expect(a.page).to_have_title(re.compile('Мирас'))
    a.page.click(".tc-tab[data-tab='day']")
    a.page.locator(".tc-item >> nth=3 >> .tc-check").click()
    newer = dict(OURS, name="Мирас и Айкош · обновлено", updated="2026-10-01T09:30+05:00")
    a.page.route("**/trips/miras-aikosh.json", fulfil(newer))
    a.page.reload()
    expect(a.page).to_have_title(re.compile('обновлено'))
    marks = json.loads(a.page.evaluate("localStorage.getItem('japan2026.today.v1')"))
    assert marks["done"] == {"d2e3": True}
    assert "01.10" in settings_text(a)


def test_local_edits_win_until_back_to_shared(app, site):
    a = app(state=NIGHT, url=site, url_suffix="?trip=miras-aikosh")
    expect(a.page).to_have_title(re.compile('Мирас'))
    a.page.click("#tcGear")
    a.page.fill("#setName", "Наша правка")
    a.page.click("#setSave")
    a.page.route("**/trips/miras-aikosh.json", fulfil(dict(OURS, name="С сервера")))
    a.page.reload()
    a.page.wait_for_selector(".tc-tab")
    a.page.wait_for_timeout(300)
    assert a.page.title() == "Наша правка"
    a.page.click("#tcGear")
    assert "свои правки" in a.page.inner_text("#tcSheet")
    assert a.page.is_disabled("#setTrip")
    a.page.click("#setReset")
    a.page.click("#setReset")
    expect(a.page).to_have_title("С сервера")


def test_hostile_or_broken_trip_file_is_ignored_or_escaped(app, site):
    evil = '<img src=x onerror="window.__pwned=1">'
    bad = {"days": "nope"}
    a = app(state=NIGHT, url=site, url_suffix="?trip=miras-aikosh", routes={"**/trips/*.json": fulfil(bad)})
    a.page.wait_for_timeout(400)
    assert "шаблон" in a.page.title()
    hostile = dict(OURS, name=evil)
    hostile["days"] = [dict(OURS["days"][1], n=2, label=evil, ev=[dict(e, t=evil, lat='1" onclick="window.__pwned=1')
                                                                 for e in OURS["days"][1]["ev"]])]
    hostile["bookings"] = [dict(b, t=evil, when=evil) for b in OURS["bookings"]]
    a.page.unroute("**/trips/*.json")
    a.page.route("**/trips/*.json", fulfil(hostile))
    a.page.reload()
    expect(a.page).to_have_title(re.compile('onerror'))
    for t in ("now", "day", "tix", "stats", "day"):
        a.page.click(f".tc-tab[data-tab='{t}']")
    a.page.click(".tc-item .tc-open >> nth=0")
    assert a.page.evaluate("window.__pwned") is None
    assert a.page.locator("[onclick], [onerror]").count() == 0
    assert a.errors == []


def test_unknown_trip_id_is_ignored(app, site):
    a = app(state=NIGHT, url=site, url_suffix="?trip=..%2F..%2Fetc%2Fpasswd")
    a.page.wait_for_timeout(300)
    assert "шаблон" in a.page.title()
    assert a.page.evaluate("localStorage.getItem('japan2026.tripid.v1')") is None


def test_switch_trip_in_settings_resets_marks(app, site):
    a = app(state={**NIGHT, "done": {"d2e3": True}}, url=site)
    assert "шаблон" in a.page.title()
    a.page.click("#tcGear")
    a.page.select_option("#setTrip", "miras-aikosh")
    expect(a.page).to_have_title(re.compile('Мирас'))
    marks = json.loads(a.page.evaluate("localStorage.getItem('japan2026.today.v1')"))
    assert marks["done"] == {}


def test_csp_blocks_foreign_scripts_but_not_the_app(app, site):
    a = app(state=NIGHT, url=site, url_suffix="?trip=miras-aikosh")
    a.page.evaluate("window.__csp = []; document.addEventListener('securitypolicyviolation', e => __csp.push(e.violatedDirective + ' ' + e.blockedURI))")
    for t in ("now", "day", "tix", "stats"):
        a.page.click(f".tc-tab[data-tab='{t}']")
    a.page.click("#tcGear")
    a.page.keyboard.press("Escape")
    assert a.page.evaluate("__csp") == []
    a.page.evaluate("""() => { const s = document.createElement('script'); s.src = 'https://example.com/x.js'; document.head.appendChild(s); }""")
    a.page.wait_for_timeout(300)
    assert any("script-src" in v for v in a.page.evaluate("__csp"))
    assert a.errors == []


def test_switching_offline_to_a_trip_not_on_the_phone_changes_nothing(app, site):
    a = app(state={**NIGHT, "done": {"d2e3": True}}, url=site, routes={"**/trips/*.json": abort})
    a.page.click("#tcGear")
    a.page.select_option("#setTrip", "miras-aikosh")
    expect(a.page.locator("#setMsg")).to_contain_text("Нет сети")
    assert "шаблон" in a.page.title()
    assert json.loads(a.page.evaluate("localStorage.getItem('japan2026.today.v1')"))["done"] == {"d2e3": True}


def test_each_trip_keeps_its_own_offline_copy(app, site):
    a = app(state=NIGHT, url=site, url_suffix="?trip=miras-aikosh")
    expect(a.page).to_have_title(re.compile("Мирас"))
    a.page.click("#tcGear")
    a.page.select_option("#setTrip", "template")
    expect(a.page).to_have_title(re.compile("шаблон"))
    a.page.route("**/trips/*.json", abort)
    a.page.click("#tcGear")
    a.page.select_option("#setTrip", "miras-aikosh")
    expect(a.page).to_have_title(re.compile("Мирас"))


def test_organiser_changes_to_start_and_people_reach_the_phone(app, site):
    a = app(state=NIGHT, url=site, url_suffix="?trip=miras-aikosh")
    expect(a.page).to_have_title(re.compile("Мирас"))
    a.page.click("#tcGear")
    a.page.keyboard.press("Escape")
    a.page.route("**/trips/miras-aikosh.json", fulfil(dict(OURS, start="2026-10-18", travelers=3, name="Мирас +1")))
    a.page.reload()
    expect(a.page).to_have_title("Мирас +1")
    a.page.click(".tc-tab[data-tab='day']")
    assert "Пн 19" in a.page.inner_text(".tc-title")          # day 2 is now the 19th
    assert "¥630" in a.page.inner_text("#tcList").replace(" ", " ")
