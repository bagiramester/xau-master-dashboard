#!/usr/bin/env python3
"""
US High-Impact Economic Calendar fetcher.

Forrás preferencia sorrendben:
  1. TradingEconomics API (nincs kulcs, de rate-limited)
  2. Investing.com scraping (fallback)
  3. FMP API (fallback, ha van kulcs)

Kimenet: no_trade_windows lista + macro_events_today (CEST timezone).
"""
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

CEST = timezone(timedelta(hours=2))
NOW = datetime.now(CEST)
TODAY = NOW.strftime("%Y-%m-%d")

REPO = Path(__file__).resolve().parent.parent
CALENDAR_JSON = REPO / "cache" / "calendar.json"

# High-impact US események, amelyek XAU-t erősen mozgatnak
HIGH_IMPACT_KEYWORDS = [
    "Nonfarm Payrolls", "NFP",
    "CPI", "Consumer Price Index",
    "PPI", "Producer Price Index",
    "FOMC", "Fed Interest Rate", "Federal Funds",
    "Fed Chair", "Powell",
    "GDP",
    "Unemployment Rate",
    "Retail Sales",
    "ISM Manufacturing", "ISM Services",
    "Core PCE", "PCE",
    "ADP",
    "JOLTS",
    "Initial Jobless Claims",
]

def is_high_impact(name):
    return any(kw.lower() in name.lower() for kw in HIGH_IMPACT_KEYWORDS)

def fetch_from_tradingeconomics():
    """
    TradingEconomics ingyenes calendar API.
    URL: https://api.tradingeconomics.com/calendar/country/united%20states
    Guest access: limitált, ISO date range.
    """
    try:
        d1 = TODAY
        d2 = TODAY
        url = f"https://api.tradingeconomics.com/calendar/country/united%20states?c=guest:guest&d1={d1}&d2={d2}&f=json"
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        events = []
        for e in data:
            if e.get("Importance") == 3 or is_high_impact(e.get("Event", "")):
                # Time UTC → CEST
                utc_time_str = e.get("Date", "")
                try:
                    utc_dt = datetime.fromisoformat(utc_time_str.replace("T", " ").replace("Z", ""))
                    utc_dt = utc_dt.replace(tzinfo=timezone.utc)
                    cest_dt = utc_dt.astimezone(CEST)
                    time_cest = cest_dt.strftime("%H:%M")
                except Exception:
                    time_cest = "TBD"
                events.append({
                    "event": e.get("Event", "Unknown"),
                    "time_cest": time_cest,
                    "effect": "HIGH-IMPACT US event",
                    "note": f"Actual: {e.get('Actual', '–')} | Forecast: {e.get('Forecast', '–')} | Prev: {e.get('Previous', '–')}",
                    "importance": e.get("Importance", 2),
                })
        return events
    except Exception as ex:
        print(f"[calendar] TradingEconomics fetch hiba: {ex}", file=sys.stderr)
        return None

def fetch_from_investing():
    """
    Investing.com egyszerű scrape fallback.
    Csak akkor fut, ha a TE API üres.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Bagira XAU Dashboard)",
            "X-Requested-With": "XMLHttpRequest",
        }
        url = "https://www.investing.com/economic-calendar/Service/getCalendarFilteredData"
        payload = {
            "country[]": "5",  # USA
            "importance[]": "3",  # High impact
            "timeZone": "8",  # GMT
            "timeFilter": "timeRemain",
            "currentTab": "today",
            "submitFilters": "1",
        }
        r = requests.post(url, headers=headers, data=payload, timeout=15)
        if r.status_code != 200:
            return None
        html = r.text
        # Egyszerű regex extraction (a JSON válasz HTML-t tartalmaz)
        events = []
        # Time + event név keresés
        for m in re.finditer(
            r'<td[^>]*class="[^"]*first left time[^"]*"[^>]*>([\d:]+)</td>.*?<td[^>]*class="[^"]*event[^"]*"[^>]*>.*?<a[^>]*>([^<]+)</a>',
            html, re.S
        ):
            time_gmt = m.group(1).strip()
            name = m.group(2).strip()
            if not is_high_impact(name):
                continue
            # GMT → CEST (+2h)
            try:
                h, mm = map(int, time_gmt.split(":"))
                cest_h = (h + 2) % 24
                time_cest = f"{cest_h:02d}:{mm:02d}"
            except Exception:
                time_cest = time_gmt
            events.append({
                "event": name,
                "time_cest": time_cest,
                "effect": "HIGH-IMPACT US event",
                "note": "Forrás: investing.com fallback",
                "importance": 3,
            })
        return events if events else None
    except Exception as ex:
        print(f"[calendar] Investing fetch hiba: {ex}", file=sys.stderr)
        return None

def build_no_trade_windows(events):
    """60 perc előtte, 30 perc utána. Ha egymáshoz közel vannak, összevonjuk."""
    windows = []
    for e in events:
        try:
            h, m = map(int, e["time_cest"].split(":"))
            start_dt = NOW.replace(hour=h, minute=m) - timedelta(minutes=60)
            end_dt = NOW.replace(hour=h, minute=m) + timedelta(minutes=30)
            windows.append({
                "start": start_dt.strftime("%H:%M"),
                "end": end_dt.strftime("%H:%M"),
                "reason": f"{e['event']} – 60p előtte, 30p utána. Nincs új XAU trade, nincs SL/TP mód.",
                "event_time": e["time_cest"],
            })
        except Exception:
            continue
    # Egymáshoz közel eső window-k összevonása
    windows.sort(key=lambda w: w["start"])
    merged = []
    for w in windows:
        if merged and merged[-1]["end"] >= w["start"]:
            merged[-1]["end"] = max(merged[-1]["end"], w["end"])
            merged[-1]["reason"] += f" + {w['reason'].split('–')[0].strip()}"
        else:
            merged.append(w)
    return merged

def is_lock_active(windows):
    """Van-e aktív tiltási ablak most?"""
    now_hm = NOW.strftime("%H:%M")
    for w in windows:
        if w["start"] <= now_hm <= w["end"]:
            return True
    return False

def main():
    events = fetch_from_tradingeconomics()
    source = "tradingeconomics"
    if not events:
        events = fetch_from_investing()
        source = "investing.com"
    if not events:
        events = []
        source = "fallback (üres)"

    windows = build_no_trade_windows(events)
    lock = is_lock_active(windows)

    output = {
        "macro_lock_active": lock,
        "macro_events_today": events,
        "macro_no_trade_windows": windows,
        "note": (f"Auto: {source}. {len(events)} high-impact US esemény ma."
                 if events else "Auto: nincs high-impact US esemény ma."),
        "source_label": f"Auto calendar: {source}",
        "updated_at": NOW.isoformat(timespec="seconds"),
    }

    CALENDAR_JSON.parent.mkdir(exist_ok=True)
    with CALENDAR_JSON.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[calendar] ok: {len(events)} events, lock={lock}, source={source}")
    return output

if __name__ == "__main__":
    main()
