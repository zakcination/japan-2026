// Scheduled messages from the assistant (P1) — pure, tested with Node. A cron (every 10 min) calls the function's tick:
// for each member, from that member's OWN day plan (group stops they are in, incl. «ехать вместе с», plus own/joined stops):
//   morning  ~08:00 local of the trip day (Japan UTC+9; Shanghai days UTC+8) — mood, goals, energy, the next 2–3 stops;
//   place    when a stop ends — «как вам?» push + a 5-star card in the app;
//   evening  ~22:00 local — how was the day.
// At most PUSH_CAP pushes a day (morning and evening are kept a slot), never in quiet hours; everything is also in the app.
import { effectiveIn, MODEL, normaliseProfile, LANGS } from './logic.mjs';

export const PUSH_CAP = 4;
export const QUIET = { from: 22 * 60 + 30, to: 7 * 60 + 30 };            // trip-local quiet hours (22:30–07:30)
export const RATE_CATS = ['activity', 'food', 'event'];
const WIN = { morning: 90, place: 40, evening: 60 };                      // minutes a due message stays due (the cron runs every 10)
const HMRE = /^([01]\d|2[0-3]):[0-5]\d$/;
const toMin = s => HMRE.test(s || '') ? +s.slice(0, 2) * 60 + +s.slice(3) : NaN;
const str = (v, n) => String(v == null ? '' : v).replace(/\s+/g, ' ').trim().slice(0, n);
const addDays = (iso, n) => { const d = new Date(iso + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const tzOf = e => (e && +e.off === 480 ? 8 : 9);
/* the UTC ms of a local wall-clock time on a date in a fixed offset */
export const at = (date, min, tz) => Date.parse(date + 'T00:00:00Z') + (min - tz * 60) * 60e3;
export const localMin = (ms, tz) => { const d = new Date(ms + tz * 3600e3); return d.getUTCHours() * 60 + d.getUTCMinutes(); };
export const quiet = (ms, tz) => { const m = localMin(ms, tz); return m >= QUIET.from || m < QUIET.to; };

/* one member's day: the stops they will actually be at, sorted */
export function myDay(D, mid, n) {
  const doc = (D.plan && D.plan.doc) || { days: [] }, inSet = effectiveIn(doc, D, mid);
  const d = (doc.days || []).find(x => +x.n === n); if (!d) return [];
  const mineIn = s => s.member === mid || (s.shared && (D.joins || []).some(j => j.member === mid && j.scope === 'mine' && j.ref === s.id && j.mode === 'in'));
  const g = (d.ev || []).filter(e => inSet.has(String(e.id))).map(e => ({ id: String(e.id), s: e.s, e: e.e, t: str(e.t, 100), cat: e.cat, off: e.off }));
  const m = (D.my_stops || []).filter(s => +s.day === n && mineIn(s)).map(s => ({ id: s.id, s: (s.ev || {}).s, e: (s.ev || {}).e, t: str((s.ev || {}).t, 100), cat: (s.ev || {}).cat || 'activity' }));
  return [...g, ...m].filter(e => HMRE.test(e.s || '')).sort((a, b) => toMin(a.s) - toMin(b.s));
}

/* what is due now for every member; `sent` = rows already written (member, key, day, pushed) */
export function dueMessages(D, now) {
  const doc = (D.plan && D.plan.doc) || { days: [] };
  const start = /^\d{4}-\d{2}-\d{2}$/.test(doc.start || '') ? doc.start : ((doc.days || [])[0] || {}).date;
  if (!start) return [];
  const sent = new Set((D.sent || []).map(r => r.member + '|' + r.key));
  const pushed = (mid, date) => (D.sent || []).filter(r => r.member === mid && r.day === date && r.pushed).length;
  const out = [];
  for (const mem of D.members || []) {
    const raw = (D.profiles || {})[mem.id];
    if (!raw || raw.seed) continue;                                  // never message someone who hasn't set up the assistant (a questionnaire seed isn't consent)
    const prof = normaliseProfile((D.profiles || {})[mem.id]);
    let used = null;
    for (const d of doc.days || []) {
      const date = addDays(start, +d.n - 1), stops = myDay(D, mem.id, +d.n);
      if (!stops.length) continue;
      if (used == null || used.date !== date) used = { date, n: pushed(mem.id, date) };
      const items = [];
      const mTz = tzOf(stops[0]), mAt = at(date, 8 * 60, mTz);
      if (now >= mAt && now < mAt + WIN.morning * 60e3) {
        const next = stops.filter(e => toMin(e.e || e.s) >= 8 * 60).slice(0, 3);
        items.push({ kind: 'morning', key: 'morning:' + date, tz: mTz, stops: next.length ? next : stops.slice(0, 3), on: prof.notify.morning });
      }
      for (const e of stops) {
        if (!RATE_CATS.includes(e.cat) || !HMRE.test(e.e || '')) continue;
        let end = toMin(e.e); if (end < toMin(e.s)) end += 1440;
        const tAt = at(date, end, tzOf(e));
        if (now >= tAt && now < tAt + WIN.place * 60e3) items.push({ kind: 'place', key: 'place:' + e.id, tz: tzOf(e), stop: e, on: prof.notify.place });
      }
      const eTz = tzOf(stops[stops.length - 1]), eAt = at(date, 22 * 60, eTz);
      if (now >= eAt && now < eAt + WIN.evening * 60e3) items.push({ kind: 'evening', key: 'evening:' + date, tz: eTz, on: prof.notify.evening });
      for (const it of items) {
        if (sent.has(mem.id + '|' + it.key)) continue;
        const reserve = it.kind === 'place' ? (sent.has(mem.id + '|evening:' + date) ? 0 : 1) : 0;   // keep a slot for the evening
        const push = it.on && !quiet(now, it.tz) && used.n + reserve < PUSH_CAP;
        if (push) used.n++;
        out.push({ member: mem.id, name: mem.name, day: +d.n, date, kind: it.kind, key: it.key, push, stop: it.stop || null, stops: it.stops || null,
                   label: str(d.label, 80), summary: str(d.summary, 200), profile: prof });
      }
    }
  }
  return out;
}

/* texts: morning and evening written by the model from the profile and the day only (short, cheap); places from a template */
const PLACE = {
  ru: e => ({ title: `Как вам «${e.t}»?`, body: 'Оцените в приложении — пять звёзд и пара слов, если хочется.' }),
  kk: e => ({ title: `«${e.t}» қалай болды?`, body: 'Қосымшада бағалаңыз — бес жұлдыз және қаласаңыз бір-екі сөз.' }),
  en: e => ({ title: `How was «${e.t}»?`, body: 'Rate it in the app — five stars and a few words if you like.' }),
};
const FALLBACK = {
  morning: { ru: m => ({ title: 'Доброе утро!', body: 'Сегодня: ' + m.stops.map(e => `${e.s} ${e.t}`).join(', ') }),
             kk: m => ({ title: 'Қайырлы таң!', body: 'Бүгін: ' + m.stops.map(e => `${e.s} ${e.t}`).join(', ') }),
             en: m => ({ title: 'Good morning!', body: 'Today: ' + m.stops.map(e => `${e.s} ${e.t}`).join(', ') }) },
  evening: { ru: () => ({ title: 'Как прошёл день?', body: 'Оцените день в приложении и напишите пару слов.' }),
             kk: () => ({ title: 'Күн қалай өтті?', body: 'Қосымшада күнді бағалап, бір-екі сөз жазыңыз.' }),
             en: () => ({ title: 'How was your day?', body: 'Rate the day in the app and add a few words.' }) },
};
export function placeText(m) { return (PLACE[m.profile.lang] || PLACE.ru)(m.stop); }
export function fallbackText(m) { return m.kind === 'place' ? placeText(m) : (FALLBACK[m.kind][m.profile.lang] || FALLBACK[m.kind].ru)(m); }
const TONE = { calm: 'тепло и спокойно', fun: 'с лёгким юмором', strict: 'коротко и по делу' };
const ENERGY = { low: 'бережёт силы', mid: 'обычная', high: 'полон сил' };
export function digestRequest(m) {
  const p = m.profile, what = m.kind === 'morning'
    ? `Утреннее сообщение на день ${m.day} (${m.label}${m.summary ? ': ' + m.summary : ''}). Ближайшие пункты: ${m.stops.map(e => `${e.s} ${e.t}`).join('; ')}. Настрой, цель дня, совет по силам.`
    : `Вечернее сообщение после дня ${m.day} (${m.label}): спросить, как прошёл день, и предложить оценить его в приложении.`;
  return { model: MODEL, max_tokens: 600, output_config: { effort: 'low' }, betas: ['server-side-fallback-2026-07-01'], fallbacks: 'default',
    system: `Ты пишешь push-уведомление участнику поездки по Японии. Язык — ${LANGS[p.lang]}. Тон — ${TONE[p.tone]}. Ответ ровно из двух строк: заголовок до 40 символов, затем текст до 150 символов. Без кавычек, эмодзи — не больше одного, не выдумывай фактов.`,
    messages: [{ role: 'user', content: `${p.name ? 'Имя: ' + p.name + '. ' : ''}Энергия: ${ENERGY[p.energy]}.${p.interests ? ' Интересы: ' + p.interests + '.' : ''} ${what}` }] };
}
export function digestText(res, m) {
  const t = res && res.stop_reason !== 'refusal' ? ((res.content || []).filter(b => b && b.type === 'text').map(b => b.text).join('')).trim() : '';
  const lines = t.split('\n').map(x => x.trim()).filter(Boolean);
  if (lines.length < 2) return fallbackText(m);
  return { title: str(lines[0], 60), body: str(lines.slice(1).join(' '), 200) };
}
export const appUrl = (trip, m) => 'https://zakcination.github.io/japan-2026/?trip=' + encodeURIComponent(trip)
  + '#' + (m.kind === 'place' ? 'rate=' + encodeURIComponent(m.stop.id) : 'briefing');             // handled by handleDeepLink → askDeepLink
