"""The assistant's server logic (supabase/functions/assistant/logic.mjs, kb.mjs) run with Node, plus the one-file bundle
run end to end under Node's type stripping with Deno, fetch and the Anthropic client stubbed — no network anywhere."""
import json, pathlib, re, shutil, subprocess, sys
import pytest
from conftest import ROOT

FN = ROOT / "supabase" / "functions" / "assistant"
TRIP = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="node not installed")
H, A, S = "h-1", "h-2", "s-1"


def state(me=S, **over):
    role = "host" if me in (H, A) else "guest"
    st = {"me": {"id": me, "name": {H: "Мирас", A: "Айкош", S: "Сания"}[me], "role": role}, "plan": {"doc": TRIP, "version": 3},
          "members": [{"id": H, "name": "Мирас", "role": "host"}, {"id": A, "name": "Айкош", "role": "host"}, {"id": S, "name": "Сания", "role": "guest"}],
          "parts": TRIP["parts"], "joins": [{"member": S, "scope": "part", "ref": "kyoto", "mode": "in"}, {"member": S, "scope": "mine", "ref": "m-aikosh", "mode": "in"}],
          "recipes": [dict(r, host_ref="SECRET-REF-123") for r in TRIP["recipes"]], "tasks": [{"id": "t1", "title": "Visit Japan Web", "due": "2026-10-15"}],
          "my_stops": [{"id": "m-lunch", "member": S, "day": 3, "shared": False, "ev": {"s": "12:00", "e": "13:00", "t": "Обед", "lat": 35.1, "lng": 135.7}},
                       {"id": "m-aikosh", "member": A, "day": 3, "shared": True, "ev": {"s": "16:00", "e": "17:00", "t": "Чайная"}},
                       {"id": "m-hidden", "member": A, "day": 3, "shared": False, "ev": {"s": "18:00", "e": "19:00", "t": "Тайное"}}],
          "attachments": [{"id": "a1", "url": "https://secret.example/booking"}], "expenses": [{"id": "e1", "amount": 999999}],
          "task_state": []}
    st.update(over)
    return st


def node(js):
    code = (f"import * as L from '{(FN / 'logic.mjs').as_uri()}'; import * as K from '{(FN / 'kb.mjs').as_uri()}';\n"
            f"const TRIP = {json.dumps(TRIP)}; const out = await (async () => {{ {js} }})(); console.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module"], input=code, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def idx_js(st):
    return f"const idx = L.tripIndex({json.dumps(st)});"


def test_the_request_is_opus_5_5_low_effort_short_with_fallbacks_and_no_disabled_thinking():
    r = node("const sys = L.buildSystem('ctx'); return { req: L.buildRequest(sys, [{role: 'user', content: 'hi'}]), tr: L.buildTranslateRequest({ text: 'привет', from: 'ru', to: 'ja' }) };")
    q = r["req"]
    assert q["model"] == "claude-opus-5-5" and q["output_config"] == {"effort": "low"} and q["max_tokens"] <= 4000
    assert q.get("thinking") in (None, {"type": "adaptive"})                     # never disabled, never a budget
    assert "tool_choice" not in q and not {"temperature", "top_p", "top_k"} & set(q)
    assert q["fallbacks"] == "default" and q["betas"] == ["server-side-fallback-2026-07-01"]
    names = [t.get("name") for t in q["tools"]]
    assert {"get_day", "find_stops", "get_bookings", "app_help", "emergency_info", "card_perks", "convert_currency", "show_japanese", "suggest_place",
            "propose_move_stop", "propose_skip_stop", "propose_add_stop", "propose_add_expense", "web_search"} <= set(names)
    ws = next(t for t in q["tools"] if t.get("name") == "web_search")
    assert ws["type"] == "web_search_20260209" and ws["max_uses"] == 3
    assert q["system"][0]["cache_control"] == {"type": "ephemeral"} and "cache_control" not in q["system"][1]
    assert "Отвечай кратко: 1–4 предложения" in q["system"][0]["text"] and "Tax-free" in q["system"][0]["text"]
    t = r["tr"]
    assert t["model"] == "claude-opus-5-5" and t["output_config"] == {"effort": "low"} and "tools" not in t and "thinking" not in t


