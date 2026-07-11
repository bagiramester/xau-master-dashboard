"""
GATE — Kritikus adatok ellenőrzése az AI lépés előtt.
Ha bármely kritikus mező pending ÉS nincs használható előző érték,
a folyamat itt megáll (exit 1), így Bagira AI nem indul, token nem fogy.
"""
import sys
from common import load_json, STATE_PATH, CRITICAL_FIELDS, CRITICAL_HEADER


def usable(f):
    if not f:
        return False
    if f.get("value") in (None, ""):
        return False
    # stale (előző) érték elfogadható; csak pending/üres nem
    return f.get("status") in ("fresh", "stale")


def main():
    state = load_json(STATE_PATH)
    macro = state.get("macro", {})
    header = state.get("header", {})

    missing = []
    for key in CRITICAL_FIELDS:
        if not usable(macro.get(key)):
            missing.append(f"macro.{key}")
    for key in CRITICAL_HEADER:
        if not usable(header.get(key)):
            missing.append(f"header.{key}")

    if missing:
        print("GATE FAIL — hiányzó kritikus adat, AI nem indul:")
        for m in missing:
            print("  -", m)
        return 1

    print("GATE OK — minden kritikus adat rendelkezésre áll.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
