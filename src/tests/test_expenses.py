"""Expenses (spec 2026-10-06): the brief's acceptance scenarios A–D, budget, shopping, transport, search, CSV, the Apple Pay link."""
import json
from conftest import until
from fake_supabase import FakeSupabase
from test_group_join import logged

R = {"KZT": 3.4, "USD": 0.0068}


def ev(pg, js):
    return pg.evaluate(f"(() => {{ const R = {json.dumps(R)}; {js} }})()")


def test_budget_states_shopping_transport_and_frozen_rates(core):
    pg = core(("core.js", "expenses.js"))
    r = ev(pg, """
      const mk = (a, c, x) => Exp.make({amount: a, cat: c, date: '2026-10-19', city: 'Киото', ...(x || {})}, R);
      const xs = [mk(350000, 'other')];
      const s1 = Exp.summary(xs, {budget: 500000, rates: R, today: '2026-10-19', start: '2026-10-17', end: '2026-10-28'});
      const shop = [mk(3990, 'shopping_self', {title: 'UNIQLO'}), mk(8500, 'shopping_gifts', {title: 'Don Quijote'})];
      const s2 = Exp.summary(shop, {rates: R, today: '2026-10-19', start: '2026-10-17', end: '2026-10-28'});
      const over = Exp.summary([mk(560000, 'other')], {budget: 500000, rates: R, today: '2026-10-19', start: '2026-10-17', end: '2026-10-28'});
      const e = mk(10000, 'food'); const before = Exp.inCur(e, 'KZT');
      const R2 = {KZT: 5, USD: 0.01}; const later = Exp.make({amount: 10000, cat: 'food', date: '2026-10-20'}, R2);
      const kzt = Exp.make({amount: 3400, currency: 'KZT', cat: 'food', date: '2026-10-19'}, R);
      return {s1, s2, over, before, after: Exp.inCur(e, 'KZT'), later: Exp.inCur(later, 'KZT'), kztJpy: kzt.jpy};""")
    s1 = r["s1"]
    assert s1["total"] == 350000 and s1["left"] == 150000 and round(s1["pct"]) == 70 and s1["state"] == "warn"
    assert s1["dayN"] == 3 and s1["elapsed"] == 3 and s1["tripDays"] == 12 and round(s1["avg"]) == round(350000 / 3)
    assert r["s2"]["shopping"] == {"self": 3990, "gifts": 8500}
    assert r["over"]["state"] == "bad" and r["over"]["over"] == -60000 and round(r["over"]["pct"]) == 112
    assert r["before"] == r["after"] == 34000 and r["later"] == 50000                 # scenario D: old rate stays
    assert r["kztJpy"] == 1000


def test_search_filters_csv_merge_and_the_apple_pay_link(core):
    pg = core(("core.js", "expenses.js"))
    r = ev(pg, """
      const xs = [Exp.make({amount: 14000, cat: 'transport', sub: 'shinkansen', from: 'Tokyo', to: 'Kyoto', date: '2026-10-22', city: 'Токио', pay: 'card'}, R),
                  Exp.make({amount: 1200, cat: 'food', title: 'Ramen', date: '2026-10-23', city: 'Токио', pay: 'cash'}, R),
                  Exp.make({amount: 0, cat: 'attractions', title: 'Fushimi Inari', date: '2026-10-20', city: 'Киото'}, R)];
      const del = {...xs[1], deleted: true};
      return {
        kyoto: Exp.filter(xs, {q: 'kyoto'}, '2026-10-23').map(e => e.cat),
        today: Exp.filter(xs, {period: 'today'}, '2026-10-23').length,
        y: Exp.filter(xs, {period: 'yesterday'}, '2026-10-23').length,
        cash: Exp.filter(xs, {pay: 'cash'}, '2026-10-23').length,
        free: Exp.filter(xs, {}, '2026-10-23').some(e => e.amount === 0),
        csv: Exp.csv(xs, '2026-10-17').split('\\n'),
        merged: Exp.merge(xs, [del, xs[0], {id: 'x', jpy: 1, date: 'bad'}]),
        l1: Exp.fromLink('#add=%C2%A51%2C500&cat=food&t=Lawson&go=1'),
        l2: Exp.fromLink('#add=1%20500%2C50%20%E2%82%B8&pay=card'),
        l3: Exp.fromLink('#add=12.5&cur=USD&cat=hack')};""")
    assert r["kyoto"] == ["transport"] and r["today"] == 1 and r["y"] == 1 and r["cash"] == 1 and r["free"]
    assert r["csv"][0].startswith("﻿Date,Trip Day,City,Category") and len(r["csv"]) == 4
    row = next(x for x in r["csv"] if "Tokyo" in x)
    assert ",6,Токио,Переезды,Синкансэн," in row and ",14000,JPY,1,14000," in row
    assert r["merged"]["added"] == 0 and r["merged"]["updated"] == 0                    # same updatedAt: nothing to take
    assert r["l1"] == {"amount": 1500, "currency": "JPY", "cat": "food", "title": "Lawson", "pay": "card", "go": True}
    assert r["l2"]["amount"] == 1500.5 and r["l2"]["currency"] == "KZT" and r["l2"]["cat"] is None and r["l2"]["go"] is False
    assert r["l3"]["currency"] == "USD" and r["l3"]["cat"] is None


