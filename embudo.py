"""Análisis de embudo (funnel) de ventas por modelo y concesionario.

Lee las 6 etapas del embudo desde /Análisis de embudo/<AGENCIA>/<MES>/:
  Tráfico → Cotizaciones → Presentación → Solicitudes → Aprobaciones → Cierre

Cada archivo tiene una fila por negocio (id) con su modelo. Cotizaciones puede
tener varias filas por id (un negocio cotiza varios modelos).

Construye:
  - Embudo global por etapa (conteo de negocios únicos)
  - Embudo por modelo × etapa
  - Tasas de conversión entre etapas
"""
from pathlib import Path
import pandas as pd

EMBUDO_BASE = Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/"
                   "Marketing/2026/Análisis de embudo")

# Orden del embudo: (nombre_archivo, etiqueta_panel)
STAGES = [
    ('Tráfico',      'Tráfico'),
    ('Cotizaciones', 'Cotización'),
    ('Presentacion', 'Presentación'),
    ('Solicitudes',  'Solicitud'),
    ('Aprobaciones', 'Aprobación'),
    ('Cierre',       'Cierre'),
]

# Agencias a procesar (por ahora solo CJA). Mapea carpeta → nombre corto del panel.
AGENCIES = {
    'CJA': 'CJA',
}


def _norm_one(s):
    s = s.strip().upper()
    if not s or s == 'NAN':
        return None
    if s == 'F150':
        s = 'F-150'
    return s


def _split_modelos(m):
    """Un campo Modelo puede traer varios modelos separados por coma
    ('ESCAPE,EVEREST'). Devuelve lista normalizada de modelos."""
    if not isinstance(m, str):
        return ['(Sin modelo)']
    parts = [_norm_one(p) for p in m.split(',')]
    parts = [p for p in parts if p]
    return parts or ['(Sin modelo)']


def _load_stage(path):
    """Lee un archivo de etapa, devuelve DataFrame con id + MODELO_N, explotando
    los registros multi-modelo (una fila por (id, modelo))."""
    df = pd.read_excel(path, sheet_name=0)
    if 'Modelo' not in df.columns or 'id' not in df.columns:
        return pd.DataFrame(columns=['id', 'MODELO_N'])
    rows = []
    for _, r in df.iterrows():
        if pd.isna(r['id']):
            continue
        for mod in _split_modelos(r['Modelo']):
            rows.append({'id': r['id'], 'MODELO_N': mod})
    return pd.DataFrame(rows)


def compute_embudo_agencia(agencia_dir, mes):
    """Procesa el embudo de una agencia/mes. Devuelve dict con etapas, por_modelo, etc."""
    folder = agencia_dir / mes
    if not folder.exists():
        return None
    stage_dfs = {}
    for fname, label in STAGES:
        p = folder / f"{fname}.xlsx"
        if p.exists():
            stage_dfs[label] = _load_stage(p)
        else:
            stage_dfs[label] = pd.DataFrame(columns=['id', 'MODELO_N'])

    labels = [lbl for _, lbl in STAGES]

    # Totales por etapa = negocios únicos (id)
    totales = {}
    for lbl in labels:
        totales[lbl] = int(stage_dfs[lbl]['id'].nunique())

    # Por modelo × etapa = negocios únicos (id) que tienen ese modelo en esa etapa
    modelos = set()
    for lbl in labels:
        modelos.update(stage_dfs[lbl]['MODELO_N'].dropna().unique().tolist())
    modelos.discard('(Sin modelo)')
    modelos = sorted(modelos)

    por_modelo = {}
    for mod in modelos + ['(Sin modelo)']:
        fila = {}
        for lbl in labels:
            d = stage_dfs[lbl]
            fila[lbl] = int(d[d['MODELO_N'] == mod]['id'].nunique())
        if sum(fila.values()) > 0:
            por_modelo[mod] = fila

    # Tasas de conversión entre etapas consecutivas (global)
    conv = {}
    for i in range(1, len(labels)):
        prev_lbl, cur_lbl = labels[i-1], labels[i]
        p, c = totales[prev_lbl], totales[cur_lbl]
        conv[cur_lbl] = round(100 * c / p, 1) if p else None

    # Conversión total Tráfico → Cierre
    conv_total = round(100 * totales['Cierre'] / totales['Tráfico'], 1) if totales['Tráfico'] else None

    return {
        'mes': mes,
        'etapas': labels,
        'totales': totales,
        'por_modelo': por_modelo,
        'conversion_etapa': conv,
        'conversion_total': conv_total,
    }


def compute_embudo_data():
    """Procesa todas las agencias configuradas. Devuelve {agencias: {...}, default}."""
    out = {'agencias': {}, 'meses': {}}
    for folder_name, short in AGENCIES.items():
        agencia_dir = EMBUDO_BASE / folder_name
        if not agencia_dir.exists():
            continue
        meses = sorted([p.name for p in agencia_dir.iterdir() if p.is_dir()])
        out['meses'][short] = meses
        out['agencias'][short] = {}
        for mes in meses:
            r = compute_embudo_agencia(agencia_dir, mes)
            if r:
                out['agencias'][short][mes] = r
    if not out['agencias']:
        return None
    out['default_agencia'] = next(iter(out['agencias'].keys()))
    return out


if __name__ == '__main__':
    import json
    d = compute_embudo_data()
    print(json.dumps(d, indent=2, ensure_ascii=False)[:2000])
