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
import warnings
import pandas as pd

from inventario import DEFAULT_INVENTORY_PATH, normalize_familia, normalize_version

EMBUDO_BASE = Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/"
                   "Marketing/2026/Análisis de embudo")

# Agencia embudo → keyword en AGENCIA_FACTURACION del inventario
AGENCY_INV_KEYWORD = {
    'CJA': 'CARLOS JULIO',
}
MES_NUM = {'Enero':1,'Febrero':2,'Marzo':3,'Abril':4,'Mayo':5,'Junio':6,
           'Julio':7,'Agosto':8,'Septiembre':9,'Octubre':10,'Noviembre':11,'Diciembre':12}
_INV_CACHE = {}


def _load_inventory_sales():
    """Carga las ventas facturadas del inventario (cache). DataFrame con
    agencia_fact, fecha, MODELO (consolidado), VERSION."""
    key = str(DEFAULT_INVENTORY_PATH)
    if key in _INV_CACHE:
        return _INV_CACHE[key]
    if not DEFAULT_INVENTORY_PATH.exists():
        _INV_CACHE[key] = None
        return None
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        df = pd.read_excel(DEFAULT_INVENTORY_PATH, sheet_name='DATOS', header=0)
    df.columns = [str(c).strip() for c in df.columns]
    df['fac_dt'] = pd.to_datetime(df.get('fecha de facturacion'), errors='coerce')
    df['marca_up'] = df.get('marca', 'FORD')
    df['MODELO'] = df.apply(lambda r: normalize_familia(r.get('familia'), 'FORD'), axis=1)
    df['VERSION'] = df.apply(lambda r: normalize_version(r.get('familia'), 'FORD'), axis=1)
    out = df[['AGENCIA_FACTURACION', 'fac_dt', 'MODELO', 'VERSION']].dropna(subset=['fac_dt'])
    _INV_CACHE[key] = out
    return out


def _ventas_inventario(agencia_short, mes, anio=2026):
    """Cuenta ventas facturadas del inventario para una agencia/mes.
    Devuelve (por_modelo {mod:n}, por_version {mod:{ver:n}}, total)."""
    inv = _load_inventory_sales()
    kw = AGENCY_INV_KEYWORD.get(agencia_short)
    mnum = MES_NUM.get(mes)
    if inv is None or not kw or not mnum:
        return {}, {}, 0
    sub = inv[inv['AGENCIA_FACTURACION'].astype(str).str.contains(kw, case=False, na=False)]
    sub = sub[(sub['fac_dt'].dt.year == anio) & (sub['fac_dt'].dt.month == mnum)]
    por_modelo, por_version = {}, {}
    for _, r in sub.iterrows():
        mod = r['MODELO'] or '(Sin modelo)'
        ver = r['VERSION'] or mod
        por_modelo[mod] = por_modelo.get(mod, 0) + 1
        por_version.setdefault(mod, {})
        por_version[mod][ver] = por_version[mod].get(ver, 0) + 1
    return por_modelo, por_version, int(len(sub))

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


def compute_embudo_agencia(agencia_dir, mes, short_agencia):
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

    # ── CIERRE desde el INVENTARIO (ventas facturadas reales), no del archivo Cierre.xlsx ──
    cierre_modelo, cierre_version, cierre_total = _ventas_inventario(short_agencia, mes)

    # Totales por etapa = negocios únicos (id). Cierre = ventas facturadas inventario.
    totales = {}
    for lbl in labels:
        if lbl == 'Cierre':
            totales[lbl] = cierre_total
        else:
            totales[lbl] = int(stage_dfs[lbl]['id'].nunique())

    # Modelos presentes (embudo + cierre inventario)
    modelos = set()
    for lbl in labels:
        modelos.update(stage_dfs[lbl]['MODELO_N'].dropna().unique().tolist())
    modelos.update(cierre_modelo.keys())
    modelos.discard('(Sin modelo)')
    modelos = sorted(modelos)

    por_modelo = {}
    por_version = {}  # {modelo: {version: cierre_count}} — solo cierre tiene versión
    for mod in modelos + ['(Sin modelo)']:
        fila = {}
        for lbl in labels:
            if lbl == 'Cierre':
                fila[lbl] = int(cierre_modelo.get(mod, 0))
            else:
                d = stage_dfs[lbl]
                fila[lbl] = int(d[d['MODELO_N'] == mod]['id'].nunique())
        if sum(fila.values()) > 0:
            por_modelo[mod] = fila
            if mod in cierre_version:
                por_version[mod] = dict(sorted(cierre_version[mod].items(),
                                               key=lambda x: -x[1]))

    # Conversión de CADA etapa vs Tráfico (no vs etapa anterior)
    base = totales['Tráfico']
    conv = {}
    for lbl in labels:
        conv[lbl] = round(100 * totales[lbl] / base, 1) if base else None
    conv_total = conv['Cierre']

    return {
        'mes': mes,
        'etapas': labels,
        'totales': totales,
        'por_modelo': por_modelo,
        'por_version': por_version,
        'conversion_etapa': conv,         # ahora todas vs Tráfico
        'conversion_total': conv_total,
        'cierre_fuente': 'inventario (ventas facturadas)',
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
            r = compute_embudo_agencia(agencia_dir, mes, short)
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
