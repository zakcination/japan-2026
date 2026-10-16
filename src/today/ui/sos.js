/* ---------- SOS sheet: one tap from any tab; works without network ----------
   Personal medical notes stay on this phone only (localStorage), never synced. */
const SOS_KEY = 'japan2026.sos.v1';
const SOS_FIELDS = [
  ['blood', 'Группа крови', 'например, A(II) Rh+'],
  ['allergy', 'Аллергии', 'лекарства, еда'],
  ['meds', 'Лекарства, болезни', 'что принимаю постоянно'],
  ['home', 'Кому звонить дома', 'имя и телефон'],
];
const sosMine = () => { try { return JSON.parse(localStorage.getItem(SOS_KEY) || '{}') || {}; } catch (e) { return {}; } };
const sosTel = (n, show) => `<a class="tc-act" href="tel:${esc(n)}">${icon('phone')}<span>${esc(show || n)}`;

function openSos() {
  const me = sosMine();
  const call = c => `${sosTel(c.n, c.show)}<small>${esc(c.t)}${c.s ? ' · ' + esc(c.s) : ''}</small></span></a>`;
  const steps = c => `<details class="tc-more" data-sos="${c.k}"><summary>${esc(c.t)}</summary>
    <ol class="tc-sos-steps">${c.steps.map(s => `<li>${esc(s)}</li>`).join('')}</ol></details>`;
  const I = SOS.insurance;
  const ins = SOS.calls.find(c => /страх/i.test(c.t));
  sheet('SOS', `
    <button type="button" class="tc-act tc-docentry" id="sosDocs">${icon('tix')}<span>Документы в телефоне<small>QR для Китая, страховка, паспорт — без интернета</small></span></button>
    ${ins ? `<p class="tc-sos-first" id="sosFirst">Сначала — страховая: <a class="tc-inl" href="tel:${esc(ins.n)}">${esc(ins.show || ins.n)}</a></p>` : ''}
    <div class="tc-group" id="sosCalls">${SOS.calls.map(call).join('')}</div>
    <details class="tc-more"><summary>Китай — пересадка в Шанхае</summary>
      <div class="tc-group">${SOS.china.map(call).join('')}</div></details>
    <span class="tc-sech">Страховка — сначала</span>
    <div class="tc-card tc-note" id="sosIns"><p>${esc(I.who)}</p>
      <table class="tc-sos-lim">${I.limits.map(([a, b]) => `<tr><td>${esc(a)}</td><td>${esc(b)}</td></tr>`).join('')}</table>
      <p class="tc-foot">${esc(I.limitsNote)}</p>
      <div class="tc-group">${I.claim.map(([t, href, show]) =>
        `<a class="tc-act" href="${esc(href)}"${href.startsWith('http') ? ' target="_blank" rel="noopener"' : ''}>${icon(href.startsWith('tel:') ? 'phone' : href.startsWith('mailto:') ? 'mail' : 'link')}<span>${esc(show)}<small>${esc(t)} · заявка в течение 90 дней</small></span></a>`).join('')}</div></div>
    <span class="tc-sech">Что делать</span>
    ${SOS.cases.map(steps).join('')}
    <details class="tc-more" id="sosPhr"><summary>Показать японцу</summary>
      ${SOS.phrases.map(([ja, ru]) => `<button type="button" class="tc-sos-ja" data-ja="${esc(ja)}"><b lang="ja">${esc(ja)}</b><small>${esc(ru)}</small></button>`).join('')}</details>
    <details class="tc-more"><summary>Посольство и консульство</summary>
      ${SOS.embassy.map(e => `<div class="tc-group">${sosTel(e.tel, e.show)}<small>${esc(e.t)} · ${esc(e.a)}</small></span></a>
        ${e.tel2 ? `${sosTel(e.tel2, e.show2)}<small>${esc(e.t)}</small></span></a>` : ''}
        <a class="tc-act" href="mailto:${esc(e.mail)}">${icon('mail')}<span>${esc(e.mail)}${e.note ? `<small>${esc(e.note)}</small>` : ''}</span></a></div>`).join('')}</details>
    <details class="tc-more"><summary>Карта Forte Travel: что даёт</summary>
      <dl class="tc-sos-card">${SOS.card.map(([a, b]) => `<dt>${esc(a)}</dt><dd>${esc(b)}</dd>`).join('')}</dl></details>
    <details class="tc-more" id="sosMe"${Object.values(me).some(Boolean) ? '' : ' open'}><summary>Мои данные для врача</summary>
      <div class="tc-form">${SOS_FIELDS.map(([k, l, ph]) =>
        `<label class="tc-f" for="sos_${k}"><span>${esc(l)}</span><input id="sos_${k}" value="${esc(me[k] || '')}" placeholder="${esc(ph)}" autocomplete="off"></label>`).join('')}</div>
      <p class="tc-foot">Хранится только на этом телефоне. Номер карты и полиса сюда не пишите.</p>
      <button type="button" class="tc-btn primary wide" id="sosSave">Сохранить</button></details>
    <p class="tc-foot" id="sosMsg" role="status"></p>`, m => {
    m.querySelector('#sosSave').addEventListener('click', () => {
      const v = {}; SOS_FIELDS.forEach(([k]) => { v[k] = m.querySelector('#sos_' + k).value.trim().slice(0, 200); });
      try { localStorage.setItem(SOS_KEY, JSON.stringify(v)); m.querySelector('#sosMsg').textContent = 'Сохранено на телефоне'; }
      catch (e) { m.querySelector('#sosMsg').textContent = 'Не удалось сохранить'; }
    });
    m.querySelector('#sosDocs').addEventListener('click', () => openDocs());
    m.querySelectorAll('.tc-sos-ja').forEach(b => b.addEventListener('click', () => sosBig(b.dataset.ja)));
  });
}

/* full-screen Japanese text to show staff; tap to close */
function sosBig(ja) {
  const d = document.createElement('div'); d.className = 'tc-sos-big'; d.setAttribute('role', 'dialog');
  d.innerHTML = `<p lang="ja">${esc(ja)}</p><small>Нажмите, чтобы закрыть</small>`;
  d.addEventListener('click', () => d.remove());
  document.body.appendChild(d);
}
