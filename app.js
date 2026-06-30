async function loadData() {
  try {
    const res = await fetch('./data.json', { cache: 'no-store' });
    const data = await res.json();
    renderDashboard(data);
  } catch (e) {
    console.error('Error loading data.json', e);
  }
}

function renderDashboard(data) {
  renderTopBar(data);
  renderSetups(data);
  renderMacro(data);
  renderRisk(data);
  renderTrades(data);
  wireToolbar(data);
}

/* ---------- HELPERS ---------- */

function getEffectiveMode(dailyStatus, riskMode) {
  const order = ['GREEN', 'YELLOW', 'RED'];
  const s = (dailyStatus || '').toUpperCase();
  const r = (riskMode || '').toUpperCase();
  const sIdx = order.indexOf(s) === -1 ? 0 : order.indexOf(s);
  const rIdx = order.indexOf(r) === -1 ? 0 : order.indexOf(r);
  return order[Math.max(sIdx, rIdx)];
}

function formatPct(value, limit) {
  if (limit <= 0) return '0%';
  const pct = Math.min(100, Math.max(0, (Math.abs(value) / limit) * 100));
  return `${pct.toFixed(0)}%`;
}

function safeGet(field, def = '-') {
  return field === null || field === undefined || field === '' ? def : field;
}

/* ---------- TOP BAR ---------- */

function renderTopBar(data) {
  const header = data.header || {};
  const risk = data.risk || {};
  const meta = data.meta || {};

  const effective = getEffectiveMode(header.daily_status, risk.mode);

  document.getElementById('top-date').textContent = safeGet(meta.date, '');
  document.getElementById('top-session').textContent = `Session: ${safeGet(header.session, 'n/a')}`;

  const biasDir = document.getElementById('bias-direction');
  biasDir.textContent = safeGet(header.bias_direction, 'n/a');

  const biasStatus = document.getElementById('bias-status');
  const status = (header.daily_status || '').toUpperCase();
  biasStatus.textContent = status || 'UNKNOWN';
  biasStatus.dataset.status = status || 'GREEN';

  document.getElementById('daily-narrative').textContent = safeGet(header.narrative, '');

  const effTop = document.getElementById('effective-mode');
  effTop.textContent = effective;
  effTop.dataset.mode = effective;

  document.getElementById('daily-risk-bar').style.width = formatPct(risk.daily_loss || 0, risk.daily_limit || 100);
  document.getElementById('daily-risk-text').textContent = `${formatPct(risk.daily_loss || 0, risk.daily_limit || 100)} of ${risk.daily_limit || 100} USD limit`;
  document.getElementById('last-auto-sync').textContent = safeGet(meta.last_auto_sync, '-');
  document.getElementById('last-manual-update').textContent = safeGet(meta.last_manual_update, '-');

  document.getElementById('setup-guideline').textContent =
    status === 'YELLOW' ? 'SÁRGA nap – max 1 setup, max 1 trade, score ≥8.'
    : status === 'RED' ? 'PIROS nap – NO-TRADE, csak megfigyelés és review.'
    : 'ZÖLD nap – max 2 setup, score ≥6, szabályok szerint.';
}

/* ---------- SETUPS ---------- */

function renderSetups(data) {
  renderSetupCard('A', data);
  renderSetupCard('B', data);

  document.getElementById('chart-active-setup').textContent =
    data.header && data.header.focus_setup ? `Setup ${data.header.focus_setup}` : 'nincs kijelölve';
  document.getElementById('chart-session').textContent = safeGet(data.header && data.header.preferred_session, 'London / Overlap');

  const chartMacro = document.getElementById('chart-macro-lock');
  const macroLocked = data.header && data.header.macro_lock_active;
  chartMacro.textContent = macroLocked ? 'LOCKED' : 'OK';
  chartMacro.dataset.status = macroLocked ? 'YELLOW' : 'GREEN';

  document.getElementById('chart-last-data').textContent = safeGet(data.meta && data.meta.last_auto_sync, '-');
}

