/* ---------- «Степной след» in the stop sheet ----------
   The facts, games and illustration are not copied into the trip: the stop only carries `kzKey`, the map
   label of its place, and everything is read from DATA.places (the map's own payload), so the page holds
   them once. Every string goes through esc(); links only through Core.safeUrl. Spot ticks share the map's
   storage key and ids, so a tick made here shows on the map and the other way round. */
const KZ_KEY = 'japan2026.kzdone.v1';
const KZ_LVL = { fact: ['✅', 'Факт'], parallel: ['🔗', 'Параллель'], joke: ['😄', 'Шутка'], note: ['⚠️', 'Важно'] };
const kzPlace = e => e && e.kzKey && typeof DATA !== 'undefined' && Array.isArray(DATA.places)
  ? DATA.places.find(p => p.label === e.kzKey && Array.isArray(p.kz) && p.kz.length) : null;
function kzDone() { try { return JSON.parse(localStorage.getItem(KZ_KEY)) || {}; } catch (er) { return {}; } }
function kzToggle(id) {
  const d = kzDone();
  if (d[id]) delete d[id]; else d[id] = Date.now();
  try { localStorage.setItem(KZ_KEY, JSON.stringify(d)); } catch (er) { /* private mode: lives until the sheet closes */ }
  window.dispatchEvent(new Event('kzdone-changed'));      // the map re-reads the same key
  return !!d[id];
}
function kzPlural(n) {
  const a = n % 10, b = n % 100;
  return a === 1 && b !== 11 ? 'факт' : a >= 2 && a <= 4 && (b < 12 || b > 14) ? 'факта' : 'фактов';
}
const kzBtn = (label, attrs) => `<button type="button" class="tc-kzbtn" ${attrs}>${esc(label)}</button>`;
function kzGameHTML(g, i) {
  const t = g.type, ok = Object.prototype.hasOwnProperty;
  let title = '🎲 Игра', q = '', ctl = '';
  if (t === 'tf') {
    title = '🎲 Верю / не верю'; q = esc(g.q);
    ctl = kzBtn('Верю', 'data-kzans="1"') + kzBtn('Не верю', 'data-kzans="0"');
  } else if (t === 'order') {
    title = '🎲 Что было раньше'; q = 'Что было раньше?';
    ctl = `<span class="tc-kzab"><b>A</b> ${esc(g.a)}</span><span class="tc-kzab"><b>B</b> ${esc(g.b)}</span>` + kzBtn('A', 'data-kzans="a"') + kzBtn('B', 'data-kzans="b"');
  } else if (t === 'guess') {
    title = '🎲 Угадай'; q = esc(g.q);
    ctl = (g.options || []).map((o, k) => kzBtn(o, `data-kzans="${k}"`)).join('');
  } else if (t === 'spot') {
    const on = !!kzDone()[g.id];
    return `<div class="tc-kzg" data-kzg="${i}"><b class="tc-kzgt">📸 Задание на месте</b><p>${esc(g.task)}</p>
      <label class="tc-kzspot"><input type="checkbox" data-kzspot="${esc(g.id)}"${on ? ' checked' : ''}><span>Нашёл!</span></label>
      <p class="tc-kzrev">Чем закрывается: ${esc(g.proof)}</p></div>`;
  } else return '';
  return `<div class="tc-kzg" data-kzg="${i}"><b class="tc-kzgt">${title}</b><p>${q}</p><div class="tc-kzopts">${ctl}</div>
    <p class="tc-kzrev" hidden aria-live="polite"></p></div>`;
}
function kzFactHTML(f, i) {
  if (f.game) return kzGameHTML(f.game, i);
  const l = KZ_LVL[f.level] || ['•', ''], u = Core.safeUrl(f.src);
  return `<div class="tc-kzi">${l[1] ? `<span class="tc-kzlvl ${esc(String(f.level).replace(/[^a-z]/g, ''))}">${l[0]} ${l[1]}</span>` : ''}
    <b>${esc(f.title)}</b><p>${esc(f.text)}</p>${u ? `<a class="tc-kzsrc" href="${esc(u)}" target="_blank" rel="noopener">Источник</a>` : ''}</div>`;
}
function kzCardHTML(e) {
  const p = kzPlace(e);
  if (!p) return '';
  return `<details class="tc-group tc-kz" id="tcKz"><summary class="tc-kzsum"><span>🇰🇿 Степной след · ${p.kz.length}</span></summary>
    <div class="tc-kzbody">${p.img ? `<img class="tc-kzimg" src="${esc(p.img)}" alt="${esc(p.label)}" loading="lazy">` : ''}${p.kz.map(kzFactHTML).join('')}</div></details>`;
}
function kzWire(m, e) {
  const p = kzPlace(e); if (!p) return;
  m.querySelectorAll('.tc-kzg[data-kzg] [data-kzans]').forEach(b => b.addEventListener('click', () => {
    const box = b.closest('.tc-kzg'), g = p.kz[+box.dataset.kzg].game, a = b.dataset.kzans;
    let right, text;
    if (g.type === 'tf') { right = (a === '1') === !!g.answer; text = (g.answer ? 'Правда. ' : 'Неправда. ') + g.reveal; }
    else if (g.type === 'order') { right = a === g.answer; text = 'Раньше — ' + (g.answer === 'a' ? 'A. ' : 'B. ') + g.reveal; }
    else { right = +a === g.answer; text = 'Ответ: ' + (g.options || [])[g.answer] + '. ' + g.reveal; }
    box.querySelectorAll('[data-kzans]').forEach(x => { x.disabled = true; x.classList.toggle('pick', x === b); });
    const r = box.querySelector('.tc-kzrev');
    r.textContent = (right ? 'Верно! ' : 'Не совсем. ') + text; r.hidden = false; r.classList.toggle('good', right);
  }));
  m.querySelectorAll('[data-kzspot]').forEach(c => c.addEventListener('change', () => { c.checked = kzToggle(c.dataset.kzspot); }));
}
