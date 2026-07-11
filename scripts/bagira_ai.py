"""
FÁZIS 4 — Bagira AI Setup Engine (v2).

Az AI a dashboard TELJES állapotát megkapja (makró, szintek, risk, trade log),
mély webkutatást végez (hírek, blogok, technikai elemzések), majd profi XAU
day-trader logikával SETUP A és SETUP B javaslatot ad (1 SHORT + 1 LONG).

Minőségi kapu:
- Az AI 1–100 skálán önértékeli a saját javaslatát (self-review kör).
- Csak QUALITY_GATE (alap: 95) feletti eredmény kerül a dashboardra.
- Ha AI_MAX_ITERATIONS alatt nem éri el, a setupok NEM frissülnek —
  nincs kitalált érték, a korábbi/zárolt állapot marad érvényben.

Kockázati garancia (a tér szabálya szerint):
- A végső allowed/locked döntés TOVÁBBRA IS szabályalapú:
  az assemble_state.evaluate_setup() hard lockjai felülírják az AI-t.
- Python-oldali sanity check: ár-realitás (spot ±3%), irány-konzisztencia,
  RR újraszámolása a számokból (nem az AI állításából), score = 5×(0–2) összeg.
- Az AI SOHA nem állít be confirmed=True értéket — a chart-megerősítés
  a felhasználóé (CONFIRM & TRADE gomb).
"""
import os, re, sys, json, urllib.request
from common import load_json, save_json, now_cest, STATE_PATH
from assemble_state import evaluate_setup

MODEL = os.environ.get("PERPLEXITY_MODEL", "sonar-pro")
API_KEY = os.environ.get("PERPLEXITY_API_KEY")
API_URL = "https://api.perplexity.ai/chat/completions"
MAX_ITERATIONS = int(os.environ.get("AI_MAX_ITERATIONS", "3"))
QUALITY_GATE = int(os.environ.get("AI_QUALITY_GATE", "95"))
SPOT_TOLERANCE = float(os.environ.get("AI_SPOT_TOLERANCE", "0.03"))  # ±3%

COMPONENT_KEYS = ("trend", "key_level", "volatility_spread", "macro", "rr_quality")


