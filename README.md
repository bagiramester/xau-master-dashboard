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

## Bagira AI — manuális trigger beállítás

A Bagira AI elemzést csak **manuálisan** indítod a dashboard `🧠 Új elemzés` gombjával. Ez elkerüli a felesleges API költséget és biztosítja, hogy a Bagira tanácsok csak akkor frissüljenek, amikor tényleg kell.

### GitHub Personal Access Token (PAT) létrehozása

1. Menj ide: [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new)
2. **Token name**: `bagira-ai-trigger`
3. **Expiration**: 90 nap (majd megújítod)
4. **Repository access**: **Only select repositories** → `bagiramester/xau-master-dashboard`
5. **Permissions** — repository permissions:
   - **Actions**: `Read and write` (ez a kritikus)
   - **Contents**: `Read` (a workflow file olvasáshoz)
   - **Metadata**: `Read` (automatikus)
6. **Generate token** → másold ki a `github_pat_...` kezdetű string-et

### Beállítás a dashboardon

1. Nyisd meg a dashboard-ot: [bagiramester.github.io/xau-master-dashboard](https://bagiramester.github.io/xau-master-dashboard)
2. Kattints a `🧠 Új elemzés` gombra a Bagira panelen
3. Beugrik egy prompt — illeszd be a PAT-ot
4. A token a böngésződ **localStorage**-jában tárolódik, **soha nem kerül a repóba**, csak Te látod

### Használat

- Gomb megnyomása → GitHub API triggereli a `ai-refresh` workflow-t
- ~30–90 mp múlva új Bagira elemzés jelenik meg a dashboardon
- A gomb magának is polling-ol, automatikusan újratölti amikor a data.json frissült

### Ha lejár vagy elveszíted a PAT-ot

Kattints ismét a gombra — új tokent kér. Ha valaki más letiltana, változtatná: mindig regeneráld a `xau-master-dashboard` repóhoz kötött legszigorúbb scope-pal.
