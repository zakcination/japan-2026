/* ---------- ⚙ «Моя поездка» and the editors, as bottom sheets ---------- */
const CAT = { transport: 'Транспорт', activity: 'Место', event: 'Событие', food: 'Еда',
              hotel: 'Жильё', konbini: 'Конбини', routine: 'Быт', money: 'Деньги' };
const STL = { fixed: 'Куплено — не сдвигать', planned: 'По плану', flex: 'Гибко — можно сократить', input: 'Нужно купить' };
const THEMES = [['auto', 'Авто'], ['light', 'Светлая'], ['dark', 'Тёмная']];

const fld = (id, label, val, type = 'text', extra = '') =>
  `<label class="tc-f" for="${id}"><span>${label}</span><input id="${id}" type="${type}" value="${esc(val ?? '')}" ${extra}></label>`;
const sel = (id, label, val, opts) =>
  `<label class="tc-f" for="${id}"><span>${label}</span><select id="${id}">${opts.map(([k, v]) =>
    `<option value="${esc(k)}"${k === val ? ' selected' : ''}>${esc(v)}</option>`).join('')}</select></label>`;
const twoTap = (b, ask, fn) => {
  if (!b.dataset.sure) {
    const was = b.textContent; b.dataset.sure = '1'; b.textContent = ask;
    setTimeout(() => { if (b.isConnected) { delete b.dataset.sure; b.textContent = was; } }, 4000);
    return;
  }
  fn();
};
const resetMarks = () => { S.done = {}; S.skip = {}; S.delay = {}; S.spent = {}; S.walked = {}; save(); };

