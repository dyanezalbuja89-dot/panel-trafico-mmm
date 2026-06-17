#!/usr/bin/env python3
"""Mergea digital.json (salida de hubspot_pull.py) dentro de data.json,
SOLO la clave 'digital' — preserva el resto de pestañas. Igual que hace
aggregate.py para digital, pero sin tocar las demás pestañas (las refresca
su propio flujo). Para el refresco horario del dato digital."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
data_p = BASE / 'data.json'
dig_p = BASE / 'digital.json'

data = json.loads(data_p.read_text(encoding='utf-8'))
digital = json.loads(dig_p.read_text(encoding='utf-8'))
data['digital'] = digital
# Compacto, igual que aggregate.py (indent=None, separators sin espacios).
data_p.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(f"data.json['digital'] actualizado desde digital.json (updated_at={digital.get('updated_at')})")
