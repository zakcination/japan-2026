/* ---------- «Деньги»: quick add (＋ → amount → category → save), budget, history, statistics, settings ---------- */
const expSet = () => ExpStore.settings();
const expPut = patch => ExpStore.setSettings({ ...expSet(), ...patch });
function expRates() {
  const r = expSet().rates || {};
  const kzt = +r.KZT || (SET.cur === 'KZT' ? +SET.rate : 0) || CUR.KZT.rate, usd = +r.USD || (SET.cur === 'USD' ? +SET.rate : 0) || CUR.USD.rate;
  return { KZT: kzt, USD: usd };
}
const tripStart = () => dateOf(T.days[0]), tripEnd = () => dateOf(T.days[T.days.length - 1]);
const tripToday = () => japanNow().date;
function cityOn(date) {
  const d = T.days.find(x => dateOf(x) === date) || T.days.find(x => dateOf(x) === tripToday());
  return d ? String(d.city || '').split('→').pop().trim() : '';
}
/* whose expenses: mine (or this phone's before signing in), plus my partner's when we chose each other */
function partnerOf() {
  const me = typeof Api !== 'undefined' && Api.me(); if (!me) return null;
  const ms = (Api.state() || {}).members || [], a = ms.find(m => m.id === me.id), b = a && ms.find(m => m.id === a.partner);
  return b && b.partner === me.id ? b : null;
}
function myExpenses() {
  const me = typeof Api !== 'undefined' && Api.me(), p = partnerOf();
  return ExpStore.all().filter(e => !me ? true : !e.member || e.member === me.id || (p && e.member === p.id));
}

/* signed in: send what this phone has, take what the server has that is newer (another phone, the partner) */
function expSync() {
  const me = typeof Api !== 'undefined' && Api.me(); if (!me || !ExpStore.ready()) return;
  const server = (Api.state() || {}).expenses || [], byId = new Map(ExpStore.all().map(e => [e.id, e]));
  let changed = false;
  server.forEach(s => { const l = byId.get(s.id); if (!l || String(s.updatedAt) > String(l.updatedAt)) { ExpStore.put({ ...s, synced: true }); changed = true; } });
  ExpStore.all().filter(e => !e.member || (e.member === me.id && !e.synced)).forEach(e => {
    const mine = { ...e, member: me.id, synced: true }; ExpStore.put(mine);
    const { member, synced, ...out } = mine; Api.call('save_expense', { p_e: out }, null);
  });
  if (changed) renderShell();
}
function expSave(e, quiet) {
  const me = typeof Api !== 'undefined' && Api.me();
  const rec = { ...e, member: me ? (e.member || me.id) : e.member || null, synced: !!me };
  ExpStore.put(rec);
  if (me && rec.member === me.id) { const { member, synced, ...out } = rec; Api.call('save_expense', { p_e: out }, null); }
  if (!quiet) renderShell();
  return rec;
}

