// ═══ RISK PANEL MODULE ═══
const renderRisk = (data) => {
  const r = data.risk || {};
  const host = $('#risk-container');
  host.innerHTML = '';

  $('#risk-mode').textContent = r.mode || '—';
  $('#risk-mode').dataset.mode = r.mode || '';

  const dailyUsage = r.daily_limit ? Math.min(100, Math.round((r.daily_loss / r.daily_limit) * 100)) : 0;
  const weeklyUsage = r.weekly_limit ? Math.min(100, Math.round((r.weekly_loss / r.weekly_limit) * 100)) : 0;

  const cell = (label, value, wide = false) => {
    const c = el('div', { class: 'risk-cell' + (wide ? ' risk-cell--wide' : '') },
      el('div', { class: 'risk-cell__label' }, label),
      el('div', { class: 'risk-cell__value' }, value)
    );
    return c;
  };

  const bar = (label, pct, current, limit) => {
    return el('div', { class: 'risk-cell risk-cell--wide' },
      el('div', { class: 'risk-cell__label' }, `${label} · $${current.toFixed(2)} / $${limit}`),
      el('div', { class: 'risk-bar' }, el('div', { class: 'risk-bar__fill', style: `width: ${pct}%` }))
    );
  };

  host.appendChild(cell('Napi P/L', `$${(r.daily_loss || 0).toFixed(2)}`));
  host.appendChild(cell('Heti P/L', `$${(r.weekly_loss || 0).toFixed(2)}`));
  host.appendChild(bar('Napi risk usage', dailyUsage, r.daily_loss || 0, r.daily_limit || 100));
  host.appendChild(bar('Heti risk usage', weeklyUsage, r.weekly_loss || 0, r.weekly_limit || 300));
  host.appendChild(cell('Loss streak', String(r.loss_streak ?? 0)));
  host.appendChild(cell('Max trade ma', String(r.max_trades_today ?? 2)));
  host.appendChild(cell('Nyitott XAU', String(r.open_xau_positions ?? 0)));
  host.appendChild(cell('Nyitott össz.', String(r.open_positions ?? 0)));
  host.appendChild(cell('RPT ajánlott', r.rpt_recommendation || '–', true));
};
