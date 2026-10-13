// Supabase Edge Function «assistant»: the in-app travel assistant (Claude). The app calls it with the traveller's own
// session; the function proves group membership through the existing RPC group_state (never the service role), builds a
// small trip context, runs a short tool loop and returns { reply, actions, sources, usage }. It never changes anything:
// actions are proposals the traveller applies in the app. Pure parts live in logic.mjs (tested with Node).
// Secret (Edge Functions → Secrets): ANTHROPIC_API_KEY. SUPABASE_URL / SUPABASE_ANON_KEY are provided by Supabase.
// Deploy as «assistant» with «Verify JWT» ON (the default) for the chat.
// The same file deployed again as «assistant-cron» with «Verify JWT» OFF serves the database's cron tick (scheduled
// morning / after-a-place / evening messages, digest.mjs): that path needs x-hook-secret = HOOK_SECRET (the notify secret),
// reads the trip with the service role (it acts for nobody in particular) and sends pushes through «notify». The chat path
// stays membership-checked through group_state on either deployment.
import Anthropic from "npm:@anthropic-ai/sdk@0.110.0";
import { createClient } from "npm:@supabase/supabase-js@2.45.4";
import { timingSafeEqual } from "node:crypto";
import { appUrl, digestRequest, digestText, dueMessages, fallbackText } from "./digest.mjs";
import { buildSystem, buildTranslateRequest, contextText, normaliseHistory, normaliseRates, normaliseTranslate, profileText, runAgent, translationOf,
  tripIndex } from "./logic.mjs";

const env = (k: string) => Deno.env.get(k) ?? "";
const ORIGINS = [/^https:\/\/zakcination\.github\.io$/, /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/];
const client = new Anthropic({ apiKey: env("ANTHROPIC_API_KEY"), timeout: 40_000, maxRetries: 0 });   // the app gives up at 60 s; never keep paying after that

function cors(req: Request): Record<string, string> {
  const o = req.headers.get("origin") ?? "";
  return ORIGINS.some((r) => r.test(o))
    ? { "Access-Control-Allow-Origin": o, "Vary": "Origin", "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
        "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Max-Age": "86400" }
    : { "Vary": "Origin" };
}
const json = (req: Request, status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors(req), "Content-Type": "application/json; charset=utf-8" } });

/* the caller's own view of the trip — RLS-guarded RPC with the caller's token; any error means "not a member" */
async function groupState(auth: string, apikey: string, trip: string) {
  const r = await fetch(env("SUPABASE_URL") + "/rest/v1/rpc/group_state", {
    method: "POST", headers: { apikey, Authorization: auth, "Content-Type": "application/json" }, body: JSON.stringify({ p_trip: trip }),
  });
  if (!r.ok) return null;
  const s = await r.json().catch(() => null);
  return s && s.me && s.plan ? s : null;
}

/* one more question today for the caller (ai_bump, _me()-guarded); false past the daily cap or on any error */
async function bump(auth: string, apikey: string) {
  const r = await fetch(env("SUPABASE_URL") + "/rest/v1/rpc/ai_bump", {
    method: "POST", headers: { apikey, Authorization: auth, "Content-Type": "application/json" }, body: "{}",
  }).catch(() => null);
  return !!r && r.ok && (await r.json().catch(() => false)) === true;
}

/* why Claude didn't answer, in words the owner can act on (never the key, never the request) */
function claudeError(e: any): string {
  const st = e && typeof e.status === "number" ? e.status : 0, msg = String((e && e.message) || "");
  const name = String((e && e.constructor && e.constructor.name) || "");
  if (/timeout/i.test(name + " " + msg)) return "Claude не ответил вовремя — повторите вопрос короче.";
  if (!st) return "Нет связи с Claude из Supabase — повторите через минуту.";
  if (st === 401) return "Ключ Anthropic не принят (401): проверьте секрет ANTHROPIC_API_KEY — без пробелов, начинается с sk-ant-.";
  if (st === 403) return "Ключу Anthropic запрещён доступ (403): проверьте ключ и организацию в console.anthropic.com.";
  if (st === 400 && /credit|balance|billing/i.test(msg)) return "На балансе Anthropic нет денег (400): пополните в console.anthropic.com → Billing.";
  if (st === 400 && /limit/i.test(msg)) return "Достигнут лимит расходов Anthropic (400): поднимите его в console.anthropic.com → Limits.";
  if (st === 404) return "Модель недоступна для этого ключа (404).";
  if (st === 429) return "Слишком много запросов к Claude (429) — попробуйте через минуту.";
  if (st === 529 || st === 503) return "Claude сейчас перегружен (" + st + ") — попробуйте через минуту.";
  return "Claude вернул ошибку " + st + (msg ? ": " + msg.replace(/sk-ant-[\w-]+/g, "…").slice(0, 160) : "") + ".";
}

const same = (a: string, b: string) => { const x = new TextEncoder().encode(a), y = new TextEncoder().encode(b); return x.length === y.length && timingSafeEqual(x, y); };

