// Supabase Edge Function «notify»: the database pings it (triggers, daily cron) with an event; it works out who should
// hear about it (logic.mjs) and sends Web Push to their phones. Secrets (Edge Functions → Secrets):
//   VAPID_PUBLIC, VAPID_PRIVATE, HOOK_SECRET   (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are provided by Supabase)
// Deploy with «Verify JWT» off: the database proves itself with x-hook-secret instead.
import webpush from "npm:web-push@3.6.7";
import { createClient } from "npm:@supabase/supabase-js@2.45.4";
import { messages } from "./logic.mjs";
import { timingSafeEqual } from "node:crypto";

const same = (a: string, b: string) => { const x = new TextEncoder().encode(a), y = new TextEncoder().encode(b); return x.length === y.length && timingSafeEqual(x, y); };

const env = (k: string) => Deno.env.get(k) ?? "";
webpush.setVapidDetails("https://zakcination.github.io/japan-2026/", env("VAPID_PUBLIC"), env("VAPID_PRIVATE"));
const db = createClient(env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY"), { auth: { persistSession: false } });

async function tripOf(ev: any): Promise<string[]> {
  if (ev.type === "deadlines") return ((await db.from("trips").select("id")).data ?? []).map((t: any) => t.id);
  if (ev.type === "plan") return [ev.trip];
  if (ev.type === "proposal" || ev.type === "decision") return [((await db.from("proposals").select("trip").eq("id", ev.id).single()).data ?? {}).trip].filter(Boolean);
  if (ev.type === "join") return [((await db.from("members").select("trip").eq("id", ev.member).single()).data ?? {}).trip].filter(Boolean);
  return [];
}

async function load(trip: string) {
  const members = (await db.from("members").select("id, name, role").eq("trip", trip)).data ?? [];
  const ids = members.map((m: any) => m.id);
  const rows = async (t: string, q: (x: any) => any) => (await q(db.from(t).select("*"))).data ?? [];
  return {
    trip, members,
    proposals: await rows("proposals", x => x.eq("trip", trip)),
    plan: (await db.from("plan").select("doc").eq("trip", trip).single()).data ?? {},
    parts: (await rows("parts", x => x.eq("trip", trip))).map((p: any) => p.part),
    joins: await rows("joins", x => x.in("member", ids)),
    recipes: (await rows("recipes", x => x.eq("trip", trip))).map((r: any) => r.r),
    task_state: await rows("task_state", x => x.in("member", ids)),
    subs: await rows("push_subs", x => x.in("member", ids)),
  };
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return new Response("POST only", { status: 405 });
  if (!env("HOOK_SECRET") || !same(req.headers.get("x-hook-secret") ?? "", env("HOOK_SECRET"))) return new Response("forbidden", { status: 403 });
  const ev = await req.json().catch(() => null);
  if (!ev || typeof ev.type !== "string") return new Response("bad event", { status: 400 });
  let sent = 0, gone = 0;
  for (const trip of await tripOf(ev)) {
    const D = await load(trip);
    const jobs = messages(ev, D, Date.now()).flatMap(m => D.subs.filter((x: any) => m.to.includes(x.member)).map((s: any) => async () => {
      try {
        await webpush.sendNotification(s.sub, JSON.stringify({ title: m.title, body: m.body, url: m.url, tag: m.tag }), { TTL: 86400, urgency: "normal", timeout: 10000 });
        sent++;
      } catch (e: any) {
        if (e && (e.statusCode === 404 || e.statusCode === 410)) { await db.from("push_subs").delete().eq("endpoint", s.endpoint); gone++; }
      }
    }));
    await Promise.allSettled(jobs.map(j => j()));                           // one slow phone never holds up the rest
  }
  return new Response(JSON.stringify({ sent, gone }), { headers: { "Content-Type": "application/json" } });
});
