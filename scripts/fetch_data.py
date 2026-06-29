#!/usr/bin/env python3
"""
XAU Dashboard – napi automatikus adatlekérő script
Futtatja: GitHub Actions, minden hétkoznap 07:30 CEST
Manuálisan is futtatható: python scripts/fetch_data.py
"""

import json
import requests
import yfinance as yf
from datetime import datetime, timezone, timedelta

CEST = timezone(timedelta(hours=2))
now = datetime.now(CEST)

# ── 1. XAU/USD – Gold Futures (GC=F) ─────────────────────────────────────────
try:
    gold = yf.Ticker("GC=F")
    hist = gold.history(period="5d", interval="1d")
    xau_price   = round(float(hist["Close"].iloc[-1]), 2)
    pdh         = round(float(hist["High"].iloc[-2]), 2)
    pdl         = round(float(hist["Low"].iloc[-2]),  2)
    daily_open  = round(float(hist["Open"].iloc[-1]), 2)
except Exception as e:
    print(f"[WARN] XAU fetch failed: {e}")
    xau_price = pdh = pdl = daily_open = None

# ── 2. US10Y hozam (^TNX) ─────────────────────────────────────────────────────
try:
    tnx = yf.Ticker("^TNX")
    us10y_val = round(float(tnx.history(period="2d")["Close"].iloc[-1]), 2)
    prev_val  = round(float(tnx.history(period="2d")["Close"].iloc[-2]), 2)
    direction = "EMELKEDŐ" if us10y_val > prev_val else "STABIL" if us10y_val == prev_val else "CSÖKKENŐ"
    us10y_label = f"{us10y_val}% – {direction}"
except Exception as e:
    print(f"[WARN] US10Y fetch failed: {e}")
    us10y_label = "N/A"
    us10y_val = None

# ── 3. DXY (DX-Y.NYB) ────────────────────────────────────────────────────────
try:
    dxy = yf.Ticker("DX-Y.NYB")
    dxy_val = round(float(dxy.history(period="1d")["Close"].iloc[-1]), 2)
    if dxy_val > 103:
        dxy_bias = "USD-BULL"
    elif dxy_val > 99:
        dxy_bias = "NEUTRAL"
    else:
        dxy_bias = "USD-BEAR"
    dxy_label = f"{dxy_val} – {dxy_bias}"
except Exception as e:
    print(f"[WARN] DXY fetch failed: {e}")
    dxy_label = "N/A"
    dxy_val = None

# ── 4. CNN Fear & Greed ───────────────────────────────────────────────────────
try:
    fg_url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    fg_resp = requests.get(fg_url, timeout=10).json()
    fg_val   = round(fg_resp["fear_and_greed"]["score"])
    fg_rating = fg_resp["fear_and_greed"]["rating"].upper()
    # Magyar fordítás
    label_map = {
        "EXTREME FEAR": "EXTRÉM FÉLELEM",
        "FEAR": "FÉLELEM",
        "NEUTRAL": "SEMLEGES",
        "GREED": "KAPZSISÁG",
        "EXTREME GREED": "EXTRÉM KAPZSISÁG"
    }
    fg_hu = label_map.get(fg_rating, fg_rating)
    sentiment_label = f"{fg_hu} ({fg_val}/100)"
except Exception as e:
    print(f"[WARN] Fear&Greed fetch failed: {e}")
    sentiment_label = "N/A"
    fg_val = None

# ── 5. HTF trend logika (ár alapján automatikus) ──────────────────────────────
# Egyszerű proxy: ha XAU > 4300 → BULL, 3800–4300 → RANGE, <3800 → BEAR
if xau_price:
    if xau_price > 4300:
        htf = "BULL"
    elif xau_price > 3800:
        htf = "RANGE"
    else:
        htf = "BEAR"
else:
    htf = "N/A"

# ── 6. FedWatch (manuális – CME API fizetős) ──────────────────────────────────
# Ha $25/hó CME API elérhetővé válik, ide jön a lekérés.
# Addig az előző manuális értéket megtartjuk.
try:
    with open("data.json", "r", encoding="utf-8") as f:
        prev = json.load(f)
    fedwatch_label = prev["macro"].get("fedwatch", "HOLD – manuális")
except Exception:
    fedwatch_label = "HOLD – manuális"

# ── 7. Adatstruktúra összerakása ──────────────────────────────────────────────
data = {
    "meta": {
        "last_updated": now.strftime("%Y-%m-%d %H:%M CEST"),
        "auto": True,
        "note": "Automatikusan frissítve: XAU, US10Y, DXY, Fear&Greed. FedWatch manuális."
    },
    "macro": {
        "fedwatch": fedwatch_label,
        "us10y": us10y_label,
        "dxy": dxy_label,
        "sentiment": sentiment_label,
        "htf_trend": htf,
        "intraday_regime": prev.get("macro", {}).get("intraday_regime", "TREND"),
        "volatility": "NORMÁL"
    },
    "levels": {
        "pdh": pdh,
        "pdl": pdl,
        "asia_high": None,
        "asia_low": None,
        "daily_open": daily_open,
        "htf_level": prev.get("levels", {}).get("htf_level", None)
    },
    "notrade_filters": prev.get("notrade_filters", {}),
    "risk": prev.get("risk", {
        "daily_pl_usd": 0,
        "daily_risk_usage_pct": 0,
        "daily_limit_usd": 100,
        "weekly_risk_usage_pct": 0,
        "weekly_limit_usd": 300,
        "loss_streak": 0,
        "risk_mode": "ZÖLD",
        "rpt_min_usd": 5,
        "rpt_max_usd": 30,
        "open_positions": 0,
        "max_positions": 3
    }),
    "header": {
        "bias_direction": prev.get("header", {}).get("bias_direction", "–"),
        "bias_status": prev.get("header", {}).get("bias_status", "–"),
        "risk_mode": prev.get("risk", {}).get("risk_mode", "ZÖLD"),
        "daily_pl_usd": prev.get("risk", {}).get("daily_pl_usd", 0),
        "daily_risk_usage_pct": prev.get("risk", {}).get("daily_risk_usage_pct", 0)
    },
    "setups": prev.get("setups", []),
    "trade_log": prev.get("trade_log", [])
}

# ── 8. Kiírás ─────────────────────────────────────────────────────────────────
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"✅ data.json frissítve: {now.strftime('%Y-%m-%d %H:%M CEST')}")
print(f"   XAU: {xau_price} | PDH: {pdh} | PDL: {pdl} | Daily Open: {daily_open}")
print(f"   US10Y: {us10y_label}")
print(f"   DXY: {dxy_label}")
print(f"   Fear&Greed: {sentiment_label}")
print(f"   HTF trend: {htf}")
