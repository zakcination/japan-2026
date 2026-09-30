"""Task 10a: the invite kit, the first run, deep links, WhatsApp nudges and the private activation funnel."""
import json, re
from urllib.parse import unquote
from conftest import until
from fake_supabase import FakeSupabase
from test_group_api import GROUPED
from test_group_join import logged

REAL = {"prevDay": 2, "prevTime": "13:24", "preview": False}
PRE = "2026-09-30T12:00:00+09:00"


def wa_text(href):
    assert href.startswith("https://wa.me/?text=")
    return unquote(href[len("https://wa.me/?text="):])


def test_host_invites_a_guest_with_whatsapp_text_link_and_qr(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    h = logged(app, fake, fake.host_id, fake.host_pin)
    h.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1')")
    h.page.click("#tcGear")
    h.page.click(f"[data-invite='{san}']")
    until(h.page, "!!document.getElementById('grInviteText')")
    s = h.page.locator("#tcSheet")
    text = h.page.inner_text("#grInviteText")
    assert "Сания" in s.inner_text() and "1. Откройте ссылку в Safari" in text and "На экран «Домой»" in text
    url = h.page.input_value("#grInvite")
    assert re.search(rf"[?&]who={san}&code={fake.invite(san)}$", url) and url in text
    assert wa_text(h.page.get_attribute("#grInviteWa", "href")) == text
    assert h.page.locator("#grInviteQr svg").count() == 1
    for b in s.locator("a.tc-btn, button.tc-btn").all():
        if b.is_visible():
            assert b.bounding_box()["height"] >= 44


def test_invite_link_first_run_joins_fuji_and_lands_on_tasks_once(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    g = app(trip=GROUPED, state={"prevDay": 2, "prevTime": "13:24"}, supabase=fake,
            url_suffix=f"?trip=miras-aikosh&who={san}&code={fake.invite(san)}")
    g.page.locator("#grPin").wait_for(state="visible")
    assert "Сания" in g.page.inner_text("#tcSheet")                 # straight to her PIN, no name to pick
    g.page.fill("#grPin", "4821")
    until(g.page, "!!document.getElementById('grFirstRun')")
    g.page.click("#grFrNext")                                       # step 1: Home Screen
    g.page.locator("[data-fr-part='fuji']").check()                 # step 2: «Фудзи / Кавагутико»
    g.page.click("#grFrNext")
    until(g.page, "document.getElementById('tcSheet').hidden && document.querySelector('.tc-tab[aria-selected=\"true\"]').dataset.tab === 'tix'")
    until(g.page, "!!document.querySelector('#grTasks [data-ref=\"bk:bus18\"]')")
    until(g.page, "Api.status().pending === 0")
    assert any(j["member"] == san and j["ref"] == "fuji" and j["mode"] == "in" for j in fake.joins)
    g.page.reload()
    g.page.wait_for_selector(".tc-tab")
    g.page.wait_for_timeout(300)
    assert g.page.locator("#grFirstRun").count() == 0


def test_deep_links_open_prep_and_tabs_then_leave_the_address(app):
    own = dict(GROUPED); own.pop("group")
    a = app(trip=own, state=REAL, now=PRE, url_suffix="#prep=tickets")
    until(a.page, "!!document.querySelector('#tcSheet [data-group=\"tickets\"]') && !document.getElementById('tcSheet').hidden")
    assert a.page.evaluate("location.hash") == ""
    b = app(trip=own, state=REAL, now=PRE, url_suffix="#tab=tix")
    until(b.page, "document.querySelector('.tc-tab[aria-selected=\"true\"]').dataset.tab === 'tix'")
    assert b.page.evaluate("location.hash") == ""


def test_first_thing_card_nudges_in_whatsapp_with_a_deep_link(app):
    own = dict(GROUPED); own.pop("group")
    a = app(trip=own, state=REAL, now=PRE)
    title = a.page.inner_text("#tcFirst b")
    t = wa_text(a.page.get_attribute("#tcFirst .tc-nudge", "href"))
    assert title in t and "#prep=tickets" in t and "до " in t
    assert a.page.locator("#tcFirst .tc-nudge").bounding_box()["height"] >= 44


def test_funnel_counts_only_and_for_hosts_only(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    h = logged(app, fake, fake.host_id, fake.host_pin)
    h.page.evaluate("track('login')")
    g = logged(app, fake, san, "4821")
    g.page.evaluate("track('login'); setJoin('part', 'fuji', 'in')")
    until(g.page, "Api.status().pending === 0")
    h.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1')")
    h.page.click("#tcGear")
    until(h.page, "/вошли 2/.test(document.getElementById('grFunnel').textContent)")
    f = h.page.inner_text("#grFunnel")
    assert "Приглашены 3" in f and "присоединились 1" in f
    counts = fake.rpc_funnel_counts(next(t for t, u in fake.tokens.items() if fake.devices.get(u) == fake.host_id))
    assert set(counts) == {"members", "login", "installed", "joined", "bought"}
    assert san not in json.dumps(counts) and "Сания" not in json.dumps(counts)
    r = g.page.evaluate("Api.run('funnel_counts', {}).then(() => 'ok', e => e.message)")
    assert "host only" in r


def test_a_deep_link_before_sign_in_keeps_who_are_you(app):
    fake = FakeSupabase.seeded(); fake._add("Сания", "guest")
    a = app(trip=GROUPED, state=REAL, now=PRE, supabase=fake, url_suffix="#prep=tickets")
    until(a.page, "!!document.querySelector('#grNames [data-member]')")      # «Кто вы?» filled in, not replaced
    assert "Кто вы?" in a.page.inner_text("#tcSheet") and a.page.evaluate("location.hash") == ""
    assert a.errors == []


def test_task_deep_link_scrolls_to_the_task(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    g = logged(app, fake, san, "4821")
    g.page.evaluate("setJoin('part', 'fuji', 'in')")
    until(g.page, "Api.status().pending === 0")
    g.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1'); location.hash = '#task=bk:bus18'; location.reload()")
    g.page.wait_for_selector(".tc-tab")
    until(g.page, "!!document.querySelector('[data-ref=\"bk:bus18\"].tc-flash')")
    assert g.page.evaluate("location.hash") == ""


def test_invite_qr_box_does_not_restyle_the_ticket_qr_button(app):
    own = dict(GROUPED); own.pop("group")
    a = app(trip=own, state={"prevDay": 2, "prevTime": "13:24"})
    a.page.click(".tc-tab[data-tab='tix']")
    bg = a.page.evaluate("(() => { const b = document.querySelector('.tc-qr'); return b ? getComputedStyle(b).backgroundColor : null; })()")
    assert bg is None or bg not in ("rgb(255, 255, 255)", "rgba(0, 0, 0, 0)")
