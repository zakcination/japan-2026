"""«Ехать вместе с»: follow anyone's personal plan, the whole trip or chosen days; own choices still win."""
import json
from conftest import ROOT, until
from fake_supabase import FakeSupabase
from test_group_join import logged
from test_group_model import state, ev, TRIP, S, H

A = "a-1"


def st(**kw):
    s = state(**kw); s["members"] = s["members"] + [{"id": A, "name": "Aman", "role": "guest"}]; return s


def test_follow_whole_trip_by_day_own_choice_wins_and_no_loops(core):
    pg = core(("core.js", "group/model.js"))
    js = [{"member": A, "scope": "part", "ref": "fuji", "mode": "in"}, {"member": A, "scope": "part", "ref": "kyoto", "mode": "in"},
          {"member": S, "scope": "follow", "ref": A, "mode": "in"},                       # Saniya follows Aman everywhere
          {"member": S, "scope": "follow", "ref": A + ":3", "mode": "out"},               # …but not on day 3
          {"member": S, "scope": "stop", "ref": "d2e3", "mode": "out"}]                   # and skips one stop herself
    r = ev(pg, f"""const st = {json.dumps(st(joins=js))};
      const a = Group.effective(P, st, '{A}'), s = Group.effective(P, st, '{S}');
      const d = n => P.days.find(x => x.n === n).ev.map(e => e.id);
      return {{ a2: d(2).filter(i => a.has(i)).length, s2: d(2).filter(i => s.has(i)), s3: d(3).filter(i => s.has(i)).length, a3: d(3).filter(i => a.has(i)).length }};""")
    assert r["a2"] > 0 and "d2e3" not in r["s2"] and len(r["s2"]) == r["a2"] - 1
    assert r["a3"] > 0 and r["s3"] == 0
    loop = js + [{"member": A, "scope": "follow", "ref": S, "mode": "in"}]                # following each other must not hang
    n = ev(pg, f"const st = {json.dumps(st(joins=loop))}; return [Group.effective(P, st, '{A}').size, Group.effective(P, st, '{S}').size];")
    assert all(isinstance(x, int) for x in n)


def test_followed_persons_shared_stops_come_along_private_ones_do_not(core):
    pg = core(("core.js", "group/model.js"))
    stops = [{"id": "m-1", "member": A, "day": 7, "shared": True, "ev": {"s": "10:00", "e": "11:00", "t": "Кофе"}},
             {"id": "m-2", "member": A, "day": 7, "shared": False, "ev": {"s": "12:00", "e": "13:00", "t": "Личное"}}]
    js = [{"member": S, "scope": "follow", "ref": A + ":7", "mode": "in"}]
    r = ev(pg, f"""const st = {json.dumps(st(joins=js, my_stops=stops))};
      const t = Group.personalTrip(P, st, '{S}');
      return t.days.find(d => d.n === 7).ev.filter(e => e.from === 'mine').map(e => e.t);""")
    assert r == ["Кофе"]


def test_saniya_follows_aman_in_settings_and_gets_his_tickets(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest"); aman = fake._add("Aman", "guest")
    fake.joins.append({"member": aman, "scope": "part", "ref": "fuji", "mode": "in"})
    g = logged(app, fake, san, "4821")
    g.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1')")
    g.page.click("#tcGear")
    g.page.click(f"#grFollow [data-follow='{aman}']")
    g.page.locator("#flAll").check()
    until(g.page, "Api.status().pending === 0")
    assert {"member": san, "scope": "follow", "ref": aman, "mode": "in"} in fake.joins
    g.page.keyboard.press("Escape")
    g.page.click(".tc-tab[data-tab='tix']")
    until(g.page, "!!document.querySelector('#grTasks [data-ref=\"bk:bus18\"]')")      # his Fuji bus is now hers to buy
    r = g.page.evaluate("Api.run('set_join', {p_scope: 'follow', p_ref: Api.me().id, p_mode: 'in'}).then(() => 'ok', e => e.message)")
    assert "bad join" in r                                                            # nobody follows themselves


def test_pick_a_face_in_settings_and_the_group_sees_it_instead_of_a_letter(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "fuji", "mode": "in"})
    g = logged(app, fake, san, "4821")
    g.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1')")
    g.page.click("#tcGear")
    b = g.page.locator("#grFaces [data-face='🦊']")
    assert b.bounding_box()["height"] >= 44
    b.click()
    until(g.page, "Api.status().pending === 0")
    assert fake.members[san]["emoji"] == "🦊"
    r = g.page.evaluate("Api.run('set_emoji', {p_emoji: '<img src=x>'}).then(() => 'ok', e => e.message)")
    assert "bad emoji" in r                                                            # only the app's own faces
    h = logged(app, fake, fake.host_id, fake.host_pin)
    h.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1')")
    h.page.click(".tc-tab[data-tab='day']")
    h.page.click("#grView [data-view='group']")
    chip = h.page.locator("[data-part='fuji'] .tc-faces")
    assert "🦊" in chip.inner_text() and chip.locator(".tc-face").first.bounding_box()["height"] <= 26


