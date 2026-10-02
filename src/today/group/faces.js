/* ---------- faces: each person picks an emoji in ⚙; small overlapping faces stand in for initials ---------- */
const FACES = '😀 😄 😎 🤓 🥳 😇 🤠 🧐 😺 🐼 🦊 🐨 🐯 🦁 🐸 🐵 🐻 🐰 🦄 🐧 🐱 🐶 🐹 🐙'.split(' ');
const memberOf = id => ((Api.state() || {}).members || []).find(m => m.id === id) || null;
/* one face: the chosen emoji (only from FACES), else the first letter */
function faceHTML(m, big) {
  const e = m && FACES.includes(m.emoji) ? m.emoji : null;
  return `<span class="tc-face${e ? '' : ' letter'}${big ? ' big' : ''}" role="img" aria-label="${esc((m && m.name) || '?')}" title="${esc((m && m.name) || '')}">${e || esc(((m && m.name) || '?')[0])}</span>`;
}
const facesHTML = ids => `<span class="tc-faces">${(ids || []).map(id => faceHTML(memberOf(id))).join('')}</span>`;

function facePickHTML() {
  const me = Api.me(); if (!me) return '';
  const cur = (memberOf(me.id) || {}).emoji;
  return `<span class="tc-sech">Ваш смайлик · его видит группа</span>
    <p class="tc-sub tc-face-now" id="grFaceNow" role="status">${FACES.includes(cur) ? `Сейчас: <span class="tc-face-cur">${cur}</span> · сохранено` : 'Сейчас: не выбран — вместо смайлика первая буква имени'}</p>
    <div class="tc-facepick" id="grFaces" role="radiogroup" aria-label="Ваш смайлик">${FACES.map(f =>
      `<button type="button" role="radio" aria-checked="${f === cur}" data-face="${f}">${f}</button>`).join('')}</div>`;
}
/* saved online, so the line under the title says what the group really sees (and why not, if it failed) */
function wireFacePick(m) {
  const now = m.querySelector('#grFaceNow');
  m.querySelectorAll('[data-face]').forEach(b => b.addEventListener('click', async () => {
    const f = b.dataset.face, me = Api.me().id, was = (memberOf(me) || {}).emoji, next = was === f ? null : f;
    m.querySelectorAll('[data-face]').forEach(x => x.setAttribute('aria-checked', String(x.dataset.face === next)));
    now.textContent = 'Сохраняю…';
    try {
      await Api.run('set_emoji', { p_emoji: next });
      const x = ((Api.state() || {}).members || []).find(y => y.id === me); if (x) x.emoji = next;
      now.innerHTML = next ? `Сейчас: <span class="tc-face-cur">${next}</span> · сохранено` : 'Сейчас: не выбран — вместо смайлика первая буква имени';
      renderShell();
    } catch (e) {
      m.querySelectorAll('[data-face]').forEach(x => x.setAttribute('aria-checked', String(x.dataset.face === was)));
      now.textContent = !e.status ? 'Не сохранилось: нет сети — попробуйте ещё раз'
        : e.status === 404 ? 'Не сохранилось: сервер группы ещё не обновлён — скажите хозяевам' : 'Не сохранилось — попробуйте ещё раз';
    }
  }));
}

/* «Показать мой план группе»: all my own stops shared at once, and new ones shared from now on (this phone) */
const SHARE_ALL = 'japan2026.shareall.v1';
const shareAllOn = () => { try { const me = typeof Api !== 'undefined' && Api.me(); return !!me && localStorage.getItem(SHARE_ALL) === me.id; } catch (e) { return false; } };
function shareAllHTML() {
  const me = Api.me(); if (!me) return '';
  const mine = ((Api.state() || {}).my_stops || []).filter(s => s.member === me.id), hidden = mine.filter(s => !s.shared).length;
  return `<label class="tc-act tc-shareall"><span><b>Показать мой план группе</b><small>${mine.length
      ? (hidden ? `ваших пунктов: ${mine.length}, скрыто: ${hidden}` : `все ${mine.length} ваших пунктов видны группе`) : 'ваши будущие пункты сразу будут видны группе'}</small></span>
    <input type="checkbox" switch id="grShareAll"${shareAllOn() && !hidden ? ' checked' : ''}></label>`;
}
function wireShareAll(m) {
  const sw = m.querySelector('#grShareAll'); if (!sw) return;
  sw.addEventListener('change', () => {
    const me = Api.me().id, on = sw.checked;
    try { if (on) localStorage.setItem(SHARE_ALL, me); else localStorage.removeItem(SHARE_ALL); } catch (e) {}
    ((Api.state() || {}).my_stops || []).filter(s => s.member === me && !!s.shared !== on).forEach(s => {
      const next = { ...s, shared: on }; delete next.member;
      Api.call('save_my_stop', { p_stop: next }, st => { const x = (st.my_stops || []).find(y => y.id === s.id); if (x) x.shared = on; });
    });
    closeSheet(); openSettings();
  });
}
