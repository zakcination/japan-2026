import json
from conftest import ROOT, until
from fake_supabase import FakeSupabase

OURS = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
GROUPED = dict(OURS, group={"url": "https://fake.supabase.co", "anon": "anon-key"})


def phone(app, fake, **kw):
    return app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24"}, supabase=fake, **kw)


def test_login_then_state_is_cached_and_survives_offline(app):
    fake = FakeSupabase.seeded()
    a = phone(app, fake)
    r = a.page.evaluate(f"Api.login('{fake.host_id}', '{fake.host_pin}')")
    assert r["ok"] and a.page.evaluate("Api.me().name") == "Мирас"
    fake.fail_network = True
    a.page.reload()
    until(a.page, "window.Api && Api.state() && Api.state().me.name === 'Мирас'")


def test_outbox_survives_reload_and_sends_once(app):
    fake = FakeSupabase.seeded()
    a = phone(app, fake)
    a.page.evaluate(f"Api.login('{fake.host_id}', '{fake.host_pin}')")
    fake.fail_network = True
    a.page.evaluate("Api.call('set_join', {p_scope: 'part', p_ref: 'fuji', p_mode: 'in'}, s => s.joins.push({member: Api.me().id, scope: 'part', ref: 'fuji', mode: 'in'}))")
    assert a.page.evaluate("Api.status().pending") == 1
    a.page.reload()
    assert a.page.evaluate("Api.status().pending") == 1
    fake.fail_network = False
    a.page.evaluate("Api.flush()")
    until(a.page, "Api.status().pending === 0")
    assert [j for j in fake.joins if j["ref"] == "fuji"] == [{"member": fake.host_id, "scope": "part", "ref": "fuji", "mode": "in"}]


def test_expired_token_is_refreshed_and_a_rejected_write_is_dropped(app):
    fake = FakeSupabase.seeded()
    a = phone(app, fake)
    a.page.evaluate(f"Api.login('{fake.host_id}', '{fake.host_pin}')")
    fake.tokens.clear()                                     # every access token now invalid; refresh token still works
    a.page.evaluate("Api.call('set_task_state', {p_ref: 'bk:bus18', p_done: true}, () => {})")
    until(a.page, "Api.status().pending === 0")
    assert (fake.host_id, "bk:bus18") in fake.task_state
    a.page.evaluate("Api.call('save_attachment', {p_a: {id: 'a-x', ref: 'bk:bus18', kind: 'link', url: 'http://x'}}, () => {})")
    until(a.page, "Api.status().pending === 0 && /https/.test(Api.status().error || '')")


def test_disabled_without_group_config(app):
    a = app(state={"prevDay": 2, "prevTime": "13:24"})
    assert a.page.evaluate("Api.enabled()") is False
    assert a.errors == []
