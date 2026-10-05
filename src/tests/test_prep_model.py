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
    g = P(pg, "return Prep.groups(I);", auto={"installed": True, "booked": ["shin18"], "tickets": []})
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


def test_closed_sale_is_not_picked_until_it_opens(core):
    pg = core(("core.js", "flights.js", "prep.js"))
    # Clear everything out of the way except the two gated items (bk:sky's `opens`, p-vjw's `from`) and
    # anything whose own due is still later than Shibuya Sky's: only then does the opens-gate on bk:sky
    # actually decide the outcome, instead of losing on due date regardless.
    ids = P(pg, "return I.filter(i => i.due ? i.due < '2026-10-11' : (i.id !== 'bk:sky' && i.id !== 'p-vjw')).map(i => i.id);")
    local = {"done": {i: True for i in ids}, "own": []}
    before = P(pg, f"return Prep.first(I, Date.UTC(2026, 8, 30, 3), {DEP});", local=local)
    assert before["item"]["id"] != "bk:sky"                       # sales aren't open yet — must not be «first»
    after = P(pg, f"return Prep.first(I, Date.UTC(2026, 9, 10, 15), {DEP});", local=local)   # 11.10 00:00 JST
    assert after["item"]["id"] == "bk:sky"                        # sales just opened, and its due (11.10) is now nearest


def test_from_gate_blocks_a_prep_item_until_its_date(core):
    pg = core(("core.js", "flights.js", "prep.js"))
    ids = P(pg, "return I.filter(i => i.id !== 'p-vjw').map(i => i.id);")
    local = {"done": {i: True for i in ids}, "own": []}
    before = P(pg, f"return Prep.first(I, Date.UTC(2026, 9, 9, 15), {DEP});", local=local)   # 10.10 00:00 JST
    assert before["item"] is None                                 # Visit Japan Web opens 11.10 — nothing doable yet
    after = P(pg, f"return Prep.first(I, Date.UTC(2026, 9, 10, 15), {DEP});", local=local)   # 11.10 00:00 JST
    assert after["item"]["id"] == "p-vjw"                         # `from` has arrived — now it's the first thing


def test_own_items_and_everything_done(core):
    pg = core(("core.js", "flights.js", "prep.js"))
    local = {"done": {}, "own": [{"id": "own-1", "group": "packing", "title": "Подарки друзьям"}]}
    it = P(pg, "return I.find(i => i.id === 'own-1');", local=local)
    assert it["own"] is True and it["group"] == "packing"
    all_ids = P(pg, "return I.map(i => i.id);", local=local)
    local["done"] = {i: True for i in all_ids}
    f = P(pg, f"return Prep.first(I, Date.UTC(2026, 9, 14), {DEP});", local=local)
    assert f == {"item": None, "rest": 0}


def test_hotels_are_booked_tickets_are_bought(core):
    pg = core(("core.js", "flights.js", "prep.js"))
    t = P(pg, "return Object.fromEntries(I.filter(i => i.group === 'tickets').map(i => [i.id, i.title]));")
    assert t["bk:h_kyoto"] == "Забронировать: отель в Киото, 18.10 → 20.10 (2 ночи)"
    assert t["bk:sky"].startswith("Купить: Shibuya Sky")
    assert pg.evaluate("Prep.taskTitle('Отель: забронировать')") == "Забронировать: отель"
