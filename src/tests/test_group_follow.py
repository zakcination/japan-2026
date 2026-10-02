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
