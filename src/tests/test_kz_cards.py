"""«Степной след» in the stop sheet: facts from the map payload, games inline, spot ticks shared with the map."""
import json
import pathlib

from test_day import marks  # noqa: F401  (kept next to the other «День» helpers)

ROOT = pathlib.Path(__file__).resolve().parents[2]
OURS = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
KEY = "japan2026.kzdone.v1"


def open_stop(app, day, eid):
    a = app(trip=OURS, state={"prevDay": day, "prevTime": "06:00"})
    a.page.click(".tc-tab[data-tab='day']")
    a.page.locator(f".tc-item[data-id='{eid}'] .tc-open").click()
    a.page.wait_for_selector("#tcSheet .tc-sheet")
    return a


def map_count(page, label):
    return page.evaluate("l => DATA.places.find(p => p.label === l).kz.length", label)


def test_section_collapsed_with_count_and_illustration(app):
    a = open_stop(app, 4, "d4e2")                                   # Fushimi Inari
    n = map_count(a.page, "Fushimi Inari Taisha")
    kz = a.page.locator("#tcSheet details.tc-kz")
    assert kz.count() == 1 and kz.get_attribute("open") is None
    assert f"Степной след · {n}" in kz.locator("summary").inner_text()
    assert not a.page.locator("#tcSheet .tc-kzimg").first.is_visible()
    kz.locator("summary").click()
    img = a.page.locator("#tcSheet .tc-kzimg")
    assert img.count() == 1 and img.get_attribute("src").startswith("data:image/webp")
    box = a.page.locator("#tcSheet .tc-kzbody")
    assert box.locator(".tc-kzi, .tc-kzg").count() == n
    assert box.locator(".tc-kzlvl").count() >= 5
    srcs = box.locator("a.tc-kzsrc")
    for i in range(srcs.count()):
        assert srcs.nth(i).get_attribute("target") == "_blank" and "noopener" in srcs.nth(i).get_attribute("rel")
        assert srcs.nth(i).get_attribute("href").startswith("https://")
    for b in a.page.locator("#tcSheet .tc-kzbody button, #tcSheet .tc-kzspot").all():
        assert b.bounding_box()["height"] >= 44
    assert a.errors == []


def test_stop_without_facts_has_no_section(app):
    a = open_stop(app, 4, "d4e0")
    assert a.page.locator("#tcSheet details.tc-kz").count() == 0


def test_tf_game_reveals(app):
    a = open_stop(app, 7, "d7e0")                                   # Senso-ji: a «верю / не верю»
    a.page.locator("#tcSheet .tc-kz summary").click()
    g = a.page.locator("#tcSheet .tc-kzg", has=a.page.locator("[data-kzans='1']"))
    assert not g.locator(".tc-kzrev").is_visible()
    g.locator("[data-kzans='1']").click()
    rev = g.locator(".tc-kzrev")
    assert rev.is_visible() and rev.inner_text().startswith(("Верно", "Не совсем"))
    assert g.locator("[data-kzans]").first.is_disabled()
    assert a.errors == []


def test_guess_game_reveals(app):
    a = open_stop(app, 4, "d4e2")
    a.page.locator("#tcSheet .tc-kz summary").click()
    g = a.page.locator("#tcSheet .tc-kzg", has=a.page.locator("[data-kzans='0']"))
    g.locator("[data-kzans='0']").click()
    assert "Ответ:" in g.locator(".tc-kzrev").inner_text()


def test_spot_tick_persists_and_shares_the_map_key(app):
    a = open_stop(app, 4, "d4e2")
    sid = a.page.evaluate("DATA.places.find(p => p.label === 'Fushimi Inari Taisha').kz.find(f => f.game && f.game.type === 'spot').game.id")
    a.page.locator("#tcSheet .tc-kz summary").click()
    a.page.locator("#tcSheet [data-kzspot]").check()
    stored = json.loads(a.page.evaluate(f"localStorage.getItem('{KEY}')"))
    assert sid in stored
    a.page.reload()
    a.page.wait_for_selector("#today", state="attached")
    a.page.click(".tc-tab[data-tab='day']")
    a.page.locator(".tc-item[data-id='d4e2'] .tc-open").click()
    a.page.locator("#tcSheet .tc-kz summary").click()
    assert a.page.locator("#tcSheet [data-kzspot]").is_checked()
    # the map reads the same key: its bingo counter sees the tick
    assert a.page.evaluate("kzSpotTasks().filter(t => KZ_DONE[t.g.id]).length") >= 1
    assert a.errors == []


def test_hostile_strings_stay_text(app):
    a = app(trip=OURS, state={"prevDay": 4, "prevTime": "06:00"})
    a.page.evaluate("""() => {
      const f = DATA.places.find(p => p.label === 'Fushimi Inari Taisha').kz;
      f[0].title = '<img src=x onerror="window.__pwn=1">T'; f[0].text = '<script>window.__pwn=2<\\/script><b>x</b>';
      f[0].src = 'javascript:window.__pwn=3';
      f[1].src = 'https://x.test/"><img src=x onerror=window.__pwn=4>';
    }""")
    a.page.click(".tc-tab[data-tab='day']")
    a.page.locator(".tc-item[data-id='d4e2'] .tc-open").click()
    a.page.locator("#tcSheet .tc-kz summary").click()
    body = a.page.locator("#tcSheet .tc-kzbody")
    assert "<img src=x" in body.inner_text() and "<script>" in body.inner_text()
    assert body.locator("img[src='x'], script, p b").count() == 0
    assert body.locator("a[href^='javascript']").count() == 0
    a.page.wait_for_timeout(200)
    assert a.page.evaluate("window.__pwn") is None
    assert a.errors == []
