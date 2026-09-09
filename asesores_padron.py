#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Padrón de asesores comerciales derivado del panel → asesores_padron.json / .csv

Lo pidió la sesión de Renovación (09-sep-2026): "una lista maestra de asesores por
agencia con fecha de ingreso/salida que pueda leer de un archivo". No existe una
nómina de RRHH en este repo; lo más cercano y reproducible es esto, derivado de
`data.json` (ventas por asesor y mes), `asesores_salidos.py` (los que Daniel marcó
como salidos), `conversion.JEFES_VENTA_RAW` (jefes de venta: venden pero no son
asesores) y FACTURADO (cédula del vendedor, la identidad dura).

Por asesor: nombre canónico del panel · cedula_vendedor · marcas · agencia_hogar ·
primer_mes / ultimo_mes con venta (2025–26; o 2024→ si solo está en FACTURADO) ·
ventas_2026 · salido (label o null) · fuente ('panel' | 'facturado': salidos históricos
sin ventas 2025–26, pedidos por Renovación para cerrar identidad hacia atrás) ·
jefe_venta (bool) · activo_por_ventas (vendió en alguno de los dos últimos meses
cerrados de ventas y no salió). "Activo" aquí es POR VENTAS, no por nómina:
quien no facturó en dos meses puede seguir en la red. Eso lo confirma Daniel.

Uso: python3 asesores_padron.py   (se regenera solo dentro de deploy.sh)
"""
import csv
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent


def construir(d, fac_df=None):
    from asesores_salidos import quien_es
    from conversion import is_jefe_venta

    corte = str(d.get('ventas_corte') or '')[:7]
    meses = sorted({m for vm in d['ventas_mensual'].values() for a in vm['by_asesor'].values()
                    for m in a if not m.startswith('_') and (not corte or m <= corte)})
    ultimos = meses[-2:]
    pad = {}
    for mk, vm in d['ventas_mensual'].items():
        for a, ms in (vm.get('by_asesor') or {}).items():
            if a.startswith('_'):
                continue
            p = pad.setdefault(a, {'asesor': a, 'marcas': set(), 'meses': {}})
            p['marcas'].add(mk.replace('_ORGU', ''))
            for m, n in ms.items():
                if not m.startswith('_') and (not corte or m <= corte):
                    p['meses'][m] = p['meses'].get(m, 0) + n
    hogar = {}
    for cd in d['conversion_data'].values():
        for a, ag in (cd.get('asesor_home_agencia') or {}).items():
            hogar.setdefault(a, ag)
    ced = {}
    if fac_df is not None and len(fac_df):
        # La grafía de FACTURADO (una por factura, casi siempre la larga) se mapea a la
        # del panel ANTES de cruzar; si no, la cédula queda huérfana en la grafía larga.
        import asesores
        freq = {n: 10**6 for n in pad}
        for n, c in Counter(fac_df['asesor'].dropna()).items():
            freq.setdefault(n, c)
        mapa = {a: c for a, c in asesores.construir_mapa(freq).items() if a not in pad}
        col = fac_df['asesor'].map(lambda a: mapa.get(a, a))
        for a, c in fac_df.groupby(col)['cedula_vendedor'].agg(lambda s: Counter(s.dropna()).most_common(1)[0][0] if s.notna().any() else None).items():
            ced[a] = c
    # Salidos históricos: asesores que solo existen en FACTURADO (2024→) y no vendieron
    # en 2025–26. Renovación los necesita con su cédula para cerrar identidad hacia atrás.
    hist = {}
    if fac_df is not None and len(fac_df):
        fac_df = fac_df.assign(_asec=col)
        for a, g in fac_df.groupby('_asec'):
            if a in pad or not a or a == 'Sin asesor':
                continue
            meses = sorted(m for m in g['mes'].dropna().unique())
            hist[a] = {'asesor': a, 'marcas': {m.replace('_ORGU', '') for m in g['marca'].dropna().unique()},
                       'meses': {m: int(n) for m, n in g.groupby('mes')['cantidad'].sum().items()},
                       'hogar': Counter(g['bodega'].dropna()).most_common(1)[0][0] if g['bodega'].notna().any() else None}
    filas = []
    for a, p in list(pad.items()) + list(hist.items()):
        con = sorted(m for m, n in p['meses'].items() if n != 0)
        sal = quien_es(a)
        filas.append({
            'asesor': a,
            'cedula_vendedor': ced.get(a),
            'marcas': ' · '.join(sorted(p['marcas'])),
            'agencia_hogar': hogar.get(a) or p.get('hogar'),
            'primer_mes': con[0] if con else None,
            'ultimo_mes': con[-1] if con else None,
            'ventas_2026': int(sum(n for m, n in p['meses'].items() if m.startswith('2026'))),
            'salido': sal['label'] if sal else None,
            'jefe_venta': bool(is_jefe_venta(a)),
            'activo_por_ventas': (not sal) and a in pad and any(p['meses'].get(m, 0) > 0 for m in ultimos),
            'fuente': 'panel' if a in pad else 'facturado',
        })
    filas.sort(key=lambda r: (str(r['agencia_hogar']), r['asesor']))
    return {'_doc': __doc__.strip().split('\n')[0], 'ventas_corte': d.get('ventas_corte'),
            'ultimos_meses': ultimos, 'asesores': filas}


def main():
    d = json.loads((HERE / 'data.json').read_text(encoding='utf-8'))
    try:
        import facturado
        fac = facturado.cargar()
        fac = fac[fac['es_vehiculo']] if fac is not None else None
    except Exception as e:
        print('[padron] WARN sin FACTURADO:', e)
        fac = None
    out = construir(d, fac)
    (HERE / 'asesores_padron.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    with (HERE / 'asesores_padron.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(out['asesores'][0].keys()))
        w.writeheader()
        w.writerows(out['asesores'])
    act = [r for r in out['asesores'] if r['activo_por_ventas'] and not r['jefe_venta']]
    print(f"[padron] {len(out['asesores'])} asesores · {len(act)} activos por ventas (sin jefes) · "
          f"{sum(1 for r in out['asesores'] if r['salido'])} salidos · {sum(1 for r in out['asesores'] if r['jefe_venta'])} jefes · "
          f"con cédula {sum(1 for r in out['asesores'] if r['cedula_vendedor'])} · últimos meses {out['ultimos_meses']}")
    return out


if __name__ == '__main__':
    main()
