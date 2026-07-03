// ═══ PIACI HATÁSOK — gazdag kártyák pontos értékkel + info (forrás, frissítés) ═══

const DRIVER_META = {
  event: {
    name: 'Magas hatású esemény',
    desc: 'Naptárban lévő US high-impact makró esemény (NFP, CPI, FOMC stb.). Ilyenkor 60p előtte / 30p utána nincs új XAU trade.',
  },
  dxy: {
    name: 'Dollár index (DXY)',
    desc: 'USD erőssége 6 fő valuta kosárhoz képest. Erős USD (DXY emelkedik) = arany headwind, gyenge USD = tailwind.',
  },
  us10y: {
    name: '10-éves hozam (US10Y)',
    desc: 'US 10 éves treasury hozam. Emelkedő relhozam növeli az arany opportunity costját → short XAU háttér. Eső hozam kedvez a long-nak.',
  },
  fedwatch: {
    name: 'Fed várakozások (FedWatch)',
    desc: 'A CME FedWatch által beárazott Fed rate változtatási valószínűségek. Növekvő cut-várakozás = long XAU háttér; hike-odds növekedése = short háttér.',
  },
  sentiment: {
    name: 'Fear & Greed',
    desc: 'CNN Fear & Greed index (0–100). Extrém fear = safe haven kereslet (long XAU háttér). Extrém greed = relatív nyomás az aranyon.',
  },
  htf_trend: {
    name: 'HTF trend',
    desc: 'Higher-timeframe trend (H4/D1). BULL / BEAR / RANGE / TRANSITION — a setupok irányát ebbe kell igazítani.',
  },
  intraday_regime: {
    name: 'Intraday rezsim',
    desc: 'Intraday struktúra (M15/H1): TREND vagy RANGE. Meghatározza, trend-követő vagy range/reversal setup illik-e.',
  },
  volatility: {
    name: 'Volatilitás',
    desc: 'Várható napi volatilitás (ATR alapján vagy makró nap). HIGH vol → SL-t szélesíteni, méretet csökkenteni.',
  },
};

const valueColorClass = (bias) => {
  if (bias === 'RED') return 'rel-card__value--red';
  if (bias === 'GREEN') return 'rel-card__value--green';
  if (bias === 'YELLOW') return 'rel-card__value--yellow';
  return '';
};

const relCard = (key, field) => {
  const meta = DRIVER_META[key] || { name: key, desc: '' };
  const impact = field.impact != null ? field.impact : 0;
  const bias = field.bias || 'NEUTRAL';
  const valueText = field.display || (field.value != null ? String(field.value) : 'pending');
  const updated = field.updated_at || '';
  const sourceLabel = field.source_label || 'ismeretlen forrás';
  const sourceUrl = field.source_url || '';
  const note = field.bias_note || '';

  const card = el('div', { class: 'rel-card', 'data-bias': bias, 'data-key': key },
    el('div', { class: 'rel-card__head' },
      el('div', { class: 'rel-card__name' }, meta.name),
      el('div', { class: 'rel-card__head-right' },
        el('span', { class: 'rel-card__impact', 'data-impact': String(impact) }, impact > 0 ? `${impact}/4` : '–'),
        (() => {
          const ib = el('span', { class: 'info-btn', tabindex: '0' }, 'i');
          const tip =
            `${meta.name}\n` +
            `Hatás: ${impact}/4 · Bias: ${bias}\n\n` +
            `${meta.desc}\n\n` +
            `Érték: ${valueText}\n` +
            (note ? `Hatás: ${note}\n\n` : '\n') +
            `Forrás: ${sourceLabel}\n` +
            (sourceUrl ? `${sourceUrl}\n` : '') +
            `Frissítve: ${updated ? fmtRelative(updated) + ' (' + fmtCEST(updated) + ')' : 'nincs adat'}`;
          ib.title = tip;
          ib.addEventListener('mouseenter', (e) => showTip(e, tip));
          ib.addEventListener('mousemove', (e) => showTip(e, tip));
          ib.addEventListener('mouseleave', hideTip);
          return ib;
        })()
      )
    ),
    el('div', { class: `rel-card__value ${valueColorClass(bias)}` }, valueText),
    note ? el('div', { class: 'rel-card__note' }, note) : null,
    el('div', { class: 'rel-card__footer' },
      el('div', { class: 'rel-card__source', title: sourceLabel },
        el('span', {}, '◆ '),
        el('span', { class: 'rel-card__source-label' }, sourceLabel)
      ),
      el('span', { class: `rel-card__freshness ${isStale(updated, 60) ? 'rel-card__freshness--stale' : ''}` },
        updated ? fmtRelative(updated) : '—')
    )
  );
  return card;
};

const renderRelevance = (data) => {
  const host = $('#relevance-container');
  host.innerHTML = '';
  const m = data.macro || {};
  const nt = data.notrade_filters || {};

  // Sorrend: event → DXY → US10Y → FedWatch → F&G → HTF → Intraday → Vol
  const order = [
    ['event', synthEventField(nt)],
    ['dxy', m.dxy],
    ['us10y', m.us10y],
    ['fedwatch', m.fedwatch],
    ['sentiment', m.sentiment],
    ['htf_trend', m.htf_trend],
    ['intraday_regime', m.intraday_regime],
    ['volatility', m.volatility],
  ]
    .filter(([_, f]) => f && f.impact != null && f.impact >= 2)
    .sort((a, b) => (b[1].impact || 0) - (a[1].impact || 0));

  if (order.length === 0) {
    host.appendChild(el('div', { class: 'log-empty' }, 'Nincs elegendő adat a piaci hatások megjelenítéséhez.'));
    return;
  }
  order.forEach(([key, field]) => host.appendChild(relCard(key, field)));
};

// Szintetikus mező a naptár eseményből
const synthEventField = (notrade) => {
  const meta = DRIVER_META.event;
  if (!notrade || !notrade.macro_events_today || notrade.macro_events_today.length === 0) {
    return {
      impact: 2, value: 'nincs', display: 'nincs', bias: 'GREEN',
      bias_note: 'Ma nincs US high-impact esemény – tiszta setup környezet.',
      source_label: 'manuális naptár',
      source_url: 'https://www.investing.com/economic-calendar/',
      updated_at: new Date().toISOString(),
    };
  }
  const ev = notrade.macro_events_today[0];
  return {
    impact: 4,
    value: ev.event,
    display: `${ev.time_cest} · ${ev.event.split(' ')[0]}`,
    bias: notrade.macro_lock_active ? 'RED' : 'YELLOW',
    bias_note: ev.note || ev.effect || '–',
    source_label: 'Investing economic calendar (manuális)',
    source_url: 'https://www.investing.com/economic-calendar/',
    updated_at: new Date().toISOString(),
  };
};
