"""Stage 2: guests propose, hosts accept or reject; an accepted change updates the plan for everyone."""
import json
from conftest import ROOT, until
from fake_supabase import FakeSupabase
from test_group_join import logged

TRIP = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))


def ev(pg, js):
    return pg.evaluate(f"(() => {{ const P = {json.dumps(TRIP)}; {js} }})()")


def test_apply_time_remove_add_and_comment(core):
    pg = core(("core.js", "group/proposals.js"))
    r = ev(pg, """
      const t = Proposals.apply(P, {kind: 'time', ref: 'd3e3', payload: {s: '11:00', e: '12:00'}});
      const r = Proposals.apply(P, {kind: 'remove', ref: 'd3e2'});
      const a = Proposals.apply(P, {id: 'abc-123', kind: 'add', day: 3, payload: {s: '16:00', e: '17:00', t: 'Чайная церемония'}});
      const c = Proposals.apply(P, {kind: 'comment', ref: 'd3e3', note: 'x'});
      const d3 = doc => doc.days.find(d => d.n === 3).ev;
      let gone = null; try { Proposals.apply(r, {kind: 'time', ref: 'd3e2', payload: {s: '09:00', e: '10:00'}}); } catch (e) { gone = e.message; }
      let bad = null; try { Proposals.apply(P, {kind: 'time', ref: 'd3e3', payload: {s: '12:00', e: '11:00'}}); } catch (e) { bad = e.message; }
      return { t: d3(t).find(e => e.id === 'd3e3'), removed: d3(r).some(e => e.id === 'd3e2'), added: d3(a).find(e => e.t === 'Чайная церемония'),
               same: JSON.stringify(c) === JSON.stringify(P), untouched: P.days.find(d => d.n === 3).ev.find(e => e.id === 'd3e3').s,
               gone, bad, desc: Proposals.describe({kind: 'time', ref: 'd3e3', payload: {s: '11:00', e: '12:00'}}, P) };""")
    assert r["t"]["s"] == "11:00" and r["t"]["e"] == "12:00" and r["untouched"] != "11:00"     # the original plan is not mutated
    assert r["removed"] is False and r["added"]["id"].startswith("p-") and r["same"]
    assert r["gone"] == "stop gone" and r["bad"] == "bad proposal"
    assert r["desc"] == "«Тэнрю-дзи, сад дзен»: другое время 11:00–12:00"


def test_guest_proposes_another_time_host_accepts_and_the_plan_changes(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "kyoto", "mode": "in"})
    g = logged(app, fake, san, "4821", state={"prevDay": 3, "prevTime": "06:00"})
    g.page.click(".tc-tab[data-tab='day']")
    g.page.locator(".tc-item[data-id='d3e3'] .tc-open").click()
    g.page.click("#tcSheet [data-propose]")
    g.page.fill("#prS", "11:00"); g.page.fill("#prE", "12:00"); g.page.fill("#prNote", "хочу подольше поспать")
    g.page.click("#prSend")
    until(g.page, "Api.status().pending === 0")
    assert len(fake.proposals) == 1 and fake.proposals[0]["payload"] == {"s": "11:00", "e": "12:00"}
    g.page.click(".tc-tab[data-tab='tix']")
    until(g.page, "/ждёт ответа/.test(document.getElementById('grProps').textContent)")

    h = logged(app, fake, fake.host_id, fake.host_pin)
    h.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1')")
    h.page.click(".tc-tab[data-tab='tix']")
    card = h.page.locator("#grProps .tc-prop").first
    assert "Сания" in card.inner_text() and "другое время 11:00–12:00" in card.inner_text() and "поспать" in card.inner_text()
    v = fake.plan["version"]
    card.locator("[data-accept]").click()
    until(h.page, "Api.status().pending === 0")
    assert fake.proposals[0]["status"] == "accepted" and fake.plan["version"] == v + 1
    assert next(e for d in fake.plan["doc"]["days"] for e in d["ev"] if e["id"] == "d3e3")["s"] == "11:00"
    assert h.page.locator("#grProps").count() == 0                          # nothing left to decide

    g.page.evaluate("Api.refresh()")
    until(g.page, "/принято/.test(document.getElementById('grProps').textContent)")


def test_guest_proposes_a_new_stop_host_rejects_and_hosts_never_see_the_button(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    g = logged(app, fake, san, "4821", state={"prevDay": 3, "prevTime": "06:00"})
    g.page.click(".tc-tab[data-tab='day']")
    g.page.click("#grView [data-view='group']")
    g.page.click("#grProposeAdd")
    g.page.fill("#prTitle", "Чайная церемония"); g.page.fill("#prS", "16:00"); g.page.fill("#prE", "17:00")
    g.page.click("#prSend")
    until(g.page, "Api.status().pending === 0")
    p = fake.proposals[0]
    assert p["kind"] == "add" and p["day"] == 3 and p["payload"]["t"] == "Чайная церемония"
    h = logged(app, fake, fake.host_id, fake.host_pin)
    h.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1')")
    h.page.click(".tc-tab[data-tab='day']")
    h.page.click("#grView [data-view='group']")
    assert h.page.locator("#grProposeAdd").count() == 0
    h.page.click(".tc-tab[data-tab='tix']")
    b = h.page.locator("#grProps [data-reject]").first
    b.click(); b.click()                                                    # two taps
    until(h.page, "Api.status().pending === 0")
    assert fake.proposals[0]["status"] == "rejected" and fake.plan["version"] == 1


def test_a_proposal_cannot_inject_markup(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.proposals.append({"id": "00000000-0000-0000-0000-00000000000a", "member": san, "kind": "add", "ref": None, "day": 3,
                           "payload": {"s": "16:00", "e": "17:00", "t": '<img src=x onerror="window.__pwned=1">'},
                           "note": '<script>window.__pwned=1</script>', "status": "open", "at": 1})
    h = logged(app, fake, fake.host_id, fake.host_pin)
    h.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1')")
    h.page.click(".tc-tab[data-tab='tix']")
    assert "<img" in h.page.inner_text("#grProps") and not h.page.evaluate("window.__pwned")
