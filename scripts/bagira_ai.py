"""
FÁZIS 4 — Bagira AI Setup Engine (v2).

Az AI a dashboard TELJES állapotát megkapja (makró, szintek, risk, trade log),
mély webkutatást végez (hírek, blogok, technikai elemzések), majd profi XAU
day-trader logikával SETUP A és SETUP B javaslatot ad (1 SHORT + 1 LONG).

Minőségi kapu:
- Az AI 1–100 skálán önértékeli a saját javaslatát (self-review kör).
- A legjobb érvényes javaslat MINDIG publikálódik a dashboardra:
  - 95+ önértékelés → SUGGESTED (CONFIRM & TRADE elérhető)
  - 95 alatt → LOCKED, tájékoztató setup az önértékelés kiírásával
- Csak a strukturálisan hibás javaslat (értelmezhetetlen/inkonzisztens
  árszintek) marad ki — nincs kitalált érték a dashboardon.

Kockázati garancia (a tér szabálya szerint):
- A végső allowed/locked döntés TOVÁBBRA IS szabályalapú:
  az assemble_state.evaluate_setup() hard lockjai felülírják az AI-t.
- Python-oldali sanity check: ár-realitás (spot ±3%), irány-konzisztencia,
  RR újraszámolása a számokból (nem az AI állításából), score = 5×(0–2) összeg.
- Az AI SOHA nem állít be confirmed=True értéket — a chart-megerősítés
  a felhasználóé (CONFIRM & TRADE gomb).
"""
import os, re, sys, json, urllib.request
from pathlib import Path
from common import load_json, save_json, now_cest, STATE_PATH
from assemble_state import evaluate_setup

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name, fallback):
    """System prompt betöltése a prompts/ mappából — kód nélkül szerkeszthető."""
    try:
        txt = (PROMPTS_DIR / name).read_text(encoding="utf-8").strip()
        return txt if txt else fallback
    except Exception:
        return fallback

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
        "now_cest": now_cest(),
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


RESEARCH_SYSTEM = load_prompt("bagira_research_prompt.md", (
    "Profi XAU/USD (arany) day-trader kutatóasszisztens vagy. Keress a weben "
    "friss, mai/legutóbbi forrásokat: Reuters, CNBC, MarketWatch, Investing.com, "
    "Kitco, FXStreet, TradingView elemzések. Tömör, tényszerű, forrás-URL-ekkel."
))


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


GENERATE_SYSTEM = load_prompt("bagira_generate_prompt.md", (
    "Profi XAU:CFD day-trader és kockázatkezelő vagy (Bagira). A legmagasabb "
    "szintű pénzügyi és technikai elemzési tudásodat használod. Kizárólag a "
    "megadott dashboard-adatokból és a kutatási összefoglalóból dolgozol — "
    "SOHA nem találsz ki árszintet. Minden számnak konzisztensnek kell lennie "
    "a spot árral és a megadott szintekkel. Csak JSON-nal válaszolj."
))


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