/* ---------- quick add ---------- */
function openAdd(pre) {
  pre = pre || {};
  const s = expSet(), cur0 = pre.currency || s.lastCur || 'JPY';
  const recent = (s.recent || []).filter(c => Exp.CATS.some(x => x.code === c));
  const order = recent.concat(Exp.CATS.map(c => c.code).filter(c => !recent.includes(c)));
  const date0 = pre.date || (tripToday() >= tripStart() && tripToday() <= tripEnd() ? tripToday() : tripToday());
  let curSel = cur0, catSel = pre.cat || null, subSel = pre.sub || null;
  sheet(pre.id ? 'Расход' : 'Новый расход', `<div class="ex-add" id="exAdd">
    <label class="ex-amount" for="exAmt"><span class="tc-vh">Сколько?</span><b id="exSym">${Exp.SYM[curSel]}</b>
      <input id="exAmt" type="text" inputmode="decimal" autocomplete="off" placeholder="0" value="${pre.amount != null ? esc(String(pre.amount)) : ''}" aria-label="Сколько?"></label>
    <div class="tc-seg3s ex-curs" role="radiogroup" aria-label="Валюта">${Exp.CURS.map(c => `<button type="button" data-cur="${c}" aria-pressed="${c === curSel}">${Exp.SYM[c]} ${c}</button>`).join('')}</div>
    <div class="ex-cats" role="radiogroup" aria-label="Категория">${order.map(code => { const c = Exp.cat(code);
      return `<button type="button" class="ex-cat" data-cat="${c.code}" aria-pressed="${c.code === catSel}" style="--c:${c.color}"><i>${c.icon}</i><span>${esc(c.name)}</span></button>`; }).join('')}</div>
    <details class="tc-more ex-more"${pre.id || pre.title || pre.note ? ' open' : ''}><summary>Добавить детали</summary>
      <div class="ex-subs" id="exSubs" ${catSel === 'transport' ? '' : 'hidden'}>${Exp.SUBS.map(([k, i, n]) => `<button type="button" data-sub="${k}" aria-pressed="${k === subSel}">${i} ${esc(n)}</button>`).join('')}</div>
      <div class="tc-form2" id="exRoute" ${catSel === 'transport' ? '' : 'hidden'}>${fld('exFrom', 'Откуда', pre.from || '')}${fld('exTo', 'Куда', pre.to || '')}</div>
      ${fld('exTitle', 'Что / где (магазин, кафе)', pre.title || '', 'text', 'maxlength="80"')}
      <div class="tc-form2">${fld('exDate', 'Дата', date0, 'date')}${fld('exCity', 'Город', pre.city || cityOn(date0), 'text', 'maxlength="40" list="exCities"')}</div>
      <datalist id="exCities">${['Токио', 'Киото', 'Нагоя', 'Осака', 'Фудзи', 'Шанхай'].map(c => `<option value="${c}">`).join('')}</datalist>
      <div class="tc-seg3s ex-pay" role="radiogroup" aria-label="Оплата">${Object.entries(Exp.PAY).map(([k, n]) =>
        `<button type="button" data-pay="${k}" aria-pressed="${k === (pre.pay || s.lastPay || 'card')}">${n}</button>`).join('')}</div>
      <label class="tc-f" for="exNote"><span>Комментарий</span><textarea id="exNote" rows="2" maxlength="300">${esc(pre.note || '')}</textarea></label>
    </details>
    <p class="tc-warn" id="exMsg" role="status"></p>
    <button type="button" class="tc-btn primary wide ex-save" id="exSave" disabled>Сохранить</button>
    ${pre.id ? `<div class="tc-actions two"><button type="button" class="tc-btn" id="exDup">Дублировать</button><button type="button" class="tc-btn" id="exDel">Удалить</button></div>` : ''}
  </div>`, m => {
    const amt = m.querySelector('#exAmt'), save = m.querySelector('#exSave');
    const val = () => { const v = parseFloat(String(amt.value).replace(/\s/g, '').replace(',', '.')); return Number.isFinite(v) && v >= 0 ? v : null; };
    const sync = () => {
      const v = val();
      save.disabled = v == null || !catSel || amt.value === '';
      save.textContent = v != null && amt.value !== '' ? `Сохранить ${Exp.fmt(v, curSel)}` : 'Сохранить';
      m.querySelector('#exSym').textContent = Exp.SYM[curSel];
      const tr = catSel === 'transport'; m.querySelector('#exSubs').hidden = !tr; m.querySelector('#exRoute').hidden = !tr;
    };
    amt.addEventListener('input', sync);
    amt.addEventListener('keydown', ev => { if (ev.key === 'Enter' && !save.disabled) save.click(); });
    const pick = (sel, attr, fn) => m.querySelectorAll(sel).forEach(b => b.addEventListener('click', () => {
      m.querySelectorAll(sel).forEach(x => x.setAttribute('aria-pressed', String(x === b))); fn(b.getAttribute(attr)); sync(); }));
    pick('[data-cur]', 'data-cur', v => { curSel = v; });
    pick('[data-cat]', 'data-cat', v => { catSel = v; });
    pick('[data-sub]', 'data-sub', v => { subSel = v; });
    pick('[data-pay]', 'data-pay', () => {});
    const read = () => {
      const g = id => (m.querySelector('#' + id) || { value: '' }).value.trim(), pay = m.querySelector('[data-pay][aria-pressed="true"]');
      return { id: pre.id, createdAt: pre.createdAt, member: pre.member, amount: val(), currency: curSel, cat: catSel, sub: catSel === 'transport' ? subSel : null,
               date: /^\d{4}-\d{2}-\d{2}$/.test(g('exDate')) ? g('exDate') : date0, city: g('exCity'), title: g('exTitle'), note: g('exNote'),
               pay: pay ? pay.dataset.pay : 'card', from: g('exFrom'), to: g('exTo') };
    };
    save.addEventListener('click', () => {
      const e = Exp.make(read(), expRates());
      expSave(e);
      const st = expSet();
      expPut({ lastCur: curSel, lastPay: e.pay, recent: [e.cat].concat((st.recent || []).filter(c => c !== e.cat)).slice(0, 4) });
      try { localStorage.removeItem('japan2026.exp.draft'); } catch (x) {}
      closeSheet();
      expToast(`✓ ${Exp.fmt(e.amount, e.currency)} · ${Exp.cat(e.cat).name}${pre.id ? ' — изменено' : ' добавлено'}`, pre.id ? null : e.id);
      if (navigator.vibrate) try { navigator.vibrate(10); } catch (x) {}
    });
    const dup = m.querySelector('#exDup'); if (dup) dup.addEventListener('click', () => { const x = read(); closeSheet(); openAdd({ ...x, id: null, createdAt: null, member: null, date: tripToday() }); });
    const del = m.querySelector('#exDel'); if (del) del.addEventListener('click', () => {
      const e = ExpStore.all().find(x => x.id === pre.id); if (!e) return;
      expSave({ ...e, deleted: true, updatedAt: new Date().toISOString() }); closeSheet();
      expToast(`Расход удалён`, null, e);
    });
    /* an unfinished amount survives an accidental close */
    amt.addEventListener('input', () => { try { if (!pre.id) localStorage.setItem('japan2026.exp.draft', amt.value); } catch (x) {} });
    sync();
    amt.focus();
  });
}
function openAddFromDraft() {
  let d = ''; try { d = localStorage.getItem('japan2026.exp.draft') || ''; } catch (e) {}
  openAdd(d ? { amount: d } : null);
}