def test_scenario_a_three_taps_then_scenario_b_survives_a_restart(app):
    a = app(state={"prevDay": 3, "prevTime": "12:00"}, now="2026-10-19T12:00:00+09:00")
    a.page.click("#tcAdd")
    assert a.page.evaluate("document.activeElement.id") == "exAmt"                  # the keyboard is up already
    assert a.page.evaluate("(s => s.scrollWidth <= s.clientWidth)(document.querySelector('.tc-sheet'))")   # nothing cut off at 390 px
    a.page.keyboard.type("1500")
    a.page.click("[data-cat='food']")
    save = a.page.locator("#exSave")
    assert save.inner_text().replace("\xa0", " ") == "Сохранить ¥1 500" and save.bounding_box()["height"] >= 56
    save.click()
    assert a.page.locator("#tcSheet").is_hidden() and "¥1 500 · Еда добавлено" in a.page.inner_text("#exToast").replace("\xa0", " ")
    a.page.click(".tc-tab[data-tab='stats']")
    t = a.page.inner_text("#exDash").replace("\xa0", " ")
    assert "¥1 500" in t and "Сегодня" in t and "Еда" in t
    a.page.reload(); a.page.wait_for_selector(".tc-tab")                            # scenario B: closed and opened again
    until(a.page, "ExpStore.ready() && ExpStore.all().length === 1")
    a.page.click(".tc-tab[data-tab='stats']")
    assert "¥1 500" in a.page.inner_text("#exDash").replace("\xa0", " ")


def test_edit_duplicate_delete_with_undo_and_budget_bar(app):
    a = app(state={"prevDay": 3, "prevTime": "12:00"}, now="2026-10-19T12:00:00+09:00")
    for amt, c in ((350000, "accommodation"), (1200, "food")):
        a.page.click("#tcAdd"); a.page.keyboard.type(str(amt)); a.page.click(f"[data-cat='{c}']"); a.page.click("#exSave")
    a.page.click(".tc-tab[data-tab='stats']")
    a.page.click("[data-exset]"); a.page.fill("#exBudget", "500000"); a.page.click("#exSetSave")
    assert "warn" in a.page.locator(".ex-budget").get_attribute("class") and "70.2%" in a.page.inner_text(".ex-budget")
    a.page.locator(".ex-item", has_text="Еда").click()
    a.page.click("#exDup"); a.page.click("#exSave")                                 # duplicate
    until(a.page, "ExpStore.all().filter(e => !e.deleted).length === 3")
    a.page.locator(".ex-item", has_text="Жильё").click(); a.page.click("#exDel")
    until(a.page, "ExpStore.all().filter(e => !e.deleted).length === 2")
    a.page.click("#exUndo")
    until(a.page, "ExpStore.all().filter(e => !e.deleted).length === 3")
    assert a.errors == []


def test_scenario_c_offline_edits_reach_the_server_once(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    g = logged(app, fake, san, "4821", state={"prevDay": 3, "prevTime": "12:00"}, now="2026-10-19T12:00:00+09:00")
    g.page.evaluate("localStorage.setItem('japan2026.onboarded.v1', '1')")
    fake.fail_network = True
    for i in range(5):
        g.page.click("#tcAdd"); g.page.keyboard.type(str(100 * (i + 1))); g.page.click("[data-cat='coffee']"); g.page.click("#exSave")
    g.page.click(".tc-tab[data-tab='stats']")
    g.page.locator(".ex-item").first.click(); g.page.fill("#exAmt", "999"); g.page.click("#exSave")
    g.page.locator(".ex-item").nth(1).click(); g.page.click("#exDel")
    assert len(fake.expenses) == 0
    fake.fail_network = False
    g.page.evaluate("window.dispatchEvent(new Event('online'))")                # the signal is back
    until(g.page, "Api.status().pending === 0", timeout=25000)             # a request stalled offline gives up after 15 s
    assert len(fake.expenses) == 5 and sum(x["deleted"] for x in fake.expenses.values()) == 1
    assert any(x["e"]["amount"] == 999 for x in fake.expenses.values())
    # her other phone gets them back; the host sees only her total
    h = logged(app, fake, fake.host_id, fake.host_pin)
    tot = h.page.evaluate("Api.state().spend_totals")
    assert [t for t in tot if t["member"] == san][0]["jpy"] > 0 and h.page.evaluate("Api.state().expenses.length") == 0


def test_apple_pay_link_saves_at_once_or_opens_filled(app):
    a = app(state={"prevDay": 3, "prevTime": "12:00"}, now="2026-10-19T12:00:00+09:00", url_suffix="#add=%C2%A5780&cat=coffee&t=Starbucks&go=1")
    until(a.page, "ExpStore.all().length === 1")
    e = a.page.evaluate("ExpStore.all()[0]")
    assert e["amount"] == 780 and e["cat"] == "coffee" and e["title"] == "Starbucks" and a.page.evaluate("location.hash") == ""
    b = app(state={"prevDay": 3, "prevTime": "12:00"}, now="2026-10-19T12:00:00+09:00", url_suffix="#add=2400&t=Lawson")
    b.page.locator("#exAmt").wait_for(state="visible")
    assert b.page.input_value("#exAmt") == "2400" and b.page.locator("#exSave").is_disabled()   # still needs a category


def test_review_fixes_link_csv_backup_and_limits(core):
    pg = core(("core.js", "expenses.js"))
    r = ev(pg, """
      const ok = Exp.make({amount: 500, cat: 'food', title: '=HYPERLINK("http://x")', note: '+1', date: '2026-10-19'}, R);
      const bad = [{...ok, id: '11111111-1111-4111-8111-111111111111', jpy: '5', currency: 'EVIL', cat: 'nope', amount: 5, extra: 'x'.repeat(9000)},
                   {...ok, id: '22222222-2222-4222-8222-222222222222', jpy: 1e12},
                   {...ok, id: '33333333-3333-4333-8333-333333333333', date: '2026-99-99'}, {id: '<img>'}];
      const m = Exp.merge([], bad);
      return { link: Exp.fromLink('#add=%&cat=food&go=1'), huge: Exp.fromLink('#add=99999999999&cat=food&go=1'),
               zero: Exp.fromLink('#add=0&cat=food&go=1').go, csv: Exp.csv([ok], '2026-10-17'), merged: m.list, added: m.added };""")
    assert r["link"]["amount"] is None and r["link"]["go"] is False                    # a stray % never throws
    assert r["huge"]["amount"] is None and r["huge"]["go"] is False and r["zero"] is False
    assert "'=HYPERLINK" in r["csv"] and ",'+1" in r["csv"]                             # formulas stay text
    assert r["added"] == 1
    e = r["merged"][0]
    assert e["jpy"] == 5 and e["currency"] == "JPY" and e["cat"] == "other" and "extra" not in e


def test_add_form_refuses_an_absurd_amount(app):
    a = app(state={"prevDay": 3, "prevTime": "12:00"}, now="2026-10-19T12:00:00+09:00")
    a.page.click("#tcAdd"); a.page.keyboard.type("999999999"); a.page.click("[data-cat='food']")
    assert a.page.locator("#exSave").is_disabled() and "Слишком большая" in a.page.inner_text("#exMsg")
