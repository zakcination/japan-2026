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
    <div class="tc-facepick" id="grFaces" role="radiogroup" aria-label="Ваш смайлик">${FACES.map(f =>
      `<button type="button" role="radio" aria-checked="${f === cur}" data-face="${f}">${f}</button>`).join('')}</div>`;
}
function wireFacePick(m) {
  m.querySelectorAll('[data-face]').forEach(b => b.addEventListener('click', () => {
    const f = b.dataset.face, me = Api.me().id, next = (memberOf(me) || {}).emoji === f ? null : f;
    Api.call('set_emoji', { p_emoji: next }, s => { const x = (s.members || []).find(y => y.id === me); if (x) x.emoji = next; });
    m.querySelectorAll('[data-face]').forEach(x => x.setAttribute('aria-checked', String(x.dataset.face === next)));
    renderShell();
  }));
}
