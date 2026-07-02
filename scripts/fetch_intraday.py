#!/usr/bin/env python3
"""
Intraday XAU elemzés — Asia High/Low + regime detektálás.

Yahoo yfinance-ből húzza a mai 5 perces / 15 perces XAU adatokat,
és számítja:
  - Asia session H/L (01:00–08:00 CEST)
  - Intraday regime: TREND-BULL / TREND-BEAR / RANGE-BULL / RANGE-BEAR / RANGE
  - Volatility regime: LOW / NORMAL / HIGH (ATR-alap)
"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import yfinance as yf
except ImportError:
    print("yfinance nincs telepítve", file=sys.stderr)
    sys.exit(1)

CEST = timezone(timedelta(hours=2))
NOW = datetime.now(CEST)

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "cache" / "intraday.json"

def fetch_intraday_data():
    """XAU 15m adatok mai napra."""
    try:
        gold = yf.Ticker("GC=F")
        hist = gold.history(period="1d", interval="15m")
        if hist.empty:
            return None
        # Time indexeket CEST-re konvertálunk
        hist.index = hist.index.tz_convert(CEST)
        return hist
    except Exception as ex:
        print(f"[intraday] yfinance hiba: {ex}", file=sys.stderr)
        return None

def compute_asia_hl(hist):
    """Ázsiai session H/L (01:00–08:00 CEST)."""
    if hist is None or hist.empty:
        return None, None
    asia = hist.between_time("01:00", "08:00")
    if asia.empty:
        return None, None
    return round(float(asia["High"].max()), 2), round(float(asia["Low"].min()), 2)

def compute_atr(hist, period=14):
    """Egyszerű ATR számítás 15m gyertyákból."""
    if hist is None or len(hist) < period + 1:
        return None
    high = hist["High"]
    low = hist["Low"]
    close_prev = hist["Close"].shift(1)
    tr = (high - low).combine(
        (high - close_prev).abs(), max
    ).combine(
        (low - close_prev).abs(), max
    )
    atr = tr.rolling(period).mean().iloc[-1]
    return round(float(atr), 2)

def compute_regime(hist):
    """
    Intraday regime detektálás. Egyszerű logika:
      - Ha az utolsó 12 gyertya (3 óra) range < 0.4% → RANGE
      - Ha a lezáró ár az utolsó 20 gyertyához képest > 0.5% felfelé → TREND-BULL
      - Ha lefelé > 0.5% → TREND-BEAR
      - Egyébként RANGE-BIAS (irányfüggő)
    """
    if hist is None or len(hist) < 20:
        return None, "insufficient data"

    last_20 = hist.tail(20)
    range_pct = (last_20["High"].max() - last_20["Low"].min()) / last_20["Close"].iloc[-1] * 100
    momentum_pct = (last_20["Close"].iloc[-1] - last_20["Close"].iloc[0]) / last_20["Close"].iloc[0] * 100

    if abs(momentum_pct) < 0.15 and range_pct < 0.5:
        regime = "RANGE"
        note = f"Range: mozgás {momentum_pct:+.2f}%, tartomány {range_pct:.2f}% az utolsó 5 órában."
    elif momentum_pct > 0.5:
        regime = "TREND-BULL"
        note = f"Bullish trend: +{momentum_pct:.2f}% az utolsó 5 órában."
    elif momentum_pct < -0.5:
        regime = "TREND-BEAR"
        note = f"Bearish trend: {momentum_pct:.2f}% az utolsó 5 órában."
    elif momentum_pct > 0:
        regime = "RANGE-BULL"
        note = f"Range with bull bias: +{momentum_pct:.2f}%, tartomány {range_pct:.2f}%."
    else:
        regime = "RANGE-BEAR"
        note = f"Range with bear bias: {momentum_pct:.2f}%, tartomány {range_pct:.2f}%."
    return regime, note

def compute_volatility(atr, price):
    """Volatility regime ATR/ár arány alapján."""
    if atr is None or price is None or price == 0:
        return None, "N/A"
    ratio_pct = atr / price * 100
    if ratio_pct > 0.35:
        return "HIGH", f"ATR15m ${atr} ({ratio_pct:.2f}%) — magas volatilitás, óvatosan."
    elif ratio_pct > 0.15:
        return "NORMAL", f"ATR15m ${atr} ({ratio_pct:.2f}%) — normál piaci vol."
    else:
        return "LOW", f"ATR15m ${atr} ({ratio_pct:.2f}%) — alacsony vol, szűkebb SL használható."

def main():
    hist = fetch_intraday_data()
    asia_h, asia_l = compute_asia_hl(hist)
    atr = compute_atr(hist)
    regime, regime_note = compute_regime(hist) if hist is not None else (None, "no data")
    price = float(hist["Close"].iloc[-1]) if hist is not None and not hist.empty else None
    vol, vol_note = compute_volatility(atr, price)

    result = {
        "asia_high": asia_h,
        "asia_low": asia_l,
        "atr_15m": atr,
        "intraday_regime": regime,
        "intraday_regime_note": regime_note,
        "volatility_regime": vol,
        "volatility_note": vol_note,
        "last_price": round(price, 2) if price else None,
        "source_label": "Yahoo GC=F 15m intraday computed",
        "updated_at": NOW.isoformat(timespec="seconds"),
    }

    CACHE.parent.mkdir(exist_ok=True)
    with CACHE.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[intraday] ok: AsiaH={asia_h} AsiaL={asia_l} regime={regime} vol={vol} ATR={atr}")
    return result

if __name__ == "__main__":
    main()
