def validate_trade_log(data):
    log = data.get("trade_log", [])
    required = [
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

    for i, t in enumerate(log):
        for k in required:
            if k not in t:
                raise ValueError(f"trade_log[{i}] hiányzó mező: {k}")

        if t.get("direction") not in ("LONG", "SHORT"):
            raise ValueError(f"trade_log[{i}] direction hibás")

        if t.get("rule_compliance") not in ("igen", "részben", "nem"):
            raise ValueError(f"trade_log[{i}] rule_compliance hibás")

        if not isinstance(t.get("allowed"), bool):
            raise ValueError(f"trade_log[{i}] allowed hibás vagy hiányzik")

        if isinstance(t.get("risk_usd"), (int, float)) and t["risk_usd"] > 30:
            raise ValueError(f"trade_log[{i}] risk_usd > 30 USD (hard cap)")

    print(f"[validate] trade_log OK ({len(log)} bejegyzés)")
