"""
FAZIS 1 - Automatikus piaci es makro adatgyujtes.
Forrasokbol tolti a mezoket. Ha egy forras nem elerheto, az elozo erteket tartja meg.
Kimenet: build_state.json (nem data.json - azt csak a push irja).
"""
import sys
import json
import urllib.request
from common import (load_json, save_json, field, keep_previous, now_cest,
                    today_cest, DATA_PATH, STATE_PATH)

import yfinance as yf


def safe(fetch_fn, prev_field, source_label, source_url=None, bias_fn=None):
    """Megprobalja lekerni az adatot; hiba eseten elozo erteket tart meg."""
    try:
        value = fetch_fn()
        if value is None:
            return keep_previous(prev_field, "ures valasz")
        bias = bias_fn(value) if bias_fn else None
        return field(value, source_type="auto", source_label=source_label,
                     source_url=source_url, bias=bias)
    except Exception as e:
        return keep_previous(prev_field, f"{source_label} hiba: {e}")


def _last_close(ticker):
    data = yf.Ticker(ticker).history(period="5d")
    if data is None or data.empty:
        return None
    return float(data["Close"].dropna().iloc[-1])


def fetch_xau_spot():
    price = _last_close("GC=F")
    if price is None:
        return None
    return f"{price:.2f}"


def fetch_us10y():
    y = _last_close("^TNX")
    if y is None:
        return None
    return f"{y:.2f}%"


def fetch_dxy():
    v = _last_close("DX-Y.NYB")
    if v is None:
        return None
    return f"{v:.2f}"


def fetch_fedwatch():
    return "n/a"


def fetch_sentiment():
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    score = payload.get("fear_and_greed", {}).get("score")
    if score is None:
        return None
    return int(round(float(score)))


def fetch_calendar():
    raise NotImplementedError("Economic calendar lekeres ide")


def bias_us10y(v):
    try:
        y = float(str(v).split("%")[0])
    except Exception:
        return "YELLOW"
    return "RED" if y > 4.2 else "YELLOW"

def main():
    prev = load_json(DATA_PATH, default={})
    prev_macro = prev.get("macro", {})
    prev_header = prev.get("header", {})
    state = {
        "meta": {
            "date": today_cest(),
            "last_auto_sync": now_cest(),
            "version": "v5",
            "source_stack": ["economic-calendar", "fedwatch", "reuters", "cnn-fear-greed", "tradingview"],
        },
        "macro": {
            "fedwatch": safe(fetch_fedwatch, prev_macro.get("fedwatch"), "CME FedWatch", "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"),
            "us10y": safe(fetch_us10y, prev_macro.get("us10y"), "US10Y yield - Yahoo Finance", "https://finance.yahoo.com/quote/%5ETNX", bias_us10y),
            "dxy": safe(fetch_dxy, prev_macro.get("dxy"), "DXY - Yahoo Finance", "https://finance.yahoo.com/quote/DX-Y.NYB"),
            "sentiment": safe(fetch_sentiment, prev_macro.get("sentiment"), "CNN Fear & Greed Index", "https://edition.cnn.com/markets/fear-and-greed"),
        },
        "header": {
            "xau_spot": safe(fetch_xau_spot, prev_header.get("xau_spot"), "XAU/USD spot - Yahoo Finance (GC=F)"),
            "date": today_cest(),
        },
        "levels_prev": prev.get("levels", {}),
        "risk_prev": prev.get("risk", {}),
        "trades_prev": prev.get("trade_log", prev.get("trades", [])),
    }
    try:
        cal = fetch_calendar()
        state["header"]["macro_events_today"] = cal.get("events", [])
        state["header"]["macro_no_trade_windows"] = cal.get("windows", [])
    except Exception as e:
        state["header"]["macro_events_today"] = prev_header.get("macro_events_today", [])
        state["header"]["macro_no_trade_windows"] = prev_header.get("macro_no_trade_windows", [])
        state["header"]["_calendar_warning"] = f"naptar nem elerheto: {e}"
    save_json(STATE_PATH, state)
    print("collect-data OK:", now_cest())

if __name__ == "__main__":
    sys.exit(main())
