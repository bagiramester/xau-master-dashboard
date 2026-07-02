// ═══ BAGIRA AI ADVISORY MODULE ═══
// A bal oszlop tetején: 🐆 mascot + narrative + confidence + key_watch
// Manuális AI trigger gomb — GitHub Actions workflow_dispatch PAT-tal.

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
      // sikeres dispatch
      btn.textContent = '✓ Fut... (~60 mp)';
      showBagiraStatus('AI elemzés fut a szerveren, 30–90 mp múlva frissül a dashboard.', 'success');
      // Poll: 20 mp múlva kezdjük nézni a data.json-t
      setTimeout(() => pollForNewAiResult(0), 20000);
    } else if (res.status === 401) {
      showBagiraStatus('PAT érvénytelen. Frissítsd (kattints újra).', 'error');
      setPat(''); // töröljük a rossz PAT-ot
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
  if (attempt > 15) {
    // 15 × 10 mp = 150 mp után feladjuk
    if (btn) { btn.textContent = '🧠 Új elemzés'; btn.disabled = false; }
    showBagiraStatus('Az AI futás elhúzódott. Próbáld pár perc múlva a dashboard frissítést.', 'warning');
    return;
  }
  const oldUpdated = (currentData?.bagira?.updated_at) || '';
  try {
    const res = await fetch(`data.json?t=${Date.now()}`, { cache: 'no-store' });
    if (res.ok) {
      const data = await res.json();
      const newUpdated = data?.bagira?.updated_at || '';
      if (newUpdated && newUpdated !== oldUpdated) {
        render(data);
        showBagiraStatus('✓ Új Bagira elemzés érkezett.', 'success');
        if (btn) { btn.textContent = '🧠 Új elemzés'; btn.disabled = false; }
        return;
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
