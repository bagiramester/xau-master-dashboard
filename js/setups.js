// ═══ SETUPS MODULE — fix SHORT + LONG kártyák AI state kezeléssel ═══
const FALLBACK_SETUP = {
  direction: 'NEUTRAL',
  type: '— (nincs setup adat)',
  entry_zone: '–',
  sl: '–',
  tp1: '–',
  tp2: null,
  rr_min: 0,
  score: 0,
  session: '–',
  invalidation: '–',
  macro_support: [],
  allowed: false,
  locked_reason: 'Nincs setup adat. Töltsd ki manuálisan.',
  confirmed: false,
  setup_quality: '–',
  bias_compatibility: '–'
};

// LocalStorage-alapú confirm tracking (a data.json-t nem tudjuk kliens oldalról írni)
const getConfirmed = (slotKey) => {
  try { return localStorage.getItem('confirm_' + slotKey) === '1'; }
  catch { return false; }
};
const setConfirmed = (slotKey, value) => {
  try { localStorage.setItem('confirm_' + slotKey, value ? '1' : '0'); }
  catch {}
};

const orderSetupsFixed = (setups) => {
  const A = (setups && setups.A && setups.A.value) || null;
  const B = (setups && setups.B && setups.B.value) || null;
  let short = null, long_ = null;
  // Direct match
  if (A && A.direction === 'SHORT') short = { key: 'A', body: A, wrap: setups.A };
  else if (A && A.direction === 'LONG') long_ = { key: 'A', body: A, wrap: setups.A };
  if (B && B.direction === 'SHORT') short = short || { key: 'B', body: B, wrap: setups.B };
  else if (B && B.direction === 'LONG') long_ = long_ || { key: 'B', body: B, wrap: setups.B };
  // Fallback: null direction esete— sorrend szerint az elso ures slotba
  if (A && !A.direction && !short) short = { key: 'A', body: {...A, direction: 'SHORT'}, wrap: setups.A };
  else if (A && !A.direction && !long_) long_ = { key: 'A', body: {...A, direction: 'LONG'}, wrap: setups.A };
  if (B && !B.direction && !long_) long_ = { key: 'B', body: {...B, direction: 'LONG'}, wrap: setups.B };
  else if (B && !B.direction && !short) short = { key: 'B', body: {...B, direction: 'SHORT'}, wrap: setups.B };
  return { short, long: long_ };
};

const getAiBadge = (wrap, isConfirmed) => {
  if (!wrap) return { text: '– EMPTY', cls: 'manual' };
  const st = wrap.ai_state;
  const src = wrap.source_type;
  const isAI = src && src.startsWith('ai');

  if (isConfirmed) return { text: '✓ CONFIRMED', cls: 'confirmed' };
  if (st === 'LOCKED' || !wrap.value?.allowed) return { text: '⛔ LOCKED', cls: 'locked' };
  if (isAI && st === 'SUGGESTED') return { text: '🤖 AI SUGGESTED', cls: 'suggested' };
  if (src === 'manual') return { text: '✏ MANUAL', cls: 'manual' };
  return { text: st || '–', cls: 'manual' };
};