REVIEW_SYSTEM = load_prompt("bagira_review_prompt.md", (
    "Könyörtelen XAU kockázatkezelő auditor vagy. A feladatod a setup-javaslat "
    "hibáinak megtalálása. Szigorúan pontozol: 95+ csak akkor, ha minden szint "
    "realisztikus, az RR matek stimmel, a makró-narratíva konzisztens és nincs "
    "nyitott kockázati kérdés. Csak JSON-nal válaszolj."
))


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
    """Visszaadja a (hard_hibák, soft_figyelmeztetések, normalizált_setup) hármast.

    hard: strukturális hiba — a javaslat NEM publikálható (értelmezhetetlen számok).
    soft: szabály-szintű gyengeség (pl. RR < 2) — publikálható, de a rule-lock zárolja.
    """
    hard, soft = [], []
    direction = (s.get("direction") or "").upper()
    if direction not in ("LONG", "SHORT"):
        hard.append(f"Setup {key}: érvénytelen irány ({direction})")

    entry = parse_price(s.get("entry_zone"))
    sl = parse_price(s.get("sl"))
    tp1 = parse_price(s.get("tp1"))
    if entry is None or sl is None or tp1 is None:
        hard.append(f"Setup {key}: hiányzó/értelmezhetetlen entry/SL/TP1")
        return hard, soft, s

    if direction == "LONG" and not (sl < entry < tp1):
        hard.append(f"Setup {key}: LONG szintek inkonzisztensek (SL<entry<TP1 kell)")
    if direction == "SHORT" and not (tp1 < entry < sl):
        hard.append(f"Setup {key}: SHORT szintek inkonzisztensek (TP1<entry<SL kell)")

    risk = abs(entry - sl)
    if risk <= 0:
        hard.append(f"Setup {key}: nulla SL távolság")
        return hard, soft, s
    rr = round(abs(tp1 - entry) / risk, 2)
    if rr < 2.0:
        soft.append(f"Setup {key}: számolt RR {rr} < 2.0 — szabály szerint zárolva")
    s["rr_min"] = rr

    if spot:
        dev = abs(entry - spot) / spot
        if dev > SPOT_TOLERANCE:
            hard.append(
                f"Setup {key}: belépő ({entry}) túl messze a spottól "
                f"({spot}, eltérés {dev:.1%} > {SPOT_TOLERANCE:.0%})")

    comps = s.get("score_components") or {}
    score = 0
    for ck in COMPONENT_KEYS:
        cv = comps.get(ck)
        if not isinstance(cv, (int, float)) or not (0 <= cv <= 2):
            soft.append(f"Setup {key}: score komponens hibás ({ck}={cv})")
            cv = 0
        score += int(cv)
    s["score"] = max(0, min(10, score))

    if not s.get("session"):
        soft.append(f"Setup {key}: hiányzó session")
    if not s.get("invalidation"):
        soft.append(f"Setup {key}: hiányzó invalidáció")
    return hard, soft, s


def sanity_check(proposal, spot):
    hard, soft = [], []
    setups = proposal.get("setups") or {}
    if set(setups.keys()) < {"A", "B"}:
        return ["Hiányzó Setup A vagy B"], [], proposal
    dirs = sorted((setups[k].get("direction") or "").upper() for k in ("A", "B"))
    if dirs != ["LONG", "SHORT"]:
        hard.append("Pontosan 1 LONG és 1 SHORT setup kell")
    for key in ("A", "B"):
        h, sft, setups[key] = sanity_check_setup(key, setups[key], spot)
        hard.extend(h)
        soft.extend(sft)
    if not proposal.get("narrative"):
        soft.append("Hiányzó narratíva")
    return hard, soft, proposal


