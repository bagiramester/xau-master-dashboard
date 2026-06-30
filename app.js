/* XAU Master Dashboard v2 – app.js
   Betölti a data.json-t és frissíti az összes UI elemet.
   Kompatibilis a GitHub Pages statikus hosztolással. */

(function () {
  'use strict';

  const DATA_URL = './data.json';
  const REFRESH_INTERVAL_MS = 120000; // 2 min

  // ─── Helpers ───────────────────────────────────────────────────────────────
  function el(id) { return document.getElementById(id); }

  function setClass(element, cls, condition) {
    if (!element) return;
    element.classList.toggle(cls, !!condition);
  }

  function fmt(v, fallback = '—') {
    return (v !== null && v !== undefined && v !== '') ? v : fallback;
  }

  function setBadgeState(element, state) {
    if (!element) return;
    element.className = element.className.replace(/state--\w+/g, '').trim();
    if (state) element.classList.add('state--' + state.toLowerCase());
  }

  // ─── Clock & Session ───────────────────────────────────────────────────────
  function updateClock() {
    const now = new Date();
    const opts = { timeZone: 'Europe/Budapest', year: 'numeric', month: '2-digit', day: '2-digit' };
    const dateStr = now.toLocaleDateString('hu-HU', opts).replace(/\./g, '.').replace(/\s/g, '');
    const h = now.toLocaleString('hu-HU', { timeZone: 'Europe/Budapest', hour: '2-digit', minute: '2-digit', hour12: false });

    const dateEl = el('currentDate');
    const dateCenterEl = el('dateCenterLabel');
    if (dateEl) dateEl.textContent = dateStr + ' - ' + h + ' CEST';
    if (dateCenterEl) dateCenterEl.textContent = dateStr + '.';

    // Session detection (CEST = UTC+2)
    const utcH = now.getUTCHours();
    const cestH = (utcH + 2) % 24;
    const sessionEl = el('sessionLabel');
    if (sessionEl) {
      if (cestH >= 9 && cestH < 12) {
        sessionEl.textContent = '● London Session';
        sessionEl.style.color = 'var(--green)';
      } else if (cestH >= 14 && cestH < 19) {
        sessionEl.textContent = '● London–NY Overlap';
        sessionEl.style.color = 'var(--teal)';
      } else if (cestH >= 3 && cestH < 9) {
        sessionEl.textContent = '● Asian Session';
        sessionEl.style.color = 'var(--text-muted)';
      } else {
        sessionEl.textContent = '○ Off Session';
        sessionEl.style.color = 'var(--text-faint)';
      }
    }
  }

  // ─── Countdown ─────────────────────────────────────────────────────────────
  let refreshSecondsLeft = 120;
  function updateRefreshCountdown() {
    refreshSecondsLeft--;
    if (refreshSecondsLeft <= 0) refreshSecondsLeft = 120;
    const mins = Math.floor(refreshSecondsLeft / 60);
    const secs = refreshSecondsLeft % 60;
    const el = document.getElementById('refreshCountdown');
    if (el) el.textContent = 'Next scheduled refresh: ' + (mins > 0 ? mins + ' min ' : '') + secs + ' sec';
  }

  // ─── Macro Cell color mapping ───────────────────────────────────────────────
  const BIAS_TO_STATE = { GREEN: 'green', YELLOW: 'yellow', RED: 'red' };

  function applyMacroCell(cellId, bias) {
    const c = el(cellId);
    if (!c) return;
    ['state--green', 'state--yellow', 'state--red'].forEach(cls => c.classList.remove(cls));
    const state = BIAS_TO_STATE[bias];
    if (state) c.classList.add('state--' + state);
  }

  // ─── Effective Mode ─────────────────────────────────────────────────────────
  function applyEffectiveMode(label) {
    const g = el('emGreen'), y = el('emYellow'), r = el('emRed');
    [g, y, r].forEach(e => { if (e) e.style.opacity = '0.25'; });
    if (label === 'GREEN' && g) g.style.opacity = '1';
    else if (label === 'YELLOW' && y) y.style.opacity = '1';
    else if (label === 'RED' && r) r.style.opacity = '1';
  }

  // ─── Setup cards ────────────────────────────────────────────────────────────
  function applySetup(prefix, setup) {
    if (!setup) return;
    const dirEl = el(prefix + 'Dir');
    const lockEl = el(prefix + 'Lock');
    const cardEl = el(prefix.replace('setup', 'setup'));

    if (dirEl) {
      dirEl.textContent = setup.direction || '—';
      dirEl.className = 'badge ' + (setup.direction === 'LONG' ? 'badge--green' : 'badge--red');
    }
    if (lockEl) {
      if (setup.allowed === false) {
        lockEl.textContent = '🔒 LOCKED';
        lockEl.style.color = 'var(--red)';
      } else {
        lockEl.textContent = '✓ ALLOWED';
        lockEl.style.color = 'var(--green)';
      }
    }
  }

  // ─── Risk bars ───────────────────────────────────────────────────────────────
  function applyRisk(risk) {
    if (!risk) return;
    const dailyPct = Math.min(100, Math.abs((risk.dailyloss || 0) / 100 * 100));
    const weeklyPct = Math.min(100, Math.abs((risk.weeklyloss || 0) / 300 * 100));
    const dFill = el('dailyFill');
    const wFill = el('weeklyFill');
    if (dFill) dFill.style.width = dailyPct + '%';
    if (wFill) wFill.style.width = weeklyPct + '%';

    const rLivePL = el('riskLivePL');
    const rStreak = el('riskLossStreak');
    if (rLivePL) rLivePL.textContent = fmt(risk.dailyloss, '0.00');
    if (rStreak) rStreak.textContent = fmt(risk.lossstreak, '0');

    // mode pill
    const pill = el('riskModePill');
    if (pill && risk.mode) {
      pill.className = 'risk-mode-pill';
      if (risk.mode === 'GREEN')  pill.style.setProperty('background', 'var(--green-dim)');
      else if (risk.mode === 'YELLOW') pill.style.setProperty('background', 'var(--yellow-dim)');
      else if (risk.mode === 'RED')    pill.style.setProperty('background', 'var(--red-dim)');
      const titleEl = pill.querySelector('.risk-mode-pill__title');
      if (titleEl) {
        titleEl.textContent = risk.mode + ' Mode';
        titleEl.style.color = risk.mode === 'GREEN' ? 'var(--green)' : risk.mode === 'RED' ? 'var(--red)' : 'var(--yellow)';
      }
    }

    const maxG = el('tAllowGreen');
    const maxY = el('tAllowYellow');
    const maxR = el('tAllowRed');
    const max = risk.maxtradestoday || 2;
    if (maxG) maxG.textContent = risk.mode === 'GREEN' ? max : (risk.mode === 'YELLOW' ? 0 : 0);
    if (maxY) maxY.textContent = risk.mode === 'YELLOW' ? max : 0;
    if (maxR) maxR.textContent = risk.mode === 'RED' ? max : 0;
  }

  // ─── Trade log ───────────────────────────────────────────────────────────────
  function applyTrades(trades, performance) {
    const tbody = el('tradeTableBody');
    if (!tbody) return;
    if (!trades || trades.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-faint)">Nincs lezárt trade ma</td></tr>';
    } else {
      tbody.innerHTML = trades.map(t => {
        const side = (t.direction || '').toLowerCase();
        const sideClass = side === 'long' ? 'td-long' : 'td-short';
        const rule = t.ruleadherence === 'igen' ? '<span class="td-ok">RULE OK</span>' : '<span class="td-violation">VIOLATION !</span>';
        return `<tr>
          <td>${fmt(t.time)}</td>
          <td class="${sideClass}">${fmt(t.direction)}</td>
          <td>${fmt(t.type, 'Trade')}</td>
          <td>${fmt(t.rr)}</td>
          <td>${fmt(t.plusd, '0.00')}</td>
          <td>${rule}</td>
        </tr>`;
      }).join('');
    }
    if (performance) {
      const tlTotal = el('tlTotal');
      const tlNetPL = el('tlNetPL');
      const tlAvgRR = el('tlAvgRR');
      const tlRule  = el('tlRule');
      if (tlTotal) tlTotal.textContent = (performance.tradecount || 0) + '/2';
      if (tlNetPL) {
        tlNetPL.textContent = (performance.netplusd >= 0 ? '+' : '') + fmt(performance.netplusd, '0.00');
        tlNetPL.className = performance.netplusd >= 0 ? 'text-green' : 'text-red';
      }
      if (tlAvgRR) tlAvgRR.textContent = fmt(performance.avgrr);
      if (tlRule) {
        const total = performance.tradecount || 1;
        const breaks = performance.rulebreakcount || 0;
        tlRule.textContent = Math.round(((total - breaks) / total) * 100) + '%';
      }
    }
  }

  // ─── Header narrative ────────────────────────────────────────────────────────
  function applyHeader(header) {
    if (!header) return;
    const nt = el('narrativeText');
    if (nt && header.narrative) nt.innerHTML = `Bias: <strong>${header.biasdirection || '—'}</strong> | ${header.narrative}`;

    // No-trade window countdown
    const ntcd = el('noTradeCountdown');
    if (ntcd) {
      if (header.macrolockactive && header.macronotradewindows && header.macronotradewindows.length > 0) {
        const w = header.macronotradewindows[0];
        ntcd.innerHTML = `TILTÁS: <strong id="countdownMin">${w.reason || 'Makró'}</strong>`;
      } else {
        ntcd.innerHTML = '<strong>Nincs aktív tiltás</strong>';
        ntcd.style.color = 'var(--green)';
      }
    }

    // Today status pills
    const pillOk = el('pillTradeOk');
    const pillNo = el('pillNoTrade');
    const status = (header.dailystatus || 'GREEN').toUpperCase();
    if (pillOk && pillNo) {
      if (status === 'RED') {
        pillOk.style.opacity = '0.3';
        pillNo.style.opacity = '1';
      } else {
        pillOk.style.opacity = '1';
        pillNo.style.opacity = '0.3';
      }
    }
  }

  // ─── Key levels ──────────────────────────────────────────────────────────────
  function applyKeyLevels(kl) {
    if (!kl) return;
    const entries = Object.entries(kl).slice(0, 4);
    const rows = ['kl1','kl2','kl3','kl4'];
    entries.forEach(([key, val], i) => {
      const row = el(rows[i]);
      if (!row) return;
      const labelEl = row.querySelector('.kl-label');
      const statusEl = row.querySelector('.kl-status');
      if (labelEl) labelEl.textContent = `[${key} - ${fmt(val.value, 'pending')}]`;
      if (statusEl) {
        const s = (val.status || 'pending').toLowerCase();
        statusEl.className = 'kl-status ' + (s === 'fresh' ? '' : 'kl-status--stale');
        statusEl.textContent = s === 'fresh' ? '[ FRESH ]' : '[ STALE - Review Needed ]';
      }
    });
  }

  // ─── Bagira speech ────────────────────────────────────────────────────────────
  function updateBagiraSpeech(data) {
    const bubble = el('bagiruBubble');
    const grid   = el('bagiraGridSpeech');
    if (!data) return;
    const em = (data.effectivemodelabel || 'GREEN').toUpperCase();
    const allowed = data.setups && (data.setups.A && data.setups.A.allowed || data.setups.B && data.setups.B.allowed);
    let msg = '';
    if (em === 'RED') msg = 'Effective Mode: RED. Nincs trade ma. Risk limit aktív.';
    else if (em === 'YELLOW') msg = 'Effective Mode: YELLOW. Csak trend-irányú sweep engedélyezett.';
    else msg = 'Effective Mode: GREEN. Minden megfelelő setup nyitható ≥6/10 score esetén.';
    if (bubble) bubble.innerHTML = `<strong>Bagira Virtual Assistant</strong><br>${msg}`;
    if (grid) grid.textContent = allowed ? '"Engedélyezett setup van. Várd a belépőt."' : '"Kockázat korlátozva. Maximum 1 trade engedélyezett mára."';
  }

  // ─── Main render ─────────────────────────────────────────────────────────────
  function render(data) {
    if (!data) return;
    applyEffectiveMode(data.effectivemodelabel || 'GREEN');
    applyHeader(data.header);
    if (data.macro) {
      applyMacroCell('mFedwatch',  data.macro.fedwatch  && data.macro.fedwatch.bias);
      applyMacroCell('mDxy',       data.macro.dxy        && data.macro.dxy.bias);
      applyMacroCell('mSentiment', data.macro.sentiment  && data.macro.sentiment.bias);
      applyMacroCell('mHtfTrend',  data.macro.htftrend   && data.macro.htftrend.bias);
      applyMacroCell('mHtfTrend2', data.macro.htftrend   && data.macro.htftrend.bias);
      applyMacroCell('mIntraday',  data.macro.intradayregime && data.macro.intradayregime.bias);
      applyMacroCell('mVolatility',data.macro.volatility  && data.macro.volatility.bias);
    }
    applyKeyLevels(data.keylevels);
    applyRisk(data.risk);
    if (data.setups) {
      applySetup('setupA', data.setups.A);
      applySetup('setupB', data.setups.B);
    }
    applyTrades(data.trades, data.performance);
    updateBagiraSpeech(data);
  }

  // ─── Fetch data ──────────────────────────────────────────────────────────────
  function fetchData() {
    fetch(DATA_URL + '?t=' + Date.now())
      .then(r => r.json())
      .then(data => {
        render(data);
        refreshSecondsLeft = 120;
      })
      .catch(err => console.warn('data.json fetch error:', err));
  }

  // ─── Init ────────────────────────────────────────────────────────────────────
  function init() {
    updateClock();
    fetchData();
    setInterval(updateClock, 1000);
    setInterval(updateRefreshCountdown, 1000);
    setInterval(fetchData, REFRESH_INTERVAL_MS);
  }

  document.addEventListener('DOMContentLoaded', init);

})();
