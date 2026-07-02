// ═══ APP — orchestration + hard lock + trade form + hybrid refresh ═══

let currentData = null;
let hardLockDismissed = false;

const applyHardLock = (data) => {
  const eff = data.header && data.header.effective_mode;
  const nt = data.notrade_filters || {};
  const hl = $('#hard-lock');

  if (hardLockDismissed) { hl.hidden = true; return; }

  const isLocked = eff === 'RED' || nt.macro_lock_active;
  if (!isLocked) { hl.hidden = true; return; }

  let reason = '—';
  if (eff === 'RED') {
    reason = 'RED effektív mód — a Risk OS és/vagy Macro állapot alapján ma nincs XAU trade. A rendszer szigorúbb-nyer logikával lockolta a setup panelt.';
  } else if (nt.macro_lock_active) {
    const w = nt.macro_no_trade_windows && nt.macro_no_trade_windows[0];
    reason = w ? `Makró tiltási ablak (${w.start}–${w.end} CEST): ${w.reason}` : 'Makró tiltási ablak aktív.';
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

  submit.addEventListener('click', () => {
    alert('A kézi naplózás egyelőre helyi jelzés.\nA következő verzióban a data.json-be írjuk (GitHub API vagy manuális PR).');
  });
};

const render = (data) => {
  currentData = data;
  renderTopBar(data);
  renderChart();
  renderChartLevels(data.levels || {});
  renderSetups(data);
  renderRisk(data);
  renderRelevance(data);
  renderWarnings(data);
  renderTradeLog(data);
  applyHardLock(data);
};

// ═══ HYBRID REFRESH ═══
// - Először a data.json-t próbáljuk (GH Actions cron 15 percente frissíti).
// - Ha updated_at > 30 perc → stale, client-side fallback próbál Yahoo-tól spotot húzni.
const clientSideXauFallback = async (data) => {
  try {
    // Yahoo unofficial quote endpoint
    const res = await fetch('https://query1.finance.yahoo.com/v8/finance/chart/GC=F?interval=1m&range=1d', { cache: 'no-store' });
    if (!res.ok) return;
    const j = await res.json();
    const r = j?.chart?.result?.[0];
    if (!r) return;
    const price = r.meta?.regularMarketPrice;
    const prevClose = r.meta?.previousClose;
    if (price && prevClose) {
      const change = ((price - prevClose) / prevClose * 100).toFixed(2);
      data.macro = data.macro || {};
      data.macro.xau_spot = {
        value: Math.round(price*100)/100,
        display: `$${price.toFixed(2)} (${change >= 0 ? '+' : ''}${change}%) [client]`,
        bias: null, bias_note: 'Client-side Yahoo fallback',
        impact: 4, status: 'fresh',
        source_type: 'auto', source_label: 'Yahoo Finance GC=F (client fallback)',
        source_url: 'https://finance.yahoo.com/quote/GC=F',
        updated_at: new Date().toISOString()
      };
      // Frissítjük a meta-t is
      data.meta = data.meta || {};
      data.meta.data_freshness = 'live';
      render(data);
      console.log('[hybrid-refresh] Client fallback sikeres:', price);
    }
  } catch (e) {
    console.warn('[hybrid-refresh] Client fallback hiba:', e);
  }
};

const load = async () => {
  try {
    const data = await fetchData();
    render(data);
    // Hybrid: ha a xau_spot vagy dxy updated_at > 30 perce, client fallback
    const spot = data.macro?.xau_spot?.updated_at;
    if (isStale(spot, 30)) {
      console.log('[hybrid-refresh] data.json stale → client fallback...');
      await clientSideXauFallback(data);
    }
  } catch (e) {
    console.error('[app] load hiba:', e);
    $('#relevance-container').innerHTML = '<div class="log-empty">⚠ data.json betöltése sikertelen: ' + e.message + '</div>';
  }
};

// ═══ INIT ═══
document.addEventListener('DOMContentLoaded', () => {
  wireTradeForm();
  $('#btn-refresh').addEventListener('click', load);
  $('#hard-lock-close').addEventListener('click', () => {
    hardLockDismissed = true;
    $('#hard-lock').hidden = true;
  });
  load();
  // 5 perces auto-refresh
  setInterval(load, 5 * 60 * 1000);
});