def test_context_is_small_private_and_centred_on_today():
    st = state()
    r = node(idx_js(st) + """
      const pre = L.contextText(idx, Date.parse('2026-10-14T03:00:00Z'), null);       // 14.10, before the trip
      const live = L.contextText(idx, Date.parse('2026-10-22T03:00:00Z'), 9);        // day 6, «День» shows day 9
      const after = L.focusDay(idx, Date.parse('2026-11-05T03:00:00Z'));
      return { pre, live, after, bk: L.runTool('get_bookings', {}, idx, { actions: [], cards: [] }).content,
               day3: L.runTool('get_day', { day_n: 3 }, idx, { actions: [], cards: [] }).content };""")
    pre, live = r["pre"], r["live"]
    assert "до поездки 3 дн." in pre and "[d1e0]" in pre and "[d3e3]" in pre and "[d4e0]" not in pre and "подробно — get_day" in pre
    assert "идёт день 6 из 12" in live and "[d4e0]" in live and "[d8e0]" in live and "[d3e0]" not in live and "[d9e3]" in live
    assert r["after"] == {"n": 12, "phase": "post"}
    for text in (pre, live, r["bk"], r["day3"]):
        assert not re.search(r"35\.\d{3}|135\.\d{3}", text)                       # no coordinates: the Kyoto house is an address
        assert "SECRET-REF-123" not in text and "secret.example" not in text and "highwaybus.com/" not in text and "999999" not in text
    assert "[m-lunch]" in r["day3"] and "[m-aikosh]" in r["day3"] and "m-hidden" not in r["day3"]
    assert "гость" in pre and "Visit Japan Web" in r["bk"] and len(live) < 12000


def test_proposals_are_validated_strictly_and_normalised():
    r = node(idx_js(state()) + """
      const v = (n, a) => L.validate(n, a, idx);
      const host = L.tripIndex(Object.assign(""" + json.dumps(state(H)) + """));
      return {
        badTime: v('propose_move_stop', { stop_id: 'd3e3', start: '25:00', end: '26:00', reason: '' }).error,
        backwards: v('propose_move_stop', { stop_id: 'd3e3', start: '12:00', end: '11:00', reason: '' }).error,
        unknown: v('propose_move_stop', { stop_id: 'd99e1', start: '11:00', end: '12:00', reason: '' }).error,
        theirs: v('propose_move_stop', { stop_id: 'm-aikosh', start: '11:00', end: '12:00', reason: '' }).error,
        hidden: v('propose_skip_stop', { stop_id: 'm-hidden', reason: '' }).error,
        long: v('propose_add_stop', { day_n: 3, start: '11:00', end: '12:00', title: 'x'.repeat(121), place_name: '', note: '' }).error,
        noDay: v('propose_add_stop', { day_n: 13, start: '11:00', end: '12:00', title: 'x', place_name: '', note: '' }).error,
        oneCoord: v('propose_add_stop', { day_n: 3, start: '11:00', end: '12:00', title: 'x', place_name: '', note: '', lat: 35 }).error,
        eur: v('propose_add_expense', { amount: 10, currency: 'EUR', category: 'food', title: '' }).error,
        cat: v('propose_add_expense', { amount: 10, currency: 'JPY', category: 'pizza', title: '' }).error,
        huge: v('propose_add_expense', { amount: 5e8, currency: 'JPY', category: 'food', title: '' }).error,
        neg: v('propose_add_expense', { amount: -1, currency: 'JPY', category: 'food', title: '' }).error,
        guestGroup: v('propose_move_stop', { stop_id: 'd3e3', start: '11:00', end: '12:00', reason: 'выспаться' }).action,
        hostGroup: L.validate('propose_move_stop', { stop_id: 'd3e3', start: '11:00', end: '12:00', reason: '' }, host).action,
        own: v('propose_move_stop', { stop_id: 'm-lunch', start: '14:00', end: '15:00', reason: '' }).action,
        skipShared: v('propose_skip_stop', { stop_id: 'm-aikosh', reason: '' }).action,
        addGroup: v('propose_add_stop', { day_n: 3, start: '16:00', end: '17:00', title: ' Чайная церемония ', place_name: 'Camellia', note: '', lat: 35.0012345, lng: 135.77, target: 'group' }).action,
        exp: v('propose_add_expense', { amount: 1200.456, currency: 'JPY', category: 'food', title: 'Рамен' }).action,
      };""")
    for k in ("badTime", "backwards", "unknown", "theirs", "hidden", "long", "noDay", "oneCoord", "eur", "cat", "huge", "neg"):
        assert r[k], k
    assert r["guestGroup"] == {"kind": "move", "stop_id": "d3e3", "day_n": 3, "title": "Тэнрю-дзи, сад дзен", "reason": "выспаться",
                               "from_s": "08:30", "from_e": "09:30", "start": "11:00", "end": "12:00", "scope": "group", "how": "propose"}
    assert r["hostGroup"]["how"] == "plan" and r["own"]["how"] == "save" and r["own"]["scope"] == "mine"
    assert r["skipShared"]["scope"] == "shared"
    assert r["addGroup"]["title"] == "Чайная церемония" and r["addGroup"]["lat"] == 35.00123 and r["addGroup"]["how"] == "propose"
    assert r["exp"] == {"kind": "expense", "amount": 1200.46, "currency": "JPY", "category": "food", "title": "Рамен"}


