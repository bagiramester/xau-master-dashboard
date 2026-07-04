// ═══ APP — orchestration + hard lock + trade form + hybrid refresh ═══
let currentData = null;
let hardLockDismissed = false;

const applyHardLock = (data) => {
  const eff = data.header && data.header.effective_mode;
  const nt = data.notrade_filters || {};
  const hl = $('#hard-lock');
  if (hardLockDismissed) { hl.hidden = true; return; }
  const isMacroLocked = nt.macro_lock_active === true;
  if (!isMacroLocked) { hl.hidden = true; return; }
  let reason = '—';
  const w = nt.macro_no_trade_windows && nt.macro_no_trade_windows[0];
  if (w) {
    reason = `Makró tiltási ablak (${w.start}–${w.end} CEST): ${w.reason}`;
  } else {
    reason = 'Makró tiltási ablak aktív — high-impact esemény környéke, nincs új XAU trade.';
  }
  $('#hard-lock-reason').textContent = reason;
  $('#hard-lock-mode').textContent = eff || 'YELLOW';
  hl.hidden = false;
};

const renderTradeLog = (data) => {
  const host = $('#log-container');
  const mini = $('#log-mini');
  host.innerHTML = '';
  const log = data.trade_log || [];
  const perf = data.performance || {};
  mini.textContent = `${perf.trade_count || 0} trade · ${perf.win_count || 0} W / ${perf.loss_count || 0} L · $${(perf.net_pl_usd || 0).toFixed(2)}`;
  if (log.length === 0) {
    host.appendChild(el('div', { class: 'log-empty' }, 'Ma még nem történt trade.'));
    return;
  }
  log.forEach(t => {
    const isWin = (t.pl_usd || 0) > 0;
    const cls = isWin ? 'log-item__pl--win' : 'log-item__pl--loss';
    host.appendChild(el('div', { class: 'log-item' },
      el('span', { class: 'mono' }, (t.datetime || '').split('T')[1]?.slice(0,5) || '—'),
      el('span', {}, `${t.direction} · ${t.setup_type || '–'} · ${t.session || '–'}`),
      el('span', { class: `mono ${cls}` }, `${isWin ? '+' : ''}$${(t.pl_usd || 0).toFixed(2)}`)
    ));
  });
};

const wireTradeForm = () => {
  const entry = $('#ti-entry'), sl = $('#ti-sl'), tp = $('#ti-tp');
  const dir = $('#ti-direction'), submit = $('#ti-submit'), rrCalc = $('#ti-rr-calc');
  const recompute = () => {
    const e = parseFloat(entry.value), s = parseFloat(sl.value), t = parseFloat(tp.value);
    if (!isFinite(e) || !isFinite(s) || !isFinite(t)) {
      rrCalc.textContent = '—';
      submit.disabled = true;
      submit.textContent = 'Naplózás (SL/TP kötelező)';
      return;
    }
    const risk = Math.abs(e - s);
    const reward = Math.abs(t - e);
    const rr = risk > 0 ? (reward / risk) : 0;
    rrCalc.textContent = rr.toFixed(2) + 'R';
    const okDirection = (dir.value === 'LONG' && t > e && s < e) || (dir.value === 'SHORT' && t < e && s > e);
    submit.disabled = !(rr >= 2.0 && okDirection);
    submit.textContent = rr < 2.0 ? `RR ${rr.toFixed(2)} < 1:2 (tiltott)`
      : !okDirection ? 'Irány/SL/TP inkonzisztens' : 'Trade naplózása';
  };
  [entry, sl, tp, dir].forEach(x => x.addEventListener('input', recompute));
  submit.addEventListener('click', submitTradeLog);
};

const render = (data) => {
  currentData = data;
  renderTopBar(data);
  renderChart();
  renderChartLevels(data.levels || {});
  renderBagira(data);
  renderSetups(data);
  renderRisk(data);
  renderRelevance(data);
  renderWarnings(data);
  renderTradeLog(data);
  applyHardLock(data);
};

const clientSideXauFallback = async (data) => {
  if (location.hostname === 'localhost' || location.hostname === '127.0.0.1') return;
  try {
    const res = await fetch('https://api.gold-api.com/price/XAU', { cache: 'no-store', mode: 'cors' });
    if (!res.ok) return;
    const j = await res.json();
    const price = j?.price;
    if (!price || !isFinite(price)) return;
    data.macro = data.macro || {};
    const prev = data.macro.xau_spot?.value || price;
    const change = ((price - prev) / prev * 100);
    data.macro.xau_spot = {
      value: Math.round(price*100)/100,
      display: `$${price.toFixed(2)} (${change >= 0 ? '+' : ''}${change.toFixed(2)}%) [live]`,
      bias: null, bias_note: 'Client-side gold-api.com live fallback',
      impact: 4, status: 'fresh',
      source_type: 'auto', source_label: 'gold-api.com (client live fallback)',
      source_url: 'https://gold-api.com/',
      updated_at: new Date().toISOString()
    };
    data.meta = data.meta || {};
    data.meta.data_freshness = 'live';
    render(data);
    const dot = $('#tb-freshness-dot');
    if (dot) dot.classList.add('freshness-live');
  } catch (e) {
    console.warn('[hybrid-refresh] Client fallback hiba:', e);
  }
};

const load = async () => {
  try {
    const data = await fetchData();
    render(data);
    const spot = data.macro?.xau_spot?.updated_at;
    if (isStale(spot, 30)) {
      await clientSideXauFallback(data);
    }
  } catch (e) {
    console.error('[app] load hiba:', e);
    $('#relevance-container').innerHTML = '<div class="log-empty">⚠ data.json betöltése sikertelen: ' + e.message + '</div>';
  }
};

document.addEventListener('DOMContentLoaded', () => {
  wireTradeForm();
  $('#btn-refresh').addEventListener('click', refreshAllData);
  $('#hard-lock-close').addEventListener('click', () => {
    hardLockDismissed = true;
    $('#hard-lock').hidden = true;
  });
  load();
  setInterval(load, 5 * 60 * 1000);
});
