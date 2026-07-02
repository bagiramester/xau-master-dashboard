#!/usr/bin/env python3
"""
Bagira XAU AI Analyzer — Perplexity Sonar Reasoning Pro integration.

Bemenet: az aktuális data.json + cache/*.json fájlok (calendar, fedwatch, intraday)
Kimenet: setup_A, setup_B, bagira_narrative, key_watch, confidence, reasoning_summary
         → beírja a data.json-ba (setups, bagira blokk)

Mode:
  - Ha PPLX_API_KEY env var van → éles Perplexity API hívás
  - Ha MOCK_AI=true env var vagy nincs kulcs → mock válaszok (dev mode)
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

CEST = timezone(timedelta(hours=2))
NOW = datetime.now(CEST)
NOW_ISO = NOW.isoformat(timespec="seconds")

REPO = Path(__file__).resolve().parent.parent
DATA_PATH = REPO / "data.json"
PROMPT_PATH = REPO / "prompts" / "ai_setup_prompt.md"
CACHE_DIR = REPO / "cache"

API_KEY = os.getenv("PPLX_API_KEY", "").strip()
MOCK = os.getenv("MOCK_AI", "").lower() in ("1", "true", "yes") or not API_KEY

MODEL = "sonar-reasoning-pro"  # alternatívák: "sonar", "sonar-pro"
API_URL = "https://api.perplexity.ai/chat/completions"


def load_json(path, default=None):
    if not path.exists():
        return default
    try:
        with path.open() as f:
            return json.load(f)
    except Exception as e:
        print(f"[ai] load hiba: {path}: {e}", file=sys.stderr)
        return default


def build_snapshot(data):
    """Kompakt piaci állapot összeállítása a prompt bemenetére."""
    macro = data.get("macro", {})
    levels = data.get("levels", {})
    risk = data.get("risk", {})
    notrade = data.get("notrade_filters", {})
    header = data.get("header", {})

    def get_val(field, key="value"):
        if isinstance(field, dict):
            return field.get(key)
        return field

    calendar = load_json(CACHE_DIR / "calendar.json", {})
    fedwatch = load_json(CACHE_DIR / "fedwatch.json", {})
    intraday = load_json(CACHE_DIR / "intraday.json", {})

    return {
        "spot": get_val(macro.get("xau_spot")),
        "spot_display": get_val(macro.get("xau_spot"), "display"),
        "levels": {
            "pdh": get_val(levels.get("pdh")),
            "pdl": get_val(levels.get("pdl")),
            "daily_open": get_val(levels.get("daily_open")),
            "asia_high": intraday.get("asia_high") or get_val(levels.get("asia_high")),
            "asia_low": intraday.get("asia_low") or get_val(levels.get("asia_low")),
            "htf_supply": get_val(levels.get("htf_supply")),
            "htf_demand": get_val(levels.get("htf_demand")),
            "psych": get_val(levels.get("psych_level")),
        },
        "macro": {
            "dxy": {
                "value": get_val(macro.get("dxy")),
                "display": get_val(macro.get("dxy"), "display"),
                "bias": get_val(macro.get("dxy"), "bias"),
                "note": get_val(macro.get("dxy"), "bias_note"),
            },
            "us10y": {
                "value": get_val(macro.get("us10y")),
                "display": get_val(macro.get("us10y"), "display"),
                "bias": get_val(macro.get("us10y"), "bias"),
                "note": get_val(macro.get("us10y"), "bias_note"),
            },
            "fedwatch": {
                "regime": fedwatch.get("regime"),
                "bias": fedwatch.get("bias"),
                "display": fedwatch.get("display"),
                "note": fedwatch.get("note"),
            },
            "fear_greed": {
                "value": get_val(macro.get("sentiment")),
                "display": get_val(macro.get("sentiment"), "display"),
                "bias": get_val(macro.get("sentiment"), "bias"),
            },
            "htf_trend": get_val(macro.get("htf_trend")),
            "intraday_regime": intraday.get("intraday_regime") or get_val(macro.get("intraday_regime")),
            "volatility": intraday.get("volatility_regime") or get_val(macro.get("volatility")),
            "atr_15m": intraday.get("atr_15m"),
        },
        "notrade": {
            "macro_lock_active": (
                calendar.get("macro_lock_active") if calendar.get("macro_events_today")
                else notrade.get("macro_lock_active", False)
            ),
            "events_today": calendar.get("macro_events_today") or notrade.get("macro_events_today", []),
            "no_trade_windows": calendar.get("macro_no_trade_windows") or notrade.get("macro_no_trade_windows", []),
        },
        "risk_state": {
            "mode": risk.get("mode"),
            "daily_loss": risk.get("daily_loss", 0),
            "weekly_loss": risk.get("weekly_loss", 0),
            "loss_streak": risk.get("loss_streak", 0),
            "open_xau": risk.get("open_xau_positions", 0),
        },
        "session": header.get("session"),
        "cest_now": NOW.strftime("%Y-%m-%d %H:%M"),
    }


def call_perplexity(system_prompt, user_snapshot):
    """Éles Perplexity API hívás."""
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_snapshot, ensure_ascii=False, indent=2)},
        ],
        "temperature": 0.15,
        "max_tokens": 2500,
        "response_format": {"type": "json_schema", "json_schema": {
            "schema": {
                "type": "object",
                "required": ["setup_A", "setup_B", "bagira_narrative", "key_watch", "confidence", "reasoning_summary"],
                "additionalProperties": True,
            }
        }}
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    r = requests.post(API_URL, json=payload, headers=headers, timeout=90)
    if r.status_code != 200:
        print(f"[ai] API HTTP {r.status_code}: {r.text[:500]}", file=sys.stderr)
        r.raise_for_status()
    try:
        resp = r.json()
    except Exception as e:
        print(f"[ai] API response non-JSON: {r.text[:500]}", file=sys.stderr)
        raise
    content = resp["choices"][0]["message"]["content"]
    print(f"[ai] Raw content prefix: {content[:200]}...", file=sys.stderr)
    return content


def extract_json_from_text(text):
    """Az AI válaszból kinyeri a JSON-t (markdown fence-t, thinking blokkot eltávolít)."""
    # <think> blokk eltávolítása (reasoning modelleknél)
    import re
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    # markdown fence
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if m:
        return m.group(1)
    # Ha nincs fence, keresi a legnagyobb JSON blokkot
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end+1]
    return text


def mock_response(snapshot):
    """Fejlesztői mock — az aktuális NFP-nap adatra generált realisztikus válasz."""
    dxy = snapshot["macro"]["dxy"].get("value") or 100
    lock = snapshot["notrade"]["macro_lock_active"]
    us10y_note = snapshot["macro"]["us10y"].get("note", "")

    if lock:
        bagira = ("A pánter csendben ül. NFP küszöbén vagyunk — semmi sem tiszta. "
                  "A 4090 zóna prémium, de várni kell a rejectiont. A short bias "
                  "makró oldalról ép, de a nyomás a szabályokból jön: 60 perc tiltás.")
    else:
        bagira = ("A pánter figyel. DXY nyugodt, hozamok magasak — a short zsigerileg "
                  "helyes. A prémium a 4058–4105 sávban. Ha M15/H1 rejection tiszta, "
                  "a setup önmagát futtatja a 3965 zónáig.")

    return {
        "setup_A": {
            "direction": "SHORT",
            "type": "HTF sell-zóna / intraday premium reakció",
            "bias_compatibility": "igen — SHORT bias-szal egyező",
            "entry_zone": "4058-4105 (konzervatív: 4090-4105; HTF core: 4058-4068)",
            "sl": "4115 felett M15 close (konzervatív); 4080 felett H1 close (HTF core)",
            "tp1": "3965 (Value Demand Zóna)",
            "tp2": "3900 (Mélyebb Támasz)",
            "rr_min": 2.0,
            "score": 8,
            "session": "London 09:00-12:00 CEST (NFP előtt)",
            "invalidation": "H1 close 4080/4115 felett — bull struktúra erősödik",
            "macro_support": [
                us10y_note or "US10Y magas → opportunity cost aranynak",
                f"DXY {dxy} — nem tailwind long-nak",
                "FedWatch NEUTRAL/HIKE — nincs cut-bid",
            ],
            "allowed": not lock,
            "locked_reason": "Makró tiltási ablak aktív" if lock else None,
            "confirmed": False,
            "setup_quality": "erős"
        },
        "setup_B": {
            "direction": "LONG",
            "type": "NFP-utáni flush + demand sweep",
            "bias_compatibility": "részben — kontratrend, csak makróforduló esetén",
            "entry_zone": "3965-3970 flush/sweep után V-reversal",
            "sl": "3925 alatt H1 close",
            "tp1": "Daily Open / Asia High",
            "tp2": "4058-4068 (HTF sell zóna)",
            "rr_min": 2.0,
            "score": 6,
            "session": "Overlap 15:00-19:00 CEST (csak NFP után)",
            "invalidation": "H1 close 3930 alatt",
            "macro_support": [
                "Csak akkor engedélyezett, ha NFP significantly miss",
                "US10Y vissza 4.3% alá kell essen",
            ],
            "allowed": False,
            "locked_reason": "Csak NFP után (15:00 CEST+) és makróforduló esetén",
            "confirmed": False,
            "setup_quality": "közepes"
        },
        "bagira_narrative": bagira,
        "key_watch": [
            "M15 rejection a 4090-nél — ha jön, az edge élesedik",
            "NFP 14:30 — 13:30-tól teljes tiltás",
            "US10Y > 4.55% → short momentum felerősödik",
        ],
        "confidence": 70 if lock else 82,
        "reasoning_summary": (
            "SHORT bias 8/10: US10Y magas + emelkedő (4/4), DXY neutral (2/4), "
            "HTF RANGE + intraday range-bear (3/4). "
            "NFP előtti YELLOW nap miatt Setup B (LONG) locked, csak makróforduló esetén."
        ),
    }


def analyze():
    data = load_json(DATA_PATH)
    if not data:
        print("[ai] data.json nem található vagy hibás", file=sys.stderr)
        return None

    snapshot = build_snapshot(data)

    if MOCK:
        print("[ai] MOCK mode (nincs PPLX_API_KEY vagy MOCK_AI=true)")
        result = mock_response(snapshot)
        source_type = "ai-mock"
        model_name = "mock-v1"
    else:
        try:
            system_prompt = PROMPT_PATH.read_text()
            print(f"[ai] Perplexity {MODEL} hívás...")
            content = call_perplexity(system_prompt, snapshot)
            json_str = extract_json_from_text(content)
            result = json.loads(json_str)
            source_type = "ai"
            model_name = MODEL
            print("[ai] Sikeres AI válasz.")
        except Exception as e:
            print(f"[ai] Éles hívás hiba, fallback mock: {e}", file=sys.stderr)
            result = mock_response(snapshot)
            source_type = "ai-fallback"
            model_name = f"mock-fallback ({MODEL} failed)"

    # Beírjuk a data.json-ba
    def wrap_setup(body, slot):
        if not body:
            body = None
        return {
            "value": body,
            "status": "fresh" if body else "pending",
            "source_type": source_type,
            "source_label": f"AI ({model_name}) auto setup",
            "source_url": "https://www.perplexity.ai/",
            "updated_at": NOW_ISO,
            "impact": None,
            "ai_state": "SUGGESTED" if body and body.get("allowed") else ("LOCKED" if body else "EMPTY"),
        }

    data["setups"] = {
        "A": wrap_setup(result.get("setup_A"), "A"),
        "B": wrap_setup(result.get("setup_B"), "B"),
    }
    data["bagira"] = {
        "narrative": result.get("bagira_narrative", ""),
        "key_watch": result.get("key_watch", []),
        "confidence": result.get("confidence", 0),
        "reasoning_summary": result.get("reasoning_summary", ""),
        "model": model_name,
        "source_type": source_type,
        "updated_at": NOW_ISO,
    }
    data["meta"] = data.get("meta", {})
    data["meta"]["ai_last_run"] = NOW_ISO
    data["meta"]["ai_model"] = model_name
    data["meta"]["ai_source_type"] = source_type

    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"[ai] data.json frissítve: setup_A allowed={result.get('setup_A', {}).get('allowed')}, "
          f"confidence={result.get('confidence')}, source_type={source_type}")
    return result


if __name__ == "__main__":
    analyze()
