/* ════════════════════════════════════════════════
   BAGIRA OS V1 — app.js
   Data-driven render: fetch('./data.json') alapú
   Nincs localStorage, nincs broker bridge
════════════════════════════════════════════════ */

async function loadData() {
  try {
    const res = await fetch('./data.json', { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderDashboard(data);
  } catch (e) {
    console.error('Bagira: data.json betöltési hiba', e);
    renderError();
  }
}

function renderError() {
  const badge = document.getElementById('effectiveBadge');
  if (badge) { badge.textContent = 'DATA ERROR'; badge.dataset.mode = 'RED'; }
  const msg = document.getElementById('bagiraMsg');
  if (msg) msg.textContent = 'data.json nem elérhető. Frissítsd az adatforrást.';
}

function renderDashboard(data) {
  renderClock();
  renderTopBar(data);
  renderGuardian(data);
  renderSetups(data);
  renderTelemetry(data);
  renderMacro(data);
  renderLevels(data);
  renderMacroEvents(data);
  renderRisk(data);
  renderExecution(data);
  renderTradeLog(data);
  setInterval(renderClock, 1000);
  setTimeout(() => loadData(), 5 * 60 * 1000); // 5 perces auto-frissítés
}

/* ─── HELPERS ─── */

function safeGet(v, def = '–') {
  return (v === null || v === undefined || v === '') ? def : v;
}

function getEffectiveMode(headerStatus, riskMode) {
  const order = ['GREEN', 'YELLOW', 'RED'];
  const a = order.indexOf((headerStatus || '').toUpperCase());
  const b = order.indexOf((riskMode || '').toUpperCase());
  return order[Math.max(a < 0 ? 0 : a, b < 0 ? 0 : b)];
}

function pct(value, limit) {
  if (!limit) return 0;
  return Math.min(100, Math.max(0, (Math.abs(value) / limit) * 100));
}

function setBadge(el, mode) {
  if (!el) return;
  el.dataset.mode = mode;
}

/* ─── CLOCK ─── */

function renderClock() {
  const now = new Date();
  const pad = n => String(n).padStart(2,'0');
  const clock = document.getElementById('liveClock');
  const dateEl = document.getElementById('liveDate');
  if (clock) clock.textContent = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  if (dateEl) dateEl.textContent = now.toLocaleDateString('hu-HU', { year:'numeric', month:'2-digit', day:'2-digit' });
}

/* ─── TOPBAR ─── */

function renderTopBar(data) {
  const h = data.header || {};
  const r = data.risk || {};
  const m = data.meta || {};

  const effective = getEffectiveMode(h.daily_status || h.risk_mode, r.mode);

  const badge = document.getElementById('effectiveBadge');
  if (badge) { badge.textContent = effective; setBadge(badge, effective); }

  const bias = document.getElementById('topBias');
  if (bias) {
    bias.textContent = safeGet(h.bias_direction, 'n/a');
    const dir = (h.bias_direction || '').toUpperCase();
    bias.style.color = dir === 'LONG' ? 'var(--accent-green)' : dir === 'SHORT' ? 'var(--accent-red)' : 'var(--text)';
  }

  const pl = document.getElementById('topDailyPL');
  if (pl) {
    const v = r.daily_loss || h.daily_pl_usd || 0;
    pl.textContent = `$${Number(v).toFixed(2)}`;
    pl.style.color = v < 0 ? 'var(--accent-red)' : v > 0 ? 'var(--accent-green)' : 'var(--text-muted)';
  }

  const autoSync = document.getElementById('topAutoSync');
  if (autoSync) autoSync.textContent = safeGet(m.last_updated || m.last_auto_sync, '–');
  const manualSync = document.getElementById('topManualSync');
  if (manualSync) manualSync.textContent = safeGet(m.last_manual_update, '–');

  // Guideline bar
  const effective2 = effective;
  const gbar = document.getElementById('guidelineBar');
  const gtext = document.getElementById('guidelineText');
  if (gtext) {
    if (effective2 === 'RED') gtext.textContent = '🔴 PIROS NAP — NO-TRADE. Csak megfigyelés és review.';
    else if (effective2 === 'YELLOW') gtext.textContent = '🟡 SÁRGA NAP — Max 1 setup, max 1 trade. Score ≥8 szükséges.';
    else gtext.textContent = '🟢 ZÖLD NAP — Max 2 setup, score ≥6, szabályok szerint.';
  }
  if (gbar) gbar.style.borderColor = effective2 === 'RED' ? 'rgba(239,68,68,0.3)' : effective2 === 'YELLOW' ? 'rgba(245,158,11,0.3)' : 'rgba(6,182,212,0.15)';

  // Macro lock bar
  const filters = data.notrade_filters || {};
  const macroLockBar = document.getElementById('macroLockBar');
  const macroLockDetail = document.getElementById('macroLockDetail');
  const isLocked = !!filters.macro_window_active;
  if (macroLockBar) macroLockBar.classList.toggle('hidden', !isLocked);
  if (macroLockDetail && filters.macro_notrade_windows) {
    const w = filters.macro_notrade_windows[0];
    if (w) macroLockDetail.textContent = `${w.start}–${w.end} CEST · ${w.reason}`;
  }
}

/* ─── GUARDIAN ─── */

function renderGuardian(data) {
  const h = data.header || {};
  const r = data.risk || {};
  const effective = getEffectiveMode(h.daily_status || h.risk_mode, r.mode);

  const ring = document.getElementById('guardianRing');
  if (ring) ring.dataset.mode = effective;

  const msg = document.getElementById('bagiraMsg');
  if (!msg) return;

  const filters = data.notrade_filters || {};
  if (effective === 'RED') {
    msg.textContent = '"Piros nap. Nézd a piacot, ne játssz benne. Holnap is lesz lehetőség."';
    msg.style.color = 'var(--accent-red)';
  } else if (filters.macro_window_active) {
    const w = (filters.macro_notrade_windows || [])[0];
    msg.textContent = w
      ? `"Makró ablak aktív (${w.start}–${w.end} CEST). Várd ki, ne siess."`
      : '"Makró ablak aktív. Tiltási protokoll érvényes."';
    msg.style.color = 'var(--accent-amber)';
  } else if (effective === 'YELLOW') {
    msg.textContent = '"Sárga nap. Csak a legjobb setup, ≥8 score, 1 trade. Fókusz és türelem."';
    msg.style.color = 'var(--accent-amber)';
  } else {
    const setups = data.setups || {};
    const aOk = setups.A && setups.A.allowed;
    const bOk = setups.B && setups.B.allowed;
    if (aOk || bOk) {
      msg.textContent = `"${aOk ? 'Setup A' : 'Setup B'} ALLOWED. Score és RR teljesül. London session fókusz."`;
      msg.style.color = 'var(--accent-green)';
    } else {
      msg.textContent = '"Nincs ALLOWED setup most. No-trade döntés is helyes döntés."';
      msg.style.color = 'var(--accent-cyan)';
    }
  }
}

/* ─── SETUPS ─── */

function renderSetups(data) {
  renderSetupCard('A', data);
  renderSetupCard('B', data);

  const h = data.header || {};
  const r = data.risk || {};
  const effective = getEffectiveMode(h.daily_status || h.risk_mode, r.mode);
  const filters = data.notrade_filters || {};

  const chartSetup = document.getElementById('chartActiveSetup');
  if (chartSetup) chartSetup.textContent = safeGet(h.focus_setup ? `Setup ${h.focus_setup}` : null, 'nincs kijelölve');
  const chartSession = document.getElementById('chartSession');
  if (chartSession) chartSession.textContent = safeGet(h.preferred_session, 'London / Overlap');
  const chartMacroLock = document.getElementById('chartMacroLock');
  if (chartMacroLock) {
    const locked = !!filters.macro_window_active || effective === 'RED';
    chartMacroLock.textContent = locked ? 'LOCKED' : 'OK';
    chartMacroLock.dataset.status = locked ? 'RED' : 'GREEN';
  }
  const chartLastData = document.getElementById('chartLastData');
  if (chartLastData) chartLastData.textContent = safeGet((data.meta || {}).last_updated, '–');
}

function renderSetupCard(letter, data) {
  const setup = (data.setups || {})[letter] || {};
  const h = data.header || {};
  const r = data.risk || {};
  const filters = data.notrade_filters || {};
  const effective = getEffectiveMode(h.daily_status || h.risk_mode, r.mode);

  const requiredScore = effective === 'RED' ? 99 : effective === 'YELLOW' ? 8 : 6;
  const score = Number(setup.score || 0);
  const rr = Number(setup.rr_min || 0);

  const lockReasons = [];
  if (effective === 'RED') lockReasons.push('Effective mode RED – NO-TRADE');
  if (rr < 2 && rr > 0) lockReasons.push('RR < 1:2');
  if (score < requiredScore && requiredScore < 99) lockReasons.push(`Score ${score} < ${requiredScore}`);
  if (filters.macro_window_active) lockReasons.push('Makró ablak aktív');

  const isAllowed = lockReasons.length === 0 && !!setup.allowed;
  const dir = (setup.direction || '').toUpperCase();

  const dirEl = document.getElementById(`dirTag${letter}`);
  if (dirEl) {
    dirEl.textContent = dir || '–';
    dirEl.className = `dir-tag ${dir === 'LONG' ? 'long' : dir === 'SHORT' ? 'short' : ''}`;
  }
  const typeEl = document.getElementById(`type${letter}`);
  if (typeEl) typeEl.textContent = safeGet(setup.type, 'n/a');

  const lb = document.getElementById(`lockBadge${letter}`);
  if (lb) {
    lb.textContent = isAllowed ? 'ALLOWED' : 'LOCKED';
    lb.dataset.state = isAllowed ? 'ALLOWED' : 'LOCKED';
  }

  const scoreEl = document.getElementById(`score${letter}`);
  if (scoreEl) scoreEl.textContent = score || '–';
  const reqEl = document.getElementById(`req${letter}`);
  if (reqEl) reqEl.textContent = requiredScore < 99 ? `${requiredScore}/10 req` : 'LOCKED';
  const rrEl = document.getElementById(`rr${letter}`);
  if (rrEl) rrEl.textContent = rr ? `1:${rr.toFixed(1)}` : '–';

  const barEl = document.getElementById(`scoreBar${letter}`);
  if (barEl) barEl.style.width = `${Math.min(100, score * 10)}%`;

  const setEl = (id, val, fallback='–') => { const e = document.getElementById(id); if(e) e.textContent = safeGet(val, fallback); };
  setEl(`entry${letter}`, setup.entry_zone);
  setEl(`sl${letter}`, setup.sl);
  setEl(`tp1${letter}`, setup.tp1);
  setEl(`tp2${letter}`, setup.tp2 !== null ? setup.tp2 : null);

  const thesisEl = document.getElementById(`thesis${letter}`);
  if (thesisEl) {
    const bullets = (setup.thesis || []).slice(0,3);
    thesisEl.innerHTML = bullets.length
      ? `<ul>${bullets.map(b => `<li>${b}</li>`).join('')}</ul>`
      : '';
  }

  const metaEl = document.getElementById(`meta${letter}`);
  if (metaEl) {
    metaEl.textContent = lockReasons.length
      ? lockReasons.join(' · ')
      : (setup.locked_reason || '');
    metaEl.style.color = isAllowed ? 'var(--accent-green)' : 'var(--accent-red)';
  }

  const card = document.getElementById(`setupCard${letter}`);
  if (card) {
    card.style.borderColor = isAllowed
      ? 'rgba(34,197,94,0.3)'
      : 'rgba(239,68,68,0.15)';
  }
}

/* ─── TELEMETRY ─── */

function renderTelemetry(data) {
  const macro = data.macro || {};
  const grid = document.getElementById('teleGrid');
  if (!grid) return;
  grid.innerHTML = '';

  const defs = [
    { key:'fedwatch',        label:'FedWatch' },
    { key:'us10y',           label:'US10Y' },
    { key:'dxy',             label:'DXY' },
    { key:'sentiment',       label:'Sentiment' },
    { key:'htf_trend',       label:'HTF Trend' },
    { key:'intraday_regime', label:'Intraday' },
  ];

  defs.forEach(def => {
    const item = macro[def.key];
    const val = typeof item === 'object' && item !== null ? item.value : item;
    const bias = typeof item === 'object' && item !== null ? (item.bias || 'NEUTRAL') : 'NEUTRAL';
    const meta = typeof item === 'object' && item !== null ? item.updated_at : '';

    const tile = document.createElement('div');
    tile.className = 'tele-tile';
    tile.innerHTML = `
      <span class="tele-tile-label">${def.label}</span>
      <span class="tele-tile-val" data-bias="${(bias||'NEUTRAL').toUpperCase()}">${safeGet(val,'n/a')}</span>
      ${meta ? `<span class="tele-tile-meta">${meta}</span>` : ''}
    `;
    grid.appendChild(tile);
  });

  const sync = document.getElementById('teleSync');
  if (sync) sync.textContent = safeGet((data.meta||{}).last_updated, '–');
}

/* ─── MACRO TILES ─── */

function renderMacro(data) {
  const macro = data.macro || {};
  const tilesEl = document.getElementById('macroTiles');
  if (!tilesEl) return;
  tilesEl.innerHTML = '';

  const defs = [
    { key:'fedwatch',        label:'FedWatch' },
    { key:'us10y',           label:'US10Y' },
    { key:'dxy',             label:'DXY' },
    { key:'sentiment',       label:'Sentiment' },
    { key:'htf_trend',       label:'HTF Trend' },
    { key:'intraday_regime', label:'Intraday' },
    { key:'volatility',      label:'Volatility' },
  ];

  defs.forEach(def => {
    const item = macro[def.key];
    const val = typeof item === 'object' && item !== null ? item.value : item;
    const bias = typeof item === 'object' && item !== null ? (item.bias || 'NEUTRAL') : 'NEUTRAL';
    const src  = typeof item === 'object' && item !== null ? item.source_label : '';
    const upd  = typeof item === 'object' && item !== null ? item.updated_at : '';

    const tile = document.createElement('div');
    tile.className = 'macro-tile';
    tile.innerHTML = `
      <div class="macro-tile__title">
        <span>${def.label}</span>
        <span class="pill" data-status="${(bias||'NEUTRAL').toUpperCase()}">${safeGet(val,'n/a')}</span>
      </div>
      <div class="macro-tile__meta">${src ? src : ''}${upd ? ` · ${upd}` : ''}</div>
    `;
    tilesEl.appendChild(tile);
  });

  const upd = document.getElementById('macroUpdateTime');
  if (upd) upd.textContent = safeGet((data.meta||{}).last_updated, '–');
}

/* ─── LEVELS ─── */

function renderLevels(data) {
  const lv = data.levels || {};
  const tbody = document.getElementById('levelsBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const defs = [
    { key:'pdh',        label:'PDH' },
    { key:'pdl',        label:'PDL' },
    { key:'daily_open', label:'Daily Open' },
    { key:'asia_high',  label:'Asia High' },
    { key:'asia_low',   label:'Asia Low' },
    { key:'htf_level',  label:'HTF Level' },
  ];

  defs.forEach(def => {
    const v = lv[def.key];
    if (v === null || v === undefined) return;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${def.label}</td><td>${v}</td><td>–</td>`;
    tbody.appendChild(tr);
  });

  const status = document.getElementById('levelsStatus');
  if (status) status.textContent = tbody.children.length ? 'OK' : 'Hiányzó szintek';
}

/* ─── MACRO EVENTS ─── */

function renderMacroEvents(data) {
  const filters = data.notrade_filters || {};
  const list = document.getElementById('macroEventsList');
  if (!list) return;
  list.innerHTML = '';

  const events = filters.macro_events_today || [];
  if (!events.length) {
    list.innerHTML = '<div style="font-size:10px;color:var(--text-faint);padding:4px 0">Nincs HIGH impact esemény ma.</div>';
    return;
  }
  events.forEach(ev => {
    const el = document.createElement('div');
    el.className = 'macro-event';
    el.innerHTML = `
      <span class="ev-time">${safeGet(ev.time_cest)}</span>
      <span class="ev-name"> · ${safeGet(ev.event)}</span>
      <span class="ev-dir"> · ${safeGet(ev.direction,'–')}</span>
    `;
    list.appendChild(el);
  });

  const windows = filters.macro_notrade_windows || [];
  windows.forEach(w => {
    const el = document.createElement('div');
    el.className = 'macro-event';
    el.style.borderColor = 'rgba(239,68,68,0.4)';
    el.style.background = 'rgba(239,68,68,0.08)';
    el.innerHTML = `<span class="ev-time">⛔ ${w.start}–${w.end}</span><span class="ev-dir"> · ${w.reason}</span>`;
    list.appendChild(el);
  });
}

/* ─── RISK ─── */

function renderRisk(data) {
  const r = data.risk || {};
  const h = data.header || {};
  const effective = getEffectiveMode(h.daily_status || h.risk_mode, r.mode);

  const modeTag = document.getElementById('riskModeTag');
  if (modeTag) { modeTag.textContent = effective; modeTag.dataset.mode = effective; }

  const dailyLoss = r.daily_loss || 0;
  const weeklyLoss = r.weekly_loss || 0;
  const dailyLimit = r.daily_limit || 100;
  const weeklyLimit = r.weekly_limit || 300;

  const dailyPL = document.getElementById('rDailyPL');
  if (dailyPL) {
    dailyPL.textContent = `$${Number(dailyLoss).toFixed(2)}`;
    dailyPL.style.color = dailyLoss < 0 ? 'var(--accent-red)' : dailyLoss > 0 ? 'var(--accent-green)' : 'var(--text-muted)';
  }
  const dailyText = document.getElementById('rDailyLimitText');
  if (dailyText) dailyText.textContent = `$${Math.abs(dailyLoss).toFixed(0)} / $${dailyLimit}`;
  const dailyBar = document.getElementById('rDailyBar');
  if (dailyBar) dailyBar.style.width = `${pct(dailyLoss, dailyLimit).toFixed(0)}%`;

  const weeklyPL = document.getElementById('rWeeklyPL');
  if (weeklyPL) {
    weeklyPL.textContent = `$${Number(weeklyLoss).toFixed(2)}`;
    weeklyPL.style.color = weeklyLoss < 0 ? 'var(--accent-red)' : weeklyLoss > 0 ? 'var(--accent-green)' : 'var(--text-muted)';
  }
  const weeklyText = document.getElementById('rWeeklyLimitText');
  if (weeklyText) weeklyText.textContent = `$${Math.abs(weeklyLoss).toFixed(0)} / $${weeklyLimit}`;
  const weeklyBar = document.getElementById('rWeeklyBar');
  if (weeklyBar) weeklyBar.style.width = `${pct(weeklyLoss, weeklyLimit).toFixed(0)}%`;

  const streak = document.getElementById('rStreak');
  if (streak) {
    streak.textContent = safeGet(r.loss_streak, 0);
    streak.style.color = (r.loss_streak || 0) >= 3 ? 'var(--accent-red)' : 'var(--text)';
  }
  const openPos = document.getElementById('rOpenPos');
  if (openPos) openPos.textContent = safeGet(r.open_positions, 0);
  const maxTrades = document.getElementById('rMaxTrades');
  if (maxTrades) maxTrades.textContent = safeGet(r.max_trades_today, '–');
  const xauOpen = document.getElementById('rXauOpen');
  if (xauOpen) xauOpen.textContent = safeGet(r.open_xau_positions, 0);

  const note = document.getElementById('riskNote');
  if (note) note.textContent = safeGet(r.trade_allowed_reason, effective === 'RED' ? 'NO-TRADE nap.' : effective === 'YELLOW' ? 'YELLOW mód – csökkentett kockázat.' : 'GREEN – szabályos kereskedés engedélyezett.');

  /* ══════════════════════════════════════════════
     HARD LOCK OVERLAY — dismiss / restore logika
     ══════════════════════════════════════════════ */
  const overlay      = document.getElementById('hardLockOverlay');
  const lockReason   = document.getElementById('lockoutReason');
  const dismissBtn   = document.getElementById('lockoutDismiss');
  const restoreBadge = document.getElementById('lockRestoreBadge');
  const filters      = data.notrade_filters || {};

  const hardLockReasons = [];
  if (effective === 'RED') hardLockReasons.push('Effective mode RED — NO-TRADE nap.');
  if (Math.abs(dailyLoss) >= dailyLimit) hardLockReasons.push(`Napi limit elérve: $${Math.abs(dailyLoss).toFixed(2)} / $${dailyLimit}.`);
  if (Math.abs(weeklyLoss) >= weeklyLimit) hardLockReasons.push(`Heti limit elérve: $${Math.abs(weeklyLoss).toFixed(2)} / $${weeklyLimit}.`);
  if ((r.loss_streak || 0) >= 3) hardLockReasons.push('3 egymás utáni vesztes trade — 2 nap szünet szabály aktív.');
  if (filters.macro_window_active) hardLockReasons.push('Makró tiltási ablak aktív — 60 perces XAU stop.');

  const isHardLocked = hardLockReasons.length > 0;

  if (lockReason) lockReason.textContent = hardLockReasons.join(' | ');

  // Csak akkor mutassuk az overlayt, ha még nem nyomták le a dismiss-t
  // (session-szintű flag, nem perzisztált)
  if (overlay) {
    const alreadyDismissed = overlay.dataset.dismissed === '1';
    overlay.classList.toggle('hidden', !isHardLocked || alreadyDismissed);
  }

  // Restore badge: látható ha van lock ÉS dismiss-elve van
  if (restoreBadge) {
    const alreadyDismissed = overlay ? overlay.dataset.dismissed === '1' : false;
    restoreBadge.classList.toggle('hidden', !isHardLocked || !alreadyDismissed);
  }

  // Dismiss gomb — overlay bezárása, restore badge megjelenítése
  if (dismissBtn && !dismissBtn._bound) {
    dismissBtn._bound = true;
    dismissBtn.addEventListener('click', () => {
      if (overlay) {
        overlay.dataset.dismissed = '1';
        overlay.classList.add('hidden');
      }
      if (restoreBadge) restoreBadge.classList.remove('hidden');
    });
  }

  // Restore badge — overlay visszahozása
  if (restoreBadge && !restoreBadge._bound) {
    restoreBadge._bound = true;
    restoreBadge.addEventListener('click', () => {
      if (overlay) {
        overlay.dataset.dismissed = '0';
        overlay.classList.remove('hidden');
      }
      restoreBadge.classList.add('hidden');
    });
  }
}

/* ─── EXECUTION ─── */

function renderExecution(data) {
  const r = data.risk || {};
  const h = data.header || {};
  const filters = data.notrade_filters || {};
  const effective = getEffectiveMode(h.daily_status || h.risk_mode, r.mode);

  const execModeTag = document.getElementById('execModeTag');
  if (execModeTag) { execModeTag.textContent = `V1 · ${effective}`; execModeTag.dataset.mode = effective; }

  const tradeOk = document.getElementById('execTradeAllowed');
  if (tradeOk) {
    tradeOk.textContent = r.trade_allowed_now ? 'IGEN' : 'NEM';
    tradeOk.style.color = r.trade_allowed_now ? 'var(--accent-green)' : 'var(--accent-red)';
  }
  const xauOk = document.getElementById('execXauAllowed');
  if (xauOk) {
    xauOk.textContent = r.xau_trade_allowed_now ? 'IGEN' : 'NEM';
    xauOk.style.color = r.xau_trade_allowed_now ? 'var(--accent-green)' : 'var(--accent-red)';
  }
  const openPos = document.getElementById('execOpenPos');
  if (openPos) openPos.textContent = safeGet(r.open_positions, 0);
  const maxTrades = document.getElementById('execMaxTrades');
  if (maxTrades) maxTrades.textContent = safeGet(r.max_trades_today, '–');

  const reasonEl = document.getElementById('execReason');
  if (reasonEl) reasonEl.textContent = safeGet(r.trade_allowed_reason, '–');

  const windowsEl = document.getElementById('execNoTradeWindows');
  if (windowsEl) {
    windowsEl.innerHTML = '';
    (filters.macro_notrade_windows || []).forEach(w => {
      const el = document.createElement('div');
      el.className = 'notrade-window-item';
      el.textContent = `⛔ ${w.start}–${w.end} CEST · ${w.reason}`;
      windowsEl.appendChild(el);
    });
  }
}

/* ─── TRADE LOG ─── */

function renderTradeLog(data) {
  const trades = data.trade_log || data.trades || [];
  const tbody = document.getElementById('tradeLogBody');
  if (!tbody) return;
  tbody.innerHTML = '';

  const countTag = document.getElementById('tradeCountTag');
  if (countTag) countTag.textContent = `${trades.length} trade`;

  if (!trades.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-log">Még nincs lezárt trade ma.</td></tr>';
    document.getElementById('tlNetPL') && (document.getElementById('tlNetPL').textContent = '$0.00');
    document.getElementById('tlAvgRR') && (document.getElementById('tlAvgRR').textContent = '–');
    document.getElementById('tlWinPct') && (document.getElementById('tlWinPct').textContent = '–');
    document.getElementById('tlRuleAdh') && (document.getElementById('tlRuleAdh').textContent = '–');
    return;
  }

  let netPL = 0, sumRR = 0, rrCnt = 0, wins = 0, ruleOk = 0;
  trades.forEach(tr => {
    netPL += tr.pl_usd || 0;
    if (tr.rr_actual !== undefined && tr.rr_actual !== null) { sumRR += tr.rr_actual; rrCnt++; }
    if ((tr.pl_usd || 0) > 0) wins++;
    if (tr.rule_ok) ruleOk++;

    const dirStyle = (tr.direction||'').toUpperCase() === 'LONG' ? 'color:var(--accent-green)' : 'color:var(--accent-red)';
    const plColor = (tr.pl_usd || 0) >= 0 ? 'color:var(--accent-green)' : 'color:var(--accent-red)';
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${safeGet(tr.time,'')}</td>
      <td style="${dirStyle}">${safeGet(tr.direction,'')}</td>
      <td style="${plColor}">${Number(tr.pl_usd||0).toFixed(2)}</td>
      <td>${tr.rr_actual !== undefined ? Number(tr.rr_actual).toFixed(2) : '–'}</td>
      <td><span class="${tr.rule_ok?'badge--ok':'badge--violation'}">${tr.rule_ok?'OK':'Viol'}</span></td>
    `;
    tbody.appendChild(row);
  });

  const n = trades.length;
  document.getElementById('tlNetPL') && (document.getElementById('tlNetPL').textContent = `$${netPL.toFixed(2)}`);
  document.getElementById('tlAvgRR') && (document.getElementById('tlAvgRR').textContent = rrCnt ? (sumRR/rrCnt).toFixed(2) : '–');
  document.getElementById('tlWinPct') && (document.getElementById('tlWinPct').textContent = n ? `${((wins/n)*100).toFixed(0)}%` : '–');
  document.getElementById('tlRuleAdh') && (document.getElementById('tlRuleAdh').textContent = n ? `${((ruleOk/n)*100).toFixed(0)}%` : '–');
}

/* ─── INIT ─── */
document.addEventListener('DOMContentLoaded', loadData);
