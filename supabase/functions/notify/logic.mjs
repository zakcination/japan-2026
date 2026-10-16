// Who gets which push, and what it says — pure, so it is tested with Node (src/tests/test_push_logic.py).
// Input: the event from the database trigger or the daily cron, and the trip's rows. Output: messages with recipients.
const APP = 'https://zakcination.github.io/japan-2026/?trip=';
const dm = iso => { const d = String(iso || '').slice(0, 10); return d ? `${d.slice(8, 10)}.${d.slice(5, 7)}` : ''; };
const almaty = (ms) => new Date(ms + 5 * 3600e3).toISOString();               // Asia/Almaty is UTC+5 all year
const findEv = (doc, ref) => { for (const d of (doc && doc.days) || []) for (const e of d.ev || []) if (String(e.id) === String(ref)) return e; return null; };

const cut = (s, n) => { s = String(s == null ? '' : s); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
function describe(p, doc) {
  const pl = Object.fromEntries(Object.entries(p.payload || {}).map(([k, v]) => [k, cut(v, 120)])), e = p.ref ? findEv(doc, p.ref) : null, what = e ? `«${e.t}»` : 'пункт';
  if (p.kind === 'time') return `${what}: другое время ${pl.s}–${pl.e}`;
  if (p.kind === 'remove') return `${what}: убрать из плана`;
  if (p.kind === 'add') return `Новый пункт: ${pl.s}–${pl.e} ${pl.t || ''}`.trim();
  return `${what}: ${p.note || 'комментарий'}`;
}

// countdown to the first flight; the cron asks every 5 minutes, a message fires once in the window [point, point + 5 min)
const TZ = { ALA: 5, NQZ: 5, TSE: 5, PVG: 8, SHA: 8, HND: 9, NRT: 9, KIX: 9, NGO: 9 };
const COUNTDOWN = {
  36: ['36 часов до вылета', 'Сегодня — бумаги: Visit Japan Web, карта прибытия в Китай, письмо о страховке. Всё в «Подготовке».'],
  24: ['Сутки до вылета', 'Онлайн-регистрация на рейс и посадочный офлайн. Проверьте «Перед выходом из дома».'],
  12: ['12 часов до вылета', 'Паспорт, карты, наличные, зарядка и лекарства — в ручную кладь. eSIM или роуминг — подключите сегодня.'],
  5: ['5 часов до вылета', 'Перед выходом: паспорт, телефон, ключи; газ, вода, окна. Список — в приложении.'],
  2: ['Интернет в поездке 📶', 'Включите eSIM или роуминг до посадки. В Китае WhatsApp и Google работают только через роуминг или eSIM.'],
  0: ['Взлетаем! ✈️', 'SHF Power Trip начинается. Хорошего полёта — до встречи на земле!'],
};
/* a warm hello 5 minutes before each landing (delivered as the phone comes off airplane mode) */
const LANDED = {
  PVG: ['Добро пожаловать в Шанхай 🇨🇳', 'Включите роуминг или eSIM. На контроле: паспорт + QR въезда — SOS → «Документы в телефоне». Хорошего дня!'],
  HND: ['Добро пожаловать в Японию 🇯🇵', 'Visit Japan Web QR — в «Документах». Отдыхайте, дальше всё в «Сейчас».'],
  NRT: ['Добро пожаловать в Японию 🇯🇵', 'Visit Japan Web QR — в «Документах». Отдыхайте, дальше всё в «Сейчас».'],
  ALA: ['С возвращением домой 🏡', 'Спасибо за поездку! Расходы и фото — в приложении.'],
};
function landings(doc) {
  return ((doc && doc.flights) || []).filter(x => x && x.date && x.arr && TZ[x.to] != null && LANDED[x.to]).map(x => {
    let t = Date.parse(`${x.date}T${x.arr}:00Z`) - TZ[x.to] * 3600e3;
    if (x.dep && x.arr < x.dep) t += 864e5;                       // lands the next day
    return { at: t, to: x.to, no: x.no };
  }).filter(x => Number.isFinite(x.at));
}
function firstDeparture(doc) {
  const f = ((doc && doc.flights) || []).filter(x => x && x.date && x.dep && TZ[x.frm] != null)
    .map(x => Date.parse(`${x.date}T${x.dep}:00Z`) - TZ[x.frm] * 3600e3).filter(Number.isFinite).sort((a, b) => a - b);
  return f.length ? f[0] : null;
}

// D = { trip, members, proposals, plan: {doc}, parts, joins, recipes, task_state } for one trip; now = epoch ms
export function messages(ev, D, now) {
  const url = h => APP + encodeURIComponent(D.trip) + '#' + h;
  const name = id => (D.members.find(m => m.id === id) || {}).name || 'Кто-то';
  const hosts = D.members.filter(m => m.role === 'host').map(m => m.id);
  const guests = D.members.filter(m => m.role !== 'host').map(m => m.id);
  const doc = (D.plan && D.plan.doc) || {};
  const out = [];
  if (ev.type === 'proposal') {
    const p = D.proposals.find(x => x.id === ev.id); if (!p) return out;
    out.push({ to: hosts.filter(h => h !== p.member), title: `Предложение от ${name(p.member)}`, body: describe(p, doc), url: url('tab=tix'), tag: 'prop-' + p.id });
  } else if (ev.type === 'decision') {
    const p = D.proposals.find(x => x.id === ev.id); if (!p || !['accepted', 'rejected'].includes(p.status)) return out;
    out.push({ to: [p.member], title: p.status === 'accepted' ? 'Ваше предложение принято' : 'Ваше предложение отклонено', body: describe(p, doc), url: url('tab=tix'), tag: 'prop-' + p.id });
  } else if (ev.type === 'join') {
    const part = ev.scope === 'part' ? (D.parts.find(x => x.id === ev.ref) || {}).title : (findEv(doc, ev.ref) || {}).t;
    if (!part) return out;
    out.push({ to: hosts.filter(h => h !== ev.member), title: ev.mode === 'in' ? `${name(ev.member)} едет` : `${name(ev.member)} не едет`, body: part, url: url('tab=day'), tag: `join-${ev.member}-${ev.ref}` });
  } else if (ev.type === 'direct') {
    // the assistant's scheduled messages (supabase/functions/assistant/digest.mjs): already written, only routed here —
    // to this trip's members only, and only with a link into this trip's app
    const ids = new Set(D.members.map(m => m.id)), base = url('');
    for (const m of (Array.isArray(ev.messages) ? ev.messages : []).slice(0, 200)) {
      const u = String((m && m.url) || '');
      if (!u.startsWith(base)) continue;
      out.push({ to: (Array.isArray(m.to) ? m.to : []).filter(x => ids.has(x)), title: String(m.title || ''), body: String(m.body || ''), url: u, tag: cut(m.tag || 'ai', 80) });
    }
  } else if (ev.type === 'plan') {
    out.push({ to: guests, title: 'План поездки обновился', body: 'Откройте «Мой план» — там уже новая версия.', url: url('tab=day'), tag: 'plan' });
  } else if (ev.type === 'countdown') {
    const dep = firstDeparture(doc), WIN = 5 * 60e3, inWin = t => now >= t && now < t + WIN;
    if (dep != null) for (const h of Object.keys(COUNTDOWN).map(Number)) if (inWin(dep - h * 3600e3)) {
      const c = COUNTDOWN[h];
      out.push({ to: D.members.map(m => m.id), title: c[0], body: c[1], url: url(h >= 24 ? 'prep=money' : h === 2 ? 'prep=phone' : h > 0 ? 'prep=door' : 'tab=now'), tag: 'countdown' });
    }
    for (const l of landings(doc)) if (inWin(l.at - WIN))
      out.push({ to: D.members.map(m => m.id), title: LANDED[l.to][0], body: LANDED[l.to][1], url: url('tab=now'), tag: 'landed-' + l.no });
  } else if (ev.type === 'deadlines') {
    const today = almaty(now).slice(0, 10), in3 = almaty(now + 3 * 864e5).slice(0, 10);
    // tasks due today: to their assignee (everyone when unassigned), unless already ticked
    for (const t of D.tasks || []) {
      if (t.due !== today) continue;
      const done = new Set(D.task_state.filter(x => x.ref === 't:' + t.id && x.done).map(x => x.member));
      const to = (t.assignee ? [t.assignee] : D.members.map(m => m.id)).filter(m => !done.has(m));
      if (to.length) out.push({ to, title: 'Сегодня: ' + t.title, body: t.note || 'Задача в «Делах»', url: url('task=t:' + t.id), tag: 'task-' + t.id });
    }
    for (const r of D.recipes) {
      const b = (doc.bookings || []).find(x => x.id === r.bk); if (!b || b.st === 'fixed') continue;
      const opensToday = r.opens && almaty(Date.parse(r.opens)).slice(0, 10) === today;
      const kind = r.buy_by === in3 ? 'in3' : r.buy_by === today ? 'today' : opensToday ? 'opens' : null;
      if (!kind) continue;
      const days = new Set(b.days || []);
      const joined = guests.filter(g => D.joins.some(j => j.member === g && j.scope === 'part' && j.mode === 'in'
        && ((D.parts.find(p => p.id === j.ref) || {}).days || []).some(n => days.has(n))));
      const done = new Set(D.task_state.filter(t => t.ref === 'bk:' + r.bk && t.done).map(t => t.member));
      const to = hosts.concat(joined).filter(m => !done.has(m));
      const what = String(r.what || b.t).replace(/\s*:\s*выбрать и забронировать\s*$/i, '');
      const title = kind === 'in3' ? `Осталось 3 дня: ${what}` : kind === 'today' ? `Сегодня последний день: ${what}` : `Сегодня открываются продажи: ${what}`;
      const body = kind === 'opens' ? `В ${almaty(Date.parse(r.opens)).slice(11, 16)} по Алматы${r.site ? ' · ' + r.site : ''}` : `Купить до ${dm(r.buy_by)}${r.site ? ' · ' + r.site : ''}`;
      if (to.length) out.push({ to, title, body, url: url('task=bk:' + r.bk), tag: 'deadline-' + r.bk });
    }
  }
  return out.filter(m => m.to.length).map(m => ({ ...m, title: cut(m.title, 120), body: cut(m.body, 200) }));
}