function renderSetupCard(letter, data) {
  const el = document.getElementById(`setup-${letter}`);
  const setup = (data.setups || {})[letter] || {};
  const header = data.header || {};
  const risk = data.risk || {};

  const effective = getEffectiveMode(header.daily_status, risk.mode);
  const status = (header.daily_status || '').toUpperCase();

  const requiredScore = status === 'YELLOW' ? 8 : status === 'GREEN' ? 6 : 99;

  let allowed = !!setup.allowed;
  const lockReasons = [];

  if (effective === 'RED') { allowed = false; lockReasons.push('Effective mode RED'); }
  if (setup.rr_min && setup.rr_min < 2) { allowed = false; lockReasons.push('RR < 1:2'); }
  if ((setup.score || 0) < requiredScore) { allowed = false; lockReasons.push(`Score < ${requiredScore}`); }
  if (header.macro_lock_active) { allowed = false; lockReasons.push('Macro lock aktív'); }

  const dir = (setup.direction || '').toUpperCase();
  const dirClass = dir === 'LONG' ? 'setup-tag--long' : dir === 'SHORT' ? 'setup-tag--short' : '';
  const bullets = (setup.thesis || []).slice(0, 3);

  el.innerHTML = `
    <div class="setup-card__head">
      <div class="setup-card__title">
        <span>Setup ${letter}</span>
        <span class="setup-tag ${dirClass}">${dir || 'n/a'}</span>
        <span class="setup-tag">${safeGet(setup.type, 'n/a')}</span>
      </div>
      <div class="setup-state">
        <span class="setup-state__label" data-allowed="${allowed}">${allowed ? 'ALLOWED' : 'LOCKED'}</span>
      </div>
    </div>
    <div class="setup-score-row">
      <span>Score: ${safeGet(setup.score, 0)}/10</span>
      <span>Required: ${requiredScore === 99 ? '–' : requiredScore}/10</span>
    </div>
    <div class="setup-score-bar bar">
      <div class="bar__fill" style="width:${Math.min(100,(setup.score||0)*10)}%;"></div>
    </div>
    <div class="setup-rr-row">
      <span>RR min: ${setup.rr_min ? `1:${Number(setup.rr_min).toFixed(1)}` : 'n/a'}</span>
      <span>Bias kompatibilitás: ${safeGet(setup.bias_compatibility, 'n/a')}</span>
    </div>
    <div class="setup-line">
      <span>Belépő: ${safeGet(setup.entry_zone, 'nincs')}</span>
    </div>
    <div class="setup-line">
      <span>SL: ${safeGet(setup.sl, '–')}</span>
      <span>TP1: ${safeGet(setup.tp1, '–')}</span>
      <span>TP2: ${setup.tp2 !== null && setup.tp2 !== undefined ? setup.tp2 : '–'}</span>
    </div>
    <div class="setup-thesis"><ul>${bullets.map(b => `<li>${b}</li>`).join('')}</ul></div>
    <div class="setup-meta">
      <span>Invalidáció: ${safeGet(setup.invalidation, '–')}</span>
      <span>Session: ${safeGet(setup.session, 'London')}</span>
      ${lockReasons.length ? `<span style="color:var(--accent-red)">${lockReasons.join(' · ')}</span>` : '<span style="color:var(--accent-green)">Szabály szerint OK</span>'}
    </div>
  `;
}

/* ---------- MACRO ---------- */

