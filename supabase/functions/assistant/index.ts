// Supabase Edge Function «assistant»: the in-app travel assistant (Claude). The app calls it with the traveller's own
// session; the function proves group membership through the existing RPC group_state (never the service role), builds a
// small trip context, runs a short tool loop and returns { reply, actions, sources, usage }. It never changes anything:
// actions are proposals the traveller applies in the app. Pure parts live in logic.mjs (tested with Node).
// Secret (Edge Functions → Secrets): ANTHROPIC_API_KEY. SUPABASE_URL / SUPABASE_ANON_KEY are provided by Supabase.
// Deploy with «Verify JWT» ON (the default).
import Anthropic from "npm:@anthropic-ai/sdk@0.110.0";
import { buildSystem, buildTranslateRequest, contextText, normaliseHistory, normaliseRates, normaliseTranslate, profileText, runAgent, translationOf,
  tripIndex } from "./logic.mjs";

const env = (k: string) => Deno.env.get(k) ?? "";
const ORIGINS = [/^https:\/\/zakcination\.github\.io$/, /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/];
const client = new Anthropic({ apiKey: env("ANTHROPIC_API_KEY"), timeout: 50_000, maxRetries: 1 });

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

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(req) });
  if (req.method !== "POST") return json(req, 405, { error: "POST only" });
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

  const st = await groupState(auth, env("SUPABASE_ANON_KEY") || req.headers.get("apikey") || "", body.trip);
  if (!st) return json(req, 403, { error: "Ассистент — только для участников группы." });
  if (!env("ANTHROPIC_API_KEY")) return json(req, 503, { error: "Ассистент ещё не настроен." });

  try {
    if (tr) {
      const res: any = await client.beta.messages.create(buildTranslateRequest(tr) as any);
      const text = translationOf(res);
      return text ? json(req, 200, { text, usage: res.usage }) : json(req, 200, { text: null, error: "Не получилось перевести." });
    }
    const idx = tripIndex(st);
    const viewDay = Number.isInteger(body.view_day) ? body.view_day : null;
    const system = buildSystem(contextText(idx, Date.now(), viewDay) + "\n" + profileText(body.profile, body.rates));
    const out = await runAgent({ create: (b: any) => client.beta.messages.create(b), system, messages, idx, rates: normaliseRates(body.rates) });
    return json(req, 200, out);
  } catch (e: any) {
    const status = e && typeof e.status === "number" ? e.status : 0;
    console.error("assistant", status, e && e.message);
    if (status === 429 || status === 529) return json(req, 503, { error: "Ассистент сейчас перегружен — попробуйте через минуту." });
    return json(req, 502, { error: "Ассистент сейчас недоступен — попробуйте позже." });
  }
});
