/* ---------- stage 2: guests propose, hosts decide (accepted changes go into the group plan for everyone) ---------- */
const PROP_STATUS = { open: 'ждёт ответа', accepted: 'принято', rejected: 'отклонено', withdrawn: 'отозвано' };
const groupDoc = () => { const s = Api.state(); return (s && s.plan && s.plan.doc) || T; };
const memberName = id => ((Api.state().members || []).find(m => m.id === id) || {}).name || '—';

/* the sheet: for a stop (another time / remove / comment) or, with no stop, a new one on that day */
function openPropose(day, e) {
  const add = !e, t = (v, id, label) => fld(id, label, v || '', 'time');
  sheet(add ? 'Предложить пункт' : 'Предложить изменение', `<p class="tc-sub">${add ? `День ${esc(Core.ddmmyyyy(dateOf(day)).slice(0, 5))}` : esc(e.t)} — хозяева посмотрят и решат.</p>
    ${add ? '' : `<div class="tc-seg3s" role="radiogroup" aria-label="Что предложить" id="prKind">${[['time', 'Время'], ['remove', 'Убрать'], ['comment', 'Комментарий']]
      .map(([k, l], i) => `<label class="tc-seg3"><input type="radio" name="prKind" value="${k}"${i ? '' : ' checked'}><span>${l}</span></label>`).join('')}</div>`}
    ${add ? fld('prTitle', 'Что', '', 'text', 'maxlength="120"') : ''}
    <div class="tc-form2" id="prTimes">${t(add ? '' : e.s, 'prS', 'Начало')}${t(add ? '' : e.e, 'prE', 'Конец')}</div>
    <label class="tc-f" for="prNote"><span>${add ? 'Зачем, ссылка, цена' : 'Комментарий'}</span><textarea id="prNote" rows="3" maxlength="500"></textarea></label>
    <p class="tc-warn" id="prMsg" role="status"></p>
    <button type="button" class="tc-btn primary wide" id="prSend">Отправить хозяевам</button>`, m => {
    const kind = () => add ? 'add' : m.querySelector('#prKind input:checked').value;
    const sync = () => { m.querySelector('#prTimes').hidden = kind() === 'remove' || kind() === 'comment'; };
    m.querySelectorAll('#prKind input').forEach(i => i.addEventListener('change', sync)); sync();
    m.querySelector('#prSend').addEventListener('click', () => {
      const v = id => (m.querySelector('#' + id) || { value: '' }).value.trim(), k = kind(), msg = m.querySelector('#prMsg');
      const payload = k === 'time' || k === 'add' ? { s: v('prS'), e: v('prE') } : {};
      if (k === 'add') payload.t = v('prTitle');
      if ((k === 'time' || k === 'add') && !(Proposals.HM.test(payload.s) && Proposals.HM.test(payload.e) && payload.e > payload.s)) { msg.textContent = 'Укажите начало и конец — конец позже начала.'; return; }
      if (k === 'add' && !payload.t) { msg.textContent = 'Напишите, что за пункт.'; return; }
      if (k === 'comment' && !v('prNote')) { msg.textContent = 'Напишите комментарий.'; return; }
      const me = Api.me().id, tmp = 'tmp-' + Date.now().toString(36);
      Api.call('propose', { p_kind: k, p_ref: add ? null : String(e.id), p_day: day.n, p_payload: payload, p_note: v('prNote') }, s => {
        s.proposals = [{ id: tmp, member: me, kind: k, ref: add ? null : String(e.id), day: day.n, payload, note: v('prNote'), status: 'open' }].concat(s.proposals || []);
      });
      closeSheet(); renderShell();
    });
  });
}

/* «Дела»: hosts decide on open proposals; everyone sees their own and can withdraw an open one */
function proposalsHTML() {
  if (!Api.me()) return '';
  const s = Api.state() || {}, me = Api.me(), doc = groupDoc(), all = s.proposals || [];
  const when = p => { const n = Proposals.dayOf(p, doc), d = (doc.days || []).find(x => x.n === n); return d ? Core.ddmmyyyy(dateOf(d)).slice(0, 5) + ' · ' : ''; };
  const card = (p, acts) => `<div class="tc-card tc-prop" data-prop="${esc(p.id)}">
      <span class="tc-sub">${esc(when(p))}${me.role === 'host' ? esc(memberName(p.member)) : esc(PROP_STATUS[p.status] || p.status)}</span>
      <b>${esc(Proposals.describe(p, doc))}</b>${p.note ? `<p class="tc-notepara">${esc(p.note)}</p>` : ''}${acts}</div>`;
  let html = '';
  if (me.role === 'host') {
    const open = all.filter(p => p.status === 'open');
    if (open.length) html += `<h2 class="tc-sech">Предложения · ${open.length}</h2>` + open.map(p => card(p, `<div class="tc-actions two">
      <button type="button" class="tc-btn primary" data-accept="${esc(p.id)}">${p.kind === 'comment' ? 'Прочитано' : 'Принять'}</button>
      <button type="button" class="tc-btn" data-reject="${esc(p.id)}">${p.kind === 'comment' ? 'Скрыть' : 'Отклонить'}</button></div>`)).join('');
  } else {
    const mine = all.filter(p => p.member === me.id && p.status !== 'withdrawn').slice(0, 8);
    if (mine.length) html += '<h2 class="tc-sech">Мои предложения</h2>' + mine.map(p => card(p, p.status === 'open' && !String(p.id).startsWith('tmp-')
      ? `<button type="button" class="tc-btn" data-withdraw="${esc(p.id)}">Отозвать</button>` : '')).join('');
  }
  return html ? `<section id="grProps">${html}</section>` : '';
}
function wireProposals(root) {
  if (!Api.me()) return;
  const find = id => (Api.state().proposals || []).find(p => p.id === id);
  const decide = (p, accept) => {
    const G = Api.state(), v = G.plan.version;
    let doc = null;
    if (accept && p.kind !== 'comment') {
      try { doc = Proposals.apply(G.plan.doc, p); }
      catch (e) { const c = root.querySelector(`[data-prop="${CSS.escape(p.id)}"]`); if (c) c.insertAdjacentHTML('beforeend', '<p class="tc-warn">План уже изменился — этот пункт не найти. Отклоните или поправьте план сами.</p>'); return; }
    }
    Api.call('decide_proposal', { p_id: p.id, p_accept: accept, p_doc: doc, p_version: doc ? v : null }, s => {
      if (doc) s.plan = { doc, version: v + 1 };
      const q = (s.proposals || []).find(x => x.id === p.id); if (q) q.status = accept ? 'accepted' : 'rejected';
    });
    renderShell();
  };
  root.querySelectorAll('[data-accept]').forEach(b => b.addEventListener('click', () => { const p = find(b.dataset.accept); if (p) decide(p, true); }));
  root.querySelectorAll('[data-reject]').forEach(b => b.addEventListener('click', () => twoTap(b, 'Точно?', () => { const p = find(b.dataset.reject); if (p) decide(p, false); })));
  root.querySelectorAll('[data-withdraw]').forEach(b => b.addEventListener('click', () => twoTap(b, 'Отозвать?', () => {
    const id = b.dataset.withdraw;
    Api.call('withdraw_proposal', { p_id: id }, s => { const q = (s.proposals || []).find(x => x.id === id); if (q) q.status = 'withdrawn'; });
    renderShell();
  })));
}
