#!/usr/bin/env python3
"""
Bagira XAU Master Dashboard – automatikus adatlekérő script (v2 séma)
=====================================================================

Fut: GitHub Actions (15 perc, hétköznap London+NY session alatt).
Manuálisan: `pip install yfinance requests jsonschema && python scripts/fetch_data.py`

Alapelvek:
  - Minden mező kap `updated_at`, `source_label`, `source_type`, `status` mezőt.
  - Hallucinált érték TILOS. Ha egy forrás elesik → `status: "error"`, `value: null`, előző érték megőrizve.
  - Manuális mezőket (setups, risk, trade_log, kulcsszintek egy része) az előző data.json-ből olvassuk vissza.
  - `effective_mode` és `bias_note` mindig újraszámolódik a friss adatokból.
"""

import json
import sys
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import yfinance as yf

# ── Konstansok ────────────────────────────────────────────────────────────────
CEST = timezone(timedelta(hours=2))
NOW = datetime.now(CEST)
NOW_ISO = NOW.isoformat(timespec="seconds")
NOW_HUMAN = NOW.strftime("%Y-%m-%d %H:%M CEST")

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = REPO_ROOT / "data.json"

# ── Segédfüggvények ───────────────────────────────────────────────────────────
def make_field(value, *, display=None, bias=None, bias_note=None, impact=None,
               status="fresh", source_type="auto", source_label="", source_url=None,
               updated_at=None):
    """Egyetlen sourceField konstruktor."""
    return {
        "value": value,
        "display": display,
        "bias": bias,
        "bias_note": bias_note,
        "impact": impact,
        "status": status,
        "source_type": source_type,
        "source_label": source_label,
        "source_url": source_url,
        "updated_at": updated_at or (NOW_ISO if value is not None else None),
    }

def load_prev():
    if not DATA_PATH.exists():
        return {}
    try:
        with DATA_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Előző data.json betöltése sikertelen: {e}")
        return {}

def preserve_field(prev, dotted_path, fallback_field):
    """Előző értéket megőrizzük, de a status-t `stale`-re állítjuk."""
    node = prev
    for part in dotted_path.split("."):
        if not isinstance(node, dict) or part not in node:
            return fallback_field
        node = node[part]
    if isinstance(node, dict) and "value" in node:
        node = dict(node)
        node["status"] = "stale"
        return node
    return fallback_field

# ── 1. XAU spot + előző napi szintek (Yahoo GC=F) ────────────────────────────
def fetch_xau():
    try:
        gold = yf.Ticker("GC=F")
        hist = gold.history(period="5d", interval="1d")
        price = round(float(hist["Close"].iloc[-1]), 2)
        prev_close = round(float(hist["Close"].iloc[-2]), 2)
        pdh = round(float(hist["High"].iloc[-2]), 2)
        pdl = round(float(hist["Low"].iloc[-2]), 2)
        daily_open = round(float(hist["Open"].iloc[-1]), 2)
        daily_change_pct = round((price - prev_close) / prev_close * 100, 2)
        display = f"${price:,.2f} ({'+' if daily_change_pct >= 0 else ''}{daily_change_pct}%)"
        return {
            "ok": True,
            "xau_spot": make_field(price, display=display, impact=4,
                                   source_type="auto",
                                   source_label="Yahoo Finance GC=F",
                                   source_url="https://finance.yahoo.com/quote/GC=F"),
            "pdh": {"value": pdh, "status": "fresh", "source_type": "auto",
                    "source_label": "Yahoo Finance GC=F (előző napi High)",
                    "source_url": None, "updated_at": NOW_ISO},
            "pdl": {"value": pdl, "status": "fresh", "source_type": "auto",
                    "source_label": "Yahoo Finance GC=F (előző napi Low)",
                    "source_url": None, "updated_at": NOW_ISO},
            "daily_open": {"value": daily_open, "status": "fresh", "source_type": "auto",
                           "source_label": "Yahoo Finance GC=F (mai Open)",
                           "source_url": None, "updated_at": NOW_ISO},
            "raw_price": price,
        }
    except Exception as e:
        print(f"[ERROR] XAU fetch: {e}")
        return {"ok": False, "error": str(e)}

