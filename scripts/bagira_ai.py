"""
FÁZIS 4 — Bagira AI elemzés.
Ez az EGYETLEN tokenköltő lépés. Csak akkor fut, ha a gate + assemble sikeres,
tehát minden bemenő adat kész (needs: assemble-state a workflow-ban).

Perplexity API hívás. Ha nincs API kulcs vagy hiba történik,
ai-fallback jelölést kap — a folyamat NEM ír kitalált értéket.
"""
import os, sys, json, urllib.request
from common import load_json, save_json, now_cest, STATE_PATH

MODEL = os.environ.get("PERPLEXITY_MODEL", "sonar-pro")
API_KEY = os.environ.get("PERPLEXITY_API_KEY")
API_URL = "https://api.perplexity.ai/chat/completions"


def build_prompt(state):
    macro = state.get("macro", {})
    header = state.get("header", {})
    setups = state.get("setups", {})
    return (
        "Te vagy Bagira, egy XAU:CFD kockázatkezelő mentor. "
        "Kizárólag a megadott adatokból dolgozz, ne találj ki értéket. "
        "Adj rövid magyar narratívát, key_watch listát, és minden setuphoz indoklást.\n\n"
        f"Effective mode: {header.get('effective_mode')}\n"
        f"Daily status: {header.get('daily_status')}\n"
        f"FedWatch: {macro.get('fedwatch', {}).get('value')}\n"
        f"US10Y: {macro.get('us10y', {}).get('value')}\n"
        f"DXY: {macro.get('dxy', {}).get('value')}\n"
        f"Fear&Greed: {macro.get('sentiment', {}).get('value')}\n"
        f"XAU spot: {header.get('xau_spot', {}).get('value')}\n"
        f"Setup A allowed: {setups.get('A', {}).get('allowed')} / {setups.get('A', {}).get('locked_reason')}\n"
        f"Setup B allowed: {setups.get('B', {}).get('allowed')} / {setups.get('B', {}).get('locked_reason')}\n\n"
        "Válasz JSON-ban: {narrative, key_watch:[], reasoning_summary, confidence:0-100}"
    )


def call_perplexity(prompt):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "Rövid, tiszta, magyar. Nincs garantált tipp."},
            {"role": "user", "content": prompt},
        ],
    }
    req = urllib.request.Request(
        API_URL, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {API_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def parse_ai(text):
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return {"narrative": text.strip()[:800], "key_watch": [],
                "reasoning_summary": "", "confidence": None}


def main():
    state = load_json(STATE_PATH)
    prompt = build_prompt(state)

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
        raw = call_perplexity(prompt)
        parsed = parse_ai(raw)
        state["bagira"] = {
            "narrative": parsed.get("narrative", ""),
            "key_watch": parsed.get("key_watch", []),
            "reasoning_summary": parsed.get("reasoning_summary", ""),
            "confidence": parsed.get("confidence"),
            "model": MODEL, "source_type": "ai", "updated_at": now_cest(),
        }
        state["meta"]["ai_model"] = MODEL
        state["meta"]["ai_source_type"] = "ai"
        state["meta"]["ai_last_run"] = now_cest()
        save_json(STATE_PATH, state)
        print("bagira-ai OK — model:", MODEL)
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
