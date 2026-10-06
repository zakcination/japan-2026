/* ---------- expenses: one record per payment, kept on the phone first (IndexedDB), synced to the group later ----------
   Pure maths in Exp.* (tested in Node-less Chromium via the core fixture); storage in ExpStore. Base currency: yen. */
const Exp = (() => {
  const CATS = [
    ['food', '🍜', 'Еда', '#FF9500'], ['transport', '🚄', 'Переезды', '#0A84FF'], ['shopping_self', '👕', 'Одежда', '#AF52DE'],
    ['shopping_gifts', '🎁', 'Подарки', '#FF2D55'], ['accommodation', '🏨', 'Жильё', '#5856D6'], ['attractions', '🏯', 'Места', '#E4002B'],
    ['coffee', '☕', 'Кофе', '#A2845E'], ['groceries', '🛒', 'Продукты', '#34C759'], ['taxi', '🚕', 'Такси', '#FFCC00'],
    ['tickets', '🎫', 'Билеты', '#30B0C7'], ['health', '💊', 'Аптека', '#FF3B30'], ['communication', '📱', 'Связь', '#64D2FF'],
    ['other', '📦', 'Другое', '#8E8E93'],
  ].map(([code, icon, name, color], i) => ({ code, icon, name, color, sort: i }));
  const cat = code => CATS.find(c => c.code === code) || CATS[CATS.length - 1];
  const SUBS = [['shinkansen', '🚄', 'Синкансэн'], ['train', '🚆', 'Поезд'], ['bus', '🚌', 'Автобус'], ['metro', '🚇', 'Метро'],
                ['taxi', '🚕', 'Такси'], ['flight', '✈️', 'Самолёт'], ['ferry', '⛴️', 'Паром'], ['walking_other', '🚶', 'Другое']];
  const PAY = { cash: 'Наличные', card: 'Карта', other: 'Другое' };
  const CURS = ['JPY', 'KZT', 'USD'];
  const SYM = { JPY: '¥', KZT: '₸', USD: '$' };
  const round = (v, d = 0) => { const k = 10 ** d; return Math.round(v * k) / k; };

  /* the amount in yen, and the rates frozen at the moment of the expense (rates: KZT and USD per 1 yen) */
  function make(input, rates, now) {
    const cur = CURS.includes(input.currency) ? input.currency : 'JPY';
    const amount = Math.max(0, +input.amount || 0);
    const r = { KZT: +rates.KZT || 0, USD: +rates.USD || 0 };
    const jpy = cur === 'JPY' ? amount : r[cur] ? amount / r[cur] : 0;
    const t = now || new Date().toISOString();
    return { id: input.id || uuid(), amount, currency: cur, jpy: round(jpy, 2), rateKzt: r.KZT, rateUsd: r.USD,
             cat: cat(input.cat).code, sub: input.sub || null, city: String(input.city || '').slice(0, 40), date: input.date,
             time: input.time || null, title: String(input.title || '').slice(0, 80), note: String(input.note || '').slice(0, 300),
             pay: PAY[input.pay] ? input.pay : 'card', from: String(input.from || '').slice(0, 40), to: String(input.to || '').slice(0, 40),
             member: input.member || null, createdAt: input.createdAt || t, updatedAt: t, deleted: false };
  }
  function uuid() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => { const r = Math.random() * 16 | 0; return (c === 'x' ? r : (r & 3 | 8)).toString(16); });
  }
  /* show an expense (or a yen total) in the chosen currency — old expenses keep their own frozen rate */
  const inCur = (e, cur) => cur === 'JPY' ? e.jpy : cur === 'KZT' ? e.jpy * (e.rateKzt || 0) : e.jpy * (e.rateUsd || 0);
  function fmt(v, cur) {
    const n = cur === 'USD' ? round(v, 2) : Math.round(v);
    const s = n.toLocaleString('ru-RU', cur === 'USD' ? { minimumFractionDigits: 0, maximumFractionDigits: 2 } : {});
    return cur === 'KZT' ? `${s} ₸` : `${SYM[cur]}${s}`;
  }
  const live = xs => xs.filter(e => !e.deleted);
  const sum = (xs, cur) => xs.reduce((s, e) => s + inCur(e, cur), 0);
  const addDays = (iso, n) => { const d = new Date(iso + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };

  /* everything «Деньги» shows; today = trip-local date; start/end = trip dates */
  function summary(all, o) {
    const xs = live(all), cur = o.cur || 'JPY';
    const total = sum(xs, cur), budget = +o.budget || 0;
    const budgetCur = budget && cur !== 'JPY' ? budget * (cur === 'KZT' ? o.rates.KZT : o.rates.USD) : budget;
    const pct = budget ? sum(xs, 'JPY') / budget * 100 : 0;
    const state = !budget ? 'none' : pct > 90 ? 'bad' : pct >= 70 ? 'warn' : 'ok';
    const day = d => sum(xs.filter(e => e.date === d), cur);
    const tripDays = Math.round((Date.parse(o.end) - Date.parse(o.start)) / 864e5) + 1;
    const started = o.today >= o.start;
    const elapsed = !started ? 0 : Math.min(tripDays, Math.round((Date.parse(o.today) - Date.parse(o.start)) / 864e5) + 1);
    const avg = elapsed ? total / elapsed : 0;
    const forecast = elapsed ? avg * tripDays : null;
    const by = key => { const m = new Map(); xs.forEach(e => { const k = key(e) || '—'; m.set(k, (m.get(k) || 0) + inCur(e, cur)); });
      return [...m.entries()].map(([k, v]) => ({ k, v })).sort((a, b) => b.v - a.v); };
    const cashSpent = sum(xs.filter(e => e.pay === 'cash'), 'JPY');
    return { total, budget: budgetCur, left: budgetCur - total, pct, state, over: budget && pct > 100 ? budgetCur - total : 0,
             today: day(o.today), yesterday: day(addDays(o.today, -1)), avg, forecast, tripDays, elapsed,
             dayN: started && elapsed <= tripDays ? elapsed : null,
             cats: by(e => e.cat), cities: by(e => e.city), pays: by(e => e.pay),
             shopping: { self: sum(xs.filter(e => e.cat === 'shopping_self'), cur), gifts: sum(xs.filter(e => e.cat === 'shopping_gifts'), cur) },
             cash: o.initialCash ? { left: +o.initialCash - cashSpent, spent: cashSpent } : null, count: xs.length };
  }

  /* the history: newest first, filtered and searched (offline, plain text) */
  function filter(all, f, today) {
    const q = String(f.q || '').trim().toLowerCase();
    const since = f.period === 'today' ? today : f.period === 'yesterday' ? addDays(today, -1) : f.period === '7d' ? addDays(today, -6) : null;
    return live(all).filter(e =>
      (!since || (f.period === 'yesterday' ? e.date === since : e.date >= since && e.date <= today)) &&
      (!f.cat || e.cat === f.cat) && (!f.city || e.city === f.city) && (!f.pay || e.pay === f.pay) && (!f.cur || e.currency === f.cur) &&
      (!q || [e.title, e.note, e.city, e.from, e.to, cat(e.cat).name].some(v => String(v || '').toLowerCase().includes(q))))
      .sort((a, b) => (b.date + (b.time || '') + b.createdAt).localeCompare(a.date + (a.time || '') + a.createdAt));
  }

  /* CSV (п. 67): one row per expense, comma-separated, quoted, with a BOM so Excel opens Cyrillic right */
  function csv(all, start) {
    const head = ['Date', 'Trip Day', 'City', 'Category', 'Subcategory', 'Description', 'Merchant', 'From', 'To', 'Amount', 'Currency',
                  'Exchange Rate', 'Amount JPY', 'Amount KZT', 'Amount USD', 'Payment Method', 'Comment'];
    const q = v => { const s = String(v == null ? '' : v); return /[",\n;]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    const rows = live(all).slice().sort((a, b) => a.date.localeCompare(b.date)).map(e => [
      e.date, Math.round((Date.parse(e.date) - Date.parse(start)) / 864e5) + 1, e.city, cat(e.cat).name, (SUBS.find(s => s[0] === e.sub) || [])[2] || '',
      e.note, e.title, e.from, e.to, e.amount, e.currency, e.currency === 'JPY' ? 1 : e.currency === 'KZT' ? e.rateKzt : e.rateUsd,
      round(e.jpy, 2), round(inCur(e, 'KZT'), 2), round(inCur(e, 'USD'), 2), PAY[e.pay], e.note].map(q).join(','));
    return '﻿' + [head.join(',')].concat(rows).join('\n');
  }

  /* a backup's expenses merged in: new ids added, known ids kept unless the backup copy is newer */
  function merge(local, incoming) {
    const m = new Map(local.map(e => [e.id, e])); let added = 0, updated = 0;
    incoming.filter(e => e && typeof e.id === 'string' && Number.isFinite(+e.jpy) && /^\d{4}-\d{2}-\d{2}$/.test(e.date || '')).forEach(e => {
      const was = m.get(e.id);
      if (!was) { m.set(e.id, e); added++; } else if (String(e.updatedAt) > String(was.updatedAt)) { m.set(e.id, e); updated++; }
    });
    return { list: [...m.values()], added, updated };
  }

  /* «#add=1500&cur=JPY&cat=food&t=Lawson&pay=card» — from an Apple Pay shortcut. Amounts may come as «¥1,500» or «1 500,00 ₸». */
  function fromLink(hash) {
    const m = /^#add=([^&]*)(.*)$/.exec(hash || ''); if (!m) return null;
    const q = new URLSearchParams(m[2].replace(/^&/, ''));
    const raw = decodeURIComponent(m[1] || '');
    const cur = (q.get('cur') || '').toUpperCase() || (/₸|KZT|тг/i.test(raw) ? 'KZT' : /\$|USD/i.test(raw) ? 'USD' : 'JPY');
    let n = raw.replace(/[^\d.,]/g, '');
    if (/,\d{1,2}$/.test(n) && !/\.\d/.test(n)) n = n.replace(/\./g, '').replace(',', '.'); else n = n.replace(/,/g, '');
    const amount = Number.isFinite(parseFloat(n)) ? parseFloat(n) : null;
    const c = q.get('cat');
    return { amount, currency: CURS.includes(cur) ? cur : 'JPY', cat: CATS.some(x => x.code === c) ? c : null,
             title: String(q.get('t') || '').slice(0, 80), pay: PAY[q.get('pay')] ? q.get('pay') : 'card', go: q.get('go') === '1' };
  }
  return { CATS, SUBS, PAY, CURS, SYM, cat, make, inCur, fmt, summary, filter, csv, merge, fromLink, addDays, uuid };
})();

