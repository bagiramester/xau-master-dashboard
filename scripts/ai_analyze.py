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

MODEL = os.getenv("PPLX_MODEL", "sonar-pro")  # alternatívák: "sonar", "sonar-reasoning-pro"
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
    """Éles Perplexity API hívás. A sonar-reasoning-pro <think> blokkot ad + JSON."""
    # Erősített prompt: kényszerítjük a tiszta JSON kimenetet
    hardened_system = system_prompt + (
        "\n\n**KRITIKUS**: A válasz csak és kizárólag egy JSON objektum legyen. "
        "Ne használj markdown code fence-t (```), ne írj magyarázatot a JSON előtt vagy után. "
        "A válasz az első karakterrel `{` kezdődik és az utolsóval `}` ér véget."
    )
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": hardened_system},
            {"role": "user", "content": "Bemenet:\n" + json.dumps(user_snapshot, ensure_ascii=False, indent=2) + "\n\nAdj egy JSON objektumot a rendszer prompt szerinti schémával."},
        ],
        "temperature": 0.15,
        "max_tokens": 2500,
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    r = requests.post(API_URL, json=payload, headers=headers, timeout=120)
    if r.status_code != 200:
        print(f"[ai] API HTTP {r.status_code}: {r.text[:800]}", file=sys.stderr)
        r.raise_for_status()
    try:
        resp = r.json()
    except Exception:
        print(f"[ai] API response non-JSON: {r.text[:800]}", file=sys.stderr)
        raise
    msg = resp["choices"][0]["message"]
    content = msg.get("content") or ""
    # Reasoning modelleknel a content mellett lehet reasoning_content is
    if not content and msg.get("reasoning_content"):
        content = msg["reasoning_content"]
        print("[ai] Using reasoning_content fallback", file=sys.stderr)
    print(f"[ai] Content length: {len(content)} chars (model={MODEL})", file=sys.stderr)
    if content:
        print(f"[ai] Content prefix: {content[:300]!r}", file=sys.stderr)
        print(f"[ai] Content suffix: {content[-200:]!r}", file=sys.stderr)
    else:
        print(f"[ai] Full response: {json.dumps(resp)[:800]}", file=sys.stderr)
    return content


def extract_json_from_text(text):
    """Az AI válaszból kinyeri a JSON-t (markdown fence-t, thinking blokkot eltávolít)."""
    import re
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if m:
        return m.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end+1]
    return text


def parse_ai_json(text):
    """Hibatűrő JSON parsing: json-repair → json5 → regex cleanup.
    Az LLM-ek gyakran nem szigorú JSON-t adnak (sortörés stringben,
    hiányzó vessző, trunccált válasz), ezért json-repair-t használunk elsődlegesen."""
    import re
    json_str = extract_json_from_text(text)

    # 1. json-repair — LLM JSON-ok javítására optimalizálva
    try:
        import json_repair
        repaired = json_repair.repair_json(json_str, return_objects=True)
        if isinstance(repaired, (dict, list)):
            return repaired
    except ImportError:
        print("[ai] json-repair nincs telepítve", file=sys.stderr)
    except Exception as e:
        print(f"[ai] json-repair hiba: {e}", file=sys.stderr)

    # 2. json5 (trailing comma, idézőjel nélküli kulcsok)
    try:
        import json5
        return json5.loads(json_str)
    except ImportError:
        print("[ai] json5 nincs, regex cleanup", file=sys.stderr)
    except Exception as e:
        print(f"[ai] json5 hiba: {e}", file=sys.stderr)

    # 3. Regex cleanup fallback
    fixed = re.sub(r",\s*([\]}])", r"\1", json_str)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        print(f"[ai] Cleanup parse hiba: {e}", file=sys.stderr)
    raise ValueError(f"AI response nem parseolhato. Elso 500: {json_str[:500]}")


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
            result = parse_ai_json(content)
            source_type = "ai"
            model_name = MODEL
            print("[ai] Sikeres AI válasz.")
        except Exception as e:
            print(f"[ai] Éles hívás hiba, fallback mock: {e}", file=sys.stderr)
            result = mock_response(snapshot)
            source_type = "ai-fallback"
            model_name = f"mock-fallback ({MODEL} failed)"

    # Normalizálás: az AI néha a bagira mezőket (narrative, confidence,
    # key_watch, reasoning_summary) a setup_A/setup_B blokkon belülre teszi a
    # top-level helyett. Hoistoljuk fel, és eltávolítjuk a setup blokkokból,
    # hogy a data.json bagira panelje mindig kapjon értéket.
    BAGIRA_KEYS = ("bagira_narrative", "confidence", "key_watch", "reasoning_summary")
    if isinstance(result, dict):
        for k in BAGIRA_KEYS:
            if result.get(k) in (None, "", [], {}):
                for slot in ("setup_A", "setup_B"):
                    body = result.get(slot)
                    if isinstance(body, dict) and body.get(k) not in (None, "", [], {}):
                        result[k] = body[k]
                        print(f"[ai] hoist: {k} <- {slot}", file=sys.stderr)
                        break
        # Misplaced másolatok eltávolítása a setup blokkokból
        for slot in ("setup_A", "setup_B"):
            body = result.get(slot)
            if isinstance(body, dict):
                for k in BAGIRA_KEYS:
                    body.pop(k, None)

    # Végső fallback: ha az AI egyáltalán nem adott narrative/confidence/key_watch
    # mezőket, szintetizálunk egyet setup_A adataiból, hogy a panel sose legyen üres.
    sa = result.get("setup_A") or {}
    if not result.get("bagira_narrative"):
        dir_a = sa.get("direction", "—")
        score_a = sa.get("score", "—")
        qual = sa.get("setup_quality", "—")
        allowed_a = sa.get("allowed")
        if allowed_a:
            result["bagira_narrative"] = (
                f"A pánter {dir_a.lower()} setupot lát ({score_a}/10, {qual}). "
                f"Várom a megerősítést a belépési zónában — addig csendben ülök.")
        else:
            reason = sa.get("locked_reason") or "a mai nap nem enged trade-t"
            result["bagira_narrative"] = (
                f"A pánter figyel, de nem lép. {reason}. "
                f"A terv {dir_a.lower()} irányban készen áll, ha a lock feloldódik.")
        print("[ai] fallback: bagira_narrative szintetizálva setup_A-ból", file=sys.stderr)
    if result.get("confidence") in (None, "", 0):
        try:
            result["confidence"] = int(sa.get("score", 0)) * 10
        except Exception:
            result["confidence"] = 50
        print(f"[ai] fallback: confidence szintetizálva = {result['confidence']}", file=sys.stderr)
    if not result.get("key_watch"):
        kw = []
        if sa.get("entry_zone"):
            kw.append(f"Belépési zóna: {sa.get('entry_zone')}")
        if sa.get("invalidation"):
            kw.append(f"Invalidáció: {sa.get('invalidation')}")
        if not kw:
            kw.append("Makró naptár és DXY/US10Y olvasat figyelése")
        result["key_watch"] = kw
        print("[ai] fallback: key_watch szintetizálva", file=sys.stderr)

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
