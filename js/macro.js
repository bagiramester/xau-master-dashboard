// ═══ MACRO MODULE — Top bar: ár középen, magyar chip-ek jobbra info gombbal ═══

// Info tooltip szövegek építése a makró adatokból
const SESSION_WINDOWS = [
  { name: 'Asia',   range: '02:00–09:00 CEST', note: 'Ázsiai session — új XAU trade alapból nem preferált.' },
  { name: 'London', range: '09:00–14:00 CEST', note: 'Elsődleges végrehajtási ablak — preferált.' },
  { name: 'Overlap', range: '14:00–19:00 CEST', note: 'London–NY overlap — másodlagos ablak.' },
  { name: 'NY',     range: '13:00–22:00 CEST', note: 'New York session.' },
];

const wireInfo = (id, tipText) => {
  const node = $('#' + id);
  if (!node) return;
  node.title = tipText; // natív fallback
  node.addEventListener('mouseenter', (e) => showTip(e, tipText));
  node.addEventListener('mousemove', (e) => showTip(e, tipText));
  node.addEventListener('mouseleave', hideTip);
  node.addEventListener('focus', (e) => {
    const r = node.getBoundingClientRect();
    showTip({ clientX: r.left, clientY: r.bottom + 6 }, tipText);
  });
  node.addEventListener('blur', hideTip);
};

const renderTopBar = (data) => {
  // Dátum/idő — csak egyszer
  const now = new Date();
  $('#tb-datetime').textContent = now.toLocaleString('hu-HU', {
    weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  });

  const h = data.header || {};
  const m = data.macro || {};
  const nt = data.notrade_filters || {};
  const r = data.risk || {};

  // Chip értékek + állapotszínek
  const setChip = (valId, chipSel, value, state) => {
    $(valId).textContent = value || '—';
    const chip = $(chipSel);
    if (state) chip.dataset.state = state;
    else delete chip.dataset.state;
  };

  // Munkamenet
  setChip('#tb-session', '.tb-chip[data-role="session"]', h.session, null);
  const sw = SESSION_WINDOWS.find(w => w.name === h.session) || { range: '—', note: 'Ismeretlen session.' };
  wireInfo('tb-info-session',
    `Munkamenet (SESSION)\n` +
    `Aktív érték: ${h.session || '—'}\n\n` +
    `Időablak: ${sw.range}\n${sw.note}\n\n` +
    `A session az aktuális időpontból származik (CEST).`);
  wireInfo('tb-info-bias',
    `Irány (BIAS)\n` +
    `Aktív érték: ${h.bias_direction || '—'}\n\n` +
    `A napi irány a makró jelekből származik: DXY, US10Y, FedWatch, Fear & Greed és HTF trend.\n\n` +
    `Indoklás: ${(h.narrative || '—').slice(0, 200)}`);
  wireInfo('tb-info-status',
    `Státusz (STATUS)\n` +
    `Aktív érték: ${h.bias_status || '—'}\n\n` +
    `Napi státusz a belépési küszöbhöz:\n` +
    `• ZÖLD → Score ≥ 6 nyitható\n` +
    `• SÁRGA → Score ≥ 8 nyitható\n` +
    `• PIROS → nincs új trade`);
  const effNote =
    h.effective_mode === 'RED' ? 'RED: nincs új trade (NO-TRADE zóna).'
    : h.effective_mode === 'YELLOW' ? 'YELLOW: max 1 setup, Score ≥ 8 kötelező.'
    : 'GREEN: normál kereskedés a szabályok szerint.';
  wireInfo('tb-info-effective',
    `Effektív mód (EFFECTIVE)\n` +
    `Aktív érték: ${h.effective_mode || '—'}\n\n` +
    `A „szigorúbb-nyer” logika: a risk mód és a napi státusz közül a szigorúbb érvényesül.\n\n` +
    `Risk mód: ${r.mode || '—'} · Napi státusz: ${h.bias_status || '—'}\n\n` +
    effNote);
  const lockActive = nt.macro_lock_active;
  const win = nt.macro_no_trade_windows && nt.macro_no_trade_windows[0];
  const ev = nt.macro_events_today && nt.macro_events_today[0];
  wireInfo('tb-info-lock',
    `Makró zár (MACRO LOCK)\n` +
    `Aktív érték: ${lockActive ? 'AKTÍV' : 'inaktív'}\n\n` +
    `High-impact makró esemény előtt 60 percig, után 30 percig nincs új XAU trade.\n\n` +
    (ev ? `Esemény: ${ev.event} · ${ev.time_cest} CEST\n${ev.note || ev.effect || ''}\n\n` : '') +
    (win ? `Tiltási ablak: ${win.start}–${win.end} CEST\n${win.reason}` : 'Nincs aktív tiltási ablak.'));

  // Állapotszínek a chip-ekhez
  setChip('#tb-bias', '.tb-chip[data-role="bias"]', h.bias_direction,
    h.bias_direction === 'LONG' ? 'long' : h.bias_direction === 'SHORT' ? 'short' : null);
  const statusMap = { 'ZÖLD': 'green', 'SÁRGA': 'yellow', 'PIROS': 'red' };
  setChip('#tb-status', '.tb-chip[data-role="status"]', h.bias_status, statusMap[h.bias_status]);
  const effMap = { 'GREEN': 'green', 'YELLOW': 'yellow', 'RED': 'red' };
  setChip('#tb-effective', '.tb-chip[data-role="effective"]', h.effective_mode, effMap[h.effective_mode]);
  setChip('#tb-lock', '.tb-chip[data-role="lock"]', lockActive ? 'AKTÍV' : 'inaktív', lockActive ? 'red' : 'green');

  // Spot ár középen + delta
  const spot = m.xau_spot;
  const priceEl = $('#tb-spot');
  const deltaEl = $('#tb-spot-delta');
  if (spot && spot.value != null) {
    priceEl.textContent = '$' + Number(spot.value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    // delta kinyerése a display-ből (pl. "$4,178.80 (+1.61%)" -> "+1.61%")
    const dm = (spot.display || '').match(/\(([^)]+)\)/);
    deltaEl.textContent = dm ? dm[1] : '';
    deltaEl.style.color = (spot.display || '').includes('-') ? 'var(--red)' : 'var(--green)';
  } else {
    priceEl.textContent = '—';
    deltaEl.textContent = '';
  }

  // Frissesség
  const fresh = data.meta && data.meta.data_freshness;
  const dot = $('#tb-freshness-dot');
  dot.dataset.state = fresh === 'live' ? 'live' : fresh === 'stale' ? 'stale' : 'error';
  $('#tb-freshness').textContent = fresh === 'live' ? 'LIVE' : fresh === 'stale' ? 'STALE' : 'PENDING';

  $('#footer-updated').textContent = 'Frissítve: ' + (data.meta ? data.meta.last_updated : '—');
};