def test_history_is_normalised_and_photos_ride_only_on_the_last_question():
    big = "A" * 1_700_000
    r = node(f"""return {{
      a: L.normaliseHistory([{{ role: 'assistant', text: 'hi' }}, {{ role: 'user', text: ' q1 ' }}, {{ role: 'user', text: 'q2' }},
                             {{ role: 'system', text: 'x' }}, {{ role: 'assistant', text: 'a1' }}, {{ role: 'user', text: 'q3', images: [{{ media_type: 'image/jpeg', data: 'QUJD' }}] }}]),
      endsWithAssistant: L.normaliseHistory([{{ role: 'user', text: 'q' }}, {{ role: 'assistant', text: 'a' }}]),
      long: L.normaliseHistory(Array.from({{ length: 61 }}, (_, i) => ({{ role: i % 2 ? 'assistant' : 'user', text: 'x'.repeat(5000) }}))),
      badImgs: L.normaliseHistory([{{ role: 'user', text: '', images: [{{ media_type: 'image/gif', data: 'QUJD' }}, {{ media_type: 'image/png', data: '<script>' }}, {{ media_type: 'image/png', data: '{big}' }}] }}]),
      onlyPhoto: L.normaliseHistory([{{ role: 'user', text: '', images: [{{ media_type: 'image/png', data: 'QUJD' }}] }}]),
      notArray: L.normaliseHistory('hi') }};""")
    a = r["a"]
    assert [m["role"] for m in a] == ["user", "assistant", "user"] and a[0]["content"] == "q1\n\nq2"
    assert a[2]["content"] == [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "QUJD"}}, {"type": "text", "text": "q3"}]
    assert r["endsWithAssistant"] is None and r["notArray"] is None and r["badImgs"] is None
    assert len(r["long"]) <= 20 and r["long"][0]["role"] == "user" and all(len(m["content"]) <= 2000 for m in r["long"])
    assert r["onlyPhoto"][0]["content"][1] == {"type": "text", "text": "(фото)"}


def test_app_help_covers_every_feature():
    topics = ["вкладка Сейчас", "День", "Дела", "Деньги", "расход", "Мои рейсы", "Показать по-японски", "Пешком", "Ехать вместе с", "лица", "предложение",
              "уведомления", "билет", "офлайн", "настройки", "на экран Домой", "Без меня"]
    r = node(f"return {json.dumps(topics)}.map(t => L.appHelp(t));")
    for t, ans in zip(topics, r):
        assert not ans.startswith("Не нашёл"), t
    assert node("return L.appHelp('квантовая физика');").startswith("Не нашёл")


def test_emergency_puts_insurance_first_and_card_perks_answer_the_question():
    r = node("""return { med: K.emergencyInfo('болит зуб'), bag: K.emergencyInfo('потерян багаж'), sh: K.emergencyInfo('Шанхай полиция'),
                 pass: K.emergencyInfo('потерял паспорт'), vague: K.emergencyInfo('помогите'), esim: K.cardPerks('как поставить eSIM'),
                 all: K.cardPerks('что даёт карта') };""")
    assert r["med"].index("Страховка") < r["med"].index("Полиция 110") and "+44 1273 765321" in r["med"]
    assert r["bag"].index("PIR") < r["bag"].index("110")
    assert "Скорая 120" in r["sh"] and "Посольство в Токио" in r["pass"]
    assert "119" in r["vague"] and "Страховка" in r["vague"]
    assert "Flexiroam" in r["esim"] and "LoungeKey" not in r["esim"] and "CVV" in r["esim"] and "LoungeKey" in r["all"]


