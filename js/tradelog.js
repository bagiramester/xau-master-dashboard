// ═══ TRADE LOG — closed trade → data.json via GitHub Actions ═══
const LOG_WORKFLOW_FILE = 'log-trade.yml';

const buildTradePayload = () => {
  const d = currentData || {};
  const h = d.header || {};
  const r = d.risk || {};
  const entry = parseFloat($('#ti-entry').value);
  const sl = parseFloat($('#ti-sl').value);
  const tp = parseFloat($('#ti-tp').value);
  const exit = parseFloat($('#ti-exit').value);
  const risk = parseFloat($('#ti-risk').value) || Math.abs(entry - sl);
  const unit = parseFloat($('#ti-unit').value) || 1;
  const direction = $('#ti-direction').value;
  const riskPts = Math.abs(entry - sl);
  const rewardPts = Math.abs(tp - entry);
  const rrPlan = riskPts > 0 ? rewardPts / riskPts : 0;
  const actualPts = Math.abs(exit - entry);
  const rrActual = riskPts > 0 ? actualPts / riskPts : rrPlan;
  const move = direction === 'LONG' ? (exit - entry) : (entry - exit);
  const plUsd = Math.round(move * unit * 100) / 100;
  return {
    datetime: new Date().toISOString(),
    instrument: 'XAU:CFD',
    session: h.session || 'Other',
    direction,
    setup_type: $('#ti-setup').value,
    bias: h.bias_direction || 'NEUTRAL',
    daily_status: h.bias_status || null,
    risk_mode: r.mode || null,
    entry, sl, tp, exit, unit,
    risk_usd: Math.round(risk * 100) / 100,
    pl_usd: plUsd,
    rr_actual: Math.round(rrActual * 100) / 100,
    score: parseInt($('#ti-score').value || '0', 10),
    allowed: h.effective_mode !== 'RED' && rrPlan >= 2,
    rule_compliance: $('#ti-compliance').value || 'igen',
    note: $('#ti-note').value || ''
  };
};

const validateClosedTrade = (t) => {
  const nums = ['entry','sl','tp','exit','unit','risk_usd','pl_usd','rr_actual','score'];
  for (const k of nums) if (!Number.isFinite(Number(t[k]))) return `${k} hibás vagy hiányzik`;
  if (t.risk_usd > 30) return 'Risk USD nagyobb mint 30 — tiltott';
  if (t.rr_actual < 0) return 'RR hibás';
  return '';
};

const submitTradeLog = async () => {
  const btn = $('#ti-submit');
  const original = btn.textContent;
  const payload = buildTradePayload();
  const err = validateClosedTrade(payload);
  if (err) { showRefreshStatus(err, 'error'); return; }
  btn.disabled = true; btn.textContent = '⏳ Naplózás...';
  try {
    const beforeSha = await getDataJsonSha();
    await dispatchWorkflow(LOG_WORKFLOW_FILE, { trade: JSON.stringify(payload) });
    showRefreshStatus('Trade naplózás elindult. Várakozás data.json commitra...', 'success');
    pollDataJsonChange({
      beforeSha,
      maxAttempts: 18,
      intervalMs: 10000,
      onDone: (data) => {
        if (currentData?.bagira && !data.bagira) data.bagira = currentData.bagira;
        render(data);
        showRefreshStatus('✓ Trade elmentve a data.json-be.', 'success');
        btn.textContent = 'Trade naplózása'; btn.disabled = false;
        ['ti-entry','ti-sl','ti-tp','ti-exit','ti-risk','ti-score','ti-note'].forEach(id => { const n = $('#'+id); if (n) n.value = ''; });
      },
      onTimeout: () => {
        showRefreshStatus('A naplózás elhúzódott. Frissíts rá kézzel 1 perc múlva.', 'warning');
        btn.textContent = original; btn.disabled = false;
      }
    });
  } catch (e) {
    showRefreshStatus('Naplózási hiba: ' + e.message, 'error');
    btn.textContent = original; btn.disabled = false;
  }
};
