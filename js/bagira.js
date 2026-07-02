// ═══ BAGIRA AI ADVISORY MODULE ═══
// A bal oszlop tetején: 🐆 mascot + narrative + confidence + key_watch

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
    el('div', { class: `bagira-model-badge ${modelClass}` }, modelBadge)
  ));

  host.appendChild(el('div', { class: 'bagira-narrative' }, b.narrative || 'Elemzés folyamatban…'));

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
      title: 'AI elemzés újrafuttatása (csak dev / kézi trigger)',
      onclick: () => triggerAiRefresh()
    }, '↻ Új elemzés')
  ));
};

const triggerAiRefresh = () => {
  const btn = document.querySelector('.bagira-refresh-btn');
  if (btn) { btn.disabled = true; btn.textContent = 'Manuális AI trigger csak GitHub Actions-ből'; }
  // A GitHub Actions workflow_dispatch triggerelhető gh CLI-vel vagy web UI-ból.
  // Client oldalról nem indítható közvetlenül (secret védve).
  setTimeout(() => {
    if (btn) { btn.disabled = false; btn.textContent = '↻ Új elemzés'; }
  }, 3000);
};