def test_currency_profile_and_translate_inputs():
    r = node("""const rates = { KZT: 3.5, USD: 0.0066 };
      return { y2k: L.convert(3500, 'JPY', 'KZT', rates), k2u: L.convert(35000, 'KZT', 'USD', rates), bad: L.convert(1, 'EUR', 'JPY', rates),
        rates: L.normaliseRates({ KZT: 999, USD: 'x' }),
        prof: L.normaliseProfile({ name: 'Саня'.repeat(20), lang: 'de', tone: 'fun', energy: 'low', food: 'халяль', notify: { evening: false } }),
        text: L.profileText({ name: 'Саня', lang: 'kk' }, rates),
        tr: L.normaliseTranslate({ text: 'Где туалет?', from: 'ru', to: 'ja' }), trBad: L.normaliseTranslate({ text: 'x', from: 'ru', to: 'en' }) };""")
    assert r["y2k"] == 12250 and r["k2u"] == 66 and r["bad"] is None
    assert r["rates"] == {"KZT": 3.4, "USD": 0.0067}
    p = r["prof"]
    assert len(p["name"]) == 40 and p["lang"] == "ru" and p["tone"] == "fun" and p["notify"] == {"morning": True, "place": True, "evening": False}
    assert "обращаться «Саня»" in r["text"] and "казахский" in r["text"] and "3.5 ₸" in r["text"]
    assert r["tr"] == {"text": "Где туалет?", "from": "ru", "to": "ja"} and r["trBad"] is None


AGENT = """
const idx = L.tripIndex(%s); const sent = [];
const script = %s; let i = 0;
const create = async body => { sent.push(JSON.parse(JSON.stringify(body.messages))); return script[Math.min(i++, script.length - 1)]; };
const out = await L.runAgent({ create, system: L.buildSystem('ctx'), messages: [{ role: 'user', content: 'q' }], idx, rates: { KZT: 3.5, USD: 0.0066 } });
return { out, sent, calls: i };"""


def agent(script, st=None):
    return node(AGENT % (json.dumps(st or state()), json.dumps(script)))


def test_agent_loop_collects_proposals_and_cards_and_returns_blocks_verbatim():
    think = {"type": "thinking", "thinking": "", "signature": "sig"}
    r = agent([
        {"stop_reason": "tool_use", "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 7},
         "content": [think, {"type": "tool_use", "id": "t1", "name": "propose_move_stop", "input": {"stop_id": "m-lunch", "start": "14:00", "end": "15:00", "reason": "дождь"}},
                     {"type": "tool_use", "id": "t2", "name": "propose_move_stop", "input": {"stop_id": "nope", "start": "14:00", "end": "15:00", "reason": ""}},
                     {"type": "tool_use", "id": "t3", "name": "show_japanese", "input": {"japanese": "トイレはどこですか", "reading": "тоирэ ва доко", "meaning": "Где туалет?"}},
                     {"type": "tool_use", "id": "t4", "name": "suggest_place", "input": {"name": "Нисики", "query": "Nishiki Market", "from": "Kyoto Station"}},
                     {"type": "tool_use", "id": "t5", "name": "emergency_info", "input": {"topic": "травма"}}]},
        {"stop_reason": "pause_turn", "usage": {"server_tool_use": {"web_search_requests": 1}}, "content": [{"type": "server_tool_use", "id": "s1", "name": "web_search", "input": {"query": "x"}}]},
        {"stop_reason": "end_turn", "usage": {"input_tokens": 3, "output_tokens": 2},
         "content": [think, {"type": "text", "text": "Перенёс бы обед. ", "citations": [{"url": "https://www.japan.travel/x", "title": "JNTO"}, {"url": "javascript:x"}]}, {"type": "text", "text": "Нажмите «Применить»."}]}])
    out, sent = r["out"], r["sent"]
    assert r["calls"] == 3 and out["reply"] == "Перенёс бы обед. Нажмите «Применить»." and out["stop"] == "done"
    assert [a["stop_id"] for a in out["actions"]] == ["m-lunch"] and out["actions"][0]["id"] == "a1" and out["sos"] is True
    assert [c["kind"] for c in out["cards"]] == ["ja", "place"]
    assert out["cards"][1]["url"] == "https://www.google.com/maps/dir/?api=1&origin=Kyoto%20Station&destination=Nishiki%20Market&travelmode=transit"
    assert out["sources"] == [{"title": "JNTO", "url": "https://www.japan.travel/x"}]
    assert out["usage"]["input_tokens"] == 13 and out["usage"]["cache_read_input_tokens"] == 7 and out["usage"]["web_search_requests"] == 1
    second = sent[1]
    assert second[1]["role"] == "assistant" and second[1]["content"][0] == think                       # thinking goes back unchanged
    results = {x["tool_use_id"]: x for x in second[2]["content"]}
    assert "ждёт его решения" in results["t1"]["content"] and results["t2"].get("is_error") and "Страховка" in results["t5"]["content"]
    assert sent[2][-1]["content"][0]["type"] == "server_tool_use"                                       # pause_turn resumed as-is


