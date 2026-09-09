#!/usr/bin/env python3
"""Cuadre de ventas por asesor: panel vs fuente cruda.

Nació del caso Daniela Jácome (4-ago-2026): su venta del 30-jul quedaba "Sin
asesor" porque el loader reconstruía el asesor por un join de VIN contra la hoja
de reservas en vez de leer el vendedor de la propia factura. Nadie lo vio hasta
que Daniel lo notó de memoria — este check existe para que el pipeline lo atrape
solo. deploy.sh lo corre después del aggregate y aborta el deploy si falla.

Compara, para cada marca, las ventas netas 2026 (hasta `ventas_corte`) por asesor:
  - CRUDO: la **Base de Ventas de Finanzas** (campo Vendedor) en los meses que
    cubre — es la fuente que manda en el panel desde agosto-2026 — y DATOS 2
    ('Usuario Vende', snapshot más reciente por mes) solo para los meses de 2026
    que la Base todavía no trae. Hasta el 09-sep-2026 comparaba SOLO contra
    DATOS 2, que no ve exonerados ni la grafía de la Base: 41 falsas alarmas, y
    nadie las vio porque deploy.sh abortaba antes por otra cosa desde el 01-sep.
  - PANEL: conversion_data[marca].master_por_asesor de data.json.

Las grafías del crudo se mapean a las del panel ANTES de comparar
(asesores.construir_mapa, el panel gana): una persona = una fila, y "REINA" vs
"REYNA" no es una discrepancia de ventas.

Sale con código 1 si hay cualquier discrepancia.
"""
import json
import re
import sys
import warnings
from collections import Counter
from pathlib import Path

import pandas as pd

warnings.filterwarnings('ignore')

import asesores
import base_ventas
from inventario import _INVENTORY_DIRS

MAP = {'FORD': 'FORD', 'DONGFENG': 'DONGFENG_ORGU', 'DONG FENG': 'DONGFENG_ORGU',
       'CHERY': 'CHERY_ORGU', 'MAZDA': 'MAZDA_ORGU', 'RAM': 'RAM_ORGU'}
MARCAS = ['FORD', 'DONGFENG_ORGU', 'CHERY_ORGU', 'MAZDA_ORGU', 'RAM_ORGU']


def _marca(m):
    mu = str(m).upper()
    for k, v in MAP.items():
        if k in mu:
            return v
    return None


def _limpio(a):
    a = str(a).strip().upper()
    return '' if a in ('NAN', 'NONE', '') else a


def cargar_base(corte):
    """{mes} cubiertos y DataFrame (mk, mes, ase, cantidad) desde la Base de Ventas."""
    b = base_ventas.cargar()
    if b is None or not len(b):
        return set(), None
    b = b[b['marca'].notna() & b['mes'].notna()]
    b = b[(b['mes'] >= '2026-01') & (b['mes'] <= corte)]
    d = pd.DataFrame({'mk': b['marca'], 'mes': b['mes'],
                      'ase': b['asesor'].map(_limpio), 'cantidad': b['cantidad']})
    return set(d['mes'].unique()), d


def cargar_datos2(meses_excluir, corte):
    """DATOS 2 con el snapshot más reciente mandando por mes, solo meses no cubiertos.

    Mismo criterio que ventas.load_ventas_completo(): el snapshot es una foto y una
    factura anulada desaparece de la siguiente sin dejar NC, así que la unión
    histórica conservaría ventas revertidas.
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
                    f = pd.read_excel(p, sheet_name='DATOS 2', header=0)
                    m = re.search(r'(\d{1,2})-(\d{1,2})-(\d{4})', p.name)
                    f['_snap'] = (pd.Timestamp(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                                  if m else pd.Timestamp.min)
                    frames.append(f)
                    got = True
                except Exception:
                    pass
        if got:
            break
    if not frames:
        return None
    d = pd.concat(frames, ignore_index=True, sort=False)
    d['f'] = pd.to_datetime(d['Fecha'], errors='coerce')
    mp = d['f'].dt.to_period('M')
    d = d[d['_snap'] == d.groupby(mp)['_snap'].transform('max')].copy()
    d = d.drop_duplicates(subset=['Vin', 'Fecha', 'Cantidad'], keep='first')
    d['mes'] = d['f'].dt.strftime('%Y-%m')
    d = d[(d['mes'] >= '2026-01') & (d['mes'] <= corte) & ~d['mes'].isin(meses_excluir)]
    if d.empty:
        return None
    return pd.DataFrame({'mk': d['Marca'].map(_marca), 'mes': d['mes'],
                         'ase': d['Usuario Vende'].map(_limpio), 'cantidad': d['Cantidad']})


def main():
    D = json.load(open(Path(__file__).parent / 'data.json'))
    corte = str(D.get('ventas_corte') or '2026-12-31')[:7]
    meses_base, base = cargar_base(corte)
    d2 = cargar_datos2(meses_base, corte)
    partes = [x for x in (base, d2) if x is not None and len(x)]
    if not partes:
        print('[checks_asesores] WARN sin Base de Ventas ni inventarios — check omitido')
        return 0
    d = pd.concat(partes, ignore_index=True)
    d = d[d['mk'].notna()]
    fuente = (f"Base de Ventas {min(meses_base)}..{max(meses_base)}" if meses_base else 'sin Base') + \
             (f" + DATOS 2 {sorted(d2['mes'].unique())}" if d2 is not None else '')

    # Grafías del crudo → las del panel (el panel gana siempre)
    panel_names = set()
    for mk in MARCAS:
        panel_names.update(((D.get('conversion_data') or {}).get(mk) or {}).get('master_por_asesor') or {})
    freq = {n: 10**6 for n in panel_names}
    for n, c in Counter(d['ase']).items():
        if n:
            freq.setdefault(n, c)
    mapa = {a: c for a, c in asesores.construir_mapa(freq).items() if a not in panel_names}
    d['asec'] = d['ase'].map(lambda a: mapa.get(a, a))

    fallas = []
    for mk in MARCAS:
        sub = d[d['mk'] == mk]
        crudo = {k: int(v) for k, v in sub.groupby('asec')['cantidad'].sum().items() if k and v != 0}
        mpa = ((D.get('conversion_data') or {}).get(mk) or {}).get('master_por_asesor') or {}
        panel = {k: v.get('ventas', 0) for k, v in mpa.items() if k != 'Sin asesor'}
        sin_ase = mpa.get('Sin asesor', {}).get('ventas', 0)
        # 1 · Todo asesor con ventas en crudo debe estar en el panel con el mismo neto
        for a, q in crudo.items():
            if panel.get(a) != q:
                fallas.append(f'{mk} · {a}: crudo {q} vs panel {panel.get(a)}')
        # 2 · El panel no puede inventar asesores con ventas que el crudo no tiene
        for a, q in panel.items():
            if a not in crudo and q != 0:
                fallas.append(f'{mk} · {a}: panel {q} vs crudo — (no existe en la fuente)')
        # 3 · "Sin asesor" debe ser residual (>2 uds = el loader está perdiendo nombres)
        if abs(sin_ase) > 2:
            fallas.append(f'{mk} · "Sin asesor" = {sin_ase} uds (el loader pierde el vendedor)')

    if fallas:
        print(f'✗ [checks_asesores] {len(fallas)} discrepancias panel vs fuente cruda ({fuente}):')
        for f in fallas:
            print('   ', f)
        return 1
    tot = int(d['cantidad'].sum())
    print(f'✓ [checks_asesores] ventas por asesor cuadran contra {fuente} '
          f'({tot} uds netas, 5 marcas, {len(mapa)} grafías mapeadas al panel)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
