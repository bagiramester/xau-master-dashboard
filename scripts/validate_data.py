#!/usr/bin/env python3
"""
Bagira XAU Dashboard – data.json validátor
==========================================

Kettős védelmi vonal:
  1. JSON Schema strukturális ellenőrzés (data-schema.json).
  2. Hallucináció-guard: minden sourceField value != null esetén
     status in {fresh, stale}, source_label nem üres, updated_at nem null.

Használat:
  python scripts/validate_data.py
"""

import json
import sys
from pathlib import Path

try:
    from jsonschema import Draft7Validator
except ImportError:
    print("Hianyzo fuggoseg: pip install jsonschema")
    sys.exit(1)

REPO = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO / "data-schema.json"
DATA_PATH = REPO / "data.json"

def check_hallucination(data):
    errors = []
    def walk(node, path=""):
        if isinstance(node, dict):
            if "value" in node and "status" in node and "source_label" in node:
                v = node.get("value")
                st = node.get("status")
                if v is not None and v != "":
                    if st not in ("fresh", "stale"):
                        errors.append(f"{path}: value nem-null de status={st!r}")
                    if not node.get("source_label"):
                        errors.append(f"{path}: value nem-null de source_label ures")
                    if not node.get("updated_at"):
                        errors.append(f"{path}: value nem-null de updated_at hianyzik")
                else:
                    if st not in ("pending", "error"):
                        errors.append(f"{path}: value=null de status={st!r}")
            else:
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
    walk(data)
    return errors

def main():
    if not SCHEMA_PATH.exists():
        print(f"Schema nem talalhato: {SCHEMA_PATH}")
        return 1
    if not DATA_PATH.exists():
        print(f"Data nem talalhato: {DATA_PATH}")
        return 1

    with SCHEMA_PATH.open() as f:
        schema = json.load(f)
    with DATA_PATH.open() as f:
        data = json.load(f)

    validator = Draft7Validator(schema)
    schema_errors = sorted(validator.iter_errors(data), key=lambda e: e.path)

    if schema_errors:
        print("JSON Schema hibak:")
        for e in schema_errors:
            path = ".".join(str(p) for p in e.path) or "<root>"
            print(f"   {path}: {e.message}")

    hall_errors = check_hallucination(data)
    if hall_errors:
        print("Hallucinacio-guard hibak:")
        for e in hall_errors:
            print(f"   {e}")

    if schema_errors or hall_errors:
        print(f"\nOssz hiba: schema={len(schema_errors)}, guard={len(hall_errors)}")
        return 1

    print("data.json valid.")
    print(f"   schema_version: {data['meta']['schema_version']}")
    print(f"   data_freshness: {data['meta']['data_freshness']}")
    print(f"   last_updated:   {data['meta']['last_updated']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