def test_agent_refusal_max_tokens_and_the_iteration_cap():
    loop = {"stop_reason": "tool_use", "usage": {}, "content": [{"type": "tool_use", "id": "t", "name": "get_day", "input": {"day_n": 3}}]}
    r = agent([{"stop_reason": "tool_use", "usage": {}, "content": [{"type": "tool_use", "id": "t", "name": "propose_skip_stop", "input": {"stop_id": "d3e3", "reason": ""}}]},
               {"stop_reason": "refusal", "usage": {}, "content": []}])
    assert r["out"]["reply"].startswith("С этим я помочь не могу") and r["out"]["actions"] == []
    r = agent([{"stop_reason": "max_tokens", "usage": {}, "content": [{"type": "text", "text": "Начало"}]}])
    assert r["out"]["reply"].startswith("Начало") and "оборвался" in r["out"]["reply"]
    r = agent([loop])
    assert r["calls"] == 8 and r["out"]["stop"] == "iterations" and r["out"]["reply"]


def test_one_file_bundle_is_current_and_runs_end_to_end(tmp_path):
    sys.path.insert(0, str(ROOT / "supabase" / "functions"))
    import bundle
    for fn in ("assistant", "notify"):
        assert (ROOT / "supabase" / "functions" / fn / "one_file.ts").read_text(encoding="utf-8") == bundle.bundle(fn), f"run: python3 supabase/functions/bundle.py {fn}"
    src = (FN / "one_file.ts").read_text(encoding="utf-8")
    assert "from \"./" not in src and "from './" not in src and "\nexport " not in src and "ANTHROPIC_API_KEY" in src
    chat = src.split("Deno.serve", 1)[1].split("return tick(req);", 1)[1]
    assert "SERVICE_ROLE" not in chat                                                        # the chat path never uses the service role
    stub = """(globalThis as any).Deno = { env: { get: (k: string) => ({ SUPABASE_URL: 'https://p.supabase.co', SUPABASE_ANON_KEY: 'anon', ANTHROPIC_API_KEY: 'k' } as any)[k] }, serve: (f: any) => { (globalThis as any).__h = f; } };
(globalThis as any).__calls = [];
const Anthropic: any = class { beta = { messages: { create: async (b: any) => { (globalThis as any).__calls.push(b);
  return b.messages.length === 1 && typeof b.messages[0].content === 'string' && !b.tools ? { stop_reason: 'end_turn', content: [{ type: 'text', text: 'トイレ' }], usage: {} }
    : { stop_reason: 'end_turn', content: [{ type: 'text', text: 'Привет' }], usage: { input_tokens: 1, output_tokens: 1 } }; } } }; };"""
    code = re.sub(r'^import Anthropic from "npm:@anthropic-ai/sdk@[\d.]+";', lambda m: stub, src, flags=re.M)
    code = re.sub(r'^import \{ createClient \} from "npm:@supabase/supabase-js@[\d.]+";', "const createClient: any = () => { throw new Error('no db in tests'); };", code, flags=re.M)
    (tmp_path / "fn.mts").write_text(code, encoding="utf-8")
    st = state()
    driver = f"""
const ST = {json.dumps(st)};
globalThis.fetch = async (url, init) => {{
  if (String(url).endsWith('/rpc/ai_bump')) {{ globalThis.__bump = (globalThis.__bump || 0) + 1;
    return init.headers.Authorization === 'Bearer member' ? new Response('true', {{ status: 200 }}) : new Response('{{}}', {{ status: 400 }}); }}
  globalThis.__rpc = {{ url, init }};
  return init.headers.Authorization === 'Bearer member' ? new Response(JSON.stringify(ST), {{ status: 200 }}) : new Response('{{"message":"not a member"}}', {{ status: 400 }}); }};
await import('{(tmp_path / "fn.mts").as_uri()}');
const h = globalThis.__h, O = 'https://zakcination.github.io';
const post = (auth, body) => h(new Request('https://p.supabase.co/functions/v1/assistant', {{ method: 'POST', headers: {{ origin: O, authorization: auth, apikey: 'anon' }}, body: JSON.stringify(body) }}));
const pre = await h(new Request('https://p.supabase.co/functions/v1/assistant', {{ method: 'OPTIONS', headers: {{ origin: O }} }}));
const evil = await h(new Request('https://p.supabase.co/functions/v1/assistant', {{ method: 'OPTIONS', headers: {{ origin: 'https://evil.example' }} }}));
const noAuth = await post('', {{ trip: 'miras-aikosh', messages: [{{ role: 'user', text: 'q' }}] }});
const stranger = await post('Bearer stranger', {{ trip: 'miras-aikosh', messages: [{{ role: 'user', text: 'q' }}] }});
const rpc = globalThis.__rpc;
const ok = await post('Bearer member', {{ trip: 'miras-aikosh', view_day: 3, messages: [{{ role: 'user', text: 'Что сегодня?' }}], profile: {{ name: 'Саня' }}, rates: {{ KZT: 3.5 }} }});
const tr = await post('Bearer member', {{ trip: 'miras-aikosh', mode: 'translate', text: 'Где туалет?', from: 'ru', to: 'ja' }});
const calls = globalThis.__calls;
console.log(JSON.stringify({{ pre: [pre.status, pre.headers.get('access-control-allow-origin'), pre.headers.get('access-control-allow-headers')],
  evil: evil.headers.get('access-control-allow-origin'), noAuth: noAuth.status, stranger: stranger.status, rpc: [rpc.url, rpc.init.headers.apikey, JSON.parse(rpc.init.body)],
  ok: [ok.status, await ok.json(), ok.headers.get('access-control-allow-origin')], tr: [tr.status, await tr.json()], bump: globalThis.__bump,
  call: {{ model: calls[0].model, effort: calls[0].output_config.effort, thinking: calls[0].thinking ?? null, sys: calls[0].system[1].text }} }}));
"""
    (tmp_path / "drive.mjs").write_text(driver, encoding="utf-8")
    p = subprocess.run([NODE, "--experimental-strip-types", "--no-warnings", str(tmp_path / "drive.mjs")], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    r = json.loads(p.stdout.strip().splitlines()[-1])
    assert r["pre"][0] == 204 and r["pre"][1] == "https://zakcination.github.io" and "apikey" in r["pre"][2] and r["evil"] is None
    assert r["noAuth"] == 401 and r["stranger"] == 403
    assert r["rpc"] == ["https://p.supabase.co/rest/v1/rpc/group_state", "anon", {"p_trip": "miras-aikosh"}]
    assert r["ok"][0] == 200 and r["ok"][1]["reply"] == "Привет" and r["ok"][1]["actions"] == [] and r["ok"][2] == "https://zakcination.github.io"
    assert r["tr"] == [200, {"text": "トイレ", "usage": {}}] and r["bump"] == 2          # one count per question; strangers never reach it
    c = r["call"]
    assert c["model"] == "claude-opus-5-5" and c["effort"] == "low" and c["thinking"] is None
    assert "Сания" in c["sys"] and "обращаться «Саня»" in c["sys"] and "На экране сейчас день 3" in c["sys"]


# ---------- P1: scheduled messages (digest.mjs) and the SQL behind them ----------
def digest(js, st=None, **over):
    st = st or state()
    D = {"members": st["members"], "plan": st["plan"], "parts": st["parts"], "joins": st["joins"], "my_stops": st["my_stops"], "sent": [],
         "profiles": {m["id"]: {"lang": "ru"} for m in st["members"]}}            # everyone set up the assistant
    if "profiles" in over: over = {**over, "profiles": {**D["profiles"], **over["profiles"]}}
    D.update(over)
    code = (f"import * as G from '{(FN / 'digest.mjs').as_uri()}';\nconst D = {json.dumps(D)};\n"
            f"const out = await (async () => {{ {js} }})(); console.log(JSON.stringify(out));")
    r = subprocess.run([NODE, "--input-type=module"], input=code, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def jst(s):
    return f"Date.parse('{s}+09:00')"


def test_morning_place_and_evening_come_from_each_persons_own_day():
    r = digest(f"""return {{ m: G.dueMessages(D, {jst('2026-10-19T08:05:00')}), p: G.dueMessages(D, {jst('2026-10-19T09:40:00')}),
      e: G.dueMessages(D, {jst('2026-10-19T22:10:00')}), none: G.dueMessages(D, {jst('2026-10-19T12:00:00')}) }};""")
    san = [x for x in r["m"] if x["member"] == S]
    assert len(san) == 1 and san[0]["kind"] == "morning" and san[0]["push"] and san[0]["key"] == "morning:2026-10-19"
    assert [e["id"] for e in san[0]["stops"]] == ["d3e2", "d3e3", "d3e4"]                       # what is still ahead at 08:00
    assert {x["member"] for x in r["m"]} == {H, A, S}                                         # hosts are in everything
    assert [x["key"] for x in r["p"] if x["member"] == S] == ["place:d3e3"]
    assert [x["kind"] for x in r["e"] if x["member"] == S] == ["evening"]
    assert not [x for x in r["none"] if x["kind"] in ("morning", "evening")]
    # a guest who joined nothing gets nothing; a host does
    st = state(members=state()["members"] + [{"id": "g-2", "name": "Шахи", "role": "guest"}])
    r2 = digest(f"return G.dueMessages(D, {jst('2026-10-18T08:05:00')});", st=st, members=st["members"])
    assert not [x for x in r2 if x["member"] == "g-2"] and [x for x in r2 if x["member"] == H]


def test_sent_once_capped_quiet_at_night_and_off_when_the_profile_says_so():
    late = {"id": "m-late", "member": S, "day": 3, "shared": False, "ev": {"s": "22:40", "e": "23:10", "t": "Онсэн", "cat": "activity"}}
    st = state(my_stops=state()["my_stops"] + [late])
    sent = [{"member": S, "key": "morning:2026-10-19", "day": "2026-10-19", "pushed": True}]
    r = digest(f"""return {{ again: G.dueMessages(D, {jst('2026-10-19T08:20:00')}).filter(x => x.member === '{S}'),
      night: G.dueMessages(D, {jst('2026-10-19T23:15:00')}).filter(x => x.member === '{S}') }};""", st=st, sent=sent)
    assert not [x for x in r["again"] if x["kind"] == "morning"] and r["night"][0]["key"] == "place:m-late" and r["night"][0]["push"] is False   # written, not pushed
    many = sent + [{"member": S, "key": f"place:x{i}", "day": "2026-10-19", "pushed": True} for i in range(2)]
    r = digest(f"return G.dueMessages(D, {jst('2026-10-19T09:40:00')}).filter(x => x.member === '{S}');", sent=many)
    assert r[0]["key"] == "place:d3e3" and r[0]["push"] is False                               # 3 pushed + the evening's slot = 4
    r = digest(f"return G.dueMessages(D, {jst('2026-10-19T22:05:00')}).filter(x => x.member === '{S}');", sent=many)
    assert r[0]["kind"] == "evening" and r[0]["push"] is True
    r = digest(f"return G.dueMessages(D, {jst('2026-10-19T09:40:00')}).filter(x => x.member === '{S}');", profiles={S: {"notify": {"place": False}}})
    assert r[0]["push"] is False
    r = digest("return [G.quiet(Date.parse('2026-10-19T07:00:00+09:00'), 9), G.quiet(Date.parse('2026-10-19T07:45:00+09:00'), 9), G.quiet(Date.parse('2026-10-19T22:45:00+09:00'), 9)];")
    assert r == [True, False, True]


def test_shanghai_day_mornings_are_at_eight_shanghai_time():
    r = digest("return G.dueMessages(D, Date.parse('2026-10-28T08:05:00+08:00')).filter(x => x.member === 'h-1');")
    assert r[0]["kind"] == "morning" and r[0]["day"] == 12
    assert not digest("return G.dueMessages(D, Date.parse('2026-10-28T07:05:00+08:00')).filter(x => x.kind === 'morning');")


def test_digest_texts_are_short_profile_only_and_fall_back():
    r = digest(f"""const m = G.dueMessages(D, {jst('2026-10-19T08:05:00')}).find(x => x.member === '{S}');
      const req = G.digestRequest(m);
      return {{ req, ok: G.digestText({{ stop_reason: 'end_turn', content: [{{ type: 'text', text: 'Доброе утро, Саня!\\nСегодня Киото: Тэнрю-дзи в 08:30.' }}] }}, m),
        refused: G.digestText({{ stop_reason: 'refusal', content: [] }}, m), url: G.appUrl('miras-aikosh', m),
        place: G.placeText({{ profile: {{ lang: 'en' }}, stop: {{ t: 'Kinkaku-ji' }} }}) }};""", profiles={S: {"name": "Саня", "lang": "ru", "tone": "fun"}})
    q = r["req"]
    assert q["model"] == "claude-opus-5-5" and q["output_config"] == {"effort": "low"} and q["max_tokens"] <= 600 and "tools" not in q and "thinking" not in q
    txt = q["system"] + q["messages"][0]["content"]
    assert "Саня" in txt and "08:30 Тэнрю-дзи" in txt and "юмором" in txt and "Мирас" not in txt and len(txt) < 1200
    assert r["ok"] == {"title": "Доброе утро, Саня!", "body": "Сегодня Киото: Тэнрю-дзи в 08:30."}
    assert r["refused"]["title"] == "Доброе утро!" and r["url"].endswith("#briefing") and r["place"]["title"] == "How was «Kinkaku-ji»?"


def test_assistant_sql_is_guarded_private_and_idempotent():
    sql = (ROOT / "supabase" / "migrations" / "001_group.sql").read_text(encoding="utf-8")
    block = sql.split("assistant: profile, ratings, scheduled messages", 1)[1]
    for name in ("save_ai_profile", "save_feedback", "my_ai", "feedback_averages", "ai_bump"):
        m = re.search(rf"create or replace function public\.{name}\((.*?)\$\$;", block, re.S)
        assert m and "security definer" in m.group(0) and "set search_path = public, extensions" in m.group(0) and "public._me()" in m.group(0), name
        assert re.search(rf"grant execute on function [^;]*public\.{name}\(", block), name
    for t in ("ai_profiles", "ai_feedback", "ai_sent", "ai_usage"):
        assert f"create table if not exists public.{t}" in block and f"alter table public.{t} enable row level security" in block
    assert "create policy" not in block and "count(*) filter (where f.member <> m.id) >= 2" in block                   # the group sees averages only
    assert "where member = m.id" in block.split("function public.my_ai()")[1].split("$$;")[0]
    assert "assistant-cron" in block and not re.search(r"^\s*(perform|select) cron\.schedule", block, re.M)   # no cron job until approved
    assert "public._ai_tick()\n  from public, anon, authenticated" in block                  # the tick is not callable from the app


def test_no_messages_without_a_profile_or_with_only_the_questionnaire_seed():
    st = state()
    ids = [m["id"] for m in st["members"]]
    r = digest(f"return G.dueMessages(D, {jst('2026-10-19T08:05:00')});", st, profiles={})
    assert r                                                                      # baseline: everyone set up → messages
    none = {i: None for i in ids}
    r = digest(f"return G.dueMessages(D, {jst('2026-10-19T08:05:00')});", st,
               profiles={**none, ids[0]: {"lang": "ru", "seed": True}})
    assert r == []
