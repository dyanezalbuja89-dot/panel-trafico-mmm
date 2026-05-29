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
    'CJA':       'CARLOS JULIO',
    'Manta':     'MANTA',       # captura 1002 Manta y 1013 Manta II
    'Orellana':  'ORELLANA',
    'Portoviejo':'PORTOVIEJO',  # aún sin agencia propia → cierres = 0
    'La Y':      'LA Y',
    'Tumbaco':   'TUMBACO',
    'Machala':   'MACHALA',
}

# Agencia → región/provincia (para filtro regional)
AGENCY_REGION = {
    'CJA':       'Guayas',
    'Manta':     'Manabí',
    'Portoviejo':'Manabí',
    'Orellana':  'Pichincha',  # Av. Orellana (Quito)
    'La Y':      'Pichincha',
    'Tumbaco':   'Pichincha',
    'Machala':   'El Oro',
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
    df['ASESOR_F'] = df.get('ASESOR_FACTURACION').apply(_norm_asesor) if 'ASESOR_FACTURACION' in df.columns else None
    out = df[['AGENCIA_FACTURACION', 'fac_dt', 'MODELO', 'VERSION', 'ASESOR_F']].dropna(subset=['fac_dt'])
    _INV_CACHE[key] = out
    return out


def _match_asesor(nombre_inv, canonicos):
    """Matchea un asesor del inventario (nombre completo) al asesor canónico del
    embudo (nombre corto) por tokens compartidos (≥2). Devuelve el canónico o None."""
    if not nombre_inv:
        return None
    toks_inv = set(nombre_inv.split())
    best, best_n = None, 0
    for can in canonicos:
        shared = len(toks_inv & set(can.split()))
        if shared > best_n:
            best, best_n = can, shared
    return best if best_n >= 2 else None


def _ventas_inventario(agencia_short, mes, asesores_canonicos=None, anio=2026):
    """Cuenta ventas facturadas del inventario para una agencia/mes.
    Devuelve (por_modelo, por_version, por_asesor, total).
    por_asesor mapea el ASESOR_FACTURACION al asesor canónico del embudo."""
    inv = _load_inventory_sales()
    kw = AGENCY_INV_KEYWORD.get(agencia_short)
    mnum = MES_NUM.get(mes)
    if inv is None or not kw or not mnum:
        return {}, {}, {}, 0
    sub = inv[inv['AGENCIA_FACTURACION'].astype(str).str.contains(kw, case=False, na=False)]
    sub = sub[(sub['fac_dt'].dt.year == anio) & (sub['fac_dt'].dt.month == mnum)]
    canonicos = asesores_canonicos or []
    por_modelo, por_version, por_asesor = {}, {}, {}
    for _, r in sub.iterrows():
        mod = r['MODELO'] or '(Sin modelo)'
        ver = r['VERSION'] or mod
        por_modelo[mod] = por_modelo.get(mod, 0) + 1
        por_version.setdefault(mod, {})
        por_version[mod][ver] = por_version[mod].get(ver, 0) + 1
        # asesor: matchear al canónico del embudo; si no, usar el del inventario
        ase = _match_asesor(r.get('ASESOR_F'), canonicos) or r.get('ASESOR_F') or '(Sin asesor)'
        por_asesor[ase] = por_asesor.get(ase, 0) + 1
    return por_modelo, por_version, por_asesor, int(len(sub))

# Orden del embudo: (nombre_archivo, etiqueta_panel)
# La base del embudo es Cotización (Tráfico se excluye a pedido del negocio).
STAGES = [
    ('Cotizaciones', 'Cotización'),
    ('Presentacion', 'Presentación'),
    ('Solicitudes',  'Solicitud'),
    ('Aprobaciones', 'Aprobación'),
    ('Cierre',       'Cierre'),
]

# Agencias a procesar. Mapea carpeta del filesystem → nombre corto del panel.
AGENCIES = {
    'CJA':        'CJA',
    'MANTA':      'Manta',
    'ORELLANA':   'Orellana',
    'PORTOVIEJO': 'Portoviejo',
    'LA Y':       'La Y',
    'TUMBACO':    'Tumbaco',
    'MACHALA':    'Machala',
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


def _norm_asesor(s):
    if not isinstance(s, str):
        return None
    s = ' '.join(s.strip().upper().split())
    return s or None


def _norm_canal(s):
    if not isinstance(s, str):
        return None
    s = s.strip()
    if not s or s.lower() == 'nan':
        return None
    return s


def _load_stage(path):
    """Lee un archivo de etapa, devuelve DataFrame con id + MODELO_N + ASESOR + CANAL,
    explotando los registros multi-modelo (una fila por (id, modelo))."""
    df = pd.read_excel(path, sheet_name=0)
    if 'Modelo' not in df.columns or 'id' not in df.columns:
        return pd.DataFrame(columns=['id', 'MODELO_N', 'ASESOR', 'CANAL'])
    rows = []
    for _, r in df.iterrows():
        if pd.isna(r['id']):
            continue
        ase = _norm_asesor(r.get('Asesor'))
        canal = _norm_canal(r.get('Canal'))
        for mod in _split_modelos(r['Modelo']):
            rows.append({'id': r['id'], 'MODELO_N': mod, 'ASESOR': ase, 'CANAL': canal})
    if not rows:
        return pd.DataFrame(columns=['id', 'MODELO_N', 'ASESOR', 'CANAL'])
    return pd.DataFrame(rows)


def compute_embudo_agencia(agencia_dir, mes, short_agencia):
    """Procesa el embudo de una agencia/mes. Devuelve dict con etapas, por_modelo, etc."""
    folder = agencia_dir / mes
    if not folder.exists():
        return None
    def _find_stage_file(fname):
        """Busca el archivo de etapa tolerando tildes/mayúsculas y singular/plural
        (ej. 'Cotización.xlsx' vs 'Cotizaciones.xlsx' vs 'Cotizacion.xlsx')."""
        import unicodedata
        def _strip(s):
            return ''.join(c for c in unicodedata.normalize('NFD', s)
                           if unicodedata.category(c) != 'Mn').lower()
        def _stem(s):
            # quita el sufijo plural ('es' o 's') para que 'cotizaciones'/'cotizacion' colapsen
            s = _strip(s)
            if s.endswith('es') and len(s) > 5:
                return s[:-2]
            if s.endswith('s') and len(s) > 4:
                return s[:-1]
            return s
        target_full = _strip(fname)
        target_stem = _stem(fname)
        import difflib
        # 1ª pasada: match exacto o por raíz
        candidates = []
        for p in folder.glob('*.xlsx'):
            if p.name.startswith('~$'):
                continue
            cand_full = _strip(p.stem)
            if cand_full == target_full:
                return p
            if _stem(p.stem) == target_stem:
                return p
            candidates.append((p, cand_full))
        # 2ª pasada: fuzzy match (tolera typos tipo 'Aptobaciones' vs 'Aprobaciones')
        if candidates:
            best, best_ratio = None, 0
            for p, cand in candidates:
                # comparar contra full y stem
                r = max(difflib.SequenceMatcher(None, cand, target_full).ratio(),
                        difflib.SequenceMatcher(None, _stem(p.stem), target_stem).ratio())
                if r > best_ratio:
                    best_ratio, best = r, p
            if best_ratio >= 0.85:
                return best
        return None

    stage_dfs = {}
    for fname, label in STAGES:
        p = _find_stage_file(fname)
        if p and p.exists():
            stage_dfs[label] = _load_stage(p)
        else:
            stage_dfs[label] = pd.DataFrame(columns=['id', 'MODELO_N', 'ASESOR', 'CANAL'])

    labels = [lbl for _, lbl in STAGES]

    # Asesores canónicos (del embudo) para matchear con el inventario
    asesores_canon = set()
    for lbl in labels:
        asesores_canon.update(stage_dfs[lbl]['ASESOR'].dropna().unique().tolist())
    asesores_canon = sorted(asesores_canon)

    # ── CIERRE desde el INVENTARIO (ventas facturadas reales), no del archivo Cierre.xlsx ──
    cierre_modelo, cierre_version, cierre_asesor, cierre_total = _ventas_inventario(
        short_agencia, mes, asesores_canonicos=asesores_canon)

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

    # Por asesor × etapa = negocios únicos por asesor; cierre desde inventario
    asesores = sorted(set(asesores_canon) | set(cierre_asesor.keys()))
    por_asesor = {}
    for ase in asesores:
        fila = {}
        for lbl in labels:
            if lbl == 'Cierre':
                fila[lbl] = int(cierre_asesor.get(ase, 0))
            else:
                d = stage_dfs[lbl]
                fila[lbl] = int(d[d['ASESOR'] == ase]['id'].nunique())
        if sum(fila.values()) > 0:
            por_asesor[ase] = fila

    # ── MATRIZ asesor × canal con cotizaciones y cierres ──
    # Para que la "tasa de cierre por asesor × canal" sea consistente, se usa
    # el archivo Cierre.xlsx (que tiene Canal y Asesor) como numerador, y
    # Cotizaciones.xlsx como denominador.
    cotiz_ase_ch = {}  # {asesor: {canal: n_negocios_únicos}}
    cierre_ase_ch = {}
    sol_ase_ch = {}    # solicitudes por (asesor, canal)
    apr_ase_ch = {}    # aprobaciones por (asesor, canal)
    sol_por_canal = {} # solicitudes por canal
    apr_por_canal = {} # aprobaciones por canal
    sol_por_modelo = {}# solicitudes por modelo
    apr_por_modelo = {}# aprobaciones por modelo
    df_cot = stage_dfs.get('Cotización', pd.DataFrame())
    df_cie = stage_dfs.get('Cierre', pd.DataFrame())
    df_sol = stage_dfs.get('Solicitud', pd.DataFrame())
    df_apr = stage_dfs.get('Aprobación', pd.DataFrame())
    # Cotización: negocios únicos (id) por (asesor, canal)
    if not df_cot.empty:
        dedup = df_cot.dropna(subset=['ASESOR','CANAL']).drop_duplicates(subset=['id','ASESOR','CANAL'])
        for _, r in dedup.iterrows():
            cotiz_ase_ch.setdefault(r['ASESOR'], {})
            cotiz_ase_ch[r['ASESOR']][r['CANAL']] = cotiz_ase_ch[r['ASESOR']].get(r['CANAL'],0)+1
    if not df_cie.empty:
        dedup = df_cie.dropna(subset=['ASESOR','CANAL']).drop_duplicates(subset=['id','ASESOR','CANAL'])
        for _, r in dedup.iterrows():
            cierre_ase_ch.setdefault(r['ASESOR'], {})
            cierre_ase_ch[r['ASESOR']][r['CANAL']] = cierre_ase_ch[r['ASESOR']].get(r['CANAL'],0)+1
    # Solicitudes: negocios únicos por (asesor, canal) y por canal/modelo
    if not df_sol.empty:
        dedup = df_sol.dropna(subset=['ASESOR','CANAL']).drop_duplicates(subset=['id','ASESOR','CANAL'])
        for _, r in dedup.iterrows():
            sol_ase_ch.setdefault(r['ASESOR'], {})
            sol_ase_ch[r['ASESOR']][r['CANAL']] = sol_ase_ch[r['ASESOR']].get(r['CANAL'],0)+1
        # por canal: negocios únicos
        for canal, n in df_sol.dropna(subset=['CANAL']).drop_duplicates(subset=['id','CANAL'])['CANAL'].value_counts().items():
            sol_por_canal[canal] = int(n)
        # por modelo: negocios únicos
        for modelo, n in df_sol.drop_duplicates(subset=['id','MODELO_N'])['MODELO_N'].value_counts().items():
            sol_por_modelo[modelo] = int(n)
    if not df_apr.empty:
        dedup = df_apr.dropna(subset=['ASESOR','CANAL']).drop_duplicates(subset=['id','ASESOR','CANAL'])
        for _, r in dedup.iterrows():
            apr_ase_ch.setdefault(r['ASESOR'], {})
            apr_ase_ch[r['ASESOR']][r['CANAL']] = apr_ase_ch[r['ASESOR']].get(r['CANAL'],0)+1
        for canal, n in df_apr.dropna(subset=['CANAL']).drop_duplicates(subset=['id','CANAL'])['CANAL'].value_counts().items():
            apr_por_canal[canal] = int(n)
        for modelo, n in df_apr.drop_duplicates(subset=['id','MODELO_N'])['MODELO_N'].value_counts().items():
            apr_por_modelo[modelo] = int(n)

    # Conversión de CADA etapa vs la base del embudo (Cotización = labels[0])
    base = totales[labels[0]]
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
        'por_asesor': por_asesor,
        'cotiz_asesor_canal': cotiz_ase_ch,
        'cierre_asesor_canal': cierre_ase_ch,
        'sol_asesor_canal': sol_ase_ch,
        'apr_asesor_canal': apr_ase_ch,
        'sol_por_canal': sol_por_canal,
        'apr_por_canal': apr_por_canal,
        'sol_por_modelo': sol_por_modelo,
        'apr_por_modelo': apr_por_modelo,
        'conversion_etapa': conv,
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
        meses = sorted([p.name for p in agencia_dir.iterdir() if p.is_dir()],
                       key=lambda m: MES_NUM.get(m, 99))  # orden cronológico, no alfabético
        out['meses'][short] = meses
        out['agencias'][short] = {}
        for mes in meses:
            r = compute_embudo_agencia(agencia_dir, mes, short)
            if r:
                out['agencias'][short][mes] = r
    if not out['agencias']:
        return None
    out['default_agencia'] = next(iter(out['agencias'].keys()))
    # Mapa agencia → región (provincia) y agrupación inversa región → [agencias]
    out['region_agencia'] = {ag: AGENCY_REGION.get(ag, '(Sin región)') for ag in out['agencias'].keys()}
    out['agencias_por_region'] = {}
    for ag, reg in out['region_agencia'].items():
        out['agencias_por_region'].setdefault(reg, []).append(ag)
    return out


if __name__ == '__main__':
    import json
    d = compute_embudo_data()
    print(json.dumps(d, indent=2, ensure_ascii=False)[:2000])
