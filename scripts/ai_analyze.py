#!/usr/bin/env python3
"""
Bagira XAU AI Analyzer — Deep Research + Setup Analyst pipeline.

Bemenet:
- data.json
- cache/*.json (calendar, fedwatch, intraday)

Kimenet:
- daily_research v3 mentése data.json-ba
- setups A/B
- bagira narrative / key_watch / confidence / reasoning_summary
- score_breakdown / conflicts_resolved
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

MODEL = os.getenv("PPLX_ANALYST_MODEL", os.getenv("PPLX_MODEL", "sonar-pro"))
DEEP_RESEARCH_MODEL = os.getenv("PPLX_DEEP_MODEL", os.getenv("PPLX_MODEL", "sonar-pro"))
API_URL = "https://api.perplexity.ai/chat/completions"


def load_json(path, default=None):
    if not path.exists():
        return default
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ai] load hiba: {path}: {e}", file=sys.stderr)
        return default


def get_val(field, key="value"):
    if isinstance(field, dict):
        return field.get(key)
    return field


def last_n_trades(data, n=5):
    log = data.get("trade_log", [])
    if not isinstance(log, list):
        return []
    return log[-n:]


def build_snapshot(data):
    """Kompakt piaci állapot összeállítása a prompt bemenetére."""
    macro = data.get("macro", {})
    levels = data.get("levels", {})
    risk = data.get("risk", {})
    notrade = data.get("notrade_filters", {})
    header = data.get("header", {})

    calendar = load_json(CACHE_DIR / "calendar.json", {})
    fedwatch_cache = load_json(CACHE_DIR / "fedwatch.json", {})
    intraday = load_json(CACHE_DIR / "intraday.json", {})

    dr = data.get("daily_research", {}) if isinstance(data.get("daily_research"), dict) else {}
    dr_interpretation = dr.get("interpretation", {}) if isinstance(dr.get("interpretation"), dict) else {}
    dr_calendar = dr.get("calendar", {}) if isinstance(dr.get("calendar"), dict) else {}
    dr_facts = dr.get("facts", {}) if isinstance(dr.get("facts"), dict) else {}
    dr_data_quality = dr.get("data_quality", {}) if isinstance(dr.get("data_quality"), dict) else {}

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
            "real_yield": {
                "value": get_val(macro.get("real_yield")),
                "display": get_val(macro.get("real_yield"), "display"),
                "bias": get_val(macro.get("real_yield"), "bias"),
                "note": get_val(macro.get("real_yield"), "bias_note"),
            },
            "fedwatch": {
                "regime": get_val(macro.get("fedwatch")) or fedwatch_cache.get("regime"),
                "bias": get_val(macro.get("fedwatch"), "bias") or fedwatch_cache.get("bias"),
                "display": get_val(macro.get("fedwatch"), "display") or fedwatch_cache.get("display"),
                "note": get_val(macro.get("fedwatch"), "bias_note") or fedwatch_cache.get("note"),
            },
            "fear_greed": {
                "value": get_val(macro.get("sentiment")),
                "display": get_val(macro.get("sentiment"), "display"),
                "bias": get_val(macro.get("sentiment"), "bias"),
            },
            "cot": macro.get("cot") or {},
            "htf_trend": get_val(macro.get("htf_trend")),
            "intraday_regime": intraday.get("intraday_regime") or get_val(macro.get("intraday_regime")),
            "volatility": intraday.get("volatility_regime") or get_val(macro.get("volatility")),
            "atr_15m": intraday.get("atr_15m"),
        },
        "notrade": {
            "macro_lock_active": (
                calendar.get("macro_lock_active")
                if calendar.get("macro_events_today")
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
        "daily_research": {
            "research_date": dr.get("research_date") or data.get("meta", {}).get("deep_research_last_run"),
            "generated_at_cest": dr.get("generated_at_cest") or NOW.strftime("%Y-%m-%d %H:%M"),
            "daily_summary": dr.get("daily_summary") or header.get("fed_regime_summary"),
            "bias_direction": dr_interpretation.get("bias_direction") or header.get("bias_direction"),
            "bias_status": dr_interpretation.get("bias_status") or header.get("bias_status"),
            "bias_narrative": dr_interpretation.get("bias_narrative") or header.get("narrative"),
            "macro_regimes": dr_interpretation.get("macro_regimes") or dr.get("macro_regimes") or {},
            "conflicts": dr_interpretation.get("conflicts") or dr.get("conflicts") or [],
            "facts": dr_facts,
            "calendar": dr_calendar or {
                "us_market_closed": notrade.get("us_market_closed"),
                "us_market_note": notrade.get("us_market_note"),
                "is_clean_day": notrade.get("is_clean_day"),
                "clean_day_note": notrade.get("clean_day_note"),
                "events_today": notrade.get("macro_events_today", []),
                "yesterday_drivers": [],
                "no_trade_windows": notrade.get("macro_no_trade_windows", []),
            },
            "news_drivers": dr.get("news_drivers") or [],
            "data_quality": dr_data_quality or {
                "tier1_all_fresh": True,
                "stale_fields": [],
                "confidence_note": None,
            },
        },
        "recent_trades": last_n_trades(data, 5),
    }


def call_perplexity(system_prompt, user_snapshot):
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
            {
                "role": "user",
                "content": "Bemenet (az összes aktuális adat + napi mély kutatás):\n"
                + json.dumps(user_snapshot, ensure_ascii=False, indent=2)
                + "\n\nVégezd el a setup elemzést és finomítást, adj egy JSON objektumot a schéma szerint.",
            },
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
    resp = r.json()
    msg = resp["choices"][0]["message"]
    content = msg.get("content") or ""
    if not content and msg.get("reasoning_content"):
        content = msg["reasoning_content"]
        print("[ai] Using reasoning_content fallback", file=sys.stderr)
    print(f"[ai] Content length: {len(content)} chars (model={MODEL})", file=sys.stderr)
    if content:
        print(f"[ai] Content prefix: {content[:300]!r}", file=sys.stderr)
        print(f"[ai] Content suffix: {content[-200:]!r}", file=sys.stderr)
    return content


def call_perplexity_with_search(system_prompt, user_question):
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
    citations = resp.get("citations") or []
    print(
        f"[deep] Content length: {len(content)} chars, citations: {len(citations)} (model={DEEP_RESEARCH_MODEL})",
        file=sys.stderr,
    )
    if content:
        print(f"[deep] Content prefix: {content[:300]!r}", file=sys.stderr)
    return content, citations


def mock_deep_research(snapshot):
    return {
        "research_date": NOW.strftime("%Y-%m-%d"),
        "generated_at_cest": NOW.strftime("%Y-%m-%d %H:%M"),
        "daily_summary": "A mai XAU-kép vegyes: a rövid távú ármozgást a makró és a likviditás együtt határozza meg.",
        "calendar": {
            "us_market_closed": False,
            "us_market_note": "US piac nyitva.",
            "is_clean_day": True,
            "clean_day_note": "Ma nincs high-impact US adat.",
            "events_today": [],
            "yesterday_drivers": [],
            "no_trade_windows": [],
        },
        "facts": {
            "spot": {"value": snapshot.get("spot"), "asof_cest": NOW.strftime("%H:%M"), "source": "snapshot", "url": ""},
            "dxy": {"value": 100.73, "prev": 100.86, "direction": "FALLING", "source": "mock", "url": ""},
            "us10y_nominal": {"value": 4.49, "prev": 4.45, "direction": "RISING", "source": "mock", "url": ""},
            "real_yield_10y": {"value": 2.20, "prev": 2.24, "direction": "FALLING", "source": "mock", "url": ""},
            "fedwatch": {"next_odds": "HOLD 70% / CUT 30%", "following_odds": "hike-bias", "source": "mock", "url": ""},
            "fear_greed": {"value": 30, "label": "FEAR", "source": "mock", "url": ""},
            "cot": {"noncommercial_net": "extreme long", "asof": NOW.strftime("%Y-%m-%d"), "source": "mock", "url": ""},
        },
        "interpretation": {
            "bias_direction": "LONG",
            "bias_status": "SÁRGA",
            "bias_narrative": "Eső reálhozam támogatja a long oldalt, de a túlzsúfolt positioning és a vegyes struktúra miatt csak szelektív long engedhető.",
            "macro_regimes": {
                "real_yield": {
                    "value": "2.20% FALLING",
                    "display": "REÁLHOZAM ESIK",
                    "bias": "GREEN",
                    "weight": "TIER-1",
                    "bias_note": "Eső reálhozam long XAU-t támogat.",
                },
                "fedwatch": {
                    "value": "HOLD 70% / hike-bias később",
                    "display": "NEUTRAL → HIKE BIAS",
                    "bias": "YELLOW",
                    "weight": "TIER-1",
                    "bias_note": "Rövid távon semleges, középtávon nem tiszta long-tailwind.",
                },
                "dxy": {
                    "value": 100.73,
                    "display": "100.73 – USD-BEAR",
                    "bias": "GREEN",
                    "weight": "TIER-1",
                    "bias_note": "Gyengülő USD rövid távon segíti az XAU-t.",
                },
                "us10y": {
                    "value": 4.49,
                    "display": "4.49% RISING",
                    "bias": "RED",
                    "weight": "TIER-2",
                    "bias_note": "Nominális hozam emelkedik, de a reálhozam a mérvadóbb.",
                },
                "sentiment": {
                    "value": 30,
                    "display": "30 – FEAR",
                    "bias": "GREEN",
                    "weight": "TIER-3",
                    "bias_note": "Fear safe-haven támogatást adhat.",
                },
                "cot": {
                    "value": "extreme long",
                    "display": "COT EXTRÉM LONG",
                    "bias": "YELLOW",
                    "weight": "TIER-3",
                    "bias_note": "A positioning túlzsúfolt, felfelé korlátozhat.",
                },
                "htf_trend": {
                    "value": "RANGE",
                    "display": "RANGE",
                    "bias": "YELLOW",
                    "weight": "STRUCTURE",
                    "bias_note": "Vegyes HTF szerkezet.",
                },
                "intraday_regime": {
                    "value": "RECOVERY BOUNCE",
                    "display": "RECOVERY BOUNCE",
                    "bias": "YELLOW",
                    "weight": "STRUCTURE",
                    "bias_note": "Rövid távú visszapattanás.",
                },
                "volatility": {
                    "value": "ELEVATED",
                    "display": "ELEVATED",
                    "bias": "YELLOW",
                    "weight": "STRUCTURE",
                    "bias_note": "Tágabb mozgás és spread.",
                },
            },
            "conflicts": [
                "Nominális US10Y emelkedik, de reálhozam esik → a reálhozam vezetőbb XAU-driver.",
            ],
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
            "Reálhozam-esés támogatja az XAU-t.",
            "DXY enyhén gyengül.",
            "COT positioning túlzsúfolt long.",
        ],
        "data_quality": {
            "tier1_all_fresh": True,
            "stale_fields": [],
            "confidence_note": "Mock adat — fejlesztői mód.",
        },
        "sources": [
            {"label": "Mock source", "url": "https://www.perplexity.ai/"},
        ],
    }


def run_deep_research(snapshot):
    if MOCK:
        print("[deep] MOCK mode (nincs PPLX_API_KEY vagy MOCK_AI=true)")
        return mock_deep_research(snapshot), "ai-mock", "mock-v1", []

    try:
        system_prompt = DEEP_RESEARCH_PROMPT_PATH.read_text(encoding="utf-8")
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
    return {
        "value": value,
        "status": "fresh" if value is not None else "pending",
        "source_type": "ai",
        "source_label": "AI mély kutatás (Perplexity)",
        "source_url": "https://www.perplexity.ai/",
        "updated_at": NOW_ISO,
    }


def _regime_field(reg, fallback_display=None, impact=4):
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
    if not isinstance(research, dict):
        print("[deep] research nem dict, skip apply", file=sys.stderr)
        return

    updated_count = 0

    interpretation = research.get("interpretation", {}) if isinstance(research.get("interpretation"), dict) else {}
    calendar = research.get("calendar", {}) if isinstance(research.get("calendar"), dict) else {}
    facts = research.get("facts", {}) if isinstance(research.get("facts"), dict) else {}
    regimes = interpretation.get("macro_regimes", {}) or research.get("macro_regimes", {}) or {}

    header = data.get("header", {})
    if interpretation.get("bias_direction"):
        header["bias_direction"] = interpretation["bias_direction"]
        updated_count += 1
    if interpretation.get("bias_status"):
        header["bias_status"] = interpretation["bias_status"]
        updated_count += 1
    if interpretation.get("bias_narrative"):
        header["narrative"] = interpretation["bias_narrative"]
    if research.get("daily_summary"):
        header["fed_regime_summary"] = research["daily_summary"]
    data["header"] = header

    macro = data.get("macro", {})
    regime_map = {
        "real_yield": "real_yield",
        "fedwatch": "fedwatch",
        "us10y": "us10y",
        "dxy": "dxy",
        "sentiment": "sentiment",
        "cot": "cot",
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

    if isinstance(facts.get("real_yield_10y"), dict) and not macro.get("real_yield"):
        ry = facts["real_yield_10y"]
        macro["real_yield"] = {
            "value": ry.get("value"),
            "display": f"{ry.get('value')} – {ry.get('direction')}" if ry.get("value") is not None else None,
            "bias": "GREEN" if str(ry.get("direction", "")).upper() == "FALLING" else "RED",
            "bias_note": "facts.real_yield_10y alapján töltve",
            "impact": 4,
            "status": "fresh" if ry.get("value") is not None else "pending",
            "source_type": "ai",
            "source_label": "AI mély kutatás (Perplexity)",
            "source_url": ry.get("url") or "https://www.perplexity.ai/",
            "updated_at": NOW_ISO,
        }
        updated_count += 1

    data["macro"] = macro

    levels = data.get("levels", {})
    kl = research.get("key_levels", {}) or {}
    for lk, dk in [
        ("pdh", "pdh"),
        ("pdl", "pdl"),
        ("daily_open", "daily_open"),
        ("asia_high", "asia_high"),
        ("asia_low", "asia_low"),
        ("htf_supply", "htf_supply"),
        ("htf_demand", "htf_demand"),
        ("psych_level", "psych_level"),
    ]:
        if lk in kl and kl[lk] is not None:
            levels[dk] = _level_field(kl[lk])
            updated_count += 1
    data["levels"] = levels

    nt = apply_calendar_cleanup(data.get("notrade_filters", {}), calendar)
    data["notrade_filters"] = nt
    updated_count += 1

    data["daily_research"] = {
        "research_date": research.get("research_date") or NOW.strftime("%Y-%m-%d"),
        "generated_at_cest": research.get("generated_at_cest") or NOW.strftime("%Y-%m-%d %H:%M"),
        "daily_summary": research.get("daily_summary"),
        "calendar": calendar,
        "facts": facts,
        "interpretation": interpretation,
        "macro_regimes": regimes,
        "conflicts": interpretation.get("conflicts") or research.get("conflicts") or [],
        "news_drivers": research.get("news_drivers") or [],
        "data_quality": research.get("data_quality") or {},
        "sources": research.get("sources") or [],
        "source_type": source_type,
        "updated_at": NOW_ISO,
    }
    updated_count += 1

    meta = data.get("meta", {})
    meta["deep_research_last_run"] = NOW_ISO
    meta["deep_research_model"] = model_name
    meta["deep_research_source_type"] = source_type
    meta["deep_research_citations"] = len(citations) if citations else 0
    data["meta"] = meta

    print(f"[deep] {updated_count} mező frissítve a mély kutatásból (source={source_type}).")
    return updated_count


def apply_calendar_cleanup(existing_nt, calendar):
    nt = dict(existing_nt) if isinstance(existing_nt, dict) else {}

    events_today = calendar.get("events_today", []) or []
    no_trade_windows = calendar.get("no_trade_windows", []) or []

    nt["macro_events_today"] = events_today
    nt["macro_no_trade_windows"] = no_trade_windows

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

    if calendar.get("us_market_closed"):
        nt["us_market_closed"] = True
        nt["us_market_note"] = calendar.get("us_market_note", "US piac zárva.")
    else:
        nt["us_market_closed"] = False
        nt["us_market_note"] = calendar.get("us_market_note", "US piac nyitva.")

    nt["is_clean_day"] = calendar.get("is_clean_day", len(events_today) == 0)
    nt["clean_day_note"] = calendar.get("clean_day_note", "")
    nt["updated_at"] = NOW_ISO
    nt["source_label"] = "AI mély kutatás (Perplexity)"
    return nt


def extract_json_from_text(text):
    import re
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if m:
        return m.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text


def parse_ai_json(text):
    import re

    json_str = extract_json_from_text(text)

    try:
        import json_repair
        repaired = json_repair.repair_json(json_str, return_objects=True)
        if isinstance(repaired, (dict, list)):
            return repaired
    except ImportError:
        print("[ai] json-repair nincs telepítve", file=sys.stderr)
    except Exception as e:
        print(f"[ai] json-repair hiba: {e}", file=sys.stderr)

    try:
        import json5
        return json5.loads(json_str)
    except ImportError:
        print("[ai] json5 nincs, regex cleanup", file=sys.stderr)
    except Exception as e:
        print(f"[ai] json5 hiba: {e}", file=sys.stderr)

    fixed = re.sub(r",\s*([\]}])", r"\1", json_str)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        print(f"[ai] Cleanup parse hiba: {e}", file=sys.stderr)
        raise ValueError(f"AI response nem parseolható. Elso 500: {json_str[:500]}")


def mock_response(snapshot):
    lock = snapshot["notrade"]["macro_lock_active"]
    real_yield_note = snapshot["macro"].get("real_yield", {}).get("note", "")
    dxy = snapshot["macro"]["dxy"].get("value") or 100

    return {
        "setup_A": {
            "direction": "LONG",
            "type": "range reversal / demand reaction",
            "bias_compatibility": "igen — LONG bias-szal egyező",
            "entry_zone": "3950-3970 demand reakció",
            "sl": "3925 alatt H1 close",
            "tp1": "4058",
            "tp2": "4176-4180",
            "rr_min": 2.1,
            "score": 8,
            "session": "London 09:00-12:00 CEST",
            "invalidation": "H1 close 3925 alatt",
            "macro_support": [
                real_yield_note or "Reálhozam esik → long háttér",
                f"DXY {dxy} → gyengülő USD segítheti az XAU-t",
                "FedWatch rövid távon nem agresszíven hawkish",
            ],
            "allowed": not lock,
            "locked_reason": "Makró tiltási ablak aktív" if lock else None,
            "entry_zone_status": "pending",
            "setup_quality": "erős",
        },
        "setup_B": {
            "direction": "SHORT",
            "type": "HTF supply rejection",
            "bias_compatibility": "részben — alternatív, ha long kifullad",
            "entry_zone": "4176-4180 rejection",
            "sl": "4205 felett M15/H1 close",
            "tp1": "4105",
            "tp2": "4058",
            "rr_min": 2.0,
            "score": 6,
            "session": "Overlap 14:00-19:00 CEST",
            "invalidation": "H1 close 4205 felett",
            "macro_support": [
                "COT extrém long → upside korlátozott lehet",
                "Csak rejection esetén érvényes",
            ],
            "allowed": False,
            "locked_reason": "Alternatív counter forgatókönyv",
            "entry_zone_status": "pending",
            "setup_quality": "közepes",
        },
        "score_breakdown": {
            "setup_A": {"trend": 1, "level": 2, "volatility": 1, "tier1_macro": 3, "rr": 1, "total": 8},
            "setup_B": {"trend": 1, "level": 2, "volatility": 1, "tier1_macro": 1, "rr": 1, "total": 6},
        },
        "conflicts_resolved": [
            "A nominális US10Y emelkedése ellenére a reálhozam esése fontosabb long-driver az XAU-nál.",
        ],
        "bagira_narrative": "A pánter long felé hajlik, de csak tiszta demand reakcióból. Ha a struktúra nem tart, nem üldözöm az árat.",
        "key_watch": [
            "3950-3970 demand zóna reakciója",
            "DXY további gyengül-e",
            "Macro lock / session likviditás",
        ],
        "confidence": 78 if not lock else 62,
        "reasoning_summary": "A Tier-1 driver-kép enyhén long, mert a reálhozam fontosabb jel, mint a nominális US10Y. A short csak supply rejection alternatíva.",
    }


def analyze():
    data = load_json(DATA_PATH)
    if not data:
        print("[ai] data.json nem található vagy hibás", file=sys.stderr)
        return None

    snapshot = build_snapshot(data)

    print("[ai] ═══ Napi mély kutatás indítása ═══")
    try:
        research, dr_source, dr_model, dr_citations = run_deep_research(snapshot)
        apply_deep_research(data, research, dr_source, dr_model, dr_citations)
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
            system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
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

    BAGIRA_KEYS = (
        "bagira_narrative",
        "confidence",
        "key_watch",
        "reasoning_summary",
        "score_breakdown",
        "conflicts_resolved",
    )

    if isinstance(result, dict):
        for k in BAGIRA_KEYS:
            if result.get(k) in (None, "", [], {}):
                for slot in ("setup_A", "setup_B"):
                    body = result.get(slot)
                    if isinstance(body, dict) and body.get(k) not in (None, "", [], {}):
                        result[k] = body[k]
                        print(f"[ai] hoist: {k} <- {slot}", file=sys.stderr)
                        break
        for slot in ("setup_A", "setup_B"):
            body = result.get(slot)
            if isinstance(body, dict):
                for k in BAGIRA_KEYS:
                    body.pop(k, None)

    sa = result.get("setup_A") or {}

    if not result.get("bagira_narrative"):
        dir_a = sa.get("direction", "—")
        score_a = sa.get("score", "—")
        qual = sa.get("setup_quality", "—")
        allowed_a = sa.get("allowed")
        if allowed_a:
            result["bagira_narrative"] = (
                f"A pánter {dir_a.lower()} setupot lát ({score_a}/10, {qual}). "
                f"Várom a megerősítést a belépési zónában — addig csendben ülök."
            )
        else:
            reason = sa.get("locked_reason") or "a mai nap nem enged trade-t"
            result["bagira_narrative"] = (
                f"A pánter figyel, de nem lép. {reason}. "
                f"A terv {dir_a.lower()} irányban készen áll, ha a lock feloldódik."
            )

    if result.get("confidence") in (None, "", 0):
        try:
            result["confidence"] = int(sa.get("score", 0)) * 10
        except Exception:
            result["confidence"] = 50

    if not result.get("key_watch"):
        kw = []
        if sa.get("entry_zone"):
            kw.append(f"Belépési zóna: {sa.get('entry_zone')}")
        if sa.get("invalidation"):
            kw.append(f"Invalidáció: {sa.get('invalidation')}")
        if not kw:
            kw.append("Makró naptár és DXY/US10Y olvasat figyelése")
        result["key_watch"] = kw

    if not result.get("conflicts_resolved"):
        result["conflicts_resolved"] = snapshot.get("daily_research", {}).get("conflicts", [])

    if not result.get("score_breakdown"):
        score_a = int(sa.get("score", 0) or 0)
        result["score_breakdown"] = {
            "setup_A": {"trend": None, "level": None, "volatility": None, "tier1_macro": None, "rr": None, "total": score_a},
            "setup_B": {"trend": None, "level": None, "volatility": None, "tier1_macro": None, "rr": None, "total": int((result.get("setup_B") or {}).get("score", 0) or 0)},
        }

    def wrap_setup(body):
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

    # SKIP_SETUPS mód: a setup + bagira írást a bagira_ai.py Setup Engine végzi
    # (95+ minőségi kapuval) — itt csak a mély kutatás (levels/bias) marad.
    if os.getenv("SKIP_SETUPS", "").lower() in ("1", "true", "yes"):
        print("[ai] SKIP_SETUPS aktív — setup/bagira írás a bagira_ai.py-ra bízva.")
    else:
        data["setups"] = {
            "A": wrap_setup(result.get("setup_A")),
            "B": wrap_setup(result.get("setup_B")),
        }
        data["bagira"] = {
            "narrative": result.get("bagira_narrative", ""),
            "key_watch": result.get("key_watch", []),
            "confidence": result.get("confidence", 0),
            "reasoning_summary": result.get("reasoning_summary", ""),
            "score_breakdown": result.get("score_breakdown", {}),
            "conflicts_resolved": result.get("conflicts_resolved", []),
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
        f.write("\n")

    print(
        f"[ai] data.json frissítve: setup_A allowed={result.get('setup_A', {}).get('allowed')}, "
        f"confidence={result.get('confidence')}, source_type={source_type}"
    )
    return result


if __name__ == "__main__":
    analyze()
