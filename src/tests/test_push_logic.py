"""Who gets which push (supabase/functions/notify/logic.mjs), run with Node."""
import json, shutil, subprocess
import pytest
from conftest import ROOT

TRIP = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
NODE = shutil.which("node")
H, A, S, M = "h-1", "h-2", "s-1", "m-1"


def run(ev, now_iso, **over):
    D = {"trip": "miras-aikosh", "members": [{"id": H, "name": "Мирас", "role": "host"}, {"id": A, "name": "Айкош", "role": "host"},
                                            {"id": S, "name": "Сания", "role": "guest"}, {"id": M, "name": "Шахи", "role": "guest"}],
         "proposals": [], "plan": {"doc": TRIP}, "parts": TRIP["parts"], "joins": [], "recipes": TRIP["recipes"], "task_state": []}
    D.update(over)
    js = (f"import {{ messages }} from '{(ROOT / 'supabase/functions/notify/logic.mjs').as_uri()}';"
          f"console.log(JSON.stringify(messages({json.dumps(ev)}, {json.dumps(D)}, Date.parse({json.dumps(now_iso)}))));")
    return json.loads(subprocess.run([NODE, "--input-type=module", "-e", js], capture_output=True, text=True, check=True).stdout)


pytestmark = pytest.mark.skipif(not NODE, reason="node not installed")


def test_a_proposal_goes_to_the_hosts_and_the_decision_to_its_author():
    p = {"id": "p1", "member": S, "kind": "time", "ref": "d3e3", "payload": {"s": "11:00", "e": "12:00"}, "status": "open"}
    m = run({"type": "proposal", "id": "p1"}, "2026-10-05T10:00:00Z", proposals=[p])
    assert len(m) == 1 and sorted(m[0]["to"]) == [H, A] and m[0]["title"] == "Предложение от Сания"
    assert m[0]["body"] == "«Тэнрю-дзи, сад дзен»: другое время 11:00–12:00" and m[0]["url"].endswith("#tab=tix")
    m = run({"type": "decision", "id": "p1"}, "2026-10-05T10:00:00Z", proposals=[dict(p, status="accepted")])
    assert m[0]["to"] == [S] and m[0]["title"] == "Ваше предложение принято"


def test_joins_tell_the_hosts_and_plan_changes_tell_the_guests():
    m = run({"type": "join", "member": S, "scope": "part", "ref": "fuji", "mode": "in"}, "2026-10-05T10:00:00Z")
    assert sorted(m[0]["to"]) == [H, A] and m[0]["title"] == "Сания едет" and "Фудзи" in m[0]["body"]
    m = run({"type": "join", "member": H, "scope": "part", "ref": "fuji", "mode": "none"}, "2026-10-05T10:00:00Z")
    assert m[0]["to"] == [A] and m[0]["title"] == "Мирас не едет"                    # never to yourself
    m = run({"type": "plan", "trip": "miras-aikosh", "version": 4}, "2026-10-05T10:00:00Z")
    assert sorted(m[0]["to"]) == [M, S] and m[0]["tag"] == "plan"


def test_deadlines_three_days_before_and_on_the_day_only_to_who_needs_to_buy():
    joins = [{"member": S, "scope": "part", "ref": "kyoto", "mode": "in"}]              # Сания joins Kyoto, Шахи joins nothing
    # h_kyoto: buy by 03.10 → three days before is 30.09 (Almaty morning)
    m = run({"type": "deadlines"}, "2026-09-30T03:00:00Z", joins=joins)
    k = next(x for x in m if x["tag"] == "deadline-h_kyoto")
    assert k["title"].startswith("Осталось 3 дня: Отель в Киото") and "выбрать" not in k["title"]
    assert sorted(k["to"]) == [H, A, S] and k["url"].endswith("#task=bk:h_kyoto")
    m = run({"type": "deadlines"}, "2026-10-03T03:00:00Z", joins=joins, task_state=[{"member": S, "ref": "bk:h_kyoto", "done": True}])
    k = next(x for x in m if x["tag"] == "deadline-h_kyoto")
    assert k["title"].startswith("Сегодня последний день") and S not in k["to"]          # ticked «Куплено»: left alone
    # Shibuya Sky: sales open 11.10 00:00 JST = 10.10 20:00 Almaty → that morning
    m = run({"type": "deadlines"}, "2026-10-10T03:00:00Z")
    sky = next(x for x in m if x["tag"] == "deadline-sky")
    assert sky["title"].startswith("Сегодня открываются продажи") and "20:00 по Алматы" in sky["body"]


def test_a_task_due_today_reaches_its_assignee_at_eight():
    tasks = [{"id": "t-shakhi", "title": "Добавить Шахи в список", "due": "2026-10-07", "note": "", "assignee": H},
             {"id": "t-all", "title": "Для всех", "due": "2026-10-07", "assignee": None},
             {"id": "t-later", "title": "Потом", "due": "2026-10-09", "assignee": H}]
    m = run({"type": "deadlines"}, "2026-10-07T03:00:00Z", tasks=tasks)               # 08:00 in Almaty
    mine = next(x for x in m if x["tag"] == "task-t-shakhi")
    assert mine["to"] == [H] and mine["title"] == "Сегодня: Добавить Шахи в список" and mine["url"].endswith("#task=t:t-shakhi")
    assert sorted(next(x for x in m if x["tag"] == "task-t-all")["to"]) == sorted([H, A, S, M])
    assert not any(x["tag"] == "task-t-later" for x in m)
    m = run({"type": "deadlines"}, "2026-10-07T03:00:00Z", tasks=tasks, task_state=[{"member": H, "ref": "t:t-shakhi", "done": True}])
    assert not any(x["tag"] == "task-t-shakhi" for x in m)                             # ticked: left alone
