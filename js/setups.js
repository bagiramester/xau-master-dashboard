// ═══ SETUPS MODULE — fix SHORT + LONG kártyák (fallback ha hiányzik) ═══
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

const orderSetupsFixed = (setups) => {
  // Cél: bal oldalon MINDIG SHORT és LONG kártya, fix sorrendben
  const A = (setups && setups.A && setups.A.value) || null;
  const B = (setups && setups.B && setups.B.value) || null;
  let short = null, long_ = null;
  if (A && A.direction === 'SHORT') short = { key: 'A', body: A, wrap: setups.A };
  else if (A && A.direction === 'LONG') long_ = { key: 'A', body: A, wrap: setups.A };
  if (B && B.direction === 'SHORT') short = short || { key: 'B', body: B, wrap: setups.B };
  else if (B && B.direction === 'LONG') long_ = long_ || { key: 'B', body: B, wrap: setups.B };
  return { short, long: long_ };
};

const renderSetupCard = (slot /* 'short' | 'long' */, entry) => {
  const body = entry ? entry.body : { ...FALLBACK_SETUP, direction: slot.toUpperCase() };
  const wrap = entry ? entry.wrap : null;
  const cardClass = `setup-card setup-card--${slot}` + (!body.allowed ? ' setup-card--locked' : '');
  const stateClass = body.allowed
    ? 'setup-card__state--allowed'
    : (body.confirmed ? 'setup-card__state--watch' : 'setup-card__state--locked');
  const stateLabel = body.allowed ? '✓ ALLOWED' : (body.confirmed ? '◐ WATCH' : '⛔ LOCKED');
  const dirClass = slot === 'long' ? 'dir-long' : 'dir-short';
  const dirEmoji = slot === 'long' ? '🟢' : '🔴';

  const card = el('div', { class: cardClass, 'data-slot': entry ? entry.key : '' },
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

  if (body.locked_reason) {
    card.appendChild(el('div', { class: 'setup-card__reason' }, body.locked_reason));
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
