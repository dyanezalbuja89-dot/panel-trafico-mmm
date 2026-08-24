#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Presupuesto de pauta digital Ford — lee los Excel mensuales y los normaliza.

Produce el nodo `pauta` de data.json: inversión por modelo, mes y zona (Costa /
Sierra), más los leads y el CPL presupuestado.

Los archivos viven en OneDrive, uno por mes, y **cambiaron de estructura en agosto
2026**: los bloques `AYF` y `POSICIONAMIENTO` pasaron a `AWARENESS` y
`CONSIDERACIÓN`, y CPL/LEADS se movieron de las columnas 9-10 a las 2-3. Por eso
todo se mapea leyendo las dos filas de encabezado, nunca por posición fija.
"""
import re
import warnings
from pathlib import Path

import pandas as pd

BASE = Path.home() / 'Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Análisis de tráfico/2026'
CARPETAS = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto',
            'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
MES_KEY = {c: f'{c.lower()}_2026' for c in CARPETAS}

FAMILIAS = ['TERRITORY', 'RANGER', 'EVEREST', 'EXPLORER', 'ESCAPE', 'BRONCO', 'EXPEDITION']

# Canales que aparecen como bloque propio en algún mes (julio trae TIKTOK con su
# propia columna Costa). Son inversión igual que los demás bloques.
CANALES_EXTRA = {'TIKTOK', 'INFLUENCERS', 'GOOGLE', 'GOOGLE SEARCH'}


def _norm(s):
    s = re.sub(r'\s+', ' ', str(s)).strip().upper()
    for a, b in (('Á', 'A'), ('É', 'E'), ('Í', 'I'), ('Ó', 'O'), ('Ú', 'U')):
        s = s.replace(a, b)
    return s


def _n0(v):
    """NaN es truthy en Python: `v or 0` devuelve NaN y envenena la suma."""
    x = pd.to_numeric(v, errors='coerce')
    return 0.0 if pd.isna(x) else float(x)


def _familia(p):
    u = _norm(p)
    if 'F150' in u or 'F-150' in u:
        return 'F-150'
    for f in FAMILIAS:
        if f in u:
            return f
    return None


# 'Presupuesto ENERO26.xlsx', 'Presupuesto_Marzo 26.xlsx', 'Presupuesto FEB26.xlsx'…
ABREV = {'Enero': ('ENERO', 'ENE'), 'Febrero': ('FEBRERO', 'FEB'), 'Marzo': ('MARZO', 'MAR'),
         'Abril': ('ABRIL', 'ABR'), 'Mayo': ('MAYO', 'MAY'), 'Junio': ('JUNIO', 'JUN'),
         'Julio': ('JULIO', 'JUL'), 'Agosto': ('AGOSTO', 'AGO'),
         'Septiembre': ('SEPTIEMBRE', 'SEP'), 'Octubre': ('OCTUBRE', 'OCT'),
         'Noviembre': ('NOVIEMBRE', 'NOV'), 'Diciembre': ('DICIEMBRE', 'DIC')}


def _archivo_del_mes(carpeta):
    """El nombre del archivo debe nombrar al MES, no basta con que esté en su carpeta:
    la de Febrero tiene además un 'Presupuesto Enero.xlsx' traspapelado, y tomar el
    primero por orden alfabético leía enero dos veces."""
    d = BASE / carpeta
    if not d.exists():
        return None
    cands = [p for p in sorted(d.glob('*.xls*'))
             if not p.name.startswith('~$') and 'PRESUPUESTO' in p.name.upper()]
    for nombre in ABREV.get(carpeta, ()):
        for p in cands:
            if nombre in p.name.upper():
                return p
    return None


def _leer_mes(path):
    """Devuelve [{producto, familia, cpl, leads, zona, monto, bloque}] de un archivo."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        d = pd.read_excel(path, sheet_name='Digital Pauta', header=None)
    grp = d.iloc[0].ffill().map(_norm)
    sub = d.iloc[1].map(_norm)

    j_prod = j_cpl = j_leads = None
    cols = []                       # (columna, zona, bloque)
    for j in range(d.shape[1]):
        g, s = grp.iloc[j], sub.iloc[j]
        if s == 'PRODUCTO':
            j_prod = j
        elif s == 'CPL':
            j_cpl = j
        elif s == 'LEADS' and g.startswith('INVERSION'):
            j_leads = j
        elif (g.startswith('INVERSION') or g.startswith('POSICIONAMIENTO')
              or g in CANALES_EXTRA):
            # CPL y LEADS viven bajo el grupo INVERSION LEADS y NO son plata.
            #
            # Una columna SIN subcolumna solo heredó el grupo por el ffill. No es un
            # bloque de inversión: en agosto sumaba $1.150 y la hoja `Embudo` de ese
            # mismo archivo declara $10.590 SIN ella, que es el control que zanja la
            # duda. Julio tiene un caso igual de $1.000.
            if s in ('CPL', 'LEADS', 'NAN', ''):
                continue
            zona = 'Sierra' if 'SIERRA' in s else ('Costa' if 'COSTA' in s else 'Sin zona')
            if g in CANALES_EXTRA:
                bloque = g.lower()
            elif 'LEADS' in g:
                bloque = 'leads'
            elif 'AWARENESS' in g or 'AYF' in g:
                bloque = 'awareness'
            elif 'CONSIDERACION' in g:
                bloque = 'consideracion'
            else:
                bloque = 'posicionamiento'
            cols.append((j, zona, bloque))
    if j_prod is None:
        return []

    filas = []
    for _, r in d[d[0].notna() & d[1].notna()].iterrows():
        fam = _familia(r.iloc[j_prod])
        if not fam:
            continue
        for j, zona, bloque in cols:
            monto = _n0(r.iloc[j])
            if not monto:
                continue
            filas.append({'producto': str(r.iloc[j_prod]).strip(), 'familia': fam,
                          'cpl': _n0(r.iloc[j_cpl]) if j_cpl is not None else 0.0,
                          'leads': _n0(r.iloc[j_leads]) if j_leads is not None else 0.0,
                          'zona': zona, 'bloque': bloque, 'monto': monto})
    return filas


