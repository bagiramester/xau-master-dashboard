// ═══════════════════════════════════════════════════════════════════════
// TRADE LOG — closed trade → data.json via GitHub Actions
// ═══════════════════════════════════════════════════════════════════════

const LOG_WORKFLOW_FILE = 'log-trade.yml';

const buildTradePayload = () => {
  const d = currentData || {};
  const h = d.header || {};
  const r = d.risk || {};

  const entry = parseFloat($('#ti-entry').value);
  const sl = parseFloat($('#ti-sl').value);
  const tp = parseFloat($('#ti-tp').value);
  const exit = parseFloat($('#ti-exit').value);
  const riskInput = parseFloat($('#ti-risk').value);
  const unit = parseFloat($('#ti-unit').value) || 1;
  const direction = $('#ti-direction').value;

  const riskPts = Math.abs(entry - sl);
  const rewardPts = Math.abs(tp - entry);
  const rrPlan = riskPts > 0 ? rewardPts / riskPts : 0;
  const actualPts = Math.abs(exit - entry);
  const rrActual = riskPts > 0 ? actualPts / riskPts : rrPlan;

  const riskUsd = Number.isFinite(riskInput) ? riskInput : riskPts;
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
    entry,
    sl,
    tp,
    exit,
    unit,
    risk_usd: Math.round(riskUsd * 100) / 100,
    pl_usd: plUsd,
    rr_actual: Math.round(rrActual * 100) / 100,
    score: parseInt($('#ti-score').value || '0', 10),
    allowed: h.effective_mode !== 'RED' && rrPlan >= 2,
    rule_compliance: $('#ti-compliance').value || 'igen',
    note: $('#ti-note').value || ''
  };
};

const validateClosedTrade = (t) => {
  const nums = ['entry', 'sl', 'tp', 'exit', 'unit', 'risk_usd', 'pl_usd', 'rr_actual', 'score'];

  for (const k of nums) {
    if (!Number.isFinite(Number(t[k]))) {
      return `${k} hibás vagy hiányzik`;
    }
  }

  if (!['LONG', 'SHORT'].includes(t.direction)) {
    return 'direction hibás';
  }

  if (!['igen', 'részben', 'nem'].includes(t.rule_compliance)) {
    return 'rule_compliance hibás';
  }

  // A 30 USD feletti kockázat szabálysértés, de NEM blokkolja a naplózást —
  // a journal minden lezárt trade-et rögzít, a rule_compliance jelöli a sértést.

  if (t.rr_actual < 0) {
    return 'RR hibás';
  }

  return '';
};

const resetTradeForm = () => {
  ['ti-entry', 'ti-sl', 'ti-tp', 'ti-exit', 'ti-risk', 'ti-score', 'ti-note'].forEach(id => {
    const n = $('#' + id);
    if (n) n.value = '';
  });

  const unit = $('#ti-unit');
  if (unit) unit.value = '1';

  const compliance = $('#ti-compliance');
  if (compliance) compliance.value = 'igen';

  const rrCalc = $('#ti-rr-calc');
  if (rrCalc) rrCalc.textContent = '—';

  const submit = $('#ti-submit');
  if (submit) {
    submit.disabled = true;
    submit.textContent = 'Naplózás (Belépő / SL / TP / Záró ár kell)';
  }
};

const submitTradeLog = async () => {
  const btn = $('#ti-submit');
  const original = btn.textContent;

  const payload = buildTradePayload();
  const err = validateClosedTrade(payload);

  if (err) {
    showRefreshStatus(err, 'error');
    return;
  }

  btn.disabled = true;
  btn.textContent = '⏳ Naplózás...';

  try {
    const beforeSha = await getDataJsonSha();

    await dispatchWorkflow(LOG_WORKFLOW_FILE, {
      trade: JSON.stringify(payload)
    });

    showRefreshStatus('Trade naplózás elindult. Várakozás a data.json commitra...', 'success');

    pollDataJsonChange({
      beforeSha,
      maxAttempts: 18,
      intervalMs: 10000,
      onDone: (data) => {
        if (currentData?.bagira && !data.bagira) {
          data.bagira = currentData.bagira;
        }

        render(data);
        showRefreshStatus('✓ Trade elmentve a data.json-be.', 'success');
        resetTradeForm();
      },
      onTimeout: () => {
        showRefreshStatus('A naplózás elhúzódott. Frissíts rá kézzel 1 perc múlva.', 'warning');
        btn.textContent = original;
        btn.disabled = false;
      }
    });
  } catch (e) {
    showRefreshStatus('Naplózási hiba: ' + e.message, 'error');
    btn.textContent = original;
    btn.disabled = false;
  }
};
