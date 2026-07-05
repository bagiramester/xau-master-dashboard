#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone

DATAFILE = "data.json"

REQUIRED = [
    "datetime",
    "session",
    "direction",
    "setup_type",
    "entry",
    "sl",
    "exit",
    "risk_usd",
    "pl_usd",
    "rr_actual",
    "score",
    "allowed",
    "rule_compliance",
]


def fail(msg):
    print(f"[append_trade] ERROR: {msg}")
    sys.exit(1)


def num(x, name):
    try:
        return float(x)
    except Exception:
        fail(f"{name} must be numeric")


def main():
    raw = os.environ.get("TRADEJSON", "").strip()
    if not raw:
        fail("TRADEJSON missing")

    try:
        trade = json.loads(raw)
    except Exception as e:
        fail(f"invalid TRADEJSON: {e}")

    for k in REQUIRED:
        if k not in trade:
            fail(f"missing field: {k}")

    if trade["direction"] not in ("LONG", "SHORT"):
        fail("direction must be LONG or SHORT")

    if trade["rule_compliance"] not in ("igen", "részben", "nem"):
        fail("rule_compliance invalid")

    for k in ["entry", "sl", "exit", "risk_usd", "pl_usd", "rr_actual"]:
        trade[k] = round(num(trade[k], k), 2)

    trade["unit"] = round(num(trade.get("unit", 1), "unit"), 2)
    trade["score"] = int(trade.get("score", 0))

    if trade["score"] < 0 or trade["score"] > 10:
        fail("score must be 0..10")

    if trade["risk_usd"] > 30:
        fail("risk_usd exceeds 30 USD hard cap")

    trade.setdefault("instrument", "XAU:CFD")
    trade.setdefault("bias", "NEUTRAL")
    trade.setdefault("daily_status", None)
    trade.setdefault("risk_mode", None)
    trade.setdefault("note", "")

    with open(DATAFILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    log = data.setdefault("trade_log", [])
    log.append(trade)

    wins = [t for t in log if (t.get("pl_usd") or 0) > 0]
    losses = [t for t in log if (t.get("pl_usd") or 0) <= 0]
    rrs = [t.get("rr_actual") for t in log if isinstance(t.get("rr_actual"), (int, float))]

    data["performance"] = {
        "trade_count": len(log),
        "win_count": len(wins),
        "loss_count": len(losses),
        "net_pl_usd": round(sum(t.get("pl_usd") or 0 for t in log), 2),
        "avg_rr": round(sum(rrs) / len(rrs), 2) if rrs else None,
        "rule_break_count": len([t for t in log if t.get("rule_compliance") == "nem"]),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(DATAFILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[append_trade] appended. trades={len(log)} net={data['performance']['net_pl_usd']}")


if __name__ == "__main__":
    main()
