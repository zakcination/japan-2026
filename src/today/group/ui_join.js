/* ---------- joining on «День»: my plan / group plan, parts, «Я еду / Без меня», own stops ---------- */
const setJoin = (scope, ref, mode) => (mode === 'in' && track('joined'), Api.call('set_join', { p_scope: scope, p_ref: String(ref), p_mode: mode }, s => {
  const me = Api.me().id; s.joins = s.joins.filter(j => !(j.member === me && j.scope === scope && j.ref === String(ref)));
  if (mode !== 'none') s.joins.push({ member: me, scope, ref: String(ref), mode });
}));
function joinBarHTML(x) {
  if (!Api.me()) return '';
  const s = Api.state(), group = S.viewMode === 'group';
  const parts = (s.parts || []).filter(p => p.days.includes(x.day.n));
  const inSet = Group.effective(planDoc(), s, Api.me().id);
  const partIn = p => (s.joins || []).some(j => j.member === Api.me().id && j.scope === 'part' && j.ref === p.id && j.mode === 'in');
  const who = p => s.members.filter(m => (s.joins || []).some(j => j.member === m.id && j.scope === 'part' && j.ref === p.id && j.mode === 'in') || m.role === 'host').map(m => m.id);
  let html = `<div class="tc-seg3s two" id="grView" role="radiogroup" aria-label="Чей план">
    <button type="button" data-view="mine" aria-pressed="${!group}">Мой план</button><button type="button" data-view="group" aria-pressed="${group}">План группы</button></div>`;
  if (group) html += parts.map(p => `<div class="tc-card tc-part"><button type="button" class="tc-part-chip" data-part="${esc(p.id)}">
      <b>${esc(p.title)}</b><small>едут ${facesHTML(who(p))}</small></button>
      ${Api.me().role === 'host' ? '' : partIn(p) ? `<button type="button" class="tc-btn" data-partjoin="${esc(p.id)}" data-mode="none">Не еду</button>`
        : `<button type="button" class="tc-btn primary" id="grJoinPart" data-partjoin="${esc(p.id)}" data-mode="in">Я с вами: ${esc(p.title)}</button>`}</div>`).join('')
      + (Api.me().role === 'host' ? '' : `<button type="button" class="tc-btn wide" id="grProposeAdd">${icon('plus')}Предложить пункт в план группы</button>`);
  else if (!x.evs.length) html += `<div class="tc-card"><b>Свободный день — спланируйте сами</b>
      ${parts.length ? `<span class="tc-sub">Группа в этот день: ${esc(parts.map(p => p.title).join(', '))} — «План группы», чтобы присоединиться.</span>` : ''}</div>`;
  return html;
}
function wireJoinBar(root, x) {
  if (!Api.me()) return;
  root.querySelectorAll('#grView [data-view]').forEach(b => b.addEventListener('click', () => { S.viewMode = b.dataset.view; save(); renderShell(); }));
  root.querySelectorAll('[data-partjoin]').forEach(b => b.addEventListener('click', () => { setJoin('part', b.dataset.partjoin, b.dataset.mode); renderShell(); }));
  root.querySelectorAll('[data-part]').forEach(b => b.addEventListener('click', () => openPart(b.dataset.part)));
  const pa = root.querySelector('#grProposeAdd'); if (pa) pa.addEventListener('click', () => openPropose(x.day, null));
}
function openPart(id) {
  const s = Api.state(), p = s.parts.find(x => x.id === id); if (!p) return;
  const going = s.members.filter(m => m.role === 'host' || s.joins.some(j => j.member === m.id && j.scope === 'part' && j.ref === id && j.mode === 'in'));
  sheet(p.title, `<p class="tc-sub">Дни: ${p.days.map(n => Core.ddmmyyyy(dateOf(planDoc().days.find(d => d.n === n) || { n })).slice(0, 5)).join(', ')}</p>
    <p class="tc-sub tc-who">Едут: ${facesHTML(going.map(m => m.id))} ${esc(going.map(m => m.name).join(', '))}</p>
    ${Api.me().role === 'host' ? '' : `<button type="button" class="tc-btn primary wide" data-in>Я с вами на всю часть</button><button type="button" class="tc-btn wide" data-none>Не еду</button>`}`, m => {
    const b1 = m.querySelector('[data-in]'), b2 = m.querySelector('[data-none]');
    if (b1) b1.addEventListener('click', () => { setJoin('part', id, 'in'); closeSheet(); renderShell(); });
    if (b2) b2.addEventListener('click', () => { setJoin('part', id, 'none'); closeSheet(); renderShell(); });
  });
}
/* extra block for the stop sheet */
function stopJoinHTML(day, e) {
  if (!Api.me()) return '';
  const me = Api.me().id, s = Api.state();
  if (e.from === 'mine' || String(e.id).startsWith('m-')) {
    const own = (s.my_stops.find(x => x.id === e.id) || {}).member === me;
    if (own) return `<label class="tc-act"><span>Показать группе<small>другие смогут присоединиться</small></span><input type="checkbox" switch id="grShare"${e.shared ? ' checked' : ''}></label>`;
    const author = (s.members.find(m => m.id === (s.my_stops.find(x => x.id === e.id) || {}).member) || {}).name || '';
    const st0 = s.my_stops.find(x => x.id === e.id), joined = !!st0 && Group.mineIn(s, me, st0);
    return `<p class="tc-sub">Планирует ${esc(author)}</p><button type="button" class="tc-btn ${joined ? '' : 'primary'} wide" data-joinmine="${joined ? 'out' : 'in'}">${joined ? 'Не пойду' : 'Присоединиться'}</button>`;
  }
  const going = Group.effective(planDoc(), s, me).has(e.id);
  const who = s.members.filter(m => Group.effective(planDoc(), s, m.id).has(e.id)).map(m => m.name);
  const whoIds = s.members.filter(m => Group.effective(planDoc(), s, m.id).has(e.id)).map(m => m.id);
  return `<p class="tc-sub tc-who">Идут: ${whoIds.length ? facesHTML(whoIds) + ' ' + esc(who.join(', ')) : '—'}</p>
    <div class="tc-actions two"><button type="button" class="tc-btn ${going ? '' : 'primary'}" data-join="in">Я еду</button>
      <button type="button" class="tc-btn ${going ? 'primary' : ''}" data-join="out">Без меня</button></div>
    ${Api.me().role === 'host' ? '' : `<button type="button" class="tc-btn wide" data-propose>${icon('edit')}Предложить изменение</button>`}`;
}
function wireStopJoin(m, day, e) {
  if (!Api.me()) return;
  m.querySelectorAll('[data-join]').forEach(b => b.addEventListener('click', () => { setJoin('stop', e.id, b.dataset.join); closeSheet(); renderShell(); }));
  const pr = m.querySelector('[data-propose]'); if (pr) pr.addEventListener('click', () => { closeSheet(); openPropose(day, e); });
  const jm = m.querySelector('[data-joinmine]'); if (jm) jm.addEventListener('click', () => { setJoin('mine', e.id, jm.dataset.joinmine); closeSheet(); renderShell(); });
  const sh = m.querySelector('#grShare'); if (sh) sh.addEventListener('change', () => {
    const st = Api.state().my_stops.find(x => x.id === e.id); if (!st) return;
    const next = { ...st, shared: sh.checked };
    Api.call('save_my_stop', { p_stop: next }, s => { const i = s.my_stops.findIndex(x => x.id === e.id); if (i >= 0) s.my_stops[i] = next; });
  });
}

