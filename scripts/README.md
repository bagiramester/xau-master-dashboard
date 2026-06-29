# scripts/

## fetch_data.py

Napi automatikus adatlekérő script. A GitHub Actions minden hétkoznap 07:30 CEST-kor futtatja.

### Mit frissít automatikusan

| Adat | Forrás | Ticker |
|---|---|---|
| XAU/USD ár, PDH, PDL, Daily Open | Yahoo Finance | `GC=F` |
| US10Y hozam + irány | Yahoo Finance | `^TNX` |
| DXY szint + bias | Yahoo Finance | `DX-Y.NYB` |
| Fear & Greed index | CNN dataviz API | – |
| HTF trend (ár alapján) | Számított | – |

### Amit NEM frissít (manuális marad)

- **FedWatch** – CME API fizetős ($25/hó), az előző értéket tartja meg
- **Asia High/Low** – csak chart alapján adható meg
- **HTF kulcsszint** – saját elemzés alapján
- **Setup belépő/SL/TP/Score** – scoring alapján
- **Bias döntés** – saját ítélet

### Manuális futtatás

```bash
pip install yfinance requests
python scripts/fetch_data.py
```

### GitHub Actions manuális trigger

A GitHub repo Actions fülén → `Auto-update data.json` → `Run workflow`
