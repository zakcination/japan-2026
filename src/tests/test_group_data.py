"""Parts, buying recipes and group config in the trip data (spec §5, appendix A)."""
import json

from conftest import ROOT

T = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))


def test_parts_cover_known_stops_and_days():
    ids = {e["id"] for d in T["days"] for e in d["ev"]}
    assert [p["id"] for p in T["parts"]] == ["arrive", "fuji", "kyoto", "nagoya", "tokyo"]
    for p in T["parts"]:
        assert p["days"] and all(1 <= n <= 11 for n in p["days"])
        assert p["stops"] is None or set(p["stops"]) <= ids
        if p["stops"] is not None:
            assert p["days"] == sorted({int(s[1:s.index("e")]) for s in p["stops"]})


def test_every_stop_of_days_1_to_11_is_in_exactly_one_part():
    counts = {}
    for p in T["parts"]:
        for sid in p["stops"]:
            counts[sid] = counts.get(sid, 0) + 1
    ids = {e["id"] for d in T["days"] if 1 <= d["n"] <= 11 for e in d["ev"]}
    assert set(counts) == ids
    assert all(c == 1 for c in counts.values())


def test_parts_split_day_2_at_the_mishima_bus_and_the_kyoto_shinkansen():
    day2 = next(d for d in T["days"] if d["n"] == 2)
    bus_mishima = next(e["id"] for e in day2["ev"] if e.get("bk") == "bus_mishima")
    shin18 = next(e["id"] for e in day2["ev"] if e.get("bk") == "shin18")
    fuji = next(p for p in T["parts"] if p["id"] == "fuji")
    kyoto = next(p for p in T["parts"] if p["id"] == "kyoto")
    assert bus_mishima in fuji["stops"] and shin18 not in fuji["stops"]
    assert shin18 in kyoto["stops"] and bus_mishima not in kyoto["stops"]


def test_parts_split_day_4_at_kyoto_checkout_and_the_nagoya_shinkansen():
    day4 = next(d for d in T["days"] if d["n"] == 4)
    checkout = next(e["id"] for e in day4["ev"] if e["t"] == "Забрать вещи из отеля")
    shin20 = next(e["id"] for e in day4["ev"] if e.get("bk") == "shin20")
    kyoto = next(p for p in T["parts"] if p["id"] == "kyoto")
    nagoya = next(p for p in T["parts"] if p["id"] == "nagoya")
    assert checkout in kyoto["stops"] and shin20 not in kyoto["stops"]
    assert shin20 in nagoya["stops"] and checkout not in nagoya["stops"]


def test_parts_split_day_6_at_nagoya_checkout_and_the_tokyo_shinkansen():
    day6 = next(d for d in T["days"] if d["n"] == 6)
    checkout = next(e["id"] for e in day6["ev"] if e["t"] == "Забрать вещи")
    shin22 = next(e["id"] for e in day6["ev"] if e.get("bk") == "shin22")
    nagoya = next(p for p in T["parts"] if p["id"] == "nagoya")
    tokyo = next(p for p in T["parts"] if p["id"] == "tokyo")
    assert checkout in nagoya["stops"] and shin22 not in nagoya["stops"]
    assert shin22 in tokyo["stops"] and checkout not in tokyo["stops"]


def test_recipes_are_public_safe_and_complete():
    bks = {b["id"] for b in T["bookings"]}
    for r in T["recipes"]:
        assert r["bk"] in bks and r["url"].startswith("https://") and r["what"]
        assert "host_ref" not in r
    txt = json.dumps(T, ensure_ascii=False)
    assert "09A" not in txt and "09B" not in txt


def test_shin20_recipe_reflects_the_moved_departure_time():
    r = next(r for r in T["recipes"] if r["bk"] == "shin20")
    assert "14:10" in r["what"] and "18:30" not in r["what"]
    assert r["price_pp"] == 5900
    assert r["buy_by"] == "2026-10-18"


def test_group_is_none_until_the_owner_sets_it_up():
    assert T["group"] is None


def test_template_has_no_group_things():
    tpl = json.loads((ROOT / "trips" / "template.json").read_text(encoding="utf-8"))
    assert not tpl.get("parts") and not tpl.get("recipes") and not tpl.get("group")
