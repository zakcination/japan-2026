from fake_supabase import FakeSupabase
from group_contract import run_all


def test_contract_on_the_fake():
    f = FakeSupabase.seeded()
    assert run_all(f.client(), f.host_id, f.host_pin)
