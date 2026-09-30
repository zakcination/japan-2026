import json
from conftest import ROOT, until
from fake_supabase import FakeSupabase
from test_group_api import GROUPED


def test_first_open_asks_who_you_are_then_pin(app):
    fake = FakeSupabase.seeded()
    san = fake._add("Сания", "guest")
    a = app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24"}, supabase=fake)
    s = a.page.locator("#tcSheet")
    s.wait_for(state="visible")
    assert "Кто вы?" in s.inner_text() and "Сания" in s.inner_text()
    for b in s.locator("button").all():
        assert b.bounding_box()["height"] >= 44
    s.locator(f"[data-member='{san}']").click()
    a.page.fill("#grPin", "4821")                          # 4 digits submit by themselves
    until(a.page, "Api.me() && Api.me().name === 'Сания' && document.getElementById('tcSheet').hidden")
    a.page.click("#tcGear")
    assert "Вы вошли как Сания" in a.page.inner_text("#tcSheet")


def test_just_look_skips_and_is_not_asked_again(app):
    fake = FakeSupabase.seeded()
    a = app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24"}, supabase=fake)
    a.page.click("#grJustLook")
    a.page.reload()
    a.page.wait_for_selector(".tc-tab")
    assert not a.page.locator("#tcSheet").is_visible()


def test_wrong_pin_message_and_host_adds_member_and_resets_pin(app):
    fake = FakeSupabase.seeded()
    a = app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24"}, supabase=fake)
    a.page.locator(f"[data-member='{fake.host_id}']").click()
    a.page.fill("#grPin", "0000")
    until(a.page, "/Неверный PIN/.test(document.getElementById('grMsg').textContent)")
    a.page.fill("#grPin", fake.host_pin)
    until(a.page, "Api.me() && Api.me().role === 'host'")
    a.page.click("#tcGear")
    a.page.fill("#grNewName", "Шахи")
    a.page.click("#grAdd")
    until(a.page, "Api.state().members.some(m => m.name === 'Шахи')")
    assert any(m["name"] == "Шахи" for m in fake.members.values())
