// ═══ PIACI HATÁSOK RELEVANCE-TÁBLA (MVP: csak 4/4 és 3/4) ═══
const relevanceEntry = (name, field, hint) => {
  if (!field || field.impact == null || field.impact < 3) return null;
  const stateClass = field.bias === 'GREEN' ? 'state-green'
                    : field.bias === 'YELLOW' ? 'state-yellow'
                    : field.bias === 'RED' ? 'state-red' : 'state-neutral';
  const row = el('div', { class: 'rel-row' },
    el('div', { class: 'rel-row__impact', 'data-impact': String(field.impact) }, `${field.impact}/4`),
    el('div', { class: 'rel-row__body' },
      el('div', { class: 'rel-row__name' }, name),
      el('div', { class: 'rel-row__note' }, field.bias_note || hint || '')
    ),
    el('div', { class: `rel-row__value ${stateClass}` }, field.display || (field.value != null ? String(field.value) : 'pending'))
  );
  return row;
};

const renderRelevance = (data) => {
  const host = $('#relevance-container');
  host.innerHTML = '';
  const m = data.macro || {};

  // Rendezés impact szerint DESC
  const rows = [
    ['🎯 High-impact event', synthEventField(data.notrade_filters)],
    ['💵 DXY', m.dxy],
    ['📈 US10Y', m.us10y],
    ['🏛 FedWatch', m.fedwatch],
    ['📊 HTF Trend', m.htf_trend],
    ['⏱ Intraday Regime', m.intraday_regime],
    ['🌊 Volatility', m.volatility]
  ]
    .filter(([_, f]) => f && f.impact >= 3)
    .sort((a, b) => (b[1].impact || 0) - (a[1].impact || 0));

  if (rows.length === 0) {
    host.appendChild(el('div', { class: 'log-empty' }, 'Nincs elegendő adat a piaci hatások megjelenítéséhez.'));
    return;
  }
  rows.forEach(([name, field]) => {
    const row = relevanceEntry(name, field);
    if (row) host.appendChild(row);
  });
};

// Szintetikus mező a naptár eseményből
const synthEventField = (notrade) => {
  if (!notrade || !notrade.macro_events_today || notrade.macro_events_today.length === 0) {
    return { impact: 3, value: 'nincs', display: 'nincs', bias: 'GREEN',
             bias_note: 'Ma nincs US high-impact esemény – tiszta setup környezet.' };
  }
  const ev = notrade.macro_events_today[0];
  return {
    impact: 4,
    value: ev.event,
    display: `${ev.time_cest} · ${ev.event.split(' ')[0]}`,
    bias: notrade.macro_lock_active ? 'RED' : 'YELLOW',
    bias_note: ev.note || ev.effect || '–'
  };
};
