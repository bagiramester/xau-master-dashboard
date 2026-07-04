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
DEEP_RESEARCH_PROMPT_PATH = REPO / "prompts" / "deep_research_prompt.md"
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
        # A napi mély kutatás eredményei — Bagira ezeket használja a setup elemzéshez
        "daily_research": {
            "daily_summary": header.get("fed_regime_summary"),
            "bias_narrative": header.get("narrative"),
            "news_drivers": data.get("bagira", {}).get("key_watch", []) if isinstance(data.get("bagira"), dict) else [],
            "us_market_closed": notrade.get("us_market_closed"),
            "us_market_note": notrade.get("us_market_note"),
            "is_clean_day": notrade.get("is_clean_day"),
            "clean_day_note": notrade.get("clean_day_note"),
            "research_date": data.get("meta", {}).get("deep_research_last_run"),
        },
    }


def call_perplexity(system_prompt, user_snapshot):
    """Éles Perplexity API hívás. A sonar-reasoning-pro <think> blokkot ad + JSON."""
    # Erősített prompt: kényszerítjük a tiszta JSON kimenetet
    hardened_system = system_prompt + (
        "\n\n**KRITIKUS**: A válasz csak és kizárólag egy JSON objektum legyen. "
        "Ne használj markdown code fence-t (```), ne írj magyarázatot a JSON előtt vagy után. "
        "A válasz az első karakterrel `{` kezdődik és az utolsóval `}` ér véget. "
        "Web search használata engedélyezett és ajánlott — ha egy szint, esemény vagy adat "
        "nem egyértelmű a bemenetből, keress utána a friss adatokért."
    )
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": hardened_system},
            {"role": "user", "content": "Bemenet (az összes aktuális adat + napi mély kutatás):\n" + json.dumps(user_snapshot, ensure_ascii=False, indent=2) + "\n\nVégezd el a setup elemzést és finomítást, adj egy JSON objektumot a schéma szerint."},
        ],
        "temperature": 0.15,
        "max_tokens": 3000,
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


# ═══ NAPI MÉLY MAKRÓ KUTATÁS ═══
# A Perplexity egy második hívásával mély, forrás-alapú kutatást végzünk,
# ami frissíti a naptárt, bias-t, rezsimet és kulcsszinteket — nem csak narratívát.

DEEP_RESEARCH_MODEL = os.getenv("PPLX_DEEP_MODEL", "sonar-pro")


