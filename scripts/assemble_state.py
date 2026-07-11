"""
FÁZIS 3 — Állapot összeállítás.
A build_state.json makró + risk + level adataiból kiszámolja:
- daily_status (döntési fa)
- effective_mode = max(daily_status, risk.mode)
- setup A/B váz + engedélyezési logika (score/RR/lock)
Bagira NARRATÍVA még NEM készül itt — az a bagira-ai lépés.
"""
import sys
from common import (load_json, save_json, now_cest, mode_num, mode_label,
                    STATE_PATH)

RED, YELLOW, GREEN = "RED", "YELLOW", "GREEN"


def val(f):
    return (f or {}).get("value")


def bias(f):
    return (f or {}).get("bias", YELLOW)


def compute_daily_status(macro, risk):
    dl = risk.get("daily_loss", 0) or 0
    wl = risk.get("weekly_loss", 0) or 0
    ls = risk.get("loss_streak", 0) or 0

    # RED feltételek
    if dl >= 100 or wl >= 300 or ls >= 3:
        return RED
    fed, dxy, us10y = bias(macro.get("fedwatch")), bias(macro.get("dxy")), bias(macro.get("us10y"))
    if fed == RED and dxy == RED and us10y == RED:
        return RED

    # YELLOW feltételek
    biases = [bias(macro.get(k)) for k in ("fedwatch", "us10y", "dxy", "sentiment")]
    if RED in biases or YELLOW in biases:
        return YELLOW
    if ls == 2 or 50 <= dl < 100:
        return YELLOW

    return GREEN


def evaluate_setup(setup, effective, macro_lock, open_xau):
    score = setup.get("score")
    rr = setup.get("rr_min", 0) or 0
    confirmed = setup.get("confirmed") is True

    if effective == RED:
        return False, "RED / NO-TRADE állapot"
    if macro_lock:
        return False, "Makró tiltási ablak aktív"
    if open_xau and open_xau >= 1:
        return False, "Már van nyitott XAU pozíció"
    if rr < 2.0:
        return False, "RR 1:2 alatt"
    if score is None:
        return False, "Score nem meghatározható"
    if effective == GREEN:
        if score >= 6 and rr >= 2.0 and (confirmed or setup.get("setup_ready")):
            return True, None
        return False, "GREEN küszöb (score>=6 + megerősítés) nem teljesül"
    if effective == YELLOW:
        if score >= 8 and rr >= 2.0 and confirmed:
            return True, None
        return False, "YELLOW napon score>=8 + chart megerősítés kötelező"
    return False, "Ismeretlen mód"


def main():
    state = load_json(STATE_PATH)
    macro = state.get("macro", {})
    risk = state.get("risk_prev", {}) or {}
    header = state.get("header", {})

    daily_status = compute_daily_status(macro, risk)
    risk_mode = risk.get("mode", GREEN)
    effective = mode_label(max(mode_num(daily_status), mode_num(risk_mode)))

    macro_lock = bool(header.get("macro_no_trade_windows"))
    open_xau = risk.get("open_xau_positions", 0) or 0

    # Setup vázak (a konkrét árszinteket a manuális/AI réteg finomítja)
    setups = state.get("setups", {
        "A": {"direction": "SHORT", "type": "HTF sell zóna reakció",
              "rr_min": 2.0, "score": None, "confirmed": "pending",
              "session": "London 09:00–12:00 CEST"},
        "B": {"direction": "SHORT", "type": "Intraday range breakdown",
              "rr_min": 2.0, "score": None, "confirmed": "pending",
              "session": "London / Overlap"},
    })
    for key in ("A", "B"):
        allowed, reason = evaluate_setup(setups[key], effective, macro_lock, open_xau)
        setups[key]["allowed"] = allowed
        setups[key]["locked_reason"] = reason
        setups[key]["updated_at"] = now_cest()

    state["header"]["daily_status"] = daily_status
    state["header"]["effective_mode"] = effective
    state["header"]["macro_lock_active"] = macro_lock
    state["risk"] = dict(risk)
    state["risk"]["mode"] = risk_mode
    state["setups"] = setups
    state["meta"]["effective_mode"] = effective
    state["meta"]["assembled_at"] = now_cest()

    save_json(STATE_PATH, state)
    print(f"assemble-state OK — daily={daily_status}, effective={effective}, lock={macro_lock}")


if __name__ == "__main__":
    sys.exit(main())