def test_see_amans_own_route_in_detail_read_only_then_follow(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest"); aman = fake._add("Aman", "guest")
    fake.joins += [{"member": aman, "scope": "part", "ref": "fuji", "mode": "in"},
                   {"member": aman, "scope": "stop", "ref": "d2e3", "mode": "out"}]               # he skips one stop
    fake.my_stops["m-a1"] = {"id": "m-a1", "member": aman, "day": 2, "shared": True, "ev": {"s": "15:00", "e": "16:00", "t": "Онсэн у озера"}}
    fake.my_stops["m-a2"] = {"id": "m-a2", "member": aman, "day": 2, "shared": False, "ev": {"s": "16:30", "e": "17:00", "t": "Личное"}}
    g = logged(app, fake, san, "4821")
    g.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1')")
    g.page.click(".tc-tab[data-tab='day']")
    g.page.click(f"#grPeople [data-person='{aman}']")
    t = g.page.inner_text("#tcList")
    assert "Онсэн у озера" in t and "Личное" not in t and "Oishi Park" in t
    ids = g.page.evaluate("[...document.querySelectorAll('#tcList .tc-item')].map(i => i.dataset.id)")
    assert "d2e3" not in ids and "m-a1" in ids
    assert "только просмотр" in g.page.inner_text(".tc-person-note")
    g.page.locator(".tc-item[data-id='m-a1'] .tc-open").click()
    assert g.page.locator("#tcSheet [data-edit]").count() == 0                         # nothing of his is editable
    g.page.keyboard.press("Escape")
    g.page.click("[data-follow-from-day]")
    assert g.page.locator("#flAll").is_visible()
    g.page.keyboard.press("Escape")
    g.page.click(".tc-tab[data-tab='now']"); g.page.click(".tc-tab[data-tab='day']")
    g.page.click("#grBackMine")
    assert "Онсэн у озера" not in g.page.inner_text("#tcList")                         # back to her own plan


def test_face_shows_what_is_saved_and_says_when_it_was_not(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    g = logged(app, fake, san, "4821")
    g.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1')")
    g.page.click("#tcGear")
    assert "не выбран" in g.page.inner_text("#grFaceNow")
    g.page.click("#grFaces [data-face='🐼']")
    until(g.page, "/🐼 · сохранено/.test(document.getElementById('grFaceNow').textContent)")
    fake.rpc_set_emoji = None                                                        # the server without the update: «no such function»
    g.page.click("#grFaces [data-face='🦊']")
    until(g.page, "/Не сохранилось/.test(document.getElementById('grFaceNow').textContent)")
    assert g.page.locator("#grFaces [aria-checked='true']").get_attribute("data-face") == "🐼"


def test_show_my_whole_plan_to_the_group_in_one_switch(app):
    fake = FakeSupabase.seeded(); aman = fake._add("Aman", "guest")
    for i in range(3):
        fake.my_stops[f"m-o{i}"] = {"id": f"m-o{i}", "member": aman, "day": 4, "shared": False, "ev": {"s": f"1{i}:00", "e": f"1{i}:30", "t": f"Осака {i}"}}
    a = logged(app, fake, aman, "4821")
    a.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1')")
    a.page.click("#tcGear")
    assert "скрыто: 3" in a.page.inner_text(".tc-shareall")
    a.page.locator("#grShareAll").check()
    until(a.page, "Api.status().pending === 0")
    assert all(s["shared"] for s in fake.my_stops.values())
    assert a.page.evaluate("localStorage.getItem('japan2026.shareall.v1')") == aman   # new stops will be shared too
    assert a.page.locator("#grShareAll").is_checked() and "все 3" in a.page.inner_text(".tc-shareall")


def test_join_someone_by_day_and_pick_single_places(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest"); aman = fake._add("Aman", "guest")
    fake.my_stops["m-u1"] = {"id": "m-u1", "member": aman, "day": 5, "shared": True, "ev": {"s": "08:30", "e": "20:30", "t": "Universal Studios Japan"}}
    fake.my_stops["m-u2"] = {"id": "m-u2", "member": aman, "day": 5, "shared": True, "ev": {"s": "21:00", "e": "22:00", "t": "Ужин в Намбе"}}
    g = logged(app, fake, san, "4821")
    g.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1')")
    g.page.click("#tcGear"); g.page.click(f"#grFollow [data-follow='{aman}']")
    day = g.page.locator(".tc-fday[data-fdn='5']")
    assert "с вами 0 из 2" in day.inner_text()
    day.locator("summary > span").click()                                             # open the day, pick one place
    day.locator("[data-flstop='m-u1']").check()
    until(g.page, "Api.status().pending === 0")
    assert {"member": san, "scope": "mine", "ref": "m-u1", "mode": "in"} in fake.joins
    day = g.page.locator(".tc-fday[data-fdn='5']")
    assert "с вами 1 из 2" in day.inner_text() and day.get_attribute("open") is not None   # stays open where you were
    day.locator("[data-flday='5']").check()                                           # then the whole day…
    until(g.page, "Api.status().pending === 0")
    assert "с вами 2 из 2" in g.page.locator(".tc-fday[data-fdn='5']").inner_text()
    g.page.locator(".tc-fday[data-fdn='5'] [data-flstop='m-u2']").uncheck()           # …except dinner
    until(g.page, "Api.status().pending === 0")
    assert "с вами 1 из 2" in g.page.locator(".tc-fday[data-fdn='5']").inner_text()
