"""Refresh inventario block in data.json without re-running full aggregate.
Use when OneDrive sync blocks historical BDs but inventario file is local.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from inventario import load_inventario, DEFAULT_INVENTORY_PATH

# Same MONTHS_CONFIG keys as aggregate.py
# Minimal stub so we keep is_current logic
MONTHS = [
    ("octubre_2025",  "Octubre 2025",  10, 2025, 31),
    ("noviembre_2025","Noviembre 2025",11, 2025, 30),
    ("diciembre_2025","Diciembre 2025",12, 2025, 31),
    ("enero_2026",    "Enero 2026",    1,  2026, 31),
    ("febrero_2026",  "Febrero 2026",  2,  2026, 28),
    ("marzo_2026",    "Marzo 2026",    3,  2026, 31),
    ("abril_2026",    "Abril 2026",    4,  2026, 30),
    ("mayo_2026",     "Mayo 2026",     5,  2026, 31),
    ("junio_2026",    "Junio 2026",    6,  2026, 17),
]

DATA_PATH = Path(__file__).parent / "data.json"

def main():
    if not DEFAULT_INVENTORY_PATH.exists():
        print(f"[FATAL] no inventario at {DEFAULT_INVENTORY_PATH}", file=sys.stderr)
        sys.exit(1)
    print(f"[refresh-inv] source: {DEFAULT_INVENTORY_PATH.name}")
    if not DATA_PATH.exists():
        print(f"[FATAL] data.json missing — run full aggregate.py first", file=sys.stderr)
        sys.exit(1)
    print("[1/3] loading existing data.json...")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    print("[2/3] regenerating inventario block...")
    now = datetime.now()
    months_config = [
        {'key': k, 'label': lbl, 'year': y, 'month': m, 'cut_day': cd,
         'is_current': (now.year == y and now.month == m)}
        for (k, lbl, m, y, cd) in MONTHS
    ]
    inv = load_inventario(months_config=months_config)
    # Sanitize NaN/Inf same way aggregate.py does
    import math
    def _safe(o):
        if isinstance(o, float):
            return None if (math.isnan(o) or math.isinf(o)) else o
        if isinstance(o, dict):
            return {k: _safe(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_safe(x) for x in o]
        return o
    data["inventario"] = _safe(inv)
    print("[3/3] writing data.json...")
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)
    print(f"[OK] data.json updated · snapshot {data['inventario'].get('snapshot_date')}")

if __name__ == "__main__":
    main()