def call_perplexity_with_search(system_prompt, user_question):
    """Perplexity hívás web search-sel a mély kutatáshoz (sonar-pro online modellek)."""
    hardened_system = system_prompt + (
        "\n\n**KRITIKUS**: A válasz csak és kizárólag egy JSON objektum legyen. "
        "Ne használj markdown code fence-t (```), ne írj magyarázatot a JSON előtt vagy után. "
        "A válasz az első karakterrel `{` kezdődik és az utolsóval `}` ér véget. "
        "Web search kötelező — használd a mai dátumhoz tartozó friss forrásokat."
    )
    payload = {
        "model": DEEP_RESEARCH_MODEL,
        "messages": [
            {"role": "system", "content": hardened_system},
            {"role": "user", "content": user_question},
        ],
        "temperature": 0.2,
        "max_tokens": 4000,
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    r = requests.post(API_URL, json=payload, headers=headers, timeout=180)
    if r.status_code != 200:
        print(f"[deep] API HTTP {r.status_code}: {r.text[:800]}", file=sys.stderr)
        r.raise_for_status()
    resp = r.json()
    msg = resp["choices"][0]["message"]
    content = msg.get("content") or ""
    if not content and msg.get("reasoning_content"):
        content = msg["reasoning_content"]
    # citations (ha vannak)
    citations = resp.get("citations") or []
    print(f"[deep] Content length: {len(content)} chars, citations: {len(citations)} (model={DEEP_RESEARCH_MODEL})", file=sys.stderr)
    if content:
        print(f"[deep] Content prefix: {content[:300]!r}", file=sys.stderr)
    return content, citations


def mock_deep_research(snapshot):
    """Fejlesztői mock a mély kutatáshoz — a példa jelentés alapján (NFP után)."""
    return {
        "research_date": NOW.strftime("%Y-%m-%d"),
        "daily_summary": "A gyenge júniusi NFP (+57K vs 110K) rövidtávú DXY-gyengülést és XAU rally-t hozott. De hawkish Fed + rövidített US nap miatt SÁRGA státusz tartandó.",
        "events_today": [],
        "us_market_closed": True,
        "us_market_note": "US piac ZÁRVA (Independence Day observed).",
        "is_clean_day": True,
        "clean_day_note": "Ma nincs high-impact adat — az NFP tegnap volt.",
        "bias_direction": "LONG",
        "bias_status": "SÁRGA",
        "bias_narrative": "Gyenge NFP → DXY gyengülés → XAU rövid távú long háttér. De HTF Death Cross korlátozza a felfelé teret.",
        "macro_regimes": {
            "fedwatch": {
                "value": "HOLD ~70% (júl 29) | ~80% hike szeptemberre",
                "display": "NEUTRAL → HIKE BIAS",
                "bias": "YELLOW",
                "bias_note": "69% hold júl 29-i FOMC-on, de ~80% hike szeptemberre — HAWKISH HOLD.",
            },
            "us10y": {
                "value": 4.49,
                "display": "4.49% – RISING",
                "bias": "RED",
                "bias_note": "4.48–4.51%, heti emelkedő trend; magas opportunity cost aranynak.",
            },
            "dxy": {
                "value": 100.73,
                "display": "100.73 – USD-BEAR (rövid táv)",
                "bias": "YELLOW",
                "bias_note": "NFP miss után ~100.31–100.85; a 101+ csúcsokról visszaesett.",
            },
            "sentiment": {
                "value": 30,
                "display": "30 – FEAR",
                "bias": "GREEN",
                "bias_note": "Fear & Greed 30 (Fear) — enyhén long XAU-kedvező.",
            },
            "htf_trend": {
                "value": "BEARISH",
                "display": "BEARISH (Death Cross)",
                "bias": "RED",
                "bias_note": "Death Cross aktív (50-SMA < 200-SMA); ár az összes major SMA alatt.",
            },
            "intraday_regime": {
                "value": "RECOVERY BOUNCE",
                "display": "RECOVERY BOUNCE",
                "bias": "YELLOW",
                "bias_note": "NFP után bullish impulzus, de ellenállás a 21-SMA (~$4,176) zónában.",
            },
            "volatility": {
                "value": "ELEVATED",
                "display": "ELEVATED",
                "bias": "YELLOW",
                "bias_note": "Post-NFP amplitúdó + rövidített US nap = alacsonyabb likviditás, tágabb spread.",
            },
        },
        "key_levels": {
            "pdh": 4179,
            "pdl": 4030,
            "daily_open": 4163,
            "asia_high": 4183,
            "asia_low": 4158,
            "htf_supply": "4176–4180",
            "htf_demand": "3950–3970",
            "psych_level": 4000,
        },
        "news_drivers": [
            "NFP aftershock: +57K vs 110K — nagy miss, XAU $4,060→$4,177 rally",
            "US–Irán béketárgyalások: Qatar pozitív előrehaladás — safe-haven premium csökken",
            "Warsh Fed Chair hawkish, 80% szeptemberi hike-odds",
        ],
        "no_trade_windows": [],
        "sources": [
            {"label": "BLS Employment Situation", "url": "https://www.bls.gov/news.release/empsit.nr0.htm"},
            {"label": "CME FedWatch", "url": "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"},
        ],
    }


def run_deep_research(snapshot):
    """Mély kutatás futtatása: Perplexity web search hívás vagy mock.
    Visszatér: (research_dict, source_type, model_name, citations)"""
    if MOCK:
        print("[deep] MOCK mode (nincs PPLX_API_KEY vagy MOCK_AI=true)")
        return mock_deep_research(snapshot), "ai-mock", "mock-v1", []
    try:
        system_prompt = DEEP_RESEARCH_PROMPT_PATH.read_text()
        question = (
            f"Ma: {NOW.strftime('%Y-%m-%d %H:%M CEST')} ({NOW.strftime('%A')}).\n"
            f"Aktuális snapshot (a spot/regime mezőket csak kontextusként használd, "
            f"a web search-ből frissítsd őket):\n"
            + json.dumps(snapshot, ensure_ascii=False, indent=2)
            + "\n\nVégezd el a mai napi mély makró kutatást és adj egy JSON objektumot a schéma szerint."
        )
        print(f"[deep] Perplexity {DEEP_RESEARCH_MODEL} hívás (web search)...")
        content, citations = call_perplexity_with_search(system_prompt, question)
        research = parse_ai_json(content)
        print("[deep] Sikeres mély kutatás.")
        return research, "ai", DEEP_RESEARCH_MODEL, citations
    except Exception as e:
        print(f"[deep] Éles hívás hiba, fallback mock: {e}", file=sys.stderr)
        return mock_deep_research(snapshot), "ai-fallback", f"mock-fallback ({DEEP_RESEARCH_MODEL} failed)", []


def _level_field(value):
    """Egy kulcsszint mező wrapper — source_type=ai (mély kutatás)."""
    return {
        "value": value,
        "status": "fresh" if value is not None else "pending",
        "source_type": "ai",
        "source_label": "AI mély kutatás (Perplexity)",
        "source_url": "https://www.perplexity.ai/",
        "updated_at": NOW_ISO,
    }


def _regime_field(reg, fallback_display=None, impact=4):
    """Egy macro_regime mező wrapper a deep research-ből."""
    if not isinstance(reg, dict):
        return None
    value = reg.get("value")
    return {
        "value": value,
        "display": reg.get("display") or fallback_display or (str(value) if value is not None else None),
        "bias": reg.get("bias"),
        "bias_note": reg.get("bias_note"),
        "impact": impact,
        "status": "fresh" if value is not None else "pending",
        "source_type": "ai",
        "source_label": "AI mély kutatás (Perplexity)",
        "source_url": "https://www.perplexity.ai/",
        "updated_at": NOW_ISO,
    }


def apply_deep_research(data, research, source_type, model_name, citations):
    """A mély kutatás eredményeit beírja a data.json megfelelő mezőibe.
    Frissíti: header (bias), macro regimes, levels, notrade_filters (calendar), meta."""
    if not isinstance(research, dict):
        print("[deep] research nem dict, skip apply", file=sys.stderr)
        return

    updated_count = 0

    # 1. Header bias + narrative
    header = data.get("header", {})
    if research.get("bias_direction"):
        header["bias_direction"] = research["bias_direction"]
        updated_count += 1
    if research.get("bias_status"):
        header["bias_status"] = research["bias_status"]
        updated_count += 1
    if research.get("bias_narrative"):
        header["narrative"] = research["bias_narrative"]
    if research.get("daily_summary"):
        header["fed_regime_summary"] = research["daily_summary"]
    data["header"] = header

    # 2. Macro regimes (csak a deep research-ben lévőket írjuk felül, auto-jegyeket nem bántjuk)
    macro = data.get("macro", {})
    regimes = research.get("macro_regimes", {}) or {}
    regime_map = {
        "fedwatch": "fedwatch",
        "us10y": "us10y",
        "dxy": "dxy",
        "sentiment": "sentiment",
        "htf_trend": "htf_trend",
        "intraday_regime": "intraday_regime",
        "volatility": "volatility",
    }
    for rkey, dkey in regime_map.items():
        if rkey in regimes:
            field = _regime_field(regimes[rkey])
            if field:
                macro[dkey] = field
                updated_count += 1
    data["macro"] = macro

    # 3. Kulcsszintek (csak ahol a deep research ad értéket)
    levels = data.get("levels", {})
    kl = research.get("key_levels", {}) or {}
    for lk, dk in [
        ("pdh", "pdh"), ("pdl", "pdl"), ("daily_open", "daily_open"),
        ("asia_high", "asia_high"), ("asia_low", "asia_low"),
        ("htf_supply", "htf_supply"), ("htf_demand", "htf_demand"),
        ("psych_level", "psych_level"),
    ]:
        if lk in kl and kl[lk] is not None:
            levels[dk] = _level_field(kl[lk])
            updated_count += 1
    data["levels"] = levels

    # 4. Naptár + no_trade_windows (a deep research-ből, elavult tisztítással)
    nt = apply_calendar_cleanup(data.get("notrade_filters", {}), research)
    data["notrade_filters"] = nt
    updated_count += 1

    # 5. Meta
    meta = data.get("meta", {})
    meta["deep_research_last_run"] = NOW_ISO
    meta["deep_research_model"] = model_name
    meta["deep_research_source_type"] = source_type
    meta["deep_research_citations"] = len(citations) if citations else 0
    data["meta"] = meta

    print(f"[deep] {updated_count} mező frissítve a mély kutatásból (source={source_type}).")
    return updated_count
    # 5. Friss napi kutatás dedikált blokkba — a setup-hívás EBBŐL olvas,
    #    így sosem a tegnapi bagira.key_watch cirkulál vissza.
    data["daily_research"] = {
        "research_date": research.get("research_date") or NOW.strftime("%Y-%m-%d"),
        "daily_summary": research.get("daily_summary"),
        "bias_narrative": research.get("bias_narrative"),
        "news_drivers": research.get("news_drivers") or [],
        "us_market_closed": research.get("us_market_closed", False),
        "us_market_note": research.get("us_market_note", ""),
        "is_clean_day": research.get("is_clean_day"),
        "clean_day_note": research.get("clean_day_note", ""),
        "source_type": source_type,
        "updated_at": NOW_ISO,
    }
    updated_count += 1
         
def apply_calendar_cleanup(existing_nt, research):
    """Naptár tisztítás + frissítés a deep research alapján.
    - Törli a tegnapi/lejárt eseményeket (dátum ellenőrzés).
    - Ha a research ma tiszta napot jelez (events_today=[]), törli a windows-t.
    - US piacpihenőnap jelölése."""
    today_str = NOW.strftime("%Y-%m-%d")
    nt = dict(existing_nt) if isinstance(existing_nt, dict) else {}

    # Deep research adatok felülírják
    events_today = research.get("events_today", [])
    if events_today is None:
        events_today = []
    no_trade_windows = research.get("no_trade_windows", [])
    if no_trade_windows is None:
        no_trade_windows = []

    nt["macro_events_today"] = events_today
    nt["macro_no_trade_windows"] = no_trade_windows

    # Lock aktív-e MOST (a mai windows alapján)
    now_hm = NOW.strftime("%H:%M")
    lock_active = False
    for w in no_trade_windows:
        try:
            if w.get("start", "") <= now_hm <= w.get("end", ""):
                lock_active = True
                break
        except Exception:
            continue
    nt["macro_lock_active"] = lock_active

    # US piacpihenőnap jelölése
    if research.get("us_market_closed"):
        nt["us_market_closed"] = True
        nt["us_market_note"] = research.get("us_market_note", "US piac zárva.")
    else:
        nt["us_market_closed"] = False
        nt["us_market_note"] = research.get("us_market_note", "US piac nyitva.")

    # Clean day jelölés
    nt["is_clean_day"] = research.get("is_clean_day", len(events_today) == 0)
    nt["clean_day_note"] = research.get("clean_day_note", "")
    nt["updated_at"] = NOW_ISO
    nt["source_label"] = "AI mély kutatás (Perplexity)"
    return nt


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

    # ═══ NAPI MÉLY KUTATÁS — frissíti a bias/naptár/rezsim/szinteket ═══
    # A setup elemzés ELŐTT fut, hogy a setup prompt már a frissített
    # makró kontextust lássa (pl. helyes bias, tiszta naptár).
    print("[ai] ═══ Napi mély kutatás indítása ═══")
    try:
        research, dr_source, dr_model, dr_citations = run_deep_research(snapshot)
        apply_deep_research(data, research, dr_source, dr_model, dr_citations)
        # Ha a deep research frissítette a bias-t/naptárt, a snapshot-t újraépítjük
        snapshot = build_snapshot(data)
    except Exception as e:
        print(f"[ai] Mély kutatás hiba (folytatódik setup elemzés nélküle): {e}", file=sys.stderr)

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
