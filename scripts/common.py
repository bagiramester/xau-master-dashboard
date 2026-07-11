"""
Közös segédfüggvények az XAU Master Dashboard frissítő pipeline-hoz.
Minden script ezt használja: data.json olvasás/írás, CEST idő, mező-provenance.
"""
import json, os
from datetime import datetime, timezone, timedelta

CEST = timezone(timedelta(hours=2))  # Európa/Budapest nyári idő
DATA_PATH = os.environ.get("DATA_PATH", "data.json")
STATE_PATH = os.environ.get("STATE_PATH", "build_state.json")

# Kritikus mezők: ezek hiánya (előző érték nélkül) megállítja az AI lépést
CRITICAL_FIELDS = ["fedwatch", "us10y", "dxy"]
CRITICAL_HEADER = ["xau_spot"]


def now_cest():
    return datetime.now(CEST).isoformat(timespec="seconds")


def today_cest():
    return datetime.now(CEST).strftime("%Y-%m-%d")


def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def field(value, status="fresh", source_type="auto", source_label="", source_url=None,
          bias=None, impact=None):
    """Egységes mező-objektum provenance-szel."""
    d = {
        "value": value,
        "status": status,
        "source_type": source_type,
        "source_label": source_label,
        "updated_at": now_cest(),
    }
    if source_url is not None:
        d["source_url"] = source_url
    if bias is not None:
        d["bias"] = bias
    if impact is not None:
        d["impact"] = impact
    return d


def keep_previous(prev_field, reason="forrás nem elérhető"):
    """Előző értéket tartja meg, stale + figyelmeztető jelöléssel."""
    if not prev_field:
        return field(None, status="pending", source_label=f"⚠️ {reason}")
    f = dict(prev_field)
    f["status"] = "stale"
    f["source_label"] = f"⚠️ Előző adat – {reason}"
    return f


def mode_num(label):
    return {"GREEN": 0, "YELLOW": 1, "RED": 2}.get(label, 1)


def mode_label(num):
    return ["GREEN", "YELLOW", "RED"][max(0, min(2, num))]