function openSettings() {
  const theme = SET.theme || 'auto';
  const custom = isCustom(), asked = Trips.asked();
  const install = Ios.isIOS() && !Ios.standalone();
  sheet('Моя поездка', `${groupSettingsHTML()}
    <div class="tc-form">
      ${sel('setTrip', 'Поездка', Trips.id(), Trips.list.map(t => [t.id, t.name]))}
      <p class="tc-foot" id="setVersion">${esc(Trips.version())}</p>
    </div>
    ${custom ? `<div class="tc-card tc-note" id="setLocal"><b>У вас свои правки — ${asked ? `ссылка ведёт на «${esc(Trips.nameOf(asked))}», но` : ''} общая версия не подтягивается</b>
      <button type="button" class="tc-btn primary" id="setReset">Вернуться к общей версии</button></div>` : ''}
    ${install ? `<p class="tc-foot">${icon('share')} «Поделиться» → «На экран „Домой“» — так приложение работает без сети, а билеты не сотрутся.</p>` : ''}
    <div class="tc-fs"><span class="tc-sech">Тема · днём светлая, после заката тёмная</span>
      <div class="tc-seg3s" role="radiogroup" aria-label="Тема">${THEMES.map(([k, l]) =>
        `<label class="tc-seg3"><input type="radio" name="tcTheme" value="${k}"${k === theme ? ' checked' : ''}><span>${l}</span></label>`).join('')}</div></div>
    <div class="tc-form">
      ${fld('setName', 'Название', T.name || '')}
      ${fld('setStart', 'Первый день', SET.start, 'date')}
      ${sel('setCur', 'Валюта дома', SET.cur, Object.keys(CUR).map(k => [k, k + ' ' + CUR[k].sym]))}
      ${fld('setRate', 'Курс: 1 ¥ =', SET.rate, 'number', 'min="0" step="0.0001" inputmode="decimal"')}
    </div>
    <p class="tc-foot">Курс по умолчанию примерный — впишите актуальный. Сдвиг даты переносит весь маршрут;
      пункты с датой (например, финалы) помечаются, если дата не совпала. Всё хранится только на этом телефоне.</p>
    <button type="button" class="tc-btn primary wide" id="setSave">Сохранить</button>
    <span class="tc-sech">Поделиться или перенести</span>
    <div class="tc-group">
      <button type="button" class="tc-act" id="setExport">${icon('share')}<span>Экспорт JSON<small>файл для другого телефона или друзей</small></span></button>
      <label class="tc-act">${icon('clip')}<span>Импорт из файла<small>.json от другого телефона</small></span><input type="file" id="setFile" accept="application/json,.json" hidden></label>
      <button type="button" class="tc-act" id="setShare">${icon('share')}<span>Поделиться поездкой<small>${esc(Trips.shareUrl().replace(/^https?:\/\//, ''))}</small></span></button>
    </div>
    <label class="tc-f" for="setJson"><span>JSON поездки — можно вставить свой</span><textarea id="setJson" rows="4" spellcheck="false"></textarea></label>
    <div class="tc-actions two"><button type="button" class="tc-btn" id="setLoad">Загрузить</button>
      <button type="button" class="tc-btn" id="setCopy">Скопировать</button></div>
    <p class="tc-foot" id="setMsg" role="status"></p>`, m => {
    wireGroupSettings(m);
    const msg = t => { m.querySelector('#setMsg').textContent = t; };
    m.querySelectorAll('input[name="tcTheme"]').forEach(r => r.addEventListener('change', () => {
      SET.theme = r.value; saveSettings(); renderShell();
      m.dataset.th = document.getElementById('today').dataset.th || 'light';
    }));
    m.querySelector('#setCur').addEventListener('change', e => { m.querySelector('#setRate').value = (CUR[e.target.value] || CUR.KZT).rate; });
    m.querySelector('#setSave').addEventListener('click', () => {
      const name = m.querySelector('#setName').value.trim();
      if (name && name !== T.name) { T.name = name; saveTrip(); }
      SET.start = m.querySelector('#setStart').value || SET.start;
      SET.cur = m.querySelector('#setCur').value in CUR ? m.querySelector('#setCur').value : 'KZT';
      SET.rate = +m.querySelector('#setRate').value || (CUR[SET.cur] || CUR.KZT).rate;
      saveSettings(); setTitle(); viewDay = null; closeSheet(); renderShell();
    });
    const exportObj = () => ({ ...T, travelers: SET.travelers, start: SET.start, currency: SET.cur, rate: SET.rate,
                               exported: new Date().toISOString() });
    m.querySelector('#setExport').addEventListener('click', () => {
      const txt = JSON.stringify(exportObj(), null, 1);
      m.querySelector('#setJson').value = txt;
      const name = (T.name || 'trip').replace(/[^\p{L}\p{N}]+/gu, '_').slice(0, 40) + '.json';
      const file = new File([txt], name, { type: 'application/json' });
      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        navigator.share({ files: [file], title: T.name || 'Поездка' }).then(() => msg('Готово.'), () => msg('JSON в поле ниже — его можно скопировать.'));
        return;
      }
      try {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(file); a.download = name;
        document.body.appendChild(a); a.click(); a.remove();
        msg('Файл сохранён. Если скачивание не началось — JSON в поле ниже.');
      } catch (e) { msg('JSON в поле ниже — скопируйте его.'); }
    });
    m.querySelector('#setCopy').addEventListener('click', () => {
      const ta = m.querySelector('#setJson');
      if (!ta.value) ta.value = JSON.stringify(exportObj(), null, 1);
      ta.select();
      (navigator.clipboard ? navigator.clipboard.writeText(ta.value) : Promise.reject()).then(() => msg('Скопировано.'), () => msg('Выделено — скопируйте вручную.'));
    });
    const load = txt => {
      let j; try { j = JSON.parse(txt); } catch (e) { msg('Это не JSON. Проверьте, что скопирован весь текст.'); return; }
      j = Core.cleanTrip(j);
      if (!j) { msg('Не похоже на поездку: нужен список days, у каждого дня n и ev с полями s и t.'); return; }
      T = j; saveTrip();
      SET = { theme: SET.theme || 'auto', travelers: +(j.travelers || 2), start: j.start || SET.start,
              cur: j.currency in CUR ? j.currency : SET.cur, rate: +(j.rate || (CUR[j.currency] || CUR.KZT).rate) };
      saveSettings(); resetMarks();
      setTitle(); viewDay = null; closeSheet(); renderShell();
    };
    m.querySelector('#setLoad').addEventListener('click', () => load(m.querySelector('#setJson').value));
    m.querySelector('#setFile').addEventListener('change', e => {
      const f = e.target.files && e.target.files[0]; if (!f) return;
      f.text().then(load, () => msg('Не удалось прочитать файл.'));
    });
    const rs = m.querySelector('#setReset');
    if (rs) rs.addEventListener('click', () => twoTap(rs, 'Точно? Ваши правки удалятся', () => {
      Trips.backToShared().then(ok => {
        if (!ok) { msg('Нет сети, а эта поездка ещё не сохранена на телефоне — попробуйте, когда появится интернет.'); return; }
        setTitle(); viewDay = null; closeSheet(); renderShell();
      });
    }));
    const tp = m.querySelector('#setTrip');
    if (custom) tp.disabled = true;
    tp.addEventListener('change', () => {
      tp.disabled = true;
      Trips.switchTo(tp.value).then(ok => {
        tp.disabled = false;
        if (!ok) { tp.value = Trips.id(); msg('Нет сети, а эта поездка ещё не сохранена на телефоне — попробуйте, когда появится интернет.'); return; }
        setTitle(); viewDay = null; closeSheet(); renderShell();
      });
    });
    m.querySelector('#setShare').addEventListener('click', () => {
      const url = Trips.shareUrl();
      if (navigator.share) { navigator.share({ url, title: T.name || 'Поездка' }).catch(() => {}); return; }
      (navigator.clipboard ? navigator.clipboard.writeText(url) : Promise.reject()).then(() => msg('Ссылка скопирована.'), () => msg(url));
    });
  });
}

