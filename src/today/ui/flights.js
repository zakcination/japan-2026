/* ---------- flights on «Сейчас»: countdown to the next departure, «Мои рейсы» to enter your own ----------
   Each phone can keep its own list (someone in the group flies differently); without one the
   trip's flights are used. Known flights (from every trip baked into the page) fill themselves in. */
const FL_KEY = 'japan2026.flights.v1';
function ownFlights() { try { const j = JSON.parse(localStorage.getItem(FL_KEY) || 'null'); return Array.isArray(j) ? j : null; } catch (e) { return null; } }
const myFlights = () => Flights.cleanList(ownFlights() || T.flights);
const knownFlights = () => [...Flights.cleanList(T.flights), ...Flights.cleanList(DATA.knownFlights)];
function saveFlights(list) { try { localStorage.setItem(FL_KEY, JSON.stringify(Flights.cleanList(list))); } catch (e) {} }

/* local time at an airport */
function atAirport(ms, code, off) {
  const o = Flights.offsetAt(code, ms, off); const d = new Date(ms + (o || 0) * 60000);
  const p2 = v => String(v).padStart(2, '0');
  return { hm: `${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())}`, dm: `${p2(d.getUTCDate())}.${p2(d.getUTCMonth() + 1)}` };
}

function flightCardHTML(x) {
  const now = Date.now(), n = Flights.next(myFlights(), now);
  if (!n) return '';
  if (x.c.live && n.dep - now > 36 * 3600e3 && !['departure', 'transit'].includes(x.ph && x.ph.phase)) return '';
  const l = n.leg, cd = Flights.countdown(n.dep - now), dep = atAirport(n.dep, l.frm, l.frmOff);
  const last = n.chain[n.chain.length - 1], lt = Flights.times(last);
  const arr = lt && lt.arr ? atAirport(lt.arr, last.to, last.toOff) : null;
  const route = [n.chain[0].frm, ...n.chain.map(c => c.to)].map(c => esc(Flights.airport(c))).join(' → ');
  const head = n.dir === 'japan' ? 'До вылета в Японию' : n.dir === 'home' ? 'До вылета домой' : 'До вылета';
  const ap = atAirport(n.dep - 3 * 3600e3, l.frm, l.frmOff);
  return `<section class="tc-card tc-flight" id="tcFlight">
    <div class="tc-row"><span class="tc-lbl">${head}</span><span class="tc-fl-no">${esc(Flights.pretty(l.no))}</span></div>
    <div class="tc-fl-count" role="timer" aria-label="${head}: ${cd.d ? cd.d + ' ' + cd.unit + ' ' : ''}${cd.h} ч ${cd.m} мин">
      ${cd.d ? `<b>${cd.d}</b><span>${cd.unit}</span>` : ''}<b class="${cd.d ? 'rest' : ''}">${cd.h}</b><span>ч</span><b class="${cd.d ? 'rest' : ''}">${String(cd.m).padStart(2, '0')}</b><span>мин</span></div>
    <span class="tc-fl-route">${route}</span>
    <span class="tc-sub">Вылет ${dep.dm} в ${dep.hm} по времени ${esc(Flights.airport(l.frm))}${Flights.airline(l.no) ? ' · ' + esc(Flights.airline(l.no)) : ''}.
      В аэропорту — к ${ap.hm}${arr ? `. Прилёт ${arr.dm} в ${arr.hm}` : ''}.</span>
    <div class="tc-actions two"><a class="tc-btn" href="${Flights.statusUrl(l.no)}" target="_blank" rel="noopener">${icon('plane')}Статус рейса</a>
      <button type="button" class="tc-btn" id="tcFlights">Мои рейсы</button></div>
  </section>`;
}
/* before the trip with no flights entered: a small tile next to the sun */
function flightTileHTML(x) {
  if (x.c.live || myFlights().length) return '';
  return `<button type="button" class="tc-flline" id="tcFlights">${icon('plane')}<span>Добавить свой рейс<small>номер и дата — будет обратный отсчёт</small></span>${icon('arrow')}</button>`;
}
function wireFlightCard(root) { const b = root.querySelector('#tcFlights'); if (b) b.addEventListener('click', openFlights); }

