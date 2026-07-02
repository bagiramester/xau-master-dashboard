# Bagira XAU Master Dashboard

Aktív döntéstámogató cockpit XAU:CFD kereskedéshez az **XAU Master OS v5** modulrendszerhez.

🔗 **Live:** [bagiramester.github.io/xau-master-dashboard](https://bagiramester.github.io/xau-master-dashboard)

## Fő elemek

- **3-oszlopos decision cockpit** — SHORT/LONG setup fókusz bal, TV chart közép, Risk/Trade/Log jobb
- **Piaci hatások relevance-tábla** — makró driverek hatáserősség szerint (4/4 → 3/4)
- **Hard Lock overlay** — RED effektív mód vagy makró tiltási ablak esetén (X-szel bezárható)
- **Cyber-panther design** — karbon háttér, neon ice-blue accents, LONG=zöld, SHORT=piros
- **Hybrid refresh** — GitHub Actions cron 15 percenként + client-side fallback (>30 perc stale)

## Adatstruktúra

`data.json` v2 séma. Validálva `data-schema.json` ellen. Minden mezőnek van `updated_at`, `source_label`, `source_type`, `status` — hallucinált érték tilos.

## Automatikus frissítés

15 percenként hétköznap 07:00–20:00 CEST:
- Yahoo Finance: XAU spot, PDH/PDL/Open, US10Y, DXY
- CNN Fear & Greed Index
- Számított: HTF trend, Effective mode

## Manuális input

Setup A/B kártyák, kulcsszintek (Asia H/L, HTF zónák), risk state, trade log, FedWatch olvasat.

## Struktúra

```
/index.html              — 3-oszlopos cockpit shell
/css/
  base.css               — reset + typography
  layout.css             — grid, top bar, cockpit
  components.css         — cards, chips, risk, warnings, hard lock
  theme-cyber-panther.css — design tokens
/js/
  utils.js               — DOM helpers, formatters
  chart.js               — TradingView OANDA:XAUUSD embed
  macro.js               — top bar chips
  setups.js              — 2 fix setup kártya (SHORT+LONG fallback)
  risk.js                — risk panel
  relevance.js           — Piaci hatások MVP tábla
  warnings.js            — figyelmeztetések
  app.js                 — orchestration + hard lock + hybrid refresh
/scripts/
  fetch_data.py          — auto adatlekérés
  validate_data.py       — schema + hallucináció-guard
/data.json               — élő állapot
/data-schema.json        — v2 séma
/.github/workflows/
  update-data.yml        — 15 perces cron
```

## Referencia modulok (XAU Master OS v5)

- Macro Market OS (Daily Header)
- Setup Execution OS (A/B setup + 0–10 scoring)
- Risk OS (30 USD hard cap, 100/300 USD napi/heti limit)
- Trade Log OS (18 kötelező mező)
- Review OS (napi 3 tanulság, heti aggregáció)
- No-Trade Playbook (RED/PIROS trigger + protokoll)
