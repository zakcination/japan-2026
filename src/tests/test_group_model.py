import json
from conftest import ROOT

TRIP = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
S, H = "s-1", "h-1"


def state(**kw):
    base = {"me": {"id": S, "role": "guest"}, "members": [{"id": H, "name": "Мирас", "role": "host"}, {"id": S, "name": "Сания", "role": "guest"}],
            "parts": TRIP["parts"], "joins": [], "recipes": TRIP["recipes"], "tasks": [], "my_stops": [], "my_bookings": [],
            "task_state": [], "attachments": []}
    base.update(kw); return base


def ev(pg, js):
    return pg.evaluate(f"(() => {{ const P = {json.dumps(TRIP)}; {js} }})()")


def test_part_join_with_opt_out_and_specific_rule_wins(core):
    pg = core(("core.js", "group/model.js"))
    st = state(joins=[{"member": S, "scope": "part", "ref": "fuji", "mode": "in"},
                      {"member": S, "scope": "stop", "ref": "d2e5", "mode": "out"},
                      {"member": S, "scope": "day", "ref": "3", "mode": "in"},
                      {"member": S, "scope": "stop", "ref": "d3e1", "mode": "out"}])
    got = set(ev(pg, f"return [...Group.effective(P, {json.dumps(st)}, '{S}')];"))
    assert "d2e3" in got and "d2e5" not in got and "d2e10" not in got
    assert "d3e0" in got and "d3e1" not in got
    hosts = set(ev(pg, f"return [...Group.effective(P, {json.dumps(state())}, '{H}')];"))
    assert len(hosts) == sum(len(d["ev"]) for d in TRIP["days"])       # hosts are in everything


def test_personal_trip_merges_own_and_shared_stops(core):
    pg = core(("core.js", "group/model.js"))
    st = state(joins=[{"member": S, "scope": "part", "ref": "fuji", "mode": "in"},
                      {"member": S, "scope": "mine", "ref": "m-h1", "mode": "in"}],
               my_stops=[{"id": "m-1", "member": S, "day": 3, "ev": {"s": "10:00", "e": "12:00", "t": "Осака: Dotonbori"}, "shared": False},
                         {"id": "m-h1", "member": H, "day": 3, "ev": {"s": "15:00", "e": "16:00", "t": "Кофе"}, "shared": True},
                         {"id": "m-h2", "member": H, "day": 3, "ev": {"s": "17:00", "e": "18:00", "t": "Не мой"}, "shared": True}])
    t = ev(pg, f"return Group.personalTrip(P, {json.dumps(st)}, '{S}');")
    d2 = next(d for d in t["days"] if d["n"] == 2); d3 = next(d for d in t["days"] if d["n"] == 3)
    assert [e["id"] for e in d2["ev"]][:2] == ["d2e0", "d2e1"] and all(e["from"] == "group" for e in d2["ev"])
    assert {e["t"] for e in d3["ev"]} == {"Осака: Dotonbori", "Кофе"}
    kofe = next(e for e in d3["ev"] if e["t"] == "Кофе")
    assert kofe["from"] == "mine" and kofe["sharedBy"] == "Мирас"
    assert [x["n"] for x in t["days"]] == list(range(1, 13))          # our trip has the Shanghai night (28.10)
    assert t["bookings"] == TRIP["bookings"]


def test_overlaps(core):
    pg = core(("core.js", "group/model.js"))
    pairs = pg.evaluate("Group.overlaps([{id:'a', s:'10:00', e:'12:00'}, {id:'b', s:'11:30', e:'13:00'}, {id:'c', s:'13:00', e:'14:00'}])")
    assert pairs == [["a", "b"]]


def test_tasks_follow_joins_and_sort_by_urgency(core):
    pg = core(("core.js", "group/model.js"))
    st = state(joins=[{"member": S, "scope": "part", "ref": "fuji", "mode": "in"}],
               task_state=[{"ref": "bk:bus_mishima", "done": True}],
               tasks=[{"id": "t-1", "title": "Оформить Suica", "due": "2026-10-10", "assignee": None}])
    ts = ev(pg, f"return Group.tasks(P, {json.dumps(st)}, '{S}', Date.UTC(2026, 8, 30));")
    refs = [t["ref"] for t in ts]
    assert "bk:bus18" in refs and "bk:bus_mishima" in refs and "bk:shin18" not in refs and "t:t-1" in refs
    assert refs[-1] == "bk:bus_mishima"                                   # done goes last
    # opting out of a stop drops its task unless already bought
    st2 = dict(st, joins=st["joins"] + [{"member": S, "scope": "stop", "ref": "d2e9", "mode": "out"}])
    ts2 = ev(pg, f"return Group.tasks(P, {json.dumps(st2)}, '{S}', Date.UTC(2026, 8, 30));")
    mish = next(t for t in ts2 if t["ref"] == "bk:bus_mishima")
    assert mish["dropped"] is True                                         # bought, then opted out → «сдайте билет»


def test_site_of_links(core):
    pg = core(("core.js", "group/model.js"))
    assert pg.evaluate("Group.siteOf('https://www.highwaybus.com/gp/reserve/x')")["site"] == "Highway Bus"
    assert pg.evaluate("Group.siteOf('https://secure.booking.com/confirmation.ru.html?x')")["site"] == "Booking.com"
    assert pg.evaluate("Group.siteOf('https://smart-ex.jp/en/')")["site"] == "Smart EX"
    assert pg.evaluate("Group.siteOf('https://example.org/a')")["site"] == "example.org"
    assert pg.evaluate("Group.siteOf('javascript:alert(1)')") is None
    assert pg.evaluate("Group.siteOf('http://booking.com')") is None