# ── 2. US10Y hozam (Yahoo ^TNX) ──────────────────────────────────────────────
def fetch_us10y():
    try:
        tnx = yf.Ticker("^TNX")
        hist = tnx.history(period="5d")
        curr = round(float(hist["Close"].iloc[-1]), 2)
        prev = round(float(hist["Close"].iloc[-2]), 2)
        direction = "RISING" if curr > prev else "FALLING" if curr < prev else "SIDEWAYS"
        # Bias logika: magas + emelkedő → RED (short XAU háttér)
        if curr >= 4.2 and direction == "RISING":
            bias, note = "RED", f"US10Y {curr}% és emelkedik – magas opportunity cost aranynak, short XAU háttér."
        elif curr < 4.0 or direction == "FALLING":
            bias, note = "GREEN", f"US10Y {curr}%, {direction.lower()} – kedvezőbb long XAU háttér."
        else:
            bias, note = "YELLOW", f"US10Y {curr}%, {direction.lower()} – vegyes."
        return make_field(curr, display=f"{curr}% – {direction}",
                          bias=bias, bias_note=note, impact=4,
                          source_type="auto",
                          source_label="Yahoo Finance ^TNX",
                          source_url="https://finance.yahoo.com/quote/%5ETNX")
    except Exception as e:
        print(f"[ERROR] US10Y fetch: {e}")
        return None

# ── 3. DXY (Yahoo DX-Y.NYB) ──────────────────────────────────────────────────
def fetch_dxy():
    try:
        dxy = yf.Ticker("DX-Y.NYB")
        hist = dxy.history(period="5d")
        curr = round(float(hist["Close"].iloc[-1]), 2)
        prev = round(float(hist["Close"].iloc[-2]), 2)
        if curr > 103:
            regime, bias = "USD-BULL", "RED"
            note = f"DXY {curr} > 103 – erős USD, headwind XAU-nak."
        elif curr < 99:
            regime, bias = "USD-BEAR", "GREEN"
            note = f"DXY {curr} < 99 – gyenge USD, tailwind XAU-nak."
        else:
            regime, bias = "RANGE", "YELLOW"
            note = f"DXY {curr} a 99–103 sávban – semleges USD-háttér."
        return make_field(curr, display=f"{curr} – {regime}",
                          bias=bias, bias_note=note, impact=4,
                          source_type="auto",
                          source_label="Yahoo Finance DX-Y.NYB",
                          source_url="https://finance.yahoo.com/quote/DX-Y.NYB")
    except Exception as e:
        print(f"[ERROR] DXY fetch: {e}")
        return None

