import re
from conftest import ROOT

SQL = (ROOT / "supabase" / "migrations" / "001_group.sql").read_text(encoding="utf-8")
RPCS = ["member_names", "group_state", "claim_member", "set_join", "save_my_stop", "delete_my_stop", "save_my_booking", "set_task_state",
        "save_attachment", "delete_attachment", "save_plan", "save_part", "save_recipe", "add_member", "reset_pin",
        "save_task", "import_tasks"]
TABLES = ["trips", "members", "member_devices", "plan", "parts", "joins", "recipes", "tasks", "task_state",
          "attachments", "my_stops", "my_bookings"]


def test_every_rpc_is_a_guarded_security_definer():
    for name in RPCS:
        m = re.search(rf"create or replace function public\.{name}\((.*?)\$\$;", SQL, re.S)
        assert m, name
        body = m.group(0)
        assert "security definer" in body and "set search_path = public, extensions" in body, name
        if name not in ("claim_member", "member_names"):
            assert "_me(" in body or "_host(" in body, name


def test_every_table_has_rls_and_no_open_policy():
    for t in TABLES:
        assert f"alter table public.{t} enable row level security" in SQL, t
    assert "create policy" not in SQL.split("-- storage")[0]      # tables: deny direct access entirely


def test_no_private_values_in_sql():
    assert not re.search(r"\b09[AB]\b|pin_hash\s*=\s*'", SQL)
