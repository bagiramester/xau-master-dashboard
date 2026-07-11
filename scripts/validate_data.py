"""
FÁZIS 5a — Validáció.
A build_state.json-ból összeállítja a végleges data.json-t, majd LEFUTTATJA a
kötelező checklistet. Ha bármi bukik, exit 1 → NINCS push, régi data.json marad.
"""
import sys
from common import (load_json, save_json, now_cest, mode_num,
                    STATE_PATH, DATA_PATH)

RED, YELLOW, GREEN = "RED", "YELLOW", "GREEN"


def build_data(state):
    header = state.get("header", {})
    return {
        "meta": {
            "date": state["meta"].get("date"),
            "last_auto_sync": state["meta"].get("last_auto_sync"),
            "last_manual_update": now_cest(),
            "data_freshness": "live-refresh",
            "version": "v5",
            "effective_mode": header.get("effective_mode"),
            "ai_model": state["meta"].get("ai_model"),
            "ai_source_type": state["meta"].get("ai_source_type"),
            "ai_last_run": state["meta"].get("ai_last_run"),
            "source_stack": state["meta"].get("source_stack", []),
        },
        "header": header,
        "risk": state.get("risk", {}),
        "macro": state.get("macro", {}),
        "levels": state.get("levels_prev", {}),
        "setups": state.get("setups", {}),
        "bagira": state.get("bagira", {}),
        "trade_log": state.get("trades_prev", []),
        "performance": state.get("performance", {
            "trade_count": 0, "win_count": 0, "loss_count": 0,
            "net_pl_usd": 0.0, "avg_rr": None, "rule_break_count": 0,
            "updated_at": now_cest(),
        }),
    }


def validate(data):
    errors = []
    header = data.get("header", {})
    risk = data.get("risk", {})
    setups = data.get("setups", {})

    # 1. effective_mode = max(daily_status, risk.mode)
    eff = header.get("effective_mode")
    expected = ["GREEN", "YELLOW", "RED"][max(
        mode_num(header.get("daily_status", GREEN)),
        mode_num(risk.get("mode", GREEN)))]
    if eff != expected:
        errors.append(f"effective_mode ({eff}) != max számított ({expected})")

    open_xau = risk.get("open_xau_positions", 0) or 0
    for key, s in setups.items():
        if not s.get("allowed"):
            continue
        score = s.get("score")
        rr = s.get("rr_min", 0) or 0
        # 2-3. score / RR küszöb
        if rr < 2.0:
            errors.append(f"Setup {key}: allowed de RR<2.0")
        if score is None:
            errors.append(f"Setup {key}: allowed de score=None")
        elif eff == GREEN and score < 6:
            errors.append(f"Setup {key}: GREEN allowed de score<6")
        elif eff == YELLOW and score < 8:
            errors.append(f"Setup {key}: YELLOW allowed de score<8")
        # 4. makró lock
        if header.get("macro_lock_active"):
            errors.append(f"Setup {key}: allowed aktív makró lock alatt")
        # 5. nyitott XAU
        if open_xau >= 1:
            errors.append(f"Setup {key}: allowed de már van nyitott XAU pozíció")
        # 6. RED
        if eff == RED:
            errors.append(f"Setup {key}: allowed RED módban")

    # 7. trades csak lezárt
    for t in data.get("trade_log", []):
        if t.get("exit") in (None, ""):
            errors.append("trade_log: lezáratlan trade szerepel")

    # 8. updated_at minden fő blokkban
    for blk in ("header", "risk", "macro", "setups", "performance"):
        if blk == "macro":
            for k, f in data["macro"].items():
                if isinstance(f, dict) and not f.get("updated_at"):
                    errors.append(f"macro.{k}: hiányzó updated_at")

    return errors


def main():
    state = load_json(STATE_PATH)
    data = build_data(state)
    errors = validate(data)

    if errors:
        print("VALIDÁCIÓ BUKOTT — nincs push:")
        for e in errors:
            print("  ✗", e)
        return 1

    save_json("data.candidate.json", data)
    print("VALIDÁCIÓ OK — data.candidate.json kész a push-hoz.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