// ═══ REFRESH — minden adat frissítése KIVÉVE Bagira + timestamp mutatása ═══
const refreshAllData = async () => {
  const btn = $('#btn-refresh');
  const original = btn.textContent;
  btn.dataset.loading = 'true';
  btn.textContent = '⏳ Frissítés...';
  try {
    const freshData = await fetchData();
    // Bagira megőrzése — a ↻ gomb nem írja felül az AI elemzést
    if (currentData && currentData.bagira) {
      freshData.bagira = currentData.bagira;
      if (currentData.meta) {
        freshData.meta = freshData.meta || {};
        freshData.meta.ai_last_run = currentData.meta.ai_last_run;
        freshData.meta.ai_model = currentData.meta.ai_model;
        freshData.meta.ai_source_type = currentData.meta.ai_source_type;
      }
    }
    currentData = freshData;
    render(freshData);
    // Ha a spot stale, élő fallback
    const spot = freshData.macro?.xau_spot?.updated_at;
    if (isStale(spot, 30)) {
      await clientSideXauFallback(freshData);
    }
    const ts = new Date().toLocaleTimeString('hu-HU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    showRefreshStatus(`Frissítve: ${ts}`, 'success');
  } catch (e) {
    console.error('[refresh] hiba:', e);
    showRefreshStatus('Frissítési hiba: ' + e.message, 'error');
  } finally {
    btn.dataset.loading = 'false';
    btn.textContent = original;
  }
};

const showRefreshStatus = (msg, level) => {
  let host = $('#refresh-status');
  if (!host) {
    host = el('div', { id: 'refresh-status', class: `refresh-status refresh-status--${level}` });
    const btn = $('#btn-refresh');
    btn.parentNode.insertBefore(host, btn.nextSibling);
  }
  host.className = `refresh-status refresh-status--${level}`;
  host.textContent = msg;
  clearTimeout(window.__refreshStatusTimer);
  window.__refreshStatusTimer = setTimeout(() => { if (host.parentNode) host.remove(); }, 5000);
};
