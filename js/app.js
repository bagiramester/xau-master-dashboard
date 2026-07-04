// ═══ BAGIRA AI ADVISORY MODULE + APP ORCHESTRATION ═══
// A bal oszlop tetején: 🐆 mascot + narrative + confidence + key_watch
// Manuális AI trigger gomb — GitHub Actions workflow_dispatch PAT-tal.
//
// BETÖLTÉSI SORREND (index.html): ... js/tradelog.js  ->  js/app.js
// (a submitTradeLog a tradelog.js-ben van, ezért annak az app.js ELŐTT kell lennie)

const GITHUB_OWNER = 'bagiramester';
const GITHUB_REPO = 'xau-master-dashboard';
const AI_WORKFLOW_FILE = 'ai-refresh.yml';
const PAT_STORAGE_KEY = 'bagira_gh_pat';

const renderBagira = (data) => {
  const host = $('#bagira-panel');
  if (!host) return;
  const b = data.bagira || {};
  host.innerHTML = '';

  const modelBadge = (b.source_type === 'ai') ? '🤖 LIVE'
                    : (b.source_type === 'ai-mock') ? '🎭 MOCK'
                    : (b.source_type === 'ai-fallback') ? '⚠ FALLBACK'
                    : '– N/A';
  const modelClass = (b.source_type === 'ai') ? 'ai-live'
                    : (b.source_type === 'ai-mock') ? 'ai-mock'
                    : 'ai-fallback';

  const conf = b.confidence ?? 0;
  const confColor = conf >= 75 ? 'var(--green)'
                  : conf >= 50 ? 'var(--yellow)'
                  : 'var(--red)';

  const updatedRel = b.updated_at ? fmtRelative(b.updated_at) : 'nincs adat';

  host.appendChild(el('div', { class: 'bagira-header' },
    el('div', { class: 'bagira-mascot' }, '🐆'),
    el('div', { class: 'bagira-title-wrap' },
      el('div', { class: 'bagira-title' }, 'BAGIRA'),
      el('div', { class: 'bagira-subtitle' }, 'AI Tanácsadó')
    ),
    el('div', { class: `bagira-model-badge ${modelClass}`, title: b.reasoning_summary || '' }, modelBadge)
  ));

  host.appendChild(el('div', { class: 'bagira-narrative' }, b.narrative || 'Nyomd meg az "Új elemzés" gombot Bagira aktiválásához.'));

  const confRow = el('div', { class: 'bagira-conf-row' },
    el('span', { class: 'bagira-conf-label' }, 'Confidence'),
    el('div', { class: 'bagira-conf-bar' },
      el('div', {
        class: 'bagira-conf-fill',
        style: `width: ${conf}%; background: ${confColor};`
      })
    ),
    el('span', { class: 'bagira-conf-value' }, `${conf}%`)
  );
  host.appendChild(confRow);

  if (b.key_watch && b.key_watch.length > 0) {
    const kw = el('div', { class: 'bagira-keywatch' },
      el('div', { class: 'bagira-keywatch-title' }, '🎯 KEY WATCH')
    );
    b.key_watch.forEach(item => {
      kw.appendChild(el('div', { class: 'bagira-keywatch-item' }, '• ' + item));
    });
    host.appendChild(kw);
  }

  host.appendChild(el('div', { class: 'bagira-footer' },
    el('span', { class: 'bagira-footer-item', title: b.reasoning_summary || '' },
      `Utolsó elemzés: ${updatedRel}`
    ),
    el('button', {
      class: 'bagira-refresh-btn',
      id: 'bagira-trigger-btn',
      title: 'Új AI elemzés indítása (Perplexity API)',
      onclick: triggerAiRefresh
    }, '🧠 Új elemzés')
  ));
};

// ═══ PAT KEZELÉS ═══
const getPat = () => {
  try { return localStorage.getItem(PAT_STORAGE_KEY) || ''; }
  catch { return ''; }
};
const setPat = (pat) => {
  try { localStorage.setItem(PAT_STORAGE_KEY, pat); return true; }
  catch { return false; }
};

const promptForPat = () => {
  const current = getPat();
  const msg = current
    ? 'GitHub PAT frissítése (üres = törlés). Guide a repo README-ben.\n\nJelenlegi: ' + current.substring(0, 8) + '...'
    : 'GitHub Personal Access Token beírása.\n\n' +
      'Szükséges scope: Actions (read+write) VAGY workflow (classic PAT).\n' +
      'Fine-grained: xau-master-dashboard repo → Actions: Read and write.\n\n' +
      'A token csak a te böngésződben tárolódik (localStorage), sose kerül a repóba.';
  const pat = prompt(msg, current);
  if (pat === null) return null; // cancelled
  setPat(pat.trim());
  return pat.trim();
};