# ────────────────────────────────────────────────────────────────────
# Eredmény beírás
# ────────────────────────────────────────────────────────────────────
def apply_proposal(state, proposal, self_score, iterations, sources, weaknesses=None):
    """A legjobb érvényes javaslatot beírja — allowed TOVÁBBRA IS szabályalapú.

    95+ önértékelés: SUGGESTED (CONFIRM & TRADE elérhető, ha a szabály engedi).
    95 alatt: LOCKED, tájékoztató setup — az önértékelés a zárolási okban.
    """
    gate_passed = self_score >= QUALITY_GATE
    effective = state.get("header", {}).get("effective_mode", "YELLOW")
    macro_lock = bool(state.get("header", {}).get("macro_lock_active"))
    open_xau = (state.get("risk", {}) or {}).get("open_xau_positions", 0) or 0

    wrapped = {}
    for key in ("A", "B"):
        body = dict(proposal["setups"][key])
        body["confirmed"] = "pending"     # a chart-megerősítés a felhasználóé
        body["setup_ready"] = False
        allowed, reason = evaluate_setup(body, effective, macro_lock, open_xau)
        body["updated_at"] = now_cest()

        # would_allow: minden hard feltétel OK, csak a megerősítés hiányzik
        probe = dict(body)
        probe["confirmed"] = True
        probe["setup_ready"] = True
        would_allow, _ = evaluate_setup(probe, effective, macro_lock, open_xau)

        if gate_passed:
            body["allowed"] = allowed
            body["locked_reason"] = reason
            if not allowed and would_allow:
                ai_state = "SUGGESTED"
                body["locked_reason"] = "Chart megerősítés szükséges (CONFIRM & TRADE)"
            else:
                ai_state = "SUGGESTED" if allowed else "LOCKED"
        else:
            # Kapu alatt: mindig zárolt, tájékoztató setup — engedély SOHA
            ai_state = "LOCKED"
            body["allowed"] = False
            gate_txt = f"AI önértékelés {self_score}/100 < {QUALITY_GATE} — tájékoztató setup"
            if not would_allow and reason:
                body["locked_reason"] = f"{gate_txt} • {reason}"
            else:
                body["locked_reason"] = gate_txt

        wrapped[key] = {
            "ai_state": ai_state,
            "source_type": "ai",
            "ai_self_score": self_score,
            "ai_gate_passed": gate_passed,
            "value": body,
        }

    narrative = proposal.get("narrative", "")
    if not gate_passed:
        top = "; ".join((weaknesses or [])[:3])
        narrative = (
            f"⚠️ Minőségi kapu alatt ({self_score}/100 < {QUALITY_GATE}) — a setupok "
            f"tájékoztató jellegűek, zárolva. " + narrative
            + (f" | Fő gyengeségek: {top}" if top else ""))

    state["setups"] = wrapped
    state["bagira"] = {
        "narrative": narrative,
        "key_watch": proposal.get("key_watch", []),
        "reasoning_summary": proposal.get("reasoning_summary", {}),
        "confidence": self_score,
        "ai_self_score": self_score,
        "ai_gate_passed": gate_passed,
        "ai_iterations": iterations,
        "sources": sources[:10],
        "model": MODEL, "source_type": "ai", "updated_at": now_cest(),
    }
    state["meta"]["ai_model"] = MODEL
    state["meta"]["ai_source_type"] = "ai"
    state["meta"]["ai_last_run"] = now_cest()
    state["meta"]["ai_self_score"] = self_score


def apply_gate_failure(state, best_score, weaknesses, iterations):
    """Nincs strukturálisan érvényes javaslat — a setupok NEM frissülnek."""
    top = "; ".join(weaknesses[:3]) if weaknesses else "n/a"
    state["bagira"] = {
        "narrative": (
            f"⚠️ Az AI nem tudott strukturálisan érvényes setupot adni "
            f"({iterations} iteráció, legjobb önértékelés: {best_score}/100). "
            f"A setupok nem frissültek — a korábbi/zárolt állapot érvényes. "
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

    best = None  # legjobb érvényes javaslat: (score, proposal, weaknesses)
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

        hard_errors, soft_warnings, proposal = sanity_check(proposal, spot)
        if hard_errors:
            print(f"  Sanity check HARD hibák (nem publikálható): {hard_errors}")
            feedback = hard_errors + soft_warnings
            best_weaknesses = best_weaknesses or feedback
            continue
        if soft_warnings:
            print(f"  Sanity soft figyelmeztetések: {soft_warnings}")

        print(f"[{i}/{MAX_ITERATIONS}] Önellenőrzés (audit)…")
        raw_rev, _ = call_perplexity(
            REVIEW_SYSTEM, build_review_prompt(state, research, proposal),
            temperature=0.1)
        review = parse_json_block(raw_rev) or {}
        self_score = review.get("self_score")
        if not isinstance(self_score, (int, float)):
            self_score = 0
        self_score = int(self_score)
        weaknesses = (review.get("weaknesses") or []) + soft_warnings
        print(f"  Önértékelés: {self_score}/100, verdict: {review.get('verdict')}")

        if best is None or self_score > best_score:
            best = (self_score, proposal, weaknesses)
            best_score, best_weaknesses = self_score, weaknesses

        if self_score >= QUALITY_GATE:
            apply_proposal(state, proposal, self_score, i, all_sources)
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

    if best is not None:
        score, proposal, weaknesses = best
        apply_proposal(state, proposal, score, MAX_ITERATIONS, all_sources, weaknesses)
        print(f"⚠️ Kapu alatt publikálva ({score}/{QUALITY_GATE}) — tájékoztató, zárolt setupok.")
        return True

    apply_gate_failure(state, best_score, best_weaknesses, MAX_ITERATIONS)
    print(f"⛔ Nincs strukturálisan érvényes javaslat — setupok nem frissültek.")
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
