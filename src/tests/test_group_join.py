from conftest import until
from fake_supabase import FakeSupabase
from test_group_api import GROUPED


def logged(app, fake, member, pin, **kw):
    a = app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24", **kw.pop("state", {})}, supabase=fake, **kw)
    a.page.evaluate("localStorage.setItem('japan2026.loginasked.v1', '1')")
    look = a.page.locator("#grJustLook")
    if look.count() and look.is_visible():
        look.click()
    assert a.page.evaluate(f"Api.login('{member}', '{pin}')")["ok"]
    a.page.evaluate("renderShell()")
    return a


def test_guest_joins_fuji_and_her_day_is_her_schedule(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='day']")
    assert "Свободный день" in g.page.inner_text("#todayBody")        # nothing joined yet
    g.page.click("#grView [data-view='group']")
    g.page.click("#grJoinPart")                                      # «Я с вами: Фудзи / Кавагутико»
    g.page.click("#grView [data-view='mine']")
    items = g.page.locator(".tc-item")
    assert items.count() == 10 and "Oishi Park" in g.page.inner_text("#tcList")
    assert "Мисима → Киото" not in g.page.inner_text("#tcList")
    h = logged(app, fake, fake.host_id, fake.host_pin)
    h.page.click(".tc-tab[data-tab='day']")
    h.page.click("#grView [data-view='group']")
    until(h.page, "document.querySelector('[data-part=\"fuji\"]').textContent.includes('С')")


def test_opt_out_of_the_boat_and_own_stop_on_a_free_day(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    g = logged(app, fake, san, "4821")
    g.page.evaluate("Api.call('set_join', {p_scope:'part', p_ref:'fuji', p_mode:'in'}, s => s.joins.push({member: Api.me().id, scope:'part', ref:'fuji', mode:'in'}))")
    g.page.click(".tc-tab[data-tab='day']")
    g.page.locator(".tc-item", has_text="Катер").locator(".tc-open").click()
    g.page.click("#tcSheet [data-join='out']")
    assert "Катер" not in g.page.inner_text("#tcList")
    g.page.click(".tc-daypick >> nth=2")                              # 19.10 — not with the group
    g.page.click("#tcAdd")
    g.page.fill("#edT", "Осака: Dotonbori"); g.page.fill("#edS", "10:00"); g.page.fill("#edE", "14:00")
    g.page.click("#edSave")
    assert "Осака: Dotonbori" in g.page.inner_text("#tcList")
    until(g.page, "Api.status().pending === 0")
    assert any(s["ev"]["t"] == "Осака: Dotonbori" and not s["shared"] for s in fake.my_stops.values())


def test_shared_own_stop_can_be_joined_by_another(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest"); am = fake._add("Аманжан", "guest")
    fake.my_stops["m-dt"] = {"id": "m-dt", "member": san, "day": 3, "ev": {"s": "10:00", "e": "14:00", "t": "Осака: Dotonbori"}, "shared": True}
    b = logged(app, fake, am, "1357")
    b.page.click(".tc-tab[data-tab='day']")
    b.page.click(".tc-daypick >> nth=2")
    b.page.click("#grView [data-view='group']")
    b.page.locator(".tc-item", has_text="Dotonbori").locator(".tc-open").click()
    assert "Сания" in b.page.inner_text("#tcSheet")
    b.page.click("#tcSheet [data-joinmine]")
    b.page.click("#grView [data-view='mine']")
    assert "Dotonbori" in b.page.inner_text("#tcList")


def test_host_moves_a_stop_and_the_guest_sees_it(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "fuji", "mode": "in"})
    h = logged(app, fake, fake.host_id, fake.host_pin)
    h.page.click(".tc-tab[data-tab='day']")
    h.page.click("#grView [data-view='group']")
    h.page.locator(".tc-item", has_text="Oishi Park").locator(".tc-open").click()
    h.page.click("#tcSheet [data-edit]")
    h.page.fill("#edS", "13:30"); h.page.click("#edSave")
    until(h.page, "Api.status().pending === 0")
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='day']")
    assert "13:30" in g.page.locator(".tc-item", has_text="Oishi Park").inner_text()


def test_overlap_warning(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "fuji", "mode": "in"})
    fake.my_stops["m-x"] = {"id": "m-x", "member": san, "day": 2, "ev": {"s": "13:30", "e": "14:30", "t": "Свой обед"}, "shared": False}
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='day']")
    row = g.page.locator(".tc-item:has(.tc-ititle:text-is('Свой обед'))")
    assert "пересекается с Oishi Park" in row.inner_text()


def test_unshared_stop_disappears_for_others_without_errors(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest"); am = fake._add("Аманжан", "guest")
    fake.my_stops["m-dt"] = {"id": "m-dt", "member": san, "day": 3, "ev": {"s": "10:00", "e": "14:00", "t": "Осака: Dotonbori"}, "shared": True}
    fake.joins.append({"member": am, "scope": "mine", "ref": "m-dt", "mode": "in"})
    b = logged(app, fake, am, "1357")
    b.page.click(".tc-tab[data-tab='day']"); b.page.click(".tc-daypick >> nth=2")
    assert "Dotonbori" in b.page.inner_text("#tcList")
    fake.my_stops["m-dt"]["shared"] = False
    b.page.evaluate("Api.refresh().then(() => renderShell())")
    until(b.page, "!document.getElementById('tcList') || !document.getElementById('tcList').textContent.includes('Dotonbori')")
    assert b.errors == []


def test_not_logged_in_is_unchanged(app):
    a = app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24"}, supabase=FakeSupabase.seeded())
    a.page.click("#grJustLook")
    a.page.click(".tc-tab[data-tab='day']")
    assert a.page.locator("#grView").count() == 0 and a.page.locator(".tc-item").count() == 13
