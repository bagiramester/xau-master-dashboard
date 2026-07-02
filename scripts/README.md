# scripts/

## fetch_data.py

Automatikus adatlekérő. A GitHub Actions 15 percenként futtatja hétköznap 07:00–20:00 CEST közt.

### Automatikusan frissül

| Adat | Forrás | Ticker/API |
|---|---|---|
| XAU/USD spot, PDH, PDL, Daily Open | Yahoo Finance | `GC=F` |
| US10Y hozam + irány + bias | Yahoo Finance | `^TNX` |
| DXY szint + rezsim + bias | Yahoo Finance | `DX-Y.NYB` |
| Fear & Greed Index + bias | CNN dataviz API | – |
| HTF trend (ár alapján) | Számított | – |
| Effective mode (szigorúbb-nyer) | Számított | – |

### Manuális marad

- **FedWatch** – CME hivatalos API fizetős. Előző értéket megtartjuk.
- **Asia High/Low** – csak chart alapján adható meg.
- **HTF supply/demand zóna** – saját elemzés.
- **Setup A/B belépő/SL/TP/score** – saját scoring.
- **Bias irány/status** – saját ítélet.
- **Risk state** (napi/heti P&L, loss streak) – trader input.
- **Trade log** – manuális naplózás.

### Kézi futtatás

```bash
pip install yfinance requests jsonschema
python scripts/fetch_data.py
python scripts/validate_data.py
```

## validate_data.py

Kettős védelmi vonal:
1. JSON Schema strukturális ellenőrzés (`data-schema.json`)
2. Hallucináció-guard — minden nem-null value-hez kötelező `updated_at`, `source_label`, `status ∈ {fresh, stale}`

## Séma dokumentáció

Lásd `../data-schema.json` — v2 séma.

## Manuális GitHub Actions trigger

Repo → Actions → **Auto-update data.json** → **Run workflow**
