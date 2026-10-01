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
    # without the personal invite link a first sign-in is refused
    until(a.page, "/ссылка-приглашение/.test(document.getElementById('grMsg').textContent)")


def test_invite_link_opens_the_pin_and_signs_in(app):
    fake = FakeSupabase.seeded()
    san = fake._add("Сания", "guest")
    a = app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24"}, supabase=fake,
            url_suffix=f"?who={san}&code={fake.invite(san)}")
    s = a.page.locator("#tcSheet")
    s.wait_for(state="visible")
    assert a.page.locator("#grPin").is_visible() and "Сания" in s.inner_text()
    a.page.fill("#grPin", "4821")
    until(a.page, "Api.me() && Api.me().name === 'Сания' && !!document.getElementById('grFirstRun')")
    a.page.click("#grFrNext")                                  # first run off iPhone: just the parts
    until(a.page, "document.getElementById('tcSheet').hidden")
    assert fake.members[san]["invite"] is None                      # one-time code used up
    a.page.click("#tcGear")
    assert "Вы вошли как Сания" in a.page.inner_text("#tcSheet")


def test_pin_fires_once_even_if_input_repeats(app):
    fake = FakeSupabase.seeded()
    calls = []
    orig = fake.rpc_claim_member
    fake.rpc_claim_member = lambda *a, **k: (calls.append(1), orig(*a, **k))[1]
    a = app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24"}, supabase=fake)
    a.page.locator(f"[data-member='{fake.host_id}']").click()
    a.page.evaluate("""() => { const p = document.getElementById('grPin'); p.value = '0000';
      p.dispatchEvent(new Event('input')); p.dispatchEvent(new Event('input')); }""")
    until(a.page, "/Неверный PIN/.test(document.getElementById('grMsg').textContent)")
    assert len(calls) == 1


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
    # the first run: off iPhone a host has no steps at all — it lands on «Дела» straight away
    until(a.page, "document.getElementById('tcSheet').hidden")
    a.page.click("#tcGear")
    a.page.fill("#grNewName", "Шахи")
    a.page.click("#grAdd")
    until(a.page, "document.getElementById('grInvite') && /[?&]who=.+&code=[0-9a-f]+/.test(document.getElementById('grInvite').value)")
    until(a.page, "Api.state().members.some(m => m.name === 'Шахи')")
    assert any(m["name"] == "Шахи" for m in fake.members.values())


def test_a_brand_new_phone_asks_who_you_are_once_the_trip_arrives(app, site):
    fake = FakeSupabase.seeded()
    a = app(url=site, url_suffix="?trip=miras-aikosh", supabase=fake)       # nothing on the phone yet: the trip comes from the site
    a.page.wait_for_selector("#grNames [data-member]", timeout=10000)
    assert "Мирас" in a.page.inner_text("#tcSheet") and "Айкош" in a.page.inner_text("#tcSheet")


def test_host_brings_the_group_plan_up_to_date_with_two_taps(app):
    from test_group_join import logged
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    for d in fake.plan["doc"]["days"]:                                      # the group's copy predates the Japanese names
        for e in d["ev"]: e.pop("loc", None); e.pop("locLang", None)
    g = logged(app, fake, san, "4821")
    g.page.click("#tcGear")
    assert g.page.locator("#grPlanSync").count() == 0                        # guests never see it
    h = logged(app, fake, fake.host_id, fake.host_pin)
    h.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1')")
    h.page.click("#tcGear")
    h.page.click("#grPlanSyncGo"); h.page.click("#grPlanSyncGo")
    until(h.page, "Api.status().pending === 0")
    assert fake.plan["version"] == 2 and any(e.get("loc") == "天龍寺" for d in fake.plan["doc"]["days"] for e in d["ev"])
    h.page.click("#tcGear")
    assert h.page.locator("#grPlanSync").count() == 0                        # up to date: the card is gone