# ── 4. CNN Fear & Greed Index ────────────────────────────────────────────────
def fetch_fear_greed():
    try:
        url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
        headers = {"User-Agent": "Mozilla/5.0 (Bagira XAU Dashboard)"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        score = int(round(data["fear_and_greed"]["score"]))
        category = data["fear_and_greed"]["rating"].upper()
        # XAU-mapping
        if score <= 25:
            bias = "GREEN"
            note = f"EXTREME FEAR ({score}) – safe haven demand, long XAU háttér."
        elif score <= 45:
            bias = "YELLOW"
            note = f"FEAR ({score}) – enyhén long XAU-kedvező."
        elif score <= 55:
            bias = "YELLOW"
            note = f"NEUTRAL ({score}) – semleges."
        elif score <= 75:
            bias = "YELLOW"
            note = f"GREED ({score}) – enyhén XAU-negatív."
        else:
            bias = "RED"
            note = f"EXTREME GREED ({score}) – risk-on, XAU-negatív."
        return make_field(score, display=f"{score} – {category}",
                          bias=bias, bias_note=note, impact=2,
                          source_type="auto",
                          source_label="CNN Fear & Greed Index",
                          source_url="https://edition.cnn.com/markets/fear-and-greed")
    except Exception as e:
        print(f"[ERROR] Fear & Greed fetch: {e}")
        return None

# ── 5. HTF trend számítás (ártartomány alapján) ─────────────────────────────
def compute_htf(raw_price):
    if raw_price is None:
        return None
    if raw_price > 4300:
        v, bias, note = "BULL", "GREEN", "Ár > 4300 – erős bull HTF, trend continuation preferált."
    elif raw_price > 3800:
        v, bias, note = "RANGE", "YELLOW", "Ár 3800–4300 sávban – range/transition."
    else:
        v, bias, note = "BEAR", "RED", "Ár < 3800 – bear HTF, short bias."
    return make_field(v, display=v, bias=bias, bias_note=note, impact=3,
                      source_type="computed",
                      source_label="Számított ártartomány alapján",
                      source_url=None)

# ── 6. Effective mode számítás ───────────────────────────────────────────────
def compute_effective_mode(macro, risk, notrade):
    """A szigorúbb szabály nyer. RED > YELLOW > GREEN."""
    order = {"GREEN": 0, "YELLOW": 1, "RED": 2}
    reverse = {v: k for k, v in order.items()}
    biases = []
    for key in ("fedwatch", "us10y", "dxy", "sentiment", "htf_trend", "intraday_regime", "volatility"):
        b = macro.get(key, {}).get("bias") if isinstance(macro.get(key), dict) else None
        if b in order:
            biases.append(order[b])
    # Risk override
    if risk.get("daily_loss", 0) >= risk.get("daily_limit", 100):
        biases.append(order["RED"])
    if risk.get("weekly_loss", 0) >= risk.get("weekly_limit", 300):
        biases.append(order["RED"])
    if risk.get("loss_streak", 0) >= 3:
        biases.append(order["RED"])
    if notrade.get("macro_lock_active"):
        biases.append(order["YELLOW"])
    return reverse[max(biases)] if biases else "GREEN"

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    prev = load_prev()

    # 1. Auto adatok
    xau = fetch_xau()
    us10y = fetch_us10y()
    dxy = fetch_dxy()
    fg = fetch_fear_greed()

    # 2. Macro blokk
    macro = {}

    # FedWatch – manuális, előző értéket megőrzünk
    macro["fedwatch"] = prev.get("macro", {}).get("fedwatch") or make_field(
        None, display="Manuálisan frissítendő", impact=4, status="pending",
        source_type="manual", source_label="CME FedWatch (manuális)",
        source_url="https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html",
        updated_at=None)

    # US10Y
    macro["us10y"] = us10y or preserve_field(prev, "macro.us10y",
        make_field(None, display="N/A", impact=4, status="error",
                   source_type="auto", source_label="Yahoo Finance ^TNX",
                   source_url="https://finance.yahoo.com/quote/%5ETNX",
                   updated_at=None))

    # DXY
    macro["dxy"] = dxy or preserve_field(prev, "macro.dxy",
        make_field(None, display="N/A", impact=4, status="error",
                   source_type="auto", source_label="Yahoo Finance DX-Y.NYB",
                   updated_at=None))

    # Sentiment
    macro["sentiment"] = fg or preserve_field(prev, "macro.sentiment",
        make_field(None, display="N/A", impact=2, status="error",
                   source_type="auto", source_label="CNN Fear & Greed",
                   source_url="https://edition.cnn.com/markets/fear-and-greed",
                   updated_at=None))

    # HTF trend – számított
    if xau.get("ok"):
        macro["htf_trend"] = compute_htf(xau["raw_price"])
    else:
        macro["htf_trend"] = preserve_field(prev, "macro.htf_trend",
            make_field(None, display="N/A", impact=3, status="error",
                       source_type="computed", source_label="Számított"))

    # Intraday regime és volatility – manuális
    macro["intraday_regime"] = prev.get("macro", {}).get("intraday_regime") or make_field(
        "RANGE", display="RANGE", impact=3, status="pending",
        source_type="manual", source_label="TradingView OANDA:XAUUSD manuális",
        source_url="https://www.tradingview.com/symbols/OANDA-XAUUSD/",
        updated_at=None)
    macro["volatility"] = prev.get("macro", {}).get("volatility") or make_field(
        "NORMAL", display="NORMAL", impact=3, status="pending",
        source_type="manual", source_label="Manuális volatility rezsim",
        updated_at=None)

    # XAU spot
    macro["xau_spot"] = xau.get("xau_spot") if xau.get("ok") else preserve_field(
        prev, "macro.xau_spot",
        make_field(None, display="N/A", impact=4, status="error",
                   source_type="auto", source_label="Yahoo Finance GC=F",
                   source_url="https://finance.yahoo.com/quote/GC=F"))

    # 3. Levels blokk
    levels = {}
    if xau.get("ok"):
        levels["pdh"] = xau["pdh"]
        levels["pdl"] = xau["pdl"]
        levels["daily_open"] = xau["daily_open"]
    else:
        for k in ("pdh", "pdl", "daily_open"):
            levels[k] = prev.get("levels", {}).get(k) or {
                "value": None, "status": "error",
                "source_type": "auto", "source_label": "Yahoo Finance GC=F",
                "source_url": None, "updated_at": None
            }

    # Manuális szintek – megőrzés
    for k in ("asia_high", "asia_low", "htf_supply", "htf_demand", "psych_level"):
        levels[k] = prev.get("levels", {}).get(k) or {
            "value": None, "status": "pending",
            "source_type": "manual",
            "source_label": f"Charton olvasandó ({k})",
            "source_url": None, "updated_at": None
        }

    # 4. Notrade filters, risk, header, setups, trade_log, performance – manuális
    notrade = prev.get("notrade_filters", {"macro_lock_active": False, "macro_events_today": [], "macro_no_trade_windows": []})
    risk = prev.get("risk", {
        "mode": "GREEN", "daily_limit": 100.0, "weekly_limit": 300.0,
        "daily_loss": 0.0, "daily_risk_usage_pct": 0,
        "weekly_loss": 0.0, "weekly_risk_usage_pct": 0,
        "loss_streak": 0, "max_trades_today": 2,
        "open_positions": 0, "open_xau_positions": 0,
        "trade_allowed_now": True, "xau_trade_allowed_now": True,
        "trade_allowed_reason": "GREEN mód, nincs makró tiltás.",
        "rpt_recommendation": "5–15 USD", "rpt_hard_cap": 30.0,
        "updated_at": NOW_ISO,
    })
    risk["updated_at"] = NOW_ISO

    setups = prev.get("setups", {"A": None, "B": None})
    trade_log = prev.get("trade_log", [])
    performance = prev.get("performance", {
        "trade_count": 0, "win_count": 0, "loss_count": 0,
        "net_pl_usd": 0.0, "avg_rr": None, "rule_break_count": 0,
        "updated_at": NOW_ISO,
    })
    performance["updated_at"] = NOW_ISO

    # 5. Header (effective mode számítás)
    effective_mode = compute_effective_mode(macro, risk, notrade)
    prev_header = prev.get("header", {})
    header = {
        "bias_direction":     prev_header.get("bias_direction", "NEUTRAL"),
        "bias_status":        prev_header.get("bias_status", "ZÖLD"),
        "effective_mode":     effective_mode,
        "session":            detect_session(),
        "session_focus":      prev_header.get("session_focus", "–"),
        "narrative":          prev_header.get("narrative", ""),
        "fed_regime_summary": prev_header.get("fed_regime_summary", ""),
    }

    # 6. Meta
    all_fresh = all(
        (isinstance(f, dict) and f.get("status") == "fresh")
        for f in [macro["us10y"], macro["dxy"], macro["sentiment"], macro["xau_spot"]]
    )
    freshness = "live" if all_fresh else "stale"

    data = {
        "meta": {
            "schema_version": "v2",
            "last_updated": NOW_HUMAN,
            "auto": True,
            "note": "Auto: XAU/US10Y/DXY/F&G/HTF (Yahoo+CNN). Manuális: FedWatch, kulcsszintek, risk, log.",
            "data_freshness": freshness,
            "source_stack": [
                "yfinance:GC=F", "yfinance:^TNX", "yfinance:DX-Y.NYB",
                "cnn:fear-greed", "cme:fedwatch (manual)",
                "investing:economic-calendar (manual)", "manual:trade-log",
            ],
        },
        "macro": macro,
        "levels": levels,
        "notrade_filters": notrade,
        "risk": risk,
        "header": header,
        "setups": setups,
        "trade_log": trade_log,
        "performance": performance,
    }

    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ data.json frissítve: {NOW_HUMAN}")
    print(f"   Freshness: {freshness} | Effective mode: {effective_mode}")
    if xau.get("ok"):
        print(f"   XAU: ${xau['raw_price']} | PDH {xau['pdh']['value']} PDL {xau['pdl']['value']} Open {xau['daily_open']['value']}")
    print(f"   US10Y: {macro['us10y'].get('display', 'N/A')}")
    print(f"   DXY: {macro['dxy'].get('display', 'N/A')}")
    print(f"   Fear&Greed: {macro['sentiment'].get('display', 'N/A')}")

def detect_session():
    h = NOW.hour + NOW.minute / 60
    if 1 <= h < 9:   return "Asia"
    if 9 <= h < 14:  return "London"
    if 14 <= h < 19: return "Overlap"
    if 19 <= h < 22: return "NY"
    return "After-hours"

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Fatal: {e}")
        traceback.print_exc()
        sys.exit(1)