/* «Ехать вместе с»: follow someone's personal plan — the whole trip or chosen days; own choices still win */
const followJoins = (who) => (Api.state().joins || []).filter(j => j.member === Api.me().id && j.scope === 'follow' && j.ref.split(':')[0] === who);
function followSummary(who) {
  const js = followJoins(who), all = js.find(j => !j.ref.includes(':') && j.mode === 'in');
  const days = js.filter(j => j.ref.includes(':') && j.mode === 'in').length, skip = js.filter(j => j.ref.includes(':') && j.mode === 'out').length;
  return all ? (skip ? `весь маршрут, кроме ${skip} дн.` : 'весь маршрут') : days ? `${days} дн.` : '';
}
function followHTML() {
  const me = Api.me(), s = Api.state(); if (!me || !s) return '';
  const others = (s.members || []).filter(m => m.id !== me.id); if (!others.length) return '';
  return `<span class="tc-sech">Ехать вместе с…</span><div class="tc-group" id="grFollow">${others.map(m => { const f = followSummary(m.id);
    return `<button type="button" class="tc-act" data-follow="${esc(m.id)}">${faceHTML(m, true)}<span>${esc(m.name)}<small>${f ? 'вы с ' + esc(m.name) + ': ' + esc(f) : 'план — в ваш, целиком или по дням'}</small></span>${icon('arrow')}</button>`; }).join('')}</div>`;
}
function wireFollow(m) { m.querySelectorAll('[data-follow]').forEach(b => b.addEventListener('click', () => { closeSheet(); openFollow(b.dataset.follow); })); }
function openFollow(who) {
  const s = Api.state(), t = (s.members || []).find(m => m.id === who); if (!t) return;
  const js = followJoins(who), all = !!js.find(j => !j.ref.includes(':') && j.mode === 'in');
  const dayMode = n => { const j = js.find(x => x.ref === who + ':' + n); return j ? j.mode : null; };
  const on = n => { const d = dayMode(n); return d ? d === 'in' : all; };
  const days = planDoc().days;
  sheet('Вместе с ' + t.name, `<p class="tc-sub">Куда едет ${esc(t.name)} — туда и вы: части поездки, пункты и пункты, которые ${esc(t.name)} показывает группе.
      Ваши «Без меня» и свои пункты остаются вашими. Билеты каждый покупает сам — они появятся в «Делах».</p>
    <label class="tc-act"><span><b>Весь маршрут</b><small>все дни поездки</small></span><input type="checkbox" switch id="flAll"${all ? ' checked' : ''}></label>
    <span class="tc-sech">Или по дням</span>
    <div class="tc-group">${days.map(d => `<label class="tc-act"><span>${esc(Core.ddmmyyyy(dateOf(d)).slice(0, 5))} · ${esc(d.label || d.city || '')}</span>
      <input type="checkbox" switch data-flday="${d.n}"${on(d.n) ? ' checked' : ''}></label>`).join('')}</div>`, m => {
    m.querySelector('#flAll').addEventListener('change', e => {
      setJoin('follow', who, e.target.checked ? 'in' : 'none');
      js.filter(j => j.ref.includes(':')).forEach(j => setJoin('follow', j.ref, 'none'));     // the whole trip resets the days
      renderShell(); openFollow(who);
    });
    m.querySelectorAll('[data-flday]').forEach(i => i.addEventListener('change', () => {
      const n = +i.dataset.flday, wholeNow = !!followJoins(who).find(j => !j.ref.includes(':') && j.mode === 'in');
      setJoin('follow', who + ':' + n, i.checked ? (wholeNow ? 'none' : 'in') : (wholeNow ? 'out' : 'none'));
      renderShell();
    }));
  });
}