/* the cron tick: who is due a morning / place / evening message now; write it to ai_sent (the in-app inbox), push via notify */
async function tick(req: Request) {
  if (!env("HOOK_SECRET") || !same(req.headers.get("x-hook-secret") ?? "", env("HOOK_SECRET"))) return new Response("forbidden", { status: 403 });
  const db = createClient(env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY"), { auth: { persistSession: false } });
  const rows = async (t: string, q: (x: any) => any) => (await q(db.from(t).select("*"))).data ?? [];
  let written = 0, pushed = 0;
  for (const { id: trip } of (await db.from("trips").select("id")).data ?? []) {
    const members = (await db.from("members").select("id, name, role").eq("trip", trip)).data ?? [];
    const ids = members.map((m: any) => m.id);
    if (!ids.length) continue;
    const since = new Date(Date.now() - 2 * 864e5).toISOString().slice(0, 10);
    const D = {
      members, plan: (await db.from("plan").select("doc").eq("trip", trip).single()).data ?? {},
      parts: (await rows("parts", (x) => x.eq("trip", trip))).map((p: any) => p.part),
      joins: await rows("joins", (x) => x.in("member", ids)),
      my_stops: (await rows("my_stops", (x) => x.in("member", ids))).map((r: any) => ({ ...r.s, id: r.id, member: r.member, shared: r.shared })),
      profiles: Object.fromEntries((await rows("ai_profiles", (x) => x.in("member", ids))).map((r: any) => [r.member, r.p])),
      sent: await rows("ai_sent", (x) => x.in("member", ids).gte("day", since)),
    };
    const out: any[] = [];
    for (const m of dueMessages(D, Date.now())) {
      let text = fallbackText(m);
      if (m.kind !== "place" && env("ANTHROPIC_API_KEY")) {
        try { text = digestText(await client.beta.messages.create(digestRequest(m) as any), m); } catch (e: any) { console.error("digest", e && e.message); }
      }
      const { error } = await db.from("ai_sent").insert({ member: m.member, key: m.key, day: m.date, kind: m.kind, ref: m.stop ? m.stop.id : "day:" + m.day,
        title: text.title, body: text.body, pushed: m.push });
      if (error) continue;                                  // already written by an overlapping tick
      written++;
      if (m.push) out.push({ to: [m.member], title: text.title, body: text.body, url: appUrl(trip, m), tag: "ai-" + m.key });
    }
    if (out.length) {
      const r = await fetch(env("SUPABASE_URL") + "/functions/v1/notify", { method: "POST",
        headers: { "Content-Type": "application/json", "x-hook-secret": env("HOOK_SECRET") }, body: JSON.stringify({ type: "direct", trip, messages: out }) }).catch(() => null);
      if (r && r.ok) pushed += out.length;
    }
  }
  return new Response(JSON.stringify({ written, pushed }), { headers: { "Content-Type": "application/json" } });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(req) });
  if (req.method !== "POST") return json(req, 405, { error: "POST only" });
  if (req.headers.has("x-hook-secret")) return tick(req);
  const auth = req.headers.get("authorization") ?? "";
  if (!/^Bearer [\w.-]+$/.test(auth)) return json(req, 401, { error: "Войдите в группу." });
  const raw = await req.text();
  if (raw.length > 4_000_000) return json(req, 413, { error: "Слишком много — пришлите одно фото или начните новый разговор." });
  let body: any = null;
  try { body = JSON.parse(raw); } catch { /* below */ }
  if (!body || typeof body.trip !== "string" || !/^[a-z0-9-]{1,60}$/.test(body.trip)) return json(req, 400, { error: "bad request" });
  const tr = body.mode === "translate" ? normaliseTranslate(body) : null;
  const messages = tr ? null : normaliseHistory(body.messages);
  if (!tr && !messages) return json(req, 400, { error: "Напишите вопрос." });

  const st = await groupState(auth, req.headers.get("apikey") || env("SUPABASE_ANON_KEY"), body.trip);   // the Bearer decides who; group_state is _me()-guarded
  if (!st) return json(req, 403, { error: "Ассистент — только для участников группы." });
  const only = env("ASSISTANT_ONLY").split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  if (only.length && !only.includes(String(st.me.name || "").trim().toLowerCase()))
    return json(req, 403, { error: "Встроенный ассистент включён только для владельца. Нажмите ✦ → «Спросить в Claude»." });
  if (!env("ANTHROPIC_API_KEY")) return json(req, 503, { error: "Ассистент ещё не настроен." });
  if (!(await bump(auth, req.headers.get("apikey") || env("SUPABASE_ANON_KEY")))) return json(req, 429, { error: "На сегодня вопросов достаточно — продолжим завтра." });

  try {
    if (tr) {
      const res: any = await client.beta.messages.create(buildTranslateRequest(tr) as any);
      const text = translationOf(res);
      return text ? json(req, 200, { text, usage: res.usage }) : json(req, 200, { text: null, error: "Не получилось перевести." });
    }
    const idx = tripIndex(st);
    const viewDay = Number.isInteger(body.view_day) ? body.view_day : null;
    const system = buildSystem(contextText(idx, Date.now(), viewDay) + "\n" + profileText(body.profile, body.rates));
    const out = await runAgent({ create: (b: any, ms: number) => client.beta.messages.create(b, { timeout: ms, maxRetries: 0 }), system, messages, idx, rates: normaliseRates(body.rates) });
    return json(req, 200, out);
  } catch (e: any) {
    const status = e && typeof e.status === "number" ? e.status : 0;
    console.error("assistant", status, e && e.message);
    return json(req, status === 429 || status === 529 ? 503 : 502, { error: claudeError(e), code: status || null });
  }
});
