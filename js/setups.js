// ═══ SETUPS MODULE — fix SHORT + LONG kártyák AI state kezeléssel ═══
// Mindig 2 kártyát renderel (SHORT + LONG). Az `allowed` státusz a backend
// scoring/RR/mode logikájából jön — a kliens SOHA nem kényszerít engedélyt.
// Confirm state: memóriában tartva (NEM localStorage — sandbox-biztos).

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

// Memóriában tartott confirm state (NEM localStorage — sandbox-biztos)
const confirmState = {};
const getConfirmed = (slotKey) => confirmState[slotKey] === true;
const setConfirmed = (slotKey, value) => { confirmState[slotKey] = !!value; };

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
  // A SUGGESTED előrébb van, mint a LOCKED: az AI által javasolt setup akkor is
  // SUGGESTED jelvényt kap, ha az allowed még false (csak a chart-megerősítés
  // hiányzik — a CONFIRM & TRADE gomb így elérhető marad).
  if (isAI && st === 'SUGGESTED') return { text: '🤖 AI SUGGESTED', cls: 'suggested' };
  if (st === 'LOCKED' || !wrap.value?.allowed) return { text: '⛔ LOCKED', cls: 'locked' };
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
  const stateLabel = (body.allowed || isConfirmed) ? '✓ ENGEDÉLYEZETT'
                    : (body.confirmed ? '◐ FIGYEL' : '⛔ ZÁROLVA');
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

    // Belépő / SL / TP1 nagy kártyák
    el('div', { class: 'setup-card__levels' },
      el('div', { class: 'setup-level setup-level--entry' },
        el('span', { class: 'setup-level__label' }, 'Belépő zóna'),
        el('span', { class: 'setup-level__value' }, body.entry_zone || '–')
      ),
      el('div', { class: 'setup-level setup-level--sl' },
        el('span', { class: 'setup-level__label' }, 'SL (invalidáció)' ),
        el('span', { class: 'setup-level__value' }, body.sl || '–')
      ),
      el('div', { class: 'setup-level setup-level--tp' },
        el('span', { class: 'setup-level__label' }, 'TP1' ),
        el('span', { class: 'setup-level__value' }, body.tp1 || '–')
      )
    ),

    // Meta rács: RR, Session, Bias, TP2, Invalidáció
    el('div', { class: 'setup-card__meta' },
      el('div', { class: 'setup-card__meta-row' },
        el('span', { class: 'setup-card__meta-label' }, 'RR min'),
        el('span', { class: 'setup-card__meta-value' }, body.rr_min ? `${body.rr_min}R` : '–')
      ),
      el('div', { class: 'setup-card__meta-row' },
        el('span', { class: 'setup-card__meta-label' }, 'Session'),
        el('span', { class: 'setup-card__meta-value' }, body.session || '–')
      ),
      body.tp2 ? el('div', { class: 'setup-card__meta-row' },
        el('span', { class: 'setup-card__meta-label' }, 'TP2'),
        el('span', { class: 'setup-card__meta-value' }, body.tp2)
      ) : null,
      el('div', { class: 'setup-card__meta-row' },
        el('span', { class: 'setup-card__meta-label' }, 'Bias'),
        el('span', { class: 'setup-card__meta-value' }, body.bias_compatibility || '–')
      ),
      el('div', { class: 'setup-card__meta-row', style: 'grid-column: 1 / -1;' },
        el('span', { class: 'setup-card__meta-label' }, 'Invalidáció'),
        el('span', { class: 'setup-card__meta-value' }, body.invalidation || '–')
      )
    ),

    // Score sáv
    el('div', { class: 'setup-card__score' },
      el('span', { class: 'setup-card__meta-label' }, 'Score'),
      el('div', { class: 'score-bar' },
        el('div', { class: 'score-bar__fill', style: `width: ${(body.score||0)*10}%` })
      ),
      el('span', { class: 'score-value' }, `${body.score||0}/10`)
    )
  );

  // Makró support info gomb a type sor végére
  if (macroSupport) {
    const infoBtn = el('span', { class: 'info-btn', tabindex: '0', title: macroSupport }, 'i');
    infoBtn.addEventListener('mouseenter', (e) => showTip(e, 'Makró alapok:\n' + macroSupport));
    infoBtn.addEventListener('mousemove', (e) => showTip(e, 'Makró alapok:\n' + macroSupport));
    infoBtn.addEventListener('mouseleave', hideTip);
    card.querySelector('.setup-card__type').appendChild(infoBtn);
  }

  // Zárolás oka — kiemelten, olvashatóan
  if (body.locked_reason) {
    card.appendChild(el('div', { class: 'setup-card__reason' },
      el('b', {}, '⛔ Zárolva: '), body.locked_reason
    ));
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