function openEditor(day, id) {
  // signed in to the group: my own stops go to my_stops; a host editing the group plan saves it with a version check
  const G = typeof Api !== 'undefined' && Api.me() && Api.state();
  const mine = !!G && (id ? String(id).startsWith('m-') : (S.viewMode !== 'group' || G.me.role !== 'host'));
  if (G && !mine && G.me.role !== 'host') return;                     // guests don't edit the group plan
  const doc = G && !mine ? clone(G.plan.doc) : null;
  const own = mine && id ? (G.my_stops || []).find(s => s.id === id) || null : null;
  const d = mine ? null : (doc || T).days.find(x => x.n === day.n);
  const blank = { s: '12:00', e: '13:00', t: '', st: 'planned', cat: 'activity' };
  const e = !id ? blank : mine ? (own ? { ...own.ev } : null) : d.ev.find(x => x.id === id);
  if (!e) return;
  sheet(id ? 'Изменить пункт' : 'Новый пункт', `
    <div class="tc-form">
      ${fld('edT', 'Что', e.t, 'text', 'required')}
      <div class="tc-form2">${fld('edS', 'Начало', e.s, 'time')}${fld('edE', 'Конец', e.e || '', 'time')}</div>
      ${sel('edSt', 'Статус', e.st, Object.entries(STL))}
      ${sel('edCat', 'Тип', e.cat, Object.entries(CAT))}
      ${fld('edCost', 'Цена на человека, ¥', e.cost ?? '', 'number', 'min="0" step="10" inputmode="numeric"')}
      <div class="tc-form3">${fld('edWalk', 'Пешком, мин', e.walk || 0, 'number', 'min="0" inputmode="numeric"')}
        ${fld('edRide', 'Дорога, мин', e.ride || 0, 'number', 'min="0" inputmode="numeric"')}
        ${fld('edBuf', 'Запас, мин', e.buf || 0, 'number', 'min="0" inputmode="numeric"')}</div>
    </div>
    <details class="tc-more"><summary>Место, транспорт, ссылка</summary><div class="tc-form">
      ${fld('edPlace', 'Место (для карты)', e.pname || '')}
      <div class="tc-form2">${fld('edLat', 'Широта', e.lat ?? '', 'number', 'step="any" inputmode="decimal"')}
        ${fld('edLng', 'Долгота', e.lng ?? '', 'number', 'step="any" inputmode="decimal"')}</div>
      ${fld('edMode', 'Транспорт (вид)', e.mode || '')}
      ${fld('edNum', 'Рейс / поезд', e.num || '')}
      <div class="tc-form2">${fld('edFrm', 'Откуда', e.frm || '')}${fld('edTo', 'Куда', e.to || '')}</div>
      ${fld('edPlat', 'Платформа / выход', e.plat || '')}
      ${fld('edLink', 'Ссылка', e.link || '', 'url')}
    </div></details>
    <label class="tc-f" for="edNote"><span>Заметки</span><textarea id="edNote" rows="3">${esc(e.note || '')}</textarea></label>
    <p class="tc-warn" id="edMsg" role="status"></p>
    <div class="tc-actions two"><button type="button" class="tc-btn primary" id="edSave">Сохранить</button>
      ${id ? '<button type="button" class="tc-btn" id="edDel">Удалить</button>' : ''}</div>`, m => {
    const v = k => m.querySelector('#' + k).value.trim();
    const num = k => { const x = v(k); return x === '' || !Number.isFinite(+x) ? null : +x; };
    m.querySelector('#edSave').addEventListener('click', () => {
      if (!v('edT') || !Number.isFinite(toMin(v('edS')))) { m.querySelector('#edMsg').textContent = 'Нужны название и время начала.'; return; }
      const x = mine ? {} : id ? e : { id: 'u' + Date.now().toString(36) };
      Object.assign(x, { t: v('edT'), s: v('edS'), e: v('edE') || null, st: v('edSt') in STL ? v('edSt') : 'planned',
        cat: v('edCat') in CAT ? v('edCat') : 'activity', pname: v('edPlace'),
        lat: num('edLat'), lng: num('edLng'), walk: num('edWalk') || 0, ride: num('edRide') || 0, buf: num('edBuf') || 0,
        cost: num('edCost'), mode: v('edMode'), num: v('edNum'), frm: v('edFrm'), to: v('edTo'), plat: v('edPlat'),
        link: Core.safeUrl(v('edLink')), note: v('edNote') });
      if (mine) {
        const stop = { id: id || 'm-' + (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36)), day: day.n, ev: x, shared: own ? !!own.shared : false };
        Api.call('save_my_stop', { p_stop: stop }, s => { s.my_stops = (s.my_stops || []).filter(q => q.id !== stop.id).concat([{ ...stop, member: Api.me().id }]); });
        closeSheet(); renderShell(); return;
      }
      if (!id) d.ev.push(x);
      d.ev.sort((a, b) => (toMin(a.s) || 0) - (toMin(b.s) || 0));
      if (doc) Api.call('save_plan', { p_doc: doc, p_version: G.plan.version }, s => { s.plan = { doc, version: s.plan.version + 1 }; });
      else saveTrip();
      closeSheet(); renderShell();
    });
    const del = m.querySelector('#edDel');
    if (del) del.addEventListener('click', () => twoTap(del, 'Точно удалить?', () => {
      if (mine) Api.call('delete_my_stop', { p_id: id }, s => { s.my_stops = (s.my_stops || []).filter(q => q.id !== id); });
      else {
        d.ev = d.ev.filter(x => x.id !== id);
        if (doc) Api.call('save_plan', { p_doc: doc, p_version: G.plan.version }, s => { s.plan = { doc, version: s.plan.version + 1 }; });
        else saveTrip();
      }
      closeSheet(); renderShell();
    }));
    m.querySelector('#edT').focus();
  });
}

function openDayEditor(day) {
  const d = T.days.find(x => x.n === day.n);
  sheet('День ' + day.n, `
    <div class="tc-form">
      ${fld('dyLabel', 'Короткое название', d.label)}
      ${fld('dyCity', 'Город', d.city)}
      ${fld('dyHotel', 'Отель на эту ночь', d.hotel)}
    </div>
    <label class="tc-f" for="dySum"><span>Главное за день</span><textarea id="dySum" rows="2">${esc(d.summary || '')}</textarea></label>
    <button type="button" class="tc-btn primary wide" id="dySave">Сохранить</button>`, m => {
    m.querySelector('#dySave').addEventListener('click', () => {
      const v = k => m.querySelector('#' + k).value.trim();
      d.label = v('dyLabel') || d.label; d.city = v('dyCity') || d.city; d.hotel = v('dyHotel'); d.summary = v('dySum');
      saveTrip(); closeSheet(); renderShell();
    });
  });
}