const renderSetupCard = (slot /* 'short' | 'long' */, entry) => {
  const body = entry ? entry.body : { ...FALLBACK_SETUP, direction: slot.toUpperCase() };
  const wrap = entry ? entry.wrap : null;
  const slotKey = entry ? entry.key : slot;
  const isConfirmed = entry ? getConfirmed(slotKey) : false;

  const cardClass = `setup-card setup-card--${slot}` + (!body.allowed && !isConfirmed ? ' setup-card--locked' : '');
  const stateClass = (body.allowed || isConfirmed)
    ? 'setup-card__state--allowed'
    : (body.confirmed ? 'setup-card__state--watch' : 'setup-card__state--locked');
  const stateLabel = (body.allowed || isConfirmed) ? '✓ ALLOWED'
                    : (body.confirmed ? '◐ WATCH' : '⛔ LOCKED');
  const dirClass = slot === 'long' ? 'dir-long' : 'dir-short';
  const dirEmoji = slot === 'long' ? '🟢' : '🔴';
  const aiBadge = getAiBadge(wrap, isConfirmed);

  const macroSupport = body.macro_support && body.macro_support.length
    ? body.macro_support.slice(0, 3).map(m => `• ${m}`).join('\n')
    : null;

  const card = el('div', { class: cardClass, 'data-slot': slotKey },
    // AI state badge (jobb felső sarok)
    el('span', { class: `setup-card__ai-badge setup-card__ai-badge--${aiBadge.cls}` }, aiBadge.text),

    el('div', { class: 'setup-card__header' },
      el('span', { class: `setup-card__direction ${dirClass}` }, `${dirEmoji} ${body.direction}`),
      el('span', { class: `setup-card__state ${stateClass}` }, stateLabel)
    ),
    el('div', { class: 'setup-card__type' }, body.type),
    el('div', { class: 'setup-card__body' },
      el('span', { class: 'setup-card__label' }, 'Belépő'),
      el('span', { class: 'setup-card__value setup-card__value--entry' }, body.entry_zone || '–'),
      el('span', { class: 'setup-card__label' }, 'SL'),
      el('span', { class: 'setup-card__value setup-card__value--sl' }, body.sl || '–'),
      el('span', { class: 'setup-card__label' }, 'TP1'),
      el('span', { class: 'setup-card__value setup-card__value--tp' }, body.tp1 || '–'),
      body.tp2 ? el('span', { class: 'setup-card__label' }, 'TP2') : null,
      body.tp2 ? el('span', { class: 'setup-card__value setup-card__value--tp' }, body.tp2) : null,
      el('span', { class: 'setup-card__label' }, 'RR min'),
      el('span', { class: 'setup-card__value' }, body.rr_min ? String(body.rr_min) : '–'),
      el('span', { class: 'setup-card__label' }, 'Session'),
      el('span', { class: 'setup-card__value' }, body.session || '–'),
      el('span', { class: 'setup-card__label' }, 'Bias'),
      el('span', { class: 'setup-card__value' }, body.bias_compatibility || '–'),
      el('span', { class: 'setup-card__label' }, 'Invalid.'),
      el('span', { class: 'setup-card__value', style: 'font-size: 0.72rem;' }, body.invalidation || '–')
    ),
    el('div', { class: 'setup-card__score' },
      el('span', { class: 'setup-card__label' }, 'Score'),
      el('div', { class: 'score-bar' },
        el('div', { class: 'score-bar__fill', style: `width: ${(body.score||0)*10}%` })
      ),
      el('span', { class: 'score-value' }, `${body.score||0}/10`)
    )
  );

  // Makró support tooltip (info gomb)
  if (macroSupport) {
    const infoBtn = el('span', { class: 'info-btn', title: macroSupport }, 'i');
    infoBtn.addEventListener('mouseenter', (e) => showTip(e, 'Makró alapok:\n' + macroSupport));
    infoBtn.addEventListener('mousemove', (e) => showTip(e, 'Makró alapok:\n' + macroSupport));
    infoBtn.addEventListener('mouseleave', hideTip);
    card.querySelector('.setup-card__type').appendChild(infoBtn);
  }

  if (body.locked_reason) {
    card.appendChild(el('div', { class: 'setup-card__reason' }, body.locked_reason));
  }

  // Confirm gomb — csak AI SUGGESTED állapotnál látszik
  if (aiBadge.cls === 'suggested' && !isConfirmed) {
    const confirmBtn = el('button',
      { class: 'setup-card__confirm setup-card__confirm--suggested', type: 'button' },
      '✓ CONFIRM & TRADE');
    confirmBtn.addEventListener('click', () => {
      setConfirmed(slotKey, true);
      renderSetups(currentData || {});
    });
    card.appendChild(confirmBtn);
  } else if (isConfirmed) {
    const btn = el('button',
      { class: 'setup-card__confirm setup-card__confirm--confirmed', type: 'button' },
      '✓ CONFIRMED (klikk = visszavonás)');
    btn.addEventListener('click', () => {
      setConfirmed(slotKey, false);
      renderSetups(currentData || {});
    });
    card.appendChild(btn);
  }

  return card;
};

const renderSetups = (data) => {
  const host = $('#setup-container');
  host.innerHTML = '';
  const { short, long } = orderSetupsFixed(data.setups);
  host.appendChild(renderSetupCard('short', short));
  host.appendChild(renderSetupCard('long', long));
};