/* a toast with «Отменить»: undo an add (soft delete) or a delete (restore) */
function expToast(text, addedId, deleted) {
  let t = document.getElementById('exToast');
  if (!t) { t = document.createElement('div'); t.id = 'exToast'; t.className = 'ex-toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
  t.innerHTML = `<span>${esc(text)}</span>${addedId || deleted ? '<button type="button" id="exUndo">Отменить</button>' : ''}`;
  t.hidden = false; clearTimeout(t._h); t._h = setTimeout(() => { t.hidden = true; }, 4000);
  const u = t.querySelector('#exUndo'); if (u) u.addEventListener('click', () => {
    const now = new Date().toISOString();
    if (addedId) { const e = ExpStore.all().find(x => x.id === addedId); if (e) expSave({ ...e, deleted: true, updatedAt: now }); }
    if (deleted) expSave({ ...deleted, deleted: false, updatedAt: now });
    t.hidden = true;
  });
}

/* ---------- «Деньги» ---------- */
let expFilter = { period: 'all', q: '', cat: '', city: '', pay: '' };
function moneyHTML() {
  const s = expSet(), cur = s.cur || 'JPY', rates = expRates();
  const all = myExpenses(), p = partnerOf();
  const S2 = Exp.summary(all, { cur, budget: s.budget, rates, today: tripToday(), start: tripStart(), end: tripEnd(), initialCash: s.cash });
  const f = v => Exp.fmt(v, cur);
  const bar = Math.min(100, S2.pct);
  const list = Exp.filter(all, expFilter, tripToday());
  const days = [...new Set(list.map(e => e.date))];
  const label = d => d === tripToday() ? 'Сегодня' : d === Exp.addDays(tripToday(), -1) ? 'Вчера' : Core.ddmmyyyy(d).slice(0, 5);
  const totals = ((typeof Api !== 'undefined' && Api.me() && Api.state()) || {}).spend_totals || [];
  const cities = [...new Set(all.filter(e => !e.deleted).map(e => e.city).filter(Boolean))];
  return `<section class="ex-dash" id="exDash">
    <div class="tc-seg3s ex-curs" id="exCur" role="radiogroup" aria-label="Показывать в">${Exp.CURS.map(c => `<button type="button" data-showcur="${c}" aria-pressed="${c === cur}">${c}</button>`).join('')}</div>
    <div class="tc-card ex-budget ${S2.state}">
      <div class="ex-big"><span class="tc-lbl">Потрачено${p ? ` · вы и ${esc(p.name)}` : ''}</span><b>${f(S2.total)}</b></div>
      ${S2.budget ? `<div class="ex-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(S2.pct)}"><i style="width:${bar}%"></i></div>
      <div class="ex-row3"><span>Бюджет<b>${f(S2.budget)}</b></span><span>${S2.left >= 0 ? 'Осталось' : 'Сверх бюджета'}<b>${f(Math.abs(S2.left))}</b></span><span>Использовано<b>${Math.round(S2.pct * 10) / 10}%</b></span></div>
      ${S2.over ? `<p class="tc-warn">Бюджет превышен на ${f(-S2.over)}</p>` : ''}`
      : `<button type="button" class="tc-link" data-exset>Задать бюджет поездки ›</button>`}
    </div>
    <div class="ex-tiles">
      <div class="tc-card"><span class="tc-lbl">Сегодня${S2.dayN ? ` · день ${S2.dayN}` : ''}</span><b>${f(S2.today)}</b><small>вчера ${f(S2.yesterday)}</small></div>
      <div class="tc-card"><span class="tc-lbl">В среднем за день</span><b>${S2.elapsed ? f(S2.avg) : '—'}</b><small>${S2.forecast != null ? 'к концу ~' + f(S2.forecast) : `поездка ${S2.tripDays} дн.`}</small></div>
      ${S2.cash ? `<div class="tc-card"><span class="tc-lbl">Наличные осталось</span><b>${Exp.fmt(S2.cash.left, 'JPY')}</b><small>из ${Exp.fmt(+s.cash, 'JPY')}</small></div>` : ''}
    </div>
    ${S2.count ? `<div class="tc-card ex-break"><span class="tc-lbl">По категориям</span>${S2.cats.slice(0, 6).map(r => { const c = Exp.cat(r.k);
        return `<div class="ex-brow"><span><i>${c.icon}</i>${esc(c.name)}</span><b>${f(r.v)}</b><em style="width:${Math.round(r.v / S2.cats[0].v * 100)}%;background:${c.color}"></em></div>`; }).join('')}
      ${S2.shopping.self || S2.shopping.gifts ? `<p class="tc-sub">Шопинг: для себя ${f(S2.shopping.self)} · подарки ${f(S2.shopping.gifts)}</p>` : ''}</div>
    <div class="tc-card ex-break"><span class="tc-lbl">По городам</span>${S2.cities.slice(0, 5).map(r =>
        `<div class="ex-brow"><span>${esc(r.k)}</span><b>${f(r.v)}</b><em style="width:${Math.round(r.v / S2.cities[0].v * 100)}%"></em></div>`).join('')}
      ${S2.pays.length > 1 ? `<p class="tc-sub">${S2.pays.map(r => `${esc(Exp.PAY[r.k] || r.k)} ${f(r.v)}`).join(' · ')}</p>` : ''}</div>` : ''}
    ${totals.length > 1 ? `<div class="tc-card ex-break" id="exGroup"><span class="tc-lbl">Группа · только итоги</span>${totals.slice().sort((a, b) => b.jpy - a.jpy).map(t => { const m = memberOf(t.member) || {};
        return `<div class="ex-brow"><span>${faceHTML(m)} ${esc(m.name || '')}</span><b>${Exp.fmt(t.jpy, 'JPY')}</b></div>`; }).join('')}</div>` : ''}
    <h2 class="tc-sech">Расходы</h2>
    <div class="ex-filters">
      <input id="exQ" type="search" placeholder="Поиск: магазин, город, маршрут" value="${esc(expFilter.q)}" aria-label="Поиск по расходам">
      <div class="ex-chips">${[['all', 'Всё'], ['today', 'Сегодня'], ['yesterday', 'Вчера'], ['7d', '7 дней']].map(([k, n]) =>
        `<button type="button" data-period="${k}" aria-pressed="${expFilter.period === k}">${n}</button>`).join('')}
        <select id="exFCat" aria-label="Категория"><option value="">Все категории</option>${Exp.CATS.map(c => `<option value="${c.code}"${expFilter.cat === c.code ? ' selected' : ''}>${c.icon} ${esc(c.name)}</option>`).join('')}</select>
        ${cities.length > 1 ? `<select id="exFCity" aria-label="Город"><option value="">Все города</option>${cities.map(c => `<option${expFilter.city === c ? ' selected' : ''}>${esc(c)}</option>`).join('')}</select>` : ''}
        <select id="exFPay" aria-label="Оплата"><option value="">Любая оплата</option>${Object.entries(Exp.PAY).map(([k, n]) => `<option value="${k}"${expFilter.pay === k ? ' selected' : ''}>${n}</option>`).join('')}</select></div>
    </div>
    <div id="exList">${!all.some(e => !e.deleted) ? `<div class="tc-card ex-empty"><b>Добавьте первый расход</b><span class="tc-sub">Кнопка ＋ внизу: сумма → категория → сохранить.</span></div>`
      : !list.length ? '<p class="tc-empty">Ничего не нашлось.</p>'
      : days.map(d => { const xs = list.filter(e => e.date === d);
        return `<h3 class="ex-day">${label(d)}<span>${f(xs.reduce((s, e) => s + Exp.inCur(e, cur), 0))}</span></h3><div class="tc-group">${xs.map(e => { const c = Exp.cat(e.cat);
          const second = e.cat === 'transport' && (e.from || e.to) ? `${e.from || '…'} → ${e.to || '…'}` : e.title;
          return `<button type="button" class="ex-item" data-exid="${esc(e.id)}"><i style="background:${c.color}22">${c.icon}</i>
            <span><b>${esc(second || c.name)}</b><small>${esc([second ? c.name : '', e.city, Exp.PAY[e.pay], partnerOf() && e.member && e.member !== Api.me().id ? (memberOf(e.member) || {}).name : ''].filter(Boolean).join(' · '))}</small></span>
            <em>${esc(Exp.fmt(e.amount, e.currency))}${e.currency !== cur ? `<small>${esc(f(Exp.inCur(e, cur)))}</small>` : ''}</em></button>`; }).join('')}</div>`; }).join('')}</div>
    <div class="tc-actions two ex-tools"><button type="button" class="tc-btn" data-exset>${icon('gear')}Бюджет и курсы</button><button type="button" class="tc-btn" id="exExport">${icon('share')}Экспорт CSV</button></div>
  </section>`;
}
function wireMoney(root) {
  root.querySelectorAll('[data-showcur]').forEach(b => b.addEventListener('click', () => { expPut({ cur: b.dataset.showcur }); renderShell(); }));
  root.querySelectorAll('[data-exset]').forEach(b => b.addEventListener('click', openExpSettings));
  root.querySelectorAll('[data-period]').forEach(b => b.addEventListener('click', () => { expFilter.period = b.dataset.period; renderShell(); }));
  const sel = (id, k) => { const x = root.querySelector(id); if (x) x.addEventListener('change', () => { expFilter[k] = x.value; renderShell(); }); };
  sel('#exFCat', 'cat'); sel('#exFCity', 'city'); sel('#exFPay', 'pay');
  const q = root.querySelector('#exQ'); if (q) q.addEventListener('input', () => {
    expFilter.q = q.value; const box = root.querySelector('#exList'), tmp = document.createElement('div'); tmp.innerHTML = moneyHTML();
    box.innerHTML = tmp.querySelector('#exList').innerHTML; wireItems(root);
  });
  wireItems(root);
  const ex = root.querySelector('#exExport'); if (ex) ex.addEventListener('click', () => expFile(Exp.csv(myExpenses(), tripStart()), 'expenses.csv', 'text/csv'));
}
const wireItems = root => root.querySelectorAll('[data-exid]').forEach(b => b.addEventListener('click', () => {
  const e = ExpStore.all().find(x => x.id === b.dataset.exid); if (!e) return;
  const me = typeof Api !== 'undefined' && Api.me();
  if (me && e.member && e.member !== me.id) { expToast('Это расход ' + ((memberOf(e.member) || {}).name || 'партнёра') + ' — правит он сам'); return; }
  openAdd(e);
}));
function expFile(text, name, type) {
  const file = new File([text], name, { type });
  if (navigator.canShare && navigator.canShare({ files: [file] })) { navigator.share({ files: [file], title: name }).catch(() => {}); return; }
  const a = document.createElement('a'); a.href = URL.createObjectURL(file); a.download = name; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

/* ---------- settings: budget, cash, rates, «считать вместе с», backup ---------- */
function openExpSettings() {
  const s = expSet(), r = expRates(), me = typeof Api !== 'undefined' && Api.me();
  const ms = me ? ((Api.state() || {}).members || []).filter(m => m.id !== me.id) : [];
  const mine = me && ((Api.state() || {}).members || []).find(m => m.id === me.id);
  const p = partnerOf();
  sheet('Бюджет и курсы', `<div class="tc-form">
      ${fld('exBudget', 'Бюджет поездки, ¥', s.budget || '', 'number', 'inputmode="numeric" min="0" step="1000"')}
      ${fld('exCash', 'Наличные на старте, ¥', s.cash || '', 'number', 'inputmode="numeric" min="0" step="1000"')}
      <div class="tc-form2">${fld('exKzt', '1 ¥ = ₸', r.KZT, 'number', 'inputmode="decimal" min="0" step="0.01"')}${fld('exUsd', '1 ¥ = $', r.USD, 'number', 'inputmode="decimal" min="0" step="0.0001"')}</div>
      <p class="tc-foot">Курс сохраняется в каждом расходе: старые суммы не пересчитываются.</p></div>
    ${me ? `<span class="tc-sech">Считать вместе с</span>
      <div class="tc-group"><label class="tc-act"><span>Только я</span><input type="radio" name="exPartner" value=""${!mine || !mine.partner ? ' checked' : ''}></label>
      ${ms.map(m => `<label class="tc-act">${faceHTML(m, true)}<span>${esc(m.name)}<small>${m.partner === me.id ? 'выбрал(а) вас' : ''}</small></span>
        <input type="radio" name="exPartner" value="${esc(m.id)}"${mine && mine.partner === m.id ? ' checked' : ''}></label>`).join('')}</div>
      <p class="tc-foot">${p ? `Вы и ${esc(p.name)} видите расходы друг друга и общий бюджет.` : 'Общие расходы и бюджет — когда вы выбрали друг друга. Группа видит только итоги.'}</p>` : ''}
    <span class="tc-sech">Данные</span>
    <div class="tc-group"><button type="button" class="tc-act" id="exBackup">${icon('share')}<span>Резервная копия<small>файл со всеми расходами (JSON)</small></span></button>
      <label class="tc-act">${icon('clip')}<span>Восстановить из копии<small>дубли не создаются</small></span><input type="file" id="exRestore" accept="application/json,.json" hidden></label></div>
    <p class="tc-foot" id="exSetMsg" role="status"></p>
    <button type="button" class="tc-btn primary wide" id="exSetSave">Сохранить</button>`, m => {
    const v = id => parseFloat(String(m.querySelector('#' + id).value).replace(',', '.'));
    m.querySelector('#exSetSave').addEventListener('click', () => {
      const ok = x => Number.isFinite(x) && x > 0;
      expPut({ budget: ok(v('exBudget')) ? v('exBudget') : 0, cash: ok(v('exCash')) ? v('exCash') : 0,
               rates: { KZT: ok(v('exKzt')) ? v('exKzt') : r.KZT, USD: ok(v('exUsd')) ? v('exUsd') : r.USD } });
      const pr = m.querySelector('input[name="exPartner"]:checked');
      if (me && pr && (pr.value || null) !== ((mine && mine.partner) || null)) {
        const next = pr.value || null;
        Api.call('set_partner', { p_member: next }, st => { const x = (st.members || []).find(y => y.id === me.id); if (x) x.partner = next; });
      }
      closeSheet(); renderShell();
    });
    m.querySelector('#exBackup').addEventListener('click', () => expFile(JSON.stringify({ app: 'japan2026', kind: 'expenses', trip: T.id || '',
      at: new Date().toISOString(), settings: expSet(), expenses: myExpenses() }, null, 1), 'expenses-backup.json', 'application/json'));
    m.querySelector('#exRestore').addEventListener('change', ev => {
      const fl = ev.target.files && ev.target.files[0]; if (!fl) return;
      fl.text().then(txt => {
        let j; try { j = JSON.parse(txt); } catch (e) { m.querySelector('#exSetMsg').textContent = 'Это не файл резервной копии.'; return; }
        if (!j || j.kind !== 'expenses' || !Array.isArray(j.expenses)) { m.querySelector('#exSetMsg').textContent = 'В файле нет расходов.'; return; }
        const r2 = Exp.merge(ExpStore.all(), j.expenses);
        r2.list.forEach(e => { const was = ExpStore.all().find(x => x.id === e.id); if (was !== e) expSave({ ...e, synced: false }, true); });
        m.querySelector('#exSetMsg').textContent = `Добавлено ${r2.added}, обновлено ${r2.updated}, дубли пропущены.`;
        renderShell();
      });
    });
  });
}

/* «#add=…» from an Apple Pay shortcut: complete → saved at once; otherwise quick add opens filled in */
function expFromLink() {
  const L = Exp.fromLink(location.hash); if (!L) return false;
  history.replaceState(null, '', location.pathname + location.search);
  if (L.go && L.amount != null && L.cat) {
    const e = Exp.make({ amount: L.amount, currency: L.currency, cat: L.cat, title: L.title, pay: L.pay, date: tripToday(), city: cityOn(tripToday()) }, expRates());
    expSave(e); go('stats');
    expToast(`✓ ${Exp.fmt(e.amount, e.currency)} · ${Exp.cat(e.cat).name} добавлено`, e.id);
  } else openAdd({ amount: L.amount, currency: L.currency, cat: L.cat, title: L.title, pay: L.pay });
  return true;
}
