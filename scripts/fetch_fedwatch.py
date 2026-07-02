#!/usr/bin/env python3
"""
CME FedWatch valószínűségek fetcher.

Forráshierarchia:
  1. Perplexity API (ha van kulcs) – aktuális FedWatch olvasat live web-ből
  2. Növbe ansprout mirror (nyilvánosan elérhető, scrape-elhető)
  3. Manuális fallback (előző érték)

Kimenet:
  - regime: CUT / NEUTRAL / HIKE
  - value: humán olvasható implicit százalék
  - bias: GREEN / YELLOW / RED  (XAU szempontból)
"""
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

CEST = timezone(timedelta(hours=2))
NOW = datetime.now(CEST)

REPO = Path(__file__).resolve().parent.parent
CACHE = REPO / "cache" / "fedwatch.json"

def parse_fedwatch_probabilities(text):
    """
    Kinyeri a legfrissebb FOMC meeting valószínűségeket.
    A szöveg pl.: "Rate Cut ~15% Hold ~70% Rate Hike ~15%" formátumban jelenik meg.
    """
    m_cut = re.search(r"[Cc]ut[^0-9]{0,20}(\d{1,3})\s*%", text)
    m_hold = re.search(r"[Hh]old[^0-9]{0,20}(\d{1,3})\s*%", text)
    m_hike = re.search(r"[Hh]ike[^0-9]{0,20}(\d{1,3})\s*%", text)

    cut = int(m_cut.group(1)) if m_cut else None
    hold = int(m_hold.group(1)) if m_hold else None
    hike = int(m_hike.group(1)) if m_hike else None

    return cut, hold, hike

def determine_regime(cut, hold, hike):
    """Domináns rezsim meghatározása."""
    if cut is None and hold is None and hike is None:
        return None, None, None
    values = [(v or 0) for v in (cut, hold, hike)]
    max_val = max(values)
    if max_val == (hike or 0) and (hike or 0) >= 30:
        regime = "HIKE"
        bias = "RED"
        note = f"HIKE ~{hike}% dominál — negatív carry aranynak, short XAU háttér."
    elif max_val == (cut or 0) and (cut or 0) >= 55:
        regime = "CUT"
        bias = "GREEN"
        note = f"CUT ~{cut}% dominál — csökkenő opportunity cost, long XAU háttér."
    elif max_val == (hold or 0) and (hold or 0) >= 50:
        regime = "NEUTRAL/HOLD"
        bias = "YELLOW"
        note = f"HOLD ~{hold}% dominál — semleges makróháttér."
    else:
        regime = "MIXED"
        bias = "YELLOW"
        note = f"Vegyes: cut {cut}% / hold {hold}% / hike {hike}%."
    return regime, bias, note

def fetch_from_growbeansprout():
    """
    Kereskedhető FedWatch mirror. Robusztus scrape.
    URL: https://www.growbeansprout.com/fed-rate-monitor
    """
    try:
        r = requests.get("https://www.growbeansprout.com/fed-rate-monitor",
                         headers={"User-Agent": "Mozilla/5.0 (Bagira XAU Dashboard)"},
                         timeout=15)
        if r.status_code != 200:
            return None
        cut, hold, hike = parse_fedwatch_probabilities(r.text)
        if cut is None and hold is None and hike is None:
            return None
        regime, bias, note = determine_regime(cut, hold, hike)
        display = " | ".join(filter(None, [
            f"CUT ~{cut}%" if cut is not None else None,
            f"HOLD ~{hold}%" if hold is not None else None,
            f"HIKE ~{hike}%" if hike is not None else None,
        ]))
        return {
            "cut_pct": cut, "hold_pct": hold, "hike_pct": hike,
            "regime": regime, "bias": bias, "note": note,
            "display": display,
            "source_label": "Growbeansprout Fed Rate Monitor (mirror CME FedWatch)",
            "source_url": "https://www.growbeansprout.com/fed-rate-monitor",
            "updated_at": NOW.isoformat(timespec="seconds"),
        }
    except Exception as ex:
        print(f"[fedwatch] Growbeansprout fetch hiba: {ex}", file=sys.stderr)
        return None

def load_previous():
    if not CACHE.exists():
        return None
    try:
        with CACHE.open() as f:
            return json.load(f)
    except Exception:
        return None

def main():
    result = fetch_from_growbeansprout()
    if not result:
        # Fallback: előző cache
        prev = load_previous()
        if prev:
            prev["updated_at_stale"] = True
            prev["stale_from"] = prev.get("updated_at")
            prev["updated_at"] = NOW.isoformat(timespec="seconds")
            result = prev
            print("[fedwatch] fallback: előző cache használva")
        else:
            result = {
                "cut_pct": None, "hold_pct": None, "hike_pct": None,
                "regime": None, "bias": None,
                "note": "FedWatch adat nem elérhető — manuálisan kell beírni.",
                "display": "N/A – manuálisan frissítendő",
                "source_label": "Nincs adat",
                "source_url": None,
                "updated_at": None,
            }

    CACHE.parent.mkdir(exist_ok=True)
    with CACHE.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"[fedwatch] ok: regime={result.get('regime')} bias={result.get('bias')} display={result.get('display')}")
    return result

if __name__ == "__main__":
    main()
