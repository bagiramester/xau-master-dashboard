// ═══ MACRO MODULE — Top bar chips és bias festés ═══
const renderTopBar = (data) => {
  const now = new Date();
  $('#tb-datetime').textContent = now.toLocaleString('hu-HU', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  }) + ' CEST';

  const setChip = (id, chipId, value, state) => {
    const chip = $(chipId);
    $(id).textContent = value || '—';
    if (state) chip.dataset.state = state;
    else delete chip.dataset.state;
  };

  const h = data.header || {};
  setChip('#tb-session', '.tb-chip[data-role="session"]', h.session, null);

  const biasState = h.bias_direction === 'LONG' ? 'long'
                  : h.bias_direction === 'SHORT' ? 'short' : 'neutral';
  setChip('#tb-bias', '.tb-chip[data-role="bias"]', h.bias_direction, biasState);

  const statusMap = { 'ZÖLD': 'green', 'SÁRGA': 'yellow', 'PIROS': 'red' };
  setChip('#tb-status', '.tb-chip[data-role="status"]', h.bias_status, statusMap[h.bias_status]);

  const effMap = { 'GREEN': 'green', 'YELLOW': 'yellow', 'RED': 'red' };
  setChip('#tb-effective', '.tb-chip[data-role="effective"]', h.effective_mode, effMap[h.effective_mode]);

  const lockActive = data.notrade_filters && data.notrade_filters.macro_lock_active;
  setChip('#tb-lock', '.tb-chip[data-role="lock"]', lockActive ? 'AKTÍV' : 'inaktív', lockActive ? 'red' : 'green');

  const spot = data.macro && data.macro.xau_spot;
  $('#tb-spot').textContent = spot ? (spot.display || `$${spot.value}`) : '—';

  const fresh = data.meta && data.meta.data_freshness;
  const dot = $('#tb-freshness-dot');
  dot.dataset.state = fresh === 'live' ? 'live' : fresh === 'stale' ? 'stale' : 'error';
  $('#tb-freshness').textContent = fresh === 'live' ? 'LIVE' : fresh === 'stale' ? 'STALE' : 'PENDING';
  $('#tb-updated').textContent = data.meta ? fmtRelative(new Date().toISOString()) + ' • ' + data.meta.last_updated : '';

  $('#footer-updated').textContent = 'Frissítve: ' + (data.meta ? data.meta.last_updated : '—');
};