/* ---------- storage: IndexedDB (records), localStorage (small settings only) ---------- */
const EXP_SET = 'japan2026.exp.v1';
const ExpStore = (() => {
  let list = [], ready = false, db = null;
  const open = () => new Promise((res, rej) => {
    if (typeof indexedDB === 'undefined') return rej(new Error('no idb'));
    const r = indexedDB.open('japan2026-expenses', 1);
    r.onupgradeneeded = () => r.result.createObjectStore('expenses', { keyPath: 'id' });
    r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
  });
  const load = () => open().then(d => { db = d; return new Promise(res => {
    const out = [], c = d.transaction('expenses').objectStore('expenses').openCursor();
    c.onsuccess = () => { const k = c.result; if (k) { out.push(k.value); k.continue(); } else res(out); };
    c.onerror = () => res(out);
  }); }).then(xs => { const early = list; list = xs; early.forEach(put);          // saved before the database opened (a link at start)
    ready = true; window.dispatchEvent(new Event('japan2026:exp')); })
    .catch(() => { ready = true; });                       // private mode: works for this session only
  const put = e => { const i = list.findIndex(x => x.id === e.id); if (i >= 0) list[i] = e; else list.push(e);
    try { if (db) db.transaction('expenses', 'readwrite').objectStore('expenses').put(e); } catch (x) {} };
  const settings = () => { try { return JSON.parse(localStorage.getItem(EXP_SET) || '{}') || {}; } catch (e) { return {}; } };
  const setSettings = s => { try { localStorage.setItem(EXP_SET, JSON.stringify(s)); } catch (e) {} };
  return { load, all: () => list, ready: () => ready, put, settings, setSettings };
})();