function renderMacro(data) {
  const macro = data.macro || {};
  const tiles = document.getElementById('macro-tiles');
  tiles.innerHTML = '';

  const defs = [
    { key: 'fedwatch', label: 'FedWatch' },
    { key: 'us10y', label: 'US10Y' },
    { key: 'dxy', label: 'DXY' },
    { key: 'sentiment', label: 'Sentiment' },
    { key: 'htf_trend', label: 'HTF Trend' },
    { key: 'intraday_regime', label: 'Intraday' },
    { key: 'volatility', label: 'Volatility' }
  ];

  defs.forEach(def => {
    const item = macro[def.key] || {};
    const bias = (item.bias || 'NEUTRAL').toUpperCase();
    const el = document.createElement('div');
    el.className = 'macro-tile';
    el.innerHTML = `
      <div class="macro-tile__title">
        <span>${def.label}</span>
        <span class="pill pill--status" data-status="${bias}">${safeGet(item.value, 'n/a')}</span>
      </div>
      <div class="macro-tile__meta">
        <span>${safeGet(item.source_label, '')}</span>
        <span>${safeGet(item.updated_at, '')}</span>
      </div>
    `;
    tiles.appendChild(el);
  });

  const keylevels = data.keylevels || {};
  const tbody = document.querySelector('#keylevels-table tbody');
  tbody.innerHTML = '';
  let overallState = 'OK';

  Object.entries(keylevels).forEach(([name, obj]) => {
    const value = obj.value !== undefined && obj.value !== null ? obj.value : '–';
    const state = obj.status || 'pending';
    if (state === 'pending' || state === 'stale') overallState = 'ATTENTION';
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${name}</td><td>${value}</td><td>${obj.source_label || ''} · ${state}</td>`;
    tbody.appendChild(tr);
  });

  const klStatus = document.getElementById('keylevels-status');
  klStatus.textContent = overallState === 'OK' ? 'Key levels rendben' : 'Key levels: figyelmet igényel';
}

/* ---------- RISK ---------- */

function renderRisk(data) {
  const risk = data.risk || {};
  const header = data.header || {};
  const effective = getEffectiveMode(header.daily_status, risk.mode);

  const effRisk = document.getElementById('risk-effective-mode');
  effRisk.textContent = effective;
  effRisk.dataset.mode = effective;

  const noteEl = document.getElementById('risk-note');
  if (effective === 'RED') {
    noteEl.textContent = 'RED – NO-TRADE nap.';
  } else if (effective === 'YELLOW') {
    noteEl.textContent = 'YELLOW – max 1 trade, csökkentett méret.';
  } else {
    noteEl.textContent = 'GREEN – normál risk, szabályok érvényes.';
  }

  const dailyLimit = risk.daily_limit || 100;
  const weeklyLimit = risk.weekly_limit || 300;
  const dailyLoss = risk.daily_loss || 0;
  const weeklyLoss = risk.weekly_loss || 0;

  const dailyPct = Math.min(100, (Math.abs(dailyLoss) / dailyLimit) * 100);
  const weeklyPct = Math.min(100, (Math.abs(weeklyLoss) / weeklyLimit) * 100);

  document.getElementById('risk-daily-pl').textContent = `${Number(dailyLoss).toFixed(2)} USD`;
  document.getElementById('risk-daily-limit').textContent = `${dailyLimit} USD limit`;
  document.getElementById('risk-weekly-limit').textContent = `${weeklyLimit} USD limit`;
  document.getElementById('risk-daily-bar').style.width = `${dailyPct.toFixed(0)}%`;
  document.getElementById('risk-daily-text').textContent = `${dailyPct.toFixed(0)}% of daily limit`;
  document.getElementById('risk-weekly-bar').style.width = `${weeklyPct.toFixed(0)}%`;
  document.getElementById('risk-weekly-text').textContent = `${weeklyPct.toFixed(0)}% of weekly limit`;

  document.getElementById('risk-loss-streak').textContent = safeGet(risk.loss_streak, 0);
  document.getElementById('risk-max-trades').textContent = safeGet(risk.max_trades_today, 0);
  document.getElementById('risk-open-positions').textContent = safeGet(risk.open_positions, 0);

  const overlay = document.getElementById('no-trade-overlay');
  overlay.style.display = effective === 'RED' ? 'flex' : 'none';
}

/* ---------- TRADES ---------- */

function renderTrades(data) {
  const trades = data.trades || [];
  const tbody = document.querySelector('#trades-table tbody');
  tbody.innerHTML = '';

  let netPL = 0, sumRR = 0, rrCount = 0, ok = 0;

  trades.forEach(tr => {
    netPL += tr.pl_usd || 0;
    if (tr.rr_actual !== undefined) { sumRR += tr.rr_actual; rrCount++; }
    if (tr.rule_ok) ok++;

    const dirStyle = (tr.direction || '').toUpperCase() === 'LONG'
      ? 'color:var(--accent-green);' : 'color:var(--accent-red);';

    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${safeGet(tr.time, '')}</td>
      <td>${safeGet(tr.session, '')}</td>
      <td style="${dirStyle}">${safeGet(tr.direction, '')}</td>
      <td>${safeGet(tr.setup_id, '')}</td>
      <td>${Number(tr.risk_usd || 0).toFixed(2)}</td>
      <td>${Number(tr.pl_usd || 0).toFixed(2)}</td>
      <td>${tr.rr_actual !== undefined ? Number(tr.rr_actual).toFixed(2) : '–'}</td>
      <td><span class="badge ${tr.rule_ok ? 'badge--ok' : 'badge--violation'}">${tr.rule_ok ? 'OK' : 'Viol'}</span></td>
    `;
    tbody.appendChild(row);
  });

  const count = trades.length;
  const avgRR = rrCount ? sumRR / rrCount : 0;
  const adherence = count ? (ok / count) * 100 : 100;

  document.getElementById('stat-trades-today').textContent = count;
  document.getElementById('stat-net-pl').textContent = `${netPL.toFixed(2)} USD`;
  document.getElementById('stat-avg-rr').textContent = rrCount ? avgRR.toFixed(2) : '–';
  document.getElementById('stat-rule-adherence').textContent = `${adherence.toFixed(0)}%`;
}

/* ---------- TOOLBAR ---------- */

function wireToolbar(data) {
  document.querySelectorAll('[data-session-toggle]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-session-toggle]').forEach(b => b.classList.remove('btn--active'));
      btn.classList.add('btn--active');
    });
  });

  document.querySelectorAll('[data-setup-focus]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-setup-focus]').forEach(b => b.classList.remove('btn--active'));
      btn.classList.add('btn--active');
      document.getElementById('chart-active-setup').textContent = `Setup ${btn.getAttribute('data-setup-focus')}`;
    });
  });
}

/* ---------- INIT ---------- */
document.addEventListener('DOMContentLoaded', loadData);