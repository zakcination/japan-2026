import json
from conftest import until
from fake_supabase import FakeSupabase
from test_group_join import logged


def test_joining_fuji_gives_two_buying_tasks_with_recipes(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.recipes["bus18"]["host_ref"] = "рейс 1431, места рядом с нашими: 10A/10B свободны"
    fake.joins.append({"member": san, "scope": "part", "ref": "fuji", "mode": "in"})
    g = logged(app, fake, san, "4821", now="2026-09-30T12:00:00+09:00")
    g.page.click(".tc-tab[data-tab='tix']")
    assert g.page.inner_text(".tc-tab[data-tab='tix']").strip() == "Дела"
    tasks = g.page.locator(".tc-task")
    refs = [t.get_attribute("data-ref") for t in tasks.all()]
    assert refs[:2] == ["bk:bus18", "bk:bus_mishima"] and "bk:shin18" not in refs
    first = tasks.first.inner_text()
    assert "Busta Shinjuku" in first and "¥2 200" in first.replace("\u00a0", " ") and "10A/10B" in first
    assert tasks.first.locator("a[href='https://www.highwaybus.com/']").count() == 1
    tasks.first.locator("[data-done]").click()
    until(g.page, "Api.status().pending === 0")
    assert fake.task_state[(san, "bk:bus18")]["done"] is True
    assert g.page.locator(".tc-task").last.get_attribute("data-ref") == "bk:bus18"   # done goes last


def test_sale_opening_is_shown_in_both_time_zones(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "tokyo", "mode": "in"})
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='tix']")
    sky = g.page.locator(".tc-task[data-ref='bk:sky']").inner_text()
    assert "11.10 00:00 по Японии" in sky and "10.10 20:00 по Алматы" in sky


def test_host_edits_recipe_and_imports_old_tasks(app):
    fake = FakeSupabase.seeded()
    h = logged(app, fake, fake.host_id, fake.host_pin)
    h.page.click(".tc-tab[data-tab='tix']")
    h.page.locator(".tc-task[data-ref='bk:bus18'] [data-recipe]").click()
    h.page.fill("#rcHost", "рейс 1431, места 10A/10B рядом")
    h.page.click("#rcSave")
    until(h.page, "Api.status().pending === 0")
    assert "10A/10B" in fake.recipes["bus18"]["host_ref"]
    h.page.click("#tkImport")
    h.page.fill("#tkJson", json.dumps([{"title": "Оформить Suica в Wallet", "due": "2026-10-15"},
                                       {"title": "<img src=x onerror=window.__pwned=1>"}]))
    h.page.click("#tkImportGo")
    until(h.page, "Api.status().pending === 0")
    assert len(fake.tasks) == 2
    h.page.evaluate("Api.refresh()")
    until(h.page, "document.querySelectorAll('.tc-task[data-ref^=\"t:\"]').length === 2")
    assert h.page.evaluate("window.__pwned") is None