function openFlights() {
  const legs = myFlights(), own = !!ownFlights(), p2 = v => String(v).padStart(2, '0');
  const offs = []; for (let m = -720; m <= 840; m += 30) offs.push(m);
  const offSel = id => `<label class="tc-f" for="${id}" hidden><span>Часовой пояс аэропорта</span><select id="${id}">${offs.map(m =>
    `<option value="${m}"${m === 300 ? ' selected' : ''}>UTC${m < 0 ? '−' : '+'}${Math.floor(Math.abs(m) / 60)}${Math.abs(m) % 60 ? ':' + p2(Math.abs(m) % 60) : ''}</option>`).join('')}</select></label>`;
  sheet('Мои рейсы', `
    <p class="tc-sub">Номер рейса и дата вылета — остальное подставится, если рейс известен. Время — местное в каждом аэропорту.
      Список хранится на этом телефоне.</p>
    ${legs.length ? `<div class="tc-group" id="flList">${legs.map((l, i) => {
      const t = Flights.times(l);
      return `<div class="tc-flrow"><span><b>${esc(Flights.pretty(l.no))}</b> · ${l.date.slice(8)}.${l.date.slice(5, 7)}<small>${esc(l.frm)} ${esc(l.dep)} → ${esc(l.to)} ${t && t.arr ? esc(l.arr) : '—'}</small></span>
        <button type="button" class="tc-x" data-fldel="${i}" aria-label="Удалить рейс ${esc(Flights.pretty(l.no))}">${icon('close')}</button></div>`;
    }).join('')}</div>` : ''}
    <span class="tc-sech">Добавить рейс</span>
    <div class="tc-form">
      <div class="tc-form2">${fld('flNo', 'Рейс', '', 'text', 'placeholder="MU575" autocapitalize="characters" autocomplete="off" spellcheck="false"')}
        ${fld('flDate', 'Дата вылета', '', 'date')}</div>
      <p class="tc-foot" id="flInfo" role="status"></p>
      <div class="tc-form2">${fld('flFrm', 'Откуда (код)', '', 'text', 'placeholder="ALA" maxlength="3" autocapitalize="characters" list="flCodes"')}
        ${fld('flDep', 'Вылет', '', 'time')}</div>
      ${offSel('flFrmOff')}
      <div class="tc-form2">${fld('flTo', 'Куда (код)', '', 'text', 'placeholder="HND" maxlength="3" autocapitalize="characters" list="flCodes"')}
        ${fld('flArr', 'Прилёт', '', 'time')}</div>
      ${offSel('flToOff')}
      <datalist id="flCodes">${Flights.codes().map(c => `<option value="${c}">${esc(Flights.airport(c))}</option>`).join('')}</datalist>
    </div>
    <p class="tc-warn" id="flMsg" role="status"></p>
    <button type="button" class="tc-btn primary wide" id="flAdd">${icon('plus')}Добавить рейс</button>
    ${own ? '<button type="button" class="tc-btn wide" id="flReset">Вернуть рейсы поездки</button>' : ''}`, m => {
    const $ = id => m.querySelector('#' + id);
    const info = () => {
      const f = Flights.lookup($('flNo').value, knownFlights());
      if (!f) { $('flInfo').textContent = $('flNo').value.trim() ? 'Формат: две буквы/цифры авиакомпании и номер, например MU575.' : ''; return; }
      if (f.frm) {
        ['frm', 'dep', 'to', 'arr'].forEach(k => { const el = $('fl' + k[0].toUpperCase() + k.slice(1)); if (!el.value || el.dataset.auto) { el.value = f[k] || ''; el.dataset.auto = '1'; } });
        $('flInfo').textContent = `${f.airline || 'Рейс'} · ${Flights.airport(f.frm)} → ${Flights.airport(f.to)} · ${f.dep}–${f.arr || '?'} — рейс знаком, проверьте дату.`;
      } else {
        $('flInfo').textContent = `${f.airline || 'Авиакомпания не знакома'} — впишите аэропорты и время из билета.`;
      }
      codes();
    };
    const codes = () => ['Frm', 'To'].forEach(k => {
      const c = $('fl' + k).value.trim().toUpperCase();
      $('fl' + k + 'Off').closest('label').hidden = !(c.length === 3 && !Flights.AIRPORTS[c]);
    });
    $('flNo').addEventListener('input', info);
    ['flFrm', 'flTo'].forEach(id => $(id).addEventListener('input', () => { delete $(id).dataset.auto; codes(); }));
    ['flDep', 'flArr'].forEach(id => $(id).addEventListener('input', () => { delete $(id).dataset.auto; }));
    $('flAdd').addEventListener('click', () => {
      const unk = k => !$('fl' + k + 'Off').closest('label').hidden;
      const leg = Flights.clean({ no: $('flNo').value, date: $('flDate').value, frm: $('flFrm').value, dep: $('flDep').value,
        to: $('flTo').value, arr: $('flArr').value,
        frmOff: unk('Frm') ? +$('flFrmOff').value : undefined, toOff: unk('To') ? +$('flToOff').value : undefined });
      if (!leg) { $('flMsg').textContent = 'Нужны рейс, дата, коды аэропортов (3 буквы) и время вылета.'; return; }
      saveFlights([...myFlights(), leg]); closeSheet(); renderShell();
    });
    m.querySelectorAll('[data-fldel]').forEach(b => b.addEventListener('click', () => twoTap(b, '?', () => {
      const l = myFlights(); l.splice(+b.dataset.fldel, 1); saveFlights(l); openFlights(); renderShell();
    })));
    const rs = $('flReset');
    if (rs) rs.addEventListener('click', () => { try { localStorage.removeItem(FL_KEY); } catch (e) {} closeSheet(); renderShell(); });
  });
}
