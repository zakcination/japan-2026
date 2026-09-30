"""Shanghai layover stops and the preparation checklist in the trip data (spec appendix B)."""
import json
from conftest import ROOT

OWN = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
TPL = json.loads((ROOT / "trips" / "template.json").read_text(encoding="utf-8"))
GROUPS = {"tickets", "phone", "money", "packing"}


def test_shanghai_day_only_in_our_trip():
    d1 = OWN["days"][0]["ev"]
    sh = [e for e in d1 if e.get("off") == 480]
    assert [e["s"] for e in sh] == ["05:30", "07:00", "07:30", "08:15", "10:45", "12:30", "14:15"]
    assert any(e["st"] == "fixed" and e["s"] == "14:15" for e in sh)          # back at the airport: an anchor
    assert not any(e.get("off") for d in TPL["days"] for e in d["ev"])


def test_prep_list_is_complete_and_public_safe():
    for t in (OWN, TPL):
        ids = [p["id"] for p in t["prep"]]
        assert len(ids) == len(set(ids)) and {p["group"] for p in t["prep"]} <= GROUPS
        assert all(p.get("url", "https://").startswith("https://") for p in t["prep"])
    own_titles = " ".join(p["title"] for p in OWN["prep"])
    assert "Шанхай" in own_titles and "Шанхай" not in " ".join(p["title"] for p in TPL["prep"])
    assert any(p.get("auto") == "installed" for p in OWN["prep"])
    vjw = next(p for p in OWN["prep"] if "Visit Japan Web" in p["title"])
    assert vjw["from"] == "2026-10-10"                                           # T-6
    assert "09A" not in json.dumps(OWN, ensure_ascii=False)