// ═══ AI TRIGGER ═══
const triggerAiRefresh = async () => {
  const btn = $('#bagira-trigger-btn');
  const original = btn.textContent;

  let pat = getPat();
  if (!pat) {
    pat = promptForPat();
    if (!pat) return;
  }

  btn.disabled = true;
  btn.textContent = '⏳ Indítás...';

  try {
    const url = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/actions/workflows/${AI_WORKFLOW_FILE}/dispatches`;
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Accept': 'application/vnd.github+json',
        'Authorization': `Bearer ${pat}`,
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ref: 'main',
        inputs: { note: 'dashboard button ' + new Date().toISOString() }
      }),
    });

    if (res.status === 204) {
      btn.textContent = '✓ Fut... (~60 mp)';
      showBagiraStatus('AI elemzés fut a szerveren, 30–90 mp múlva frissül a dashboard.', 'success');
      try {
        const cr = await fetch(`https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/commits?path=data.json&per_page=1`, { headers: { 'Accept': 'application/vnd.github+json' } });
        if (cr.ok) { const cj = await cr.json(); window.__bagiraPreSha = cj[0]?.sha || ''; }
      } catch (e) { /* non-critical */ }
      setTimeout(() => pollForNewAiResult(0), 15000);
    } else if (res.status === 401) {
      showBagiraStatus('PAT érvénytelen. Frissítsd (kattints újra).', 'error');
      setPat('');
      btn.textContent = original;
      btn.disabled = false;
    } else if (res.status === 403) {
      showBagiraStatus('PAT-nek nincs Actions írási joga. Guide a README-ben.', 'error');
      btn.textContent = original;
      btn.disabled = false;
    } else if (res.status === 404) {
      showBagiraStatus('Workflow vagy repo nem található. Ellenőrizd a beállítást.', 'error');
      btn.textContent = original;
      btn.disabled = false;
    } else {
      const txt = await res.text();
      showBagiraStatus(`Hiba (HTTP ${res.status}): ${txt.substring(0,100)}`, 'error');
      btn.textContent = original;
      btn.disabled = false;
    }
  } catch (e) {
    showBagiraStatus('Hálózati hiba: ' + e.message, 'error');
    btn.textContent = original;
    btn.disabled = false;
  }
};

const pollForNewAiResult = async (attempt) => {
  const btn = $('#bagira-trigger-btn');
  if (attempt > 18) {
    if (btn) { btn.textContent = '🧠 Új elemzés'; btn.disabled = false; }
    showBagiraStatus('Az AI futás elhúzódott. A data.json valószínűleg frissült — töltsd újra az oldalt (Ctrl+Shift+R).', 'warning');
    return;
  }
  try {
    const cr = await fetch(`https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/commits?path=data.json&per_page=1`, { cache: 'no-store', headers: { 'Accept': 'application/vnd.github+json' } });
    if (cr.ok) {
      const cj = await cr.json();
      const newSha = cj[0]?.sha || '';
      const preSha = window.__bagiraPreSha || '';
      if (newSha && newSha !== preSha) {
        const rr = await fetch(`https://raw.githubusercontent.com/${GITHUB_OWNER}/${GITHUB_REPO}/${newSha}/data.json`, { cache: 'no-store', mode: 'cors' });
        if (rr.ok) {
          const data = await rr.json();
          const newUpdated = data?.bagira?.updated_at || '';
          const oldUpdated = (currentData?.bagira?.updated_at) || '';
          if (newUpdated && newUpdated !== oldUpdated) {
            currentData = data;
            render(data);
            showBagiraStatus('✓ Új Bagira elemzés érkezett.', 'success');
          } else {
            showBagiraStatus('✓ AI futás befejeződött (a tartalom nem változott).', 'success');
          }
          if (btn) { btn.textContent = '🧠 Új elemzés'; btn.disabled = false; }
          return;
        }
      }
    }
  } catch (e) { /* silent */ }
  setTimeout(() => pollForNewAiResult(attempt + 1), 10000);
};

const showBagiraStatus = (msg, level) => {
  const host = $('#bagira-panel');
  let statusEl = $('.bagira-status');
  if (!statusEl) {
    statusEl = el('div', { class: `bagira-status bagira-status--${level}` });
    host.appendChild(statusEl);
  } else {
    statusEl.className = `bagira-status bagira-status--${level}`;
  }
  statusEl.textContent = msg;
  setTimeout(() => { if (statusEl.parentNode) statusEl.remove(); }, 8000);
};

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

  // ── PATCH: régi alert() helyett a valódi data.json naplózás (tradelog.js) ──
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

// ═══ HYBRID REFRESH ═══
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
    console.log('[hybrid-refresh] Client live fallback sikeres:', price);
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
  $('#btn-refresh').addEventListener('click', refreshAllData);
  $('#hard-lock-close').addEventListener('click', () => {
    hardLockDismissed = true;
    $('#hard-lock').hidden = true;
  });
  load();
  setInterval(load, 5 * 60 * 1000);
});
