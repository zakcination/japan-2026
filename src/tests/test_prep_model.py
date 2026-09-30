import json
from conftest import ROOT

OWN = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
DEP = "Date.UTC(2026, 9, 16, 15, 50)"


def P(pg, js, local=None, auto=None):
    local = local or {"done": {}, "own": []}
    auto = auto or {"installed": False, "booked": [], "tickets": []}
    return pg.evaluate(f"""(() => {{ const T = {json.dumps(OWN)}; const L = {json.dumps(local)};
      const A = {{installed: {json.dumps(auto['installed'])}, booked: new Set({json.dumps(auto['booked'])}), tickets: new Set({json.dumps(auto['tickets'])})}};
      const I = Prep.items(T, L, A); {js} }})()""")


def test_groups_count_and_auto_ticks(core):
    pg = core(("core.js", "flights.js", "prep.js"))
    g = P(pg, "return Prep.groups(I);", auto={"installed": True, "booked": ["bus_mishima"], "tickets": []})
    assert [x["title"] for x in g] == ["Билеты и отели", "Телефон", "Деньги и документы", "Сборы"]
    tickets = g[0]
    fixed = sum(b["st"] == "fixed" for b in OWN["bookings"])
    assert tickets["total"] == len(OWN["bookings"]) and tickets["done"] == fixed + 1   # + the one the app sees as bought
    phone = g[1]
    assert phone["done"] == 1                                    # installed on the Home Screen, ticked by the app
    it = P(pg, "return I.find(i => i.id === 'p-home');", auto={"installed": True, "booked": [], "tickets": []})
    assert it["checked"] == "auto"


def test_first_picks_the_nearest_doable_deadline(core):
    pg = core(("core.js", "flights.js", "prep.js"))
    f = P(pg, f"return Prep.first(I, Date.UTC(2026, 8, 30, 3), {DEP});")
    assert f["item"]["due"] == "2026-10-03" and f["rest"] > 5   # bk:h_kyoto — earliest doable buy_by, not the 10.10 items
    assert f["item"]["id"] != "bk:sky"                          # Shibuya Sky: sales open 11.10 — not today
    op = P(pg, "return Prep.opening(I, Date.UTC(2026, 9, 9, 16));")   # 10.10 01:00 Tokyo → sales in < 48 h
    assert op and op["id"] == "bk:sky"
    assert P(pg, "return Prep.opening(I, Date.UTC(2026, 8, 30, 3));") is None


def test_packing_waits_until_three_days_before(core):
    pg = core(("core.js", "flights.js", "prep.js"))
    done_all_but_packing = {"done": {}, "own": []}
    ids = P(pg, "return I.filter(i => i.group !== 'packing').map(i => i.id);")
    done_all_but_packing["done"] = {i: True for i in ids}
    f = P(pg, f"return Prep.first(I, Date.UTC(2026, 9, 1), {DEP});", local=done_all_but_packing)
    assert f["item"] is None                                     # 15 days out: packing isn't urgent yet
    f = P(pg, f"return Prep.first(I, Date.UTC(2026, 9, 14), {DEP});", local=done_all_but_packing)
    assert f["item"]["group"] == "packing"


def test_own_items_and_everything_done(core):
    pg = core(("core.js", "flights.js", "prep.js"))
    local = {"done": {}, "own": [{"id": "own-1", "group": "packing", "title": "Подарки друзьям"}]}
    it = P(pg, "return I.find(i => i.id === 'own-1');", local=local)
    assert it["own"] is True and it["group"] == "packing"
    all_ids = P(pg, "return I.map(i => i.id);", local=local)
    local["done"] = {i: True for i in all_ids}
    f = P(pg, f"return Prep.first(I, Date.UTC(2026, 9, 14), {DEP});", local=local)
    assert f == {"item": None, "rest": 0}