# ────────────────────────────────────────────────────────────────────
# API réteg
# ────────────────────────────────────────────────────────────────────
def call_perplexity(system, user, temperature=0.2):
    """Egy Perplexity hívás. Visszaadja a (szöveg, citations) párost."""
    payload = {
        "model": MODEL,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {API_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    citations = data.get("citations") or data.get("search_results") or []
    urls = []
    for c in citations:
        if isinstance(c, str):
            urls.append(c)
        elif isinstance(c, dict) and c.get("url"):
            urls.append(c["url"])
    return content, urls


def parse_json_block(text):
    """A válaszból kiszedi az első teljes JSON objektumot."""
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None


# ────────────────────────────────────────────────────────────────────
# Prompt építés
# ────────────────────────────────────────────────────────────────────
def dashboard_snapshot(state):
    """A teljes releváns dashboard állapot kompakt JSON-ban."""
    snap = {
        "date": state.get("meta", {}).get("date"),
        "header": {
            "xau_spot": (state.get("header", {}).get("xau_spot") or {}).get("value"),
            "daily_status": state.get("header", {}).get("daily_status"),
            "effective_mode": state.get("header", {}).get("effective_mode"),
            "macro_lock_active": state.get("header", {}).get("macro_lock_active"),
            "macro_events_today": state.get("header", {}).get("macro_events_today", []),
            "macro_no_trade_windows": state.get("header", {}).get("macro_no_trade_windows", []),
        },
        "risk": state.get("risk", {}),
        "macro": {k: {kk: vv for kk, vv in (v or {}).items()
                      if kk in ("value", "bias", "impact", "status")}
                  for k, v in state.get("macro", {}).items()},
        "levels": {k: (v or {}).get("value")
                   for k, v in (state.get("levels_prev") or state.get("levels") or {}).items()},
        "previous_setups": state.get("setups", {}),
        "recent_trades": (state.get("trades_prev") or state.get("trade_log") or [])[-10:],
        "performance": state.get("performance", {}),
    }
    return json.dumps(snap, ensure_ascii=False, indent=1)


RESEARCH_SYSTEM = (
    "Profi XAU/USD (arany) day-trader kutatóasszisztens vagy. Keress a weben "
    "friss, mai/legutóbbi forrásokat: Reuters, CNBC, MarketWatch, Investing.com, "
    "Kitco, FXStreet, TradingView elemzések. Tömör, tényszerű, forrás-URL-ekkel."
)


def build_research_prompt(state, focus_questions=None):
    spot = (state.get("header", {}).get("xau_spot") or {}).get("value")
    date = state.get("meta", {}).get("date")
    base = (
        f"Mai dátum: {date}. XAU/USD spot: {spot}.\n"
        "Végezz mély kutatást a mai arany (XAU/USD) kereskedési helyzetről:\n"
        "1. Friss hírek és piaci mozgatók (Fed, infláció, geopolitika, USD).\n"
        "2. Technikai elemzések: kulcsszintek, támasz/ellenállás, trend H4/H1/M15.\n"
        "3. Intézményi/elemzői vélemények és pozicionáltság (CFTC, ETF flow).\n"
        "4. Mai/holnapi magas impaktú makró események és várható hatásuk.\n"
        "5. TradingView / blog narratívák: merre néz a crowd?\n"
        "Adj tömör, pontokba szedett összefoglalót konkrét árszintekkel és forrásokkal."
    )
    if focus_questions:
        base += "\n\nKIEMELT PONTOSÍTANDÓ KÉRDÉSEK (előző kör hiányosságai):\n"
        base += "\n".join(f"- {q}" for q in focus_questions[:6])
    return base


GENERATE_SYSTEM = (
    "Profi XAU:CFD day-trader és kockázatkezelő vagy (Bagira). A legmagasabb "
    "szintű pénzügyi és technikai elemzési tudásodat használod. Kizárólag a "
    "megadott dashboard-adatokból és a kutatási összefoglalóból dolgozol — "
    "SOHA nem találsz ki árszintet. Minden számnak konzisztensnek kell lennie "
    "a spot árral és a megadott szintekkel. Csak JSON-nal válaszolj."
)


def build_generate_prompt(state, research, feedback=None):
    prompt = (
        "DASHBOARD TELJES ÁLLAPOTA:\n" + dashboard_snapshot(state) + "\n\n"
        "MÉLY KUTATÁS EREDMÉNYE:\n" + research[:9000] + "\n\n"
        "FELADAT: Határozz meg 2 setupot XAU:CFD-re (Revolut, 1 egység, 20x):\n"
        "- Setup A: a magasabb meggyőződésű irány (elsődleges setup).\n"
        "- Setup B: az ellenirányú alternatíva.\n"
        "- Pontosan 1 SHORT és 1 LONG legyen a kettő között.\n"
        "Szabályok: RR minimum 1:2 (TP1-ig). SL és TP kötelező. A belépőnek a "
        "spot ±3%-án belül, releváns kulcsszinten kell lennie. Session: London "
        "09:00–12:00 CEST vagy Overlap 14:00–19:00 CEST. Magas impakt makró "
        "esemény előtti 60 percben nincs belépő.\n"
        "Score komponensek (mind 0–2): trend, key_level, volatility_spread, "
        "macro, rr_quality. Légy szigorú — a gyenge komponens 0 vagy 1 pont.\n\n"
        "VÁLASZ KIZÁRÓLAG EZZEL A JSON SÉMÁVAL:\n"
        "{\n"
        ' "setups": {\n'
        '  "A": {"direction":"SHORT|LONG","type":"setup tipus","entry_zone":"pl. 4085-4095",\n'
        '   "sl":szam,"tp1":szam,"tp2":szam_vagy_null,"session":"...","invalidation":"...",\n'
        '   "macro_support":["max 3 pont"],"setup_quality":"A|B|C","bias_compatibility":"...",\n'
        '   "score_components":{"trend":0,"key_level":0,"volatility_spread":0,"macro":0,"rr_quality":0},\n'
        '   "reasoning":"1-2 mondat"},\n'
        '  "B": {ugyanaz a sema}\n'
        " },\n"
        ' "narrative": "Az elemzes lenyege: hogyan jutottal el Setup A-ig es B-ig (max 5 mondat, magyarul)",\n'
        ' "key_watch": ["max 7 kulcstenyezo"],\n'
        ' "reasoning_summary": {"setup_A":"...","setup_B":"...","risk_view":"..."}\n'
        "}"
    )
    if feedback:
        prompt += (
            "\n\nELŐZŐ KÖR HIÁNYOSSÁGAI — EZEKET KÖTELEZŐEN JAVÍTSD:\n"
            + "\n".join(f"- {w}" for w in feedback[:8])
        )
    return prompt


REVIEW_SYSTEM = (
    "Könyörtelen XAU kockázatkezelő auditor vagy. A feladatod a setup-javaslat "
    "hibáinak megtalálása. Szigorúan pontozol: 95+ csak akkor, ha minden szint "
    "realisztikus, az RR matek stimmel, a makró-narratíva konzisztens és nincs "
    "nyitott kockázati kérdés. Csak JSON-nal válaszolj."
)


def build_review_prompt(state, research, proposal):
    return (
        "DASHBOARD ÁLLAPOT:\n" + dashboard_snapshot(state) + "\n\n"
        "KUTATÁSI ÖSSZEFOGLALÓ:\n" + research[:6000] + "\n\n"
        "ELLENŐRIZENDŐ SETUP-JAVASLAT:\n" + json.dumps(proposal, ensure_ascii=False) + "\n\n"
        "Auditáld a javaslatot az alábbi szempontok szerint:\n"
        "1. Árszintek realitása (spot, PDH/PDL, HTF zónák, Asia range tükrében).\n"
        "2. RR matek helyessége (entry→SL vs entry→TP1, min 1:2).\n"
        "3. Makró konzisztencia (DXY, US10Y, FedWatch, Fear&Greed vs irány).\n"
        "4. Hír-kockázatok: van-e olyan friss esemény, ami invalidálja?\n"
        "5. Session és tiltási ablak logika.\n"
        "6. Score komponensek indokoltsága (nem túlpontozott-e).\n\n"
        "VÁLASZ JSON: {\"self_score\": 1-100, \"weaknesses\": [\"...\"], "
        "\"focus_questions\": [\"tovabbi kutatast igenylo kerdesek\"], "
        "\"verdict\": \"ACCEPT|REVISE\"}"
    )


# ────────────────────────────────────────────────────────────────────
# Python-oldali sanity check (nem bízunk az AI aritmetikájában)
# ────────────────────────────────────────────────────────────────────
def parse_price(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    nums = re.findall(r"\d+(?:[.,]\d+)?", str(v).replace(" ", ""))
    if not nums:
        return None
    vals = [float(n.replace(",", ".")) for n in nums]
    return sum(vals) / len(vals)


def sanity_check_setup(key, s, spot):
    """Visszaadja a (hibalista, normalizált_setup) párost."""
    errors = []
    direction = (s.get("direction") or "").upper()
    if direction not in ("LONG", "SHORT"):
        errors.append(f"Setup {key}: érvénytelen irány ({direction})")

    entry = parse_price(s.get("entry_zone"))
    sl = parse_price(s.get("sl"))
    tp1 = parse_price(s.get("tp1"))
    if entry is None or sl is None or tp1 is None:
        errors.append(f"Setup {key}: hiányzó/értelmezhetetlen entry/SL/TP1")
        return errors, s

    if direction == "LONG" and not (sl < entry < tp1):
        errors.append(f"Setup {key}: LONG szintek inkonzisztensek (SL<entry<TP1 kell)")
    if direction == "SHORT" and not (tp1 < entry < sl):
        errors.append(f"Setup {key}: SHORT szintek inkonzisztensek (TP1<entry<SL kell)")

    risk = abs(entry - sl)
    if risk <= 0:
        errors.append(f"Setup {key}: nulla SL távolság")
        return errors, s
    rr = round(abs(tp1 - entry) / risk, 2)
    if rr < 2.0:
        errors.append(f"Setup {key}: számolt RR {rr} < 2.0")
    s["rr_min"] = rr

    if spot:
        dev = abs(entry - spot) / spot
        if dev > SPOT_TOLERANCE:
            errors.append(
                f"Setup {key}: belépő ({entry}) túl messze a spottól "
                f"({spot}, eltérés {dev:.1%} > {SPOT_TOLERANCE:.0%})")

    comps = s.get("score_components") or {}
    score = 0
    for ck in COMPONENT_KEYS:
        cv = comps.get(ck)
        if not isinstance(cv, (int, float)) or not (0 <= cv <= 2):
            errors.append(f"Setup {key}: score komponens hibás ({ck}={cv})")
            cv = 0
        score += int(cv)
    s["score"] = max(0, min(10, score))

    if not s.get("session"):
        errors.append(f"Setup {key}: hiányzó session")
    if not s.get("invalidation"):
        errors.append(f"Setup {key}: hiányzó invalidáció")
    return errors, s


def sanity_check(proposal, spot):
    errors = []
    setups = proposal.get("setups") or {}
    if set(setups.keys()) < {"A", "B"}:
        return ["Hiányzó Setup A vagy B"], proposal
    dirs = sorted((setups[k].get("direction") or "").upper() for k in ("A", "B"))
    if dirs != ["LONG", "SHORT"]:
        errors.append("Pontosan 1 LONG és 1 SHORT setup kell")
    for key in ("A", "B"):
        errs, setups[key] = sanity_check_setup(key, setups[key], spot)
        errors.extend(errs)
    if not proposal.get("narrative"):
        errors.append("Hiányzó narratíva")
    return errors, proposal


# ────────────────────────────────────────────────────────────────────
# Eredmény beírás
# ────────────────────────────────────────────────────────────────────
def apply_accepted_proposal(state, proposal, self_score, iterations, sources):
    """A 95+ minősítésű setupokat beírja — allowed TOVÁBBRA IS szabályalapú."""
    effective = state.get("header", {}).get("effective_mode", "YELLOW")
    macro_lock = bool(state.get("header", {}).get("macro_lock_active"))
    open_xau = (state.get("risk", {}) or {}).get("open_xau_positions", 0) or 0

    wrapped = {}
    for key in ("A", "B"):
        body = dict(proposal["setups"][key])
        body["confirmed"] = "pending"     # a chart-megerősítés a felhasználóé
        body["setup_ready"] = False
        allowed, reason = evaluate_setup(body, effective, macro_lock, open_xau)
        body["allowed"] = allowed
        body["locked_reason"] = reason
        body["updated_at"] = now_cest()

        # SUGGESTED: minden hard feltétel OK, csak a megerősítés hiányzik
        probe = dict(body)
        probe["confirmed"] = True
        probe["setup_ready"] = True
        would_allow, _ = evaluate_setup(probe, effective, macro_lock, open_xau)
        if not allowed and would_allow:
            ai_state = "SUGGESTED"
            body["locked_reason"] = "Chart megerősítés szükséges (CONFIRM & TRADE)"
        else:
            ai_state = "SUGGESTED" if allowed else "LOCKED"

        wrapped[key] = {
            "ai_state": ai_state,
            "source_type": "ai",
            "ai_self_score": self_score,
            "value": body,
        }

    state["setups"] = wrapped
    state["bagira"] = {
        "narrative": proposal.get("narrative", ""),
        "key_watch": proposal.get("key_watch", []),
        "reasoning_summary": proposal.get("reasoning_summary", {}),
        "confidence": self_score,
        "ai_self_score": self_score,
        "ai_iterations": iterations,
        "sources": sources[:10],
        "model": MODEL, "source_type": "ai", "updated_at": now_cest(),
    }
    state["meta"]["ai_model"] = MODEL
    state["meta"]["ai_source_type"] = "ai"
    state["meta"]["ai_last_run"] = now_cest()
    state["meta"]["ai_self_score"] = self_score


def apply_gate_failure(state, best_score, weaknesses, iterations):
    """A minőségi kapu nem teljesült — a setupok NEM frissülnek."""
    top = "; ".join(weaknesses[:3]) if weaknesses else "n/a"
    state["bagira"] = {
        "narrative": (
            f"⚠️ AI minőségi kapu nem teljesült ({iterations} iteráció, legjobb "
            f"önértékelés: {best_score}/100, küszöb: {QUALITY_GATE}). A setupok "
            f"nem frissültek — a korábbi/zárolt állapot érvényes. "
            f"Fő hiányosságok: {top}"),
        "key_watch": [], "reasoning_summary": "",
        "confidence": best_score, "ai_self_score": best_score,
        "ai_iterations": iterations,
        "model": MODEL, "source_type": "ai-fallback", "updated_at": now_cest(),
    }
    state["meta"]["ai_source_type"] = "ai-fallback"
    state["meta"]["ai_last_run"] = now_cest()
    state["meta"]["ai_self_score"] = best_score


# ────────────────────────────────────────────────────────────────────
# Fő ciklus
# ────────────────────────────────────────────────────────────────────
def run_engine(state):
    spot = parse_price((state.get("header", {}).get("xau_spot") or {}).get("value"))
    all_sources = []

    print(f"[1/{MAX_ITERATIONS}] Mély kutatás indul…")
    research, urls = call_perplexity(
        RESEARCH_SYSTEM, build_research_prompt(state), temperature=0.2)
    all_sources.extend(urls)

    best_score, best_weaknesses = 0, []
    feedback = None

    for i in range(1, MAX_ITERATIONS + 1):
        print(f"[{i}/{MAX_ITERATIONS}] Setup generálás…")
        raw, _ = call_perplexity(
            GENERATE_SYSTEM, build_generate_prompt(state, research, feedback),
            temperature=0.3)
        proposal = parse_json_block(raw)
        if proposal is None:
            feedback = ["A válasz nem volt érvényes JSON — tartsd a sémát"]
            continue

        errors, proposal = sanity_check(proposal, spot)
        if errors:
            print(f"  Sanity check hibák: {errors}")
            feedback = errors
            best_weaknesses = best_weaknesses or errors
            continue

        print(f"[{i}/{MAX_ITERATIONS}] Önellenőrzés (audit)…")
        raw_rev, _ = call_perplexity(
            REVIEW_SYSTEM, build_review_prompt(state, research, proposal),
            temperature=0.1)
        review = parse_json_block(raw_rev) or {}
        self_score = review.get("self_score")
        if not isinstance(self_score, (int, float)):
            self_score = 0
        self_score = int(self_score)
        weaknesses = review.get("weaknesses") or []
        print(f"  Önértékelés: {self_score}/100, verdict: {review.get('verdict')}")

        if self_score > best_score:
            best_score, best_weaknesses = self_score, weaknesses

        if self_score >= QUALITY_GATE:
            apply_accepted_proposal(state, proposal, self_score, i, all_sources)
            print(f"✅ Minőségi kapu teljesült ({self_score} ≥ {QUALITY_GATE}) — setupok beírva.")
            return True

        # következő kör: célzott után-kutatás a gyenge pontokra
        feedback = weaknesses
        fq = review.get("focus_questions") or weaknesses
        if i < MAX_ITERATIONS and fq:
            print(f"[{i}/{MAX_ITERATIONS}] Célzott után-kutatás…")
            extra, urls2 = call_perplexity(
                RESEARCH_SYSTEM, build_research_prompt(state, fq), temperature=0.2)
            research = research[:6000] + "\n\nKIEGÉSZÍTŐ KUTATÁS:\n" + extra
            all_sources.extend(urls2)

    apply_gate_failure(state, best_score, best_weaknesses, MAX_ITERATIONS)
    print(f"⛔ Minőségi kapu NEM teljesült (legjobb: {best_score}/{QUALITY_GATE}).")
    return False


def main():
    state = load_json(STATE_PATH)

    if not API_KEY:
        state["bagira"] = {
            "narrative": "⚠️ Nincs PERPLEXITY_API_KEY — AI elemzés kihagyva.",
            "key_watch": [], "reasoning_summary": "", "confidence": None,
            "model": MODEL, "source_type": "ai-fallback", "updated_at": now_cest(),
        }
        state["meta"]["ai_source_type"] = "ai-fallback"
        save_json(STATE_PATH, state)
        print("bagira-ai FALLBACK — nincs API kulcs.")
        return 0

    try:
        run_engine(state)
        save_json(STATE_PATH, state)
        return 0
    except Exception as e:
        state["bagira"] = {
            "narrative": f"⚠️ AI hiba: {e}. Előző elemzés érvényes marad.",
            "key_watch": [], "reasoning_summary": "", "confidence": None,
            "model": MODEL, "source_type": "ai-fallback", "updated_at": now_cest(),
        }
        state["meta"]["ai_source_type"] = "ai-fallback"
        save_json(STATE_PATH, state)
        print("bagira-ai FALLBACK — hiba:", e)
        return 0  # nem állítjuk meg a pipeline-t; a validáció dönt


if __name__ == "__main__":
    sys.exit(main())
