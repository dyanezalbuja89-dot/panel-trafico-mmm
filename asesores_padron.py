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
primer_mes / ultimo_mes con venta (2025–26) · ventas_2026 · salido (label o null) ·
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
        for a, c in fac_df.groupby('asesor')['cedula_vendedor'].agg(lambda s: Counter(s.dropna()).most_common(1)[0][0] if s.notna().any() else None).items():
            ced[a] = c
    filas = []
    for a, p in pad.items():
        con = sorted(m for m, n in p['meses'].items() if n != 0)
        sal = quien_es(a)
        filas.append({
            'asesor': a,
            'cedula_vendedor': ced.get(a),
            'marcas': ' · '.join(sorted(p['marcas'])),
            'agencia_hogar': hogar.get(a),
            'primer_mes': con[0] if con else None,
            'ultimo_mes': con[-1] if con else None,
            'ventas_2026': int(sum(n for m, n in p['meses'].items() if m.startswith('2026'))),
            'salido': sal['label'] if sal else None,
            'jefe_venta': bool(is_jefe_venta(a)),
            'activo_por_ventas': (not sal) and any(p['meses'].get(m, 0) > 0 for m in ultimos),
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