def build_pauta():
    """{meses, por_mes, por_modelo, por_zona, flat, total} — listo para data.json."""
    flat, meses = [], []
    for carpeta in CARPETAS:
        p = _archivo_del_mes(carpeta)
        if p is None:
            continue
        try:
            filas = _leer_mes(p)
        except Exception as e:
            print(f'[pauta] {carpeta}: no se pudo leer ({e})')
            continue
        if not filas:
            continue
        key = MES_KEY[carpeta]
        meses.append(key)
        for f in filas:
            f['mes'] = key
            f['mes_label'] = carpeta
        flat += filas

    if not flat:
        return None

    def _agg(claves):
        out = {}
        for f in flat:
            k = tuple(f[c] for c in claves)
            out[k] = out.get(k, 0.0) + f['monto']
        return out

    por_mes = {}
    for (m,), v in _agg(['mes']).items():
        por_mes[m] = round(v, 2)
    por_modelo = {}
    for (mod, m), v in _agg(['familia', 'mes']).items():
        por_modelo.setdefault(mod, {})[m] = round(v, 2)
    por_zona = {}
    for (z, m), v in _agg(['zona', 'mes']).items():
        por_zona.setdefault(z, {})[m] = round(v, 2)
    por_modelo_zona = {}
    for (mod, z, m), v in _agg(['familia', 'zona', 'mes']).items():
        por_modelo_zona.setdefault(mod, {}).setdefault(z, {})[m] = round(v, 2)
    por_bloque = {}
    for (b, m), v in _agg(['bloque', 'mes']).items():
        por_bloque.setdefault(b, {})[m] = round(v, 2)

    # leads y CPL presupuestados: una vez por producto/mes, no por columna de zona
    vistos, leads_mes = set(), {}
    for f in flat:
        k = (f['mes'], f['producto'])
        if k in vistos:
            continue
        vistos.add(k)
        leads_mes[f['mes']] = leads_mes.get(f['mes'], 0.0) + f['leads']

    return {
        'meses': meses,
        'por_mes': por_mes,
        'por_modelo': por_modelo,
        'por_zona': por_zona,
        'por_modelo_zona': por_modelo_zona,
        'por_bloque': por_bloque,
        'leads_presupuestados': {k: round(v) for k, v in leads_mes.items()},
        'total': round(sum(por_mes.values()), 2),
        'doc': {
            'que_es': 'Presupuesto de pauta digital Ford, de los Excel mensuales de OneDrive. '
                      'Es lo PLANIFICADO, no lo ejecutado en Ads Manager.',
            'zonas': 'Sierra = Quito (La Y + Tumbaco). Costa = Guayaquil, Manta, Portoviejo y Machala.',
            'bloques': 'ene–jul: leads · awareness (AYF) · posicionamiento. '
                       'Desde agosto: leads · awareness · consideración.',
            'ojo': 'El tráfico responde al presupuesto del mes ANTERIOR: correlación +0,63 con un '
                   'mes de desfase contra −0,43 en el mismo mes.',
        },
    }


if __name__ == '__main__':
    import json
    r = build_pauta()
    if not r:
        raise SystemExit('sin datos de pauta')
    print(f"total ${r['total']:,.0f} · {len(r['meses'])} meses")
    for m in r['meses']:
        print(f"  {m:16} ${r['por_mes'][m]:>10,.0f}")
    print('\npor zona:', {k: round(sum(v.values())) for k, v in r['por_zona'].items()})
    print('por modelo:', {k: round(sum(v.values())) for k, v in
                          sorted(r['por_modelo'].items(), key=lambda x: -sum(x[1].values()))})
