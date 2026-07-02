// ═══ FIGYELMEZTETÉSEK PANEL ═══
const buildWarnings = (data) => {
  const warnings = [];
  const r = data.risk || {};
  const h = data.header || {};
  const nt = data.notrade_filters || {};

  // Aktív tiltások
  if (h.effective_mode === 'RED') {
    warnings.push({ level: 'active', icon: '⛔', text: 'NO-TRADE (RED effektív mód)' });
  }
  if (nt.macro_lock_active) {
    const w = nt.macro_no_trade_windows && nt.macro_no_trade_windows[0];
    warnings.push({ level: 'active', icon: '📅',
      text: `Makró tiltási ablak aktív${w ? ` (${w.start}–${w.end}: ${w.reason})` : ''}` });
  }
  if ((r.loss_streak || 0) >= 3) {
    warnings.push({ level: 'active', icon: '🔻', text: `Loss streak = ${r.loss_streak} → kötelező szünet` });
  }
  if ((r.daily_loss || 0) >= (r.daily_limit || 100)) {
    warnings.push({ level: 'active', icon: '💰', text: 'Napi vesztesélimit elérve' });
  }
  if ((r.weekly_loss || 0) >= (r.weekly_limit || 300)) {
    warnings.push({ level: 'active', icon: '📉', text: 'Heti vesztesélimit elérve' });
  }

  // Figyelendő
  if (h.effective_mode === 'YELLOW' && warnings.filter(w => w.level==='active').length === 0) {
    warnings.push({ level: 'watch', icon: '⚠', text: 'YELLOW mód: max 1 setup, Score ≥ 8 kötelező' });
  }
  if ((r.loss_streak || 0) === 2) {
    warnings.push({ level: 'watch', icon: '⚠', text: 'Loss streak = 2 → egy vesztő trade és RED-be lép' });
  }
  if (data.macro && data.macro.volatility && data.macro.volatility.value === 'HIGH') {
    warnings.push({ level: 'watch', icon: '🌊', text: 'HIGH vol regime – SL-t szélesíteni, méretet csökkenteni' });
  }
  if ((r.open_xau_positions || 0) >= 1) {
    warnings.push({ level: 'watch', icon: '📍', text: `${r.open_xau_positions} XAU pozíció nyitva – új XAU trade tiltva` });
  }

  // Ha semmi nem aktív
  if (warnings.length === 0) {
    warnings.push({ level: 'ok', icon: '✓', text: 'Nincs aktív figyelmeztetés — clear to trade a szabályok szerint' });
  }
  return warnings;
};

const renderWarnings = (data) => {
  const host = $('#warnings-container');
  host.innerHTML = '';
  const warns = buildWarnings(data);
  warns.forEach(w => {
    const li = el('li', { class: `warning-item warning-item--${w.level}` },
      el('span', { class: 'warning-icon' }, w.icon),
      el('span', {}, w.text)
    );
    host.appendChild(li);
  });
};
