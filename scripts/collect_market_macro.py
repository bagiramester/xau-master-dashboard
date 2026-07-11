"""
FÁZIS 1 — Automatikus piaci és makró adatgyűjtés.
Forrásokból tölti a mezőket. Ha egy forrás nem elérhető, az előző értéket tartja meg.
Kimenet: build_state.json (nem data.json — azt csak a push írja).

FIGYELEM: A tényleges HTTP-scraping helyét jelöltük. A repóban a saját
fetch-logikádat (requests/yfinance/API) ide illeszd be a fetch_* függvényekbe.
"""
import sys
from common import (load_json, save_json, field, keep_previous, now_cest,
                    today_cest, DATA_PATH, STATE_PATH)


def safe(fetch_fn, prev_field, source_label, source_url=None, bias_fn=None):
    """Megpróbálja lekérni az adatot; hiba esetén előző értéket tart meg."""
    try:
        value = fetch_fn()
        if value is None:
            return keep_previous(prev_field, "üres válasz")
        bias = bias_fn(value) if bias_fn else None
        return field(value, source_type="auto", source_label=source_label,
                     source_url=source_url, bias=bias)
    except Exception as e:
        return keep_previous(prev_field, f"{source_label} hiba: {e}")


# --- Forrás-lekérő függvények (ide jön a valódi implementáció) ---
def fetch_fedwatch():   raise NotImplementedError("CME FedWatch lekérés ide")
def fetch_us10y():      raise NotImplementedError("US10Y lekérés ide")
def fetch_dxy():        raise NotImplementedError("DXY lekérés ide")
def fetch_sentiment():  raise NotImplementedError("CNN Fear & Greed lekérés ide")
def fetch_xau_spot():   raise NotImplementedError("XAU spot lekérés ide")
def fetch_calendar():   raise NotImplementedError("Economic calendar lekérés ide")


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
            "source_stack": ["economic-calendar", "fedwatch", "reuters",
                             "cnn-fear-greed", "tradingview"],
        },
        "macro": {
            "fedwatch": safe(fetch_fedwatch, prev_macro.get("fedwatch"),
                             "CME FedWatch",
                             "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"),
            "us10y": safe(fetch_us10y, prev_macro.get("us10y"),
                          "US10Y yield – CNBC/Reuters",
                          "https://www.cnbc.com/markets/", bias_us10y),
            "dxy": safe(fetch_dxy, prev_macro.get("dxy"),
                        "DXY – TradingView",
                        "https://www.tradingview.com/symbols/TVC-DXY"),
            "sentiment": safe(fetch_sentiment, prev_macro.get("sentiment"),
                              "CNN Fear & Greed Index",
                              "https://edition.cnn.com/markets/fear-and-greed"),
        },
        "header": {
            "xau_spot": safe(fetch_xau_spot, prev_header.get("xau_spot"),
                             "XAU/USD spot – Reuters/TradingView"),
            "date": today_cest(),
        },
        "levels_prev": prev.get("levels", {}),
        "risk_prev": prev.get("risk", {}),
        "trades_prev": prev.get("trade_log", prev.get("trades", [])),
    }

    # Makró naptár + tiltási ablakok
    try:
        cal = fetch_calendar()
        state["header"]["macro_events_today"] = cal.get("events", [])
        state["header"]["macro_no_trade_windows"] = cal.get("windows", [])
    except Exception as e:
        state["header"]["macro_events_today"] = prev_header.get("macro_events_today", [])
        state["header"]["macro_no_trade_windows"] = prev_header.get("macro_no_trade_windows", [])
        state["header"]["_calendar_warning"] = f"⚠️ naptár nem elérhető: {e}"

    save_json(STATE_PATH, state)
    print("collect-data OK:", now_cest())


if __name__ == "__main__":
    sys.exit(main())
