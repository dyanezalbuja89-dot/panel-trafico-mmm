#!/usr/bin/env python3
"""Cuadre de ventas por asesor: panel vs fuente cruda.

Nació del caso Daniela Jácome (4-ago-2026): su venta del 30-jul quedaba "Sin
asesor" porque el loader reconstruía el asesor por un join de VIN contra la hoja
de reservas en vez de leer 'Usuario Vende' de la propia factura. Nadie lo vio
hasta que Daniel lo notó de memoria — este check existe para que el pipeline lo
atrape solo.

Compara, para cada marca, las ventas netas 2026 por asesor:
  - CRUDO: DATOS 2 con el snapshot más reciente mandando por mes (mismo criterio
    que ventas.load_ventas_completo), agrupado por
    'Usuario Vende' directamente — SIN pasar por ventas.py, para poder atrapar
    bugs de atribución del propio loader.
  - PANEL: conversion_data[marca].master_por_asesor de data.json.

Sale con código 1 si hay cualquier discrepancia. deploy.sh lo corre después del
aggregate y aborta el deploy si falla.
"""
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from conversion import norm_asesor
from inventario import _INVENTORY_DIRS

MAP = {'FORD': 'FORD', 'DONGFENG': 'DONGFENG_ORGU', 'CHERY': 'CHERY_ORGU',
       'MAZDA': 'MAZDA_ORGU', 'RAM': 'RAM_ORGU'}


def cargar_crudo():
    """DATOS 2 con el snapshot más reciente mandando por mes.

    Mismo criterio que ventas.load_ventas_completo(): el snapshot es una foto y una
    factura anulada desaparece de la siguiente sin dejar NC, así que la unión
    histórica conserva ventas revertidas. Si este check usara la unión, marcaría
    como discrepancia justamente las filas que el panel descarta con razón.
    """
    frames, seen = [], set()
    for d in _INVENTORY_DIRS:
        if not d.exists():
            continue
        got = False
        for ext in ('*.xlsm', '*.xlsx'):
            for p in d.glob(ext):
                if p.name.startswith('~$') or 'INVENTARIO' not in p.name.upper() or p in seen:
                    continue
                seen.add(p)
                try:
                    _f = pd.read_excel(p, sheet_name='DATOS 2', header=0)
                    import re as _re
                    _m = _re.search(r'(\d{1,2})-(\d{1,2})-(\d{4})', p.name)
                    _f['_snap'] = (pd.Timestamp(int(_m.group(3)), int(_m.group(2)), int(_m.group(1)))
                                   if _m else pd.Timestamp.min)
                    frames.append(_f)
                    got = True
                except Exception:
                    pass
        if got:
            break
    if not frames:
        return None
    d = pd.concat(frames, ignore_index=True, sort=False)
    if '_snap' in d.columns and 'Fecha' in d.columns:
        _mp = pd.to_datetime(d['Fecha'], errors='coerce').dt.to_period('M')
        d = d[d['_snap'] == d.groupby(_mp)['_snap'].transform('max')].copy()
        d = d.drop(columns=['_snap'])
    d = d.drop_duplicates(subset=['Vin', 'Fecha', 'Cantidad'], keep='first')
    d['f'] = pd.to_datetime(d['Fecha'], errors='coerce')
    return d[d['f'].dt.year == 2026].copy()


def main():
    data_path = Path(__file__).parent / 'data.json'
    D = json.load(open(data_path))
    d = cargar_crudo()
    if d is None:
        print('[checks_asesores] WARN sin inventarios — check omitido')
        return 0

    def marca_of(m):
        mu = str(m).upper()
        for k, v in MAP.items():
            if k in mu:
                return v
        return None

    d['mk'] = d['Marca'].apply(marca_of)
    d['ase'] = d['Usuario Vende'].astype(str).str.strip().str.upper().replace({'NAN': ''})
    d['asen'] = d['ase'].apply(lambda a: norm_asesor(a) if a else '')

    fallas = []
    for mk in MAP.values():
        sub = d[d['mk'] == mk]
        crudo = {k: int(v) for k, v in sub.groupby('asen')['Cantidad'].sum().items() if k and v != 0}
        mpa = (D.get('conversion_data', {}).get(mk, {}) or {}).get('master_por_asesor', {}) or {}
        panel = {k: v.get('ventas', 0) for k, v in mpa.items() if k != 'Sin asesor'}
        sin_ase = mpa.get('Sin asesor', {}).get('ventas', 0)

        # 1 · Todo asesor con ventas en crudo debe estar en el panel con el mismo neto
        for a, q in crudo.items():
            if panel.get(a) != q:
                fallas.append(f'{mk} · {a}: crudo {q} vs panel {panel.get(a)}')
        # 2 · El panel no puede inventar asesores con ventas que el crudo no tiene
        for a, q in panel.items():
            if a not in crudo and q != 0:
                fallas.append(f'{mk} · {a}: panel {q} vs crudo — (no existe en Usuario Vende)')
        # 3 · "Sin asesor" debe ser residual (>2 uds = el loader está perdiendo nombres)
        if abs(sin_ase) > 2:
            fallas.append(f'{mk} · "Sin asesor" = {sin_ase} uds (el loader pierde el Usuario Vende)')

    if fallas:
        print(f'✗ [checks_asesores] {len(fallas)} discrepancias panel vs fuente cruda:')
        for f in fallas:
            print('   ', f)
        return 1
    tot = int(d.groupby('mk')['Cantidad'].sum().sum())
    print(f'✓ [checks_asesores] ventas por asesor cuadran contra Usuario Vende ({tot} uds netas, 5 marcas)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
