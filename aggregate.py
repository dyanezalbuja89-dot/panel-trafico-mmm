"""Aggregates Excel traffic data into anonymous JSON for the dashboard.
Includes Ford-specific processed data matching ford_traffic_generator.py logic.
"""
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from inventario import load_inventario, DEFAULT_INVENTORY_PATH
from conversion import compute_conversion_metrics, norm_ced as _conv_norm_ced, cedula_base as _conv_cedula_base, norm_email as _conv_norm_email, norm_cel as _conv_norm_cel
from competencia import compute_competencia_data
from embudo import compute_embudo_data

def _compute_embudo_safe():
    try:
        return compute_embudo_data()
    except Exception as e:
        print(f"WARN: embudo no disponible: {e}")
        return None

def _compute_ventas_mensual(sales_df):
    """Pivot mensual de ventas NETAS por marca/modelo/asesor/agencia.
    Devuelve {marca_key: {months, months_labels, by_modelo, by_asesor, by_agencia, totals}}.
    Cantidad ya viene signada (+1 FACTURA, -1 NC) desde ventas.load_ventas().
    """
    if sales_df is None or len(sales_df) == 0:
        return None
    df = sales_df.copy()
    df['fecha_fact'] = pd.to_datetime(df.get('fecha de facturacion'), errors='coerce')
    df = df[df['fecha_fact'].dt.year == 2026].copy()
    if len(df) == 0:
        return None
    df['mes'] = df['fecha_fact'].dt.strftime('%Y-%m')
    df['Cantidad'] = df['Cantidad'].fillna(1).astype(int)
    df['marca_up'] = df['marca'].astype(str).str.strip().str.upper()
    df['modelo_up'] = df['familia'].astype(str).str.strip().str.upper()
    df['asesor'] = df['ASESOR_FACTURACION'].astype(str).str.strip().str.upper().replace({'NAN': 'Sin asesor', '': 'Sin asesor'})
    # Agencia: el archivo de ventas trae "Bodega Venta Vehiculo" (e.g. "1001 VEHICULOS CARLOS JULIO AROSEMENA").
    # Normalizamos a corto via fact_agency_norm de inventario.py.
    from inventario import fact_agency_norm
    df['agencia'] = df['AGENCIA_FACTURACION'].apply(lambda s: fact_agency_norm(s) or 'Sin agencia')
    months_all = sorted(df['mes'].unique())
    MES_LBL = {'2026-01':'Enero','2026-02':'Febrero','2026-03':'Marzo','2026-04':'Abril','2026-05':'Mayo','2026-06':'Junio','2026-07':'Julio','2026-08':'Agosto','2026-09':'Septiembre','2026-10':'Octubre','2026-11':'Noviembre','2026-12':'Diciembre'}

    BRAND_KEY_MAP = {'FORD':'FORD','DONGFENG':'DONGFENG_ORGU','CHERY':'CHERY_ORGU','MAZDA':'MAZDA_ORGU','RAM':'RAM_ORGU'}
    # Mapa agencia → zona (mismo del módulo conversion.py)
    ZONA_MAP = {
        'CJA':'Guayaquil','Orellana':'Guayaquil',
        'La Y':'Quito','Tumbaco':'Quito',
        'Manta':'Manta','Portoviejo':'Manta',
        'Machala':'Machala',
    }
    df['zona'] = df['agencia'].apply(lambda a: ZONA_MAP.get(a, 'Otra'))

    def _pivot_dim(sub_df, dim_col):
        out = {}
        for key, g in sub_df.groupby(dim_col):
            if not key or str(key).lower() in ('nan','none'):
                continue
            per_mes = g.groupby('mes')['Cantidad'].sum().astype(int).to_dict()
            row = {m: int(per_mes.get(m, 0)) for m in months_all}
            row['_total'] = int(sum(row.values()))
            out[str(key)] = row
        return out

    result = {}
    for marca_raw, brand_key in BRAND_KEY_MAP.items():
        sub = df[df['marca_up'] == marca_raw]
        if len(sub) == 0:
            continue
        # Flat rows — el cliente hace pivot dinámico con filtros agencia/zona/modelo.
        flat = []
        for _, r in sub.iterrows():
            flat.append({
                'mes': str(r['mes']),
                'modelo': str(r['modelo_up']) if r['modelo_up'] and str(r['modelo_up']).lower() not in ('nan','none','') else 'Sin modelo',
                'asesor': str(r['asesor']) if r['asesor'] and str(r['asesor']).lower() not in ('nan','sin asesor','none','') else 'Sin asesor',
                'agencia': str(r['agencia']),
                'zona': str(r['zona']),
                'cantidad': int(r['Cantidad']),
            })
        # Pivots agregados (compat hacia atrás; el cliente puede usarlos cuando no hay filtros)
        by_modelo = _pivot_dim(sub, 'modelo_up')
        by_asesor = {}
        for asesor, g in sub.groupby('asesor'):
            if not asesor or asesor.lower() in ('nan','sin asesor','none'):
                continue
            per_mes = g.groupby('mes')['Cantidad'].sum().astype(int).to_dict()
            row = {m: int(per_mes.get(m, 0)) for m in months_all}
            row['_total'] = int(sum(row.values()))
            row['_por_modelo'] = {
                str(mk): int(mv) for mk, mv in g.groupby('modelo_up')['Cantidad'].sum().astype(int).to_dict().items()
                if mk and str(mk).lower() not in ('nan','none')
            }
            row['_agencia'] = g['agencia'].mode().iloc[0] if len(g['agencia'].mode()) else 'Sin agencia'
            row['_zona'] = g['zona'].mode().iloc[0] if len(g['zona'].mode()) else 'Otra'
            by_asesor[str(asesor)] = row
        by_agencia = _pivot_dim(sub, 'agencia')
        by_zona = _pivot_dim(sub, 'zona')
        per_mes_total = sub.groupby('mes')['Cantidad'].sum().astype(int).to_dict()
        totals = {m: int(per_mes_total.get(m, 0)) for m in months_all}
        totals['_total'] = int(sum(totals.values()))
        result[brand_key] = {
            'months': months_all,
            'months_labels': [MES_LBL.get(m, m) for m in months_all],
            'totals': totals,
            'by_modelo': by_modelo,
            'by_asesor': by_asesor,
            'by_agencia': by_agencia,
            'by_zona': by_zona,
            'flat': flat,
        }
    return result

BASE = Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Análisis de tráfico/2026/Mayo")
ABRIL_BASE = Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Análisis de tráfico/2026/Abril")
# Files used for Dashboard tab "Marzo (cierre) vs Abril (cierre)" comparison
MARZO  = BASE / "BD_MAYO/BD_MARZO_31_03_26.xlsx"
ABRIL  = BASE / "BD_MAYO/BD_ABR_30_04_26.xlsx"
ABRIL_PREV = BASE / "BD_MAYO/BD_ABR_29_04_26.xlsx"
# Brand metas file: default (Abril) for prior months, Mayo file for Mayo, Junio for Junio
DEFAULT_BRAND_METAS_FILE = ABRIL_BASE / "TRAFICO_DY/ABR_NUEVO_AI_MARCAS.xlsx"
MAY_BRAND_METAS_FILE = BASE / "TRAFICO_DY/MAY_NUEVO_AI_MARCAS.xlsx"
JUN_BASE = Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Análisis de tráfico/2026/Junio")
JUN_BRAND_METAS_FILE = JUN_BASE / "TRAFICO_DY/JUNIO_NUEVO_AI_MARCAS.xlsx"
# Ford metas files por mes (cada uno con metas oficiales del mes)
ENE_FORD_METAS_FILE = BASE / "TRAFICO_DY/ENE_NUEVO_AI_FORD.xlsx"
FEB_FORD_METAS_FILE = BASE / "TRAFICO_DY/FEB_NUEVO_AI_FORD.xlsx"
MAR_FORD_METAS_FILE = BASE / "TRAFICO_DY/MAR_NUEVO_AI_FORD.xlsx"
ABR_FORD_METAS_FILE = ABRIL_BASE / "TRAFICO_DY/ABR_NUEVO_AI_FORD.xlsx"
MAY_FORD_METAS_FILE = BASE / "TRAFICO_DY/MAY_NUEVO_AI_FORD.xlsx"
JUN_FORD_METAS_FILE = JUN_BASE / "TRAFICO_DY/JUNIO_NUEVO_AI_FORD.xlsx"

# ---------------- SHORT NAMES ----------------
SUCURSAL_TO_SHORT = {
    "AUTOSHARECORP CARLOS JULIO AROSEMENA": "CJA",
    "AUTOSHARECORP ORELLANA": "Orellana",
    "AUTOSHARECORP LA Y": "La Y",
    "AUTOSHARECORP TUMBACO": "Tumbaco",
    "AUTOSHARECORP MANTA": "Manta",
    "AUTOSHARECORP MACHALA": "Machala",
    "AUTOSHARECORP PORTOVIEJO": "Portoviejo",
    "ORGU LA Y DONGFENG": "La Y (DF)",
    "ORGU LA Y EXONERADOS  DONGFENG": "La Y (DF)",
    "ORGU MACHALA  DONGFENG": "Machala (DF)",
    "ORGU MACHALA DONGFENG": "Machala (DF)",
    "ORGU MACHALA CHERY": "Machala (Chery)",
    "ORGU MACHALA MAZDA": "Machala (Mazda)",
    "ORGU MACHALA EXONERADOS MAZDA": "Machala (Mazda)",
    "ORGU MACHALA STELLANTIS": "Machala (Stellantis)",
    "ORGU MACHALA EXONERADOS STELLANTIS": "Machala (Stellantis)",
}

CHANNEL_NORM = {
    "REDES SOCIALES PROPIAS": "Redes Sociales Propias",
    "Redes Sociales Propias": "Redes Sociales Propias",
    "Prospeccion": "Prospección",
}

FUNNEL_ORDER = ["Indagación", "Cotización", "Demostración", "Cierre", "Entrega"]

# ---------------- FORD CONFIG (copied from ford_traffic_generator.py) ----------------
DEALERS = ['CJA', 'Orellana', 'La Y', 'Tumbaco', 'Manta', 'Machala', 'Portoviejo']

# Cada agencia acepta TODAS las variantes de canal válido (Showroom/Hubspot/Ferias y Eventos|
# Feria/Eventos|Ferias/Llamada In). El BD usa diferentes spellings y antes algunas variantes
# caían a "Otros" por mismatch (e.g. Tumbaco filtraba sólo 'Ferias' pero el BD trae 'Feria/Eventos').
_DEALER_CHANNELS = ['Showroom', 'Hubspot', 'Ferias y Eventos', 'Feria/Eventos', 'Ferias', 'Llamada In']
DEALER_CONFIG = {
    'CJA':        ('CARLOS JULIO', _DEALER_CHANNELS),
    'Orellana':   ('ORELLANA',     _DEALER_CHANNELS),
    'La Y':       ('LA Y',         _DEALER_CHANNELS),
    'Tumbaco':    ('TUMBACO',      _DEALER_CHANNELS),
    'Manta':      ('MANTA',        _DEALER_CHANNELS),
    'Machala':    ('MACHALA',      _DEALER_CHANNELS),
    'Portoviejo': ('PORTOVIEJO',   _DEALER_CHANNELS),
}

MODEL_METAS = {
    'TERRITORY':  [5, 0, 0, 0, 0, 0, 0],
    'ESCAPE':     [27, 27, 16, 21, 16, 11, 5],
    'EVEREST':    [16, 16, 11, 11, 11, 0, 5],
    'EXPLORER':   [0, 11, 5, 0, 0, 0, 0],
    'EXPEDITION': [0, 0, 0, 0, 0, 0, 0],
    'BRONCO':     [0, 0, 0, 0, 0, 0, 0],
    'F-150':      [0, 5, 0, 5, 5, 5, 0],
    'RANGER':     [21, 21, 5, 11, 11, 5, 5],
}
MODEL_ORDER = ['TERRITORY','ESCAPE','EVEREST','EXPLORER','EXPEDITION','BRONCO','F-150','RANGER']
VALID_TRAFFIC_CHANNELS = ['Showroom','Hubspot','Ferias y Eventos','Feria/Eventos','Ferias','Llamada In']
# Clasificación por origen del tráfico (Marketing ~80% vs Asesor Comercial ~20%)
MARKETING_CHANNELS = ['Showroom','Hubspot','Ferias y Eventos','Feria/Eventos','Ferias','Llamada In']
ASESOR_CHANNELS = ['Recompra','Referido por Cliente','Referidos por empleado','Gestión Externa',
                   'Prospección','Empleado','Talleres','Redes Sociales Propias','Catálogo público']
ALL_TRAFFIC_CHANNELS = MARKETING_CHANNELS + ASESOR_CHANNELS
# Split estructural de la meta total (definido por el Excel METAS_FORD: row 77 = 0.8):
#   meta total (TRÁFICO POR CONCESIONARIO)        = 100%
#   meta marketing (PRESUPUESTO MARKETING)        =  80% del total  ← lo que carga load_ford_metas
#   meta asesor comercial                          =  20% del total  ← derivado (cuadro de arriba - marketing)
# Esto permite que, en la pestaña Otros, al filtrar por categoría de canal la meta
# se ajuste consistentemente al subset.
META_MARKETING_PCT = 0.80
META_ASESOR_PCT    = 0.20
ZONES = {
    'Quito':     ['Tumbaco','La Y'],
    'Guayaquil': ['CJA','Orellana'],
    'Manta':     ['Manta','Portoviejo'],
    'Machala':   ['Machala'],
}
HOLIDAYS_2026 = [(1,1),(1,2),(2,16),(2,17),(4,2),(4,3),(5,1),(5,25),(8,10),(10,9),(11,2),(11,3),(12,25)]
HOLIDAYS_2025 = [(1,1),(3,3),(3,4),(4,18),(5,1),(5,26),(8,11),(10,9),(11,3),(12,25)]
HOLIDAYS_BY_YEAR = {2025: HOLIDAYS_2025, 2026: HOLIDAYS_2026}

def daily_cum_filtered(df):
    """Returns {daily:{day:n}, cum:{day:cum_n}} from a filtered df."""
    s = df.dropna(subset=["FECHA"]).copy()
    if s.empty:
        return {"daily": {}, "cum": {}}
    s["DAY"] = s["FECHA"].dt.day
    daily = s.groupby("DAY").size().sort_index()
    cum = daily.cumsum()
    return {"daily": {int(k): int(v) for k, v in daily.items()},
            "cum":   {int(k): int(v) for k, v in cum.items()}}

def expected_pace_calendar(month, year, meta_total, days_lab, extra_non_working=None):
    """Returns list of {day, wd, expected, is_wd} for each calendar day of the month.
    'expected' = ritmo ideal acumulado al final del día (lineal vs días laborables).
    extra_non_working: lista de (month, day) que se tratan como no-laborables además
    de domingos y feriados (e.g. [(5,2)] para overrides puntuales)."""
    holidays_set = {(m, d) for m, d in HOLIDAYS_BY_YEAR.get(year, HOLIDAYS_2026)}
    if extra_non_working:
        holidays_set.update(extra_non_working)
    if month == 12:
        last_day = 31
    else:
        last_day = (pd.Timestamp(year=year, month=month+1, day=1) - timedelta(days=1)).day
    out = []
    wd_count = 0
    for d in range(1, last_day+1):
        date = pd.Timestamp(year=year, month=month, day=d)
        is_wd = date.weekday() <= 5 and (month, d) not in holidays_set
        if is_wd:
            wd_count += 1
        expected = round(meta_total * wd_count / days_lab, 1) if days_lab else 0
        out.append({"day": d, "wd": wd_count, "expected": expected, "is_wd": bool(is_wd)})
    return out

def working_days(month, year, up_to_day=None, extra_non_working=None):
    holidays_set = {(m,d) for m,d in HOLIDAYS_BY_YEAR.get(year, HOLIDAYS_2026)}
    if extra_non_working:
        holidays_set.update(extra_non_working)
    if month == 12: last_day = 31
    else: last_day = (pd.Timestamp(year=year,month=month+1,day=1) - timedelta(days=1)).day
    if up_to_day is None: up_to_day = last_day
    total = trans = 0
    for day in range(1, last_day+1):
        d = pd.Timestamp(year=year, month=month, day=day)
        if d.weekday() <= 5 and (month,day) not in holidays_set:
            total += 1
            if day <= up_to_day: trans += 1
    return total, trans

def short_agency(s):
    return SUCURSAL_TO_SHORT.get(str(s).strip(), str(s).strip())

def norm_channel(c):
    c = " ".join(str(c).strip().split())
    return CHANNEL_NORM.get(c, c)

def normalize_modelo_ford(m):
    if not isinstance(m,str): return ''
    m = m.upper().strip()
    return 'F-150' if m == 'F150' else m

def _infer_marca_from_sucursal(sucursal):
    """Cuando la columna MARCA viene vacía (error de carga del CRM), inferir
    la marca desde el nombre de la SUCURSAL. El patrón es inequívoco:
      'ORGU LA Y DONGFENG' → DONGFENG_ORGU
      'AUTOSHARECORP ...'  → FORD
      '... MAZDA'          → MAZDA_ORGU, etc.
    Devuelve None si no se puede inferir."""
    if not isinstance(sucursal, str):
        return None
    s = sucursal.upper()
    if 'DONGFENG' in s:      return 'DONGFENG_ORGU'
    if 'MAZDA' in s:         return 'MAZDA_ORGU'
    if 'CHERY' in s:         return 'CHERY_ORGU'
    if 'RAM' in s:           return 'RAM_ORGU'
    if 'AUTOSHARECORP' in s: return 'FORD'  # AUTOSHARECORP = concesionario Ford
    return None

def load_raw(path):
    df = pd.read_excel(path, sheet_name="Negocios")
    df["AGENCIA"] = df["SUCURSAL"].apply(short_agency)
    df["CANAL"] = df["CANAL"].apply(norm_channel)
    df["MODELO"] = df["MODELO"].astype(str).str.strip().str.upper()
    df["MARCA"] = df["MARCA"].astype(str).str.strip()
    # Inferir MARCA desde SUCURSAL cuando está vacía/NaN (error de carga del CRM).
    # Sin esto el panel descarta registros reales con MARCA en blanco (ej. 14
    # DongFeng La Y en mayo cuya celda MARCA quedó vacía).
    _marca_vacia = df["MARCA"].isin(['', 'nan', 'NaN', 'None', 'NONE'])
    df.loc[_marca_vacia, "MARCA"] = df.loc[_marca_vacia, "SUCURSAL"].apply(
        lambda s: _infer_marca_from_sucursal(s) or '')
    # Normalize legacy brand names (BDs 2025 used CHERY/DONGFENG/MAZDA/RAM sin sufijo _ORGU)
    df["MARCA"] = df["MARCA"].replace({
        'CHERY': 'CHERY_ORGU', 'DONGFENG': 'DONGFENG_ORGU',
        'MAZDA': 'MAZDA_ORGU', 'RAM': 'RAM_ORGU',
    })
    df["ESTADO"] = df["ESTADO"].astype(str).str.strip()
    df["ASESOR"] = df["ASESOR"].astype(str).str.strip()
    df["CAMPAÑA"] = df["CAMPAÑA"].astype(str).str.strip()
    df["FECHA"] = pd.to_datetime(df["FECHA"], errors="coerce")
    return df

# ---------------- DASHBOARD AGGREGATION (all-brand) ----------------
def count_by(df, col): return dict(df[col].value_counts().to_dict())
def cross(df, row, col):
    ct = pd.crosstab(df[row], df[col])
    return {r: {c: int(ct.loc[r, c]) for c in ct.columns} for r in ct.index}
def daily_cum(df):
    s = df.dropna(subset=["FECHA"]).copy()
    s["DAY"] = s["FECHA"].dt.day
    daily = s.groupby("DAY").size().sort_index()
    cum = daily.cumsum()
    return {"daily": {int(k): int(v) for k,v in daily.items()},
            "cum":   {int(k): int(v) for k,v in cum.items()}}
def funnel(df):
    vc = df["ESTADO"].value_counts().to_dict()
    return {k: int(vc.get(k,0)) for k in FUNNEL_ORDER}

def summarize(df, label):
    d = {
        "label": label,
        "total": int(len(df)),
        "byAgency": count_by(df,"AGENCIA"),
        "byChannel": count_by(df,"CANAL"),
        "byModel": count_by(df,"MODELO"),
        "byBrand": count_by(df,"MARCA"),
        "byStatus": funnel(df),
        "byAdvisor": dict(df["ASESOR"].value_counts().head(20).to_dict()),
        "byCampaign": dict(df["CAMPAÑA"].value_counts().head(15).to_dict()),
        "daily": daily_cum(df),
        "agencyChannel": cross(df,"AGENCIA","CANAL"),
        "agencyModel":   cross(df,"AGENCIA","MODELO"),
        "agencyStatus":  cross(df,"AGENCIA","ESTADO"),
    }
    aa = {}
    for ag in df["AGENCIA"].unique():
        sub = df[df["AGENCIA"]==ag]
        aa[ag] = {
            "topAdvisors": dict(sub["ASESOR"].value_counts().head(10).to_dict()),
            "topCampaigns": dict(sub["CAMPAÑA"].value_counts().head(10).to_dict()),
            "byChannel": dict(sub["CANAL"].value_counts().to_dict()),
            "byModel":   dict(sub["MODELO"].value_counts().to_dict()),
            "byStatus":  {k: int(sub["ESTADO"].value_counts().get(k,0)) for k in FUNNEL_ORDER},
            "total": int(len(sub)),
        }
    d["agencyDetail"] = aa
    return d

# ---------------- FORD PROCESSING ----------------
def process_bd_ford(df, channels=None):
    """Filtra registros Ford. Fuente de verdad: MARCA == FORD.

    NO se filtra por SUCURSAL=AUTOSHARECORP (cambio 2026-05-19) para
    evitar perder negocios reales mal categorizados.

    Dedupe por SOLO CEDULA: 1 persona = 1 negocio (independiente de
    cuántos modelos haya explorado). El último registro cronológico
    determina el modelo asignado.

    channels=None → VALID_TRAFFIC_CHANNELS (marketing only)
    channels=ALL_TRAFFIC_CHANNELS → marketing + asesor comercial
    """
    if channels is None:
        channels = VALID_TRAFFIC_CHANNELS
    df = df[df["MARCA"] == "FORD"].copy()
    df["MODELO_F"] = df["MODELO"].apply(normalize_modelo_ford)
    df["MODELO_F"] = df["MODELO_F"].astype(str).str.strip().str.upper()
    df.loc[df["MODELO_F"].isin(['NAN','NONE','']) | df["MODELO_F"].isna(), "MODELO_F"] = 'Por definir'
    # ► Dedup por cédula: si un cliente tiene varias filas en el mes, preferimos
    # la última que TENGA modelo válido. Antes hacíamos keep='last' por fecha,
    # lo que podía dejar 'Por definir' si la fila más reciente del cliente
    # estaba sin modelo (típico cuando un asesor reabre el negocio sin completarlo).
    df["_has_model"] = (~df["MODELO_F"].isin(['Por definir'])).astype(int)
    df = df.sort_values(["FECHA", "_has_model"])  # con modelo va al final
    df = df.drop_duplicates(subset=["CEDULA"], keep="last")
    df = df.drop(columns=["_has_model"])
    df = df[df["CANAL"].isin(channels)]
    return df

def get_dealer_df(df, dealer):
    pattern, channels = DEALER_CONFIG[dealer]
    mask = (df["SUCURSAL"].str.contains(pattern, case=False, na=False)) & (df["CANAL"].isin(channels))
    return df[mask]

# Mapeo modelo específico del Excel METAS_FORD → modelo del panel
FORD_META_MODEL_MAP = {
    'Territory Titanium FHEV':        'TERRITORY',
    'Escape Titanium 1.5 GAS':        'ESCAPE',
    'Escape ST':                      'ESCAPE',
    'Everest Active':                 'EVEREST',
    'Explorer Active':                'EXPLORER',
    'Explorer Platinum':              'EXPLORER',
    'Expedition Platinum':            'EXPEDITION',
    'Bronco Badlands':                'BRONCO',
    'F-150 XLT':                      'F-150',
    'F-150 Lariat':                   'F-150',
    'F-150 Platinum':                 'F-150',
    'F-150 RAPTOR':                   'F-150',
    'All new ranger XL 4x4 MT':       'RANGER',
    'All new ranger XLT 4x4 AT':      'RANGER',
    'All new Ranger Raptor':          'RANGER',
}

def load_ford_meta_breakdown(path):
    """Extrae del tab METAS_FORD los cuadros 'PRESUPUESTO NACIONAL' (meta ventas)
    y 'RESERVAS POR CONCESIONARIO' (reservas pre-mes) agrupados por modelo.
    Devuelve {modelo: {meta_ventas: int, reservas_pre: int, por_agencia: {ag: {meta_ventas, reservas_pre}}}}.
    Columnas en el Excel: 2..8 = CJA, Orellana, La Y, Tumbaco, Manta, Machala, Portoviejo. 9 = Total."""
    try:
        df = pd.read_excel(path, sheet_name='METAS_FORD', header=None)
    except Exception:
        return {}
    AGENCIAS_ORDER = ['CJA','Orellana','La Y','Tumbaco','Manta','Machala','Portoviejo']
    out = {m: {'meta_ventas': 0, 'reservas_pre': 0,
               'por_agencia': {ag: {'meta_ventas':0, 'reservas_pre':0} for ag in AGENCIAS_ORDER}}
           for m in MODEL_ORDER}

    def find_header(text_part):
        for i in range(min(60, len(df))):
            v = df.iloc[i, 0]
            if isinstance(v, str) and text_part in v.upper():
                return i
        return None
    h_ventas = find_header('PRESUPUESTO NACIONAL')
    h_reser  = find_header('RESERVAS POR CONCESIONARIO')

    def read_section(header_row, key):
        if header_row is None: return
        for i in range(header_row + 2, min(header_row + 25, len(df))):
            label = df.iloc[i, 0]
            if pd.isna(label): continue
            label = str(label).strip()
            if label.upper() == 'TOTAL': break
            modelo = FORD_META_MODEL_MAP.get(label)
            if not modelo or modelo not in out: continue
            # Totalcolumna 9
            total_raw = df.iloc[i, 9]
            if pd.notna(total_raw):
                try: out[modelo][key] += int(round(float(total_raw)))
                except (ValueError, TypeError): pass
            # Por agencia: columnas 2..8
            for ag_idx, ag in enumerate(AGENCIAS_ORDER, start=2):
                ag_raw = df.iloc[i, ag_idx]
                if pd.notna(ag_raw):
                    try: out[modelo]['por_agencia'][ag][key] += int(round(float(ag_raw)))
                    except (ValueError, TypeError): pass

    read_section(h_ventas, 'meta_ventas')
    read_section(h_reser,  'reservas_pre')
    return out

def load_ford_metas(path):
    """Load per-agency Ford metas from a workbook with sheets CJA/Orellana/LA Y/Tumbaco/Manta/Machala/Portoviejo.
    Sólo escanea el bloque inicial "CUMPLIMIENTO POR MODELO" (header 'Meta Mensual' en col[1]).
    Para evitar leer tablas posteriores como MATRIZ MODELO×CANAL que reusan los mismos BD Keys.
    Returns: {model: [meta_CJA, meta_Orellana, meta_LaY, meta_Tumbaco, meta_Manta, meta_Machala, meta_Portoviejo]}
    """
    sheet_to_idx = {'CJA':0, 'Orellana':1, 'LA Y':2, 'Tumbaco':3, 'Manta':4, 'Machala':5, 'Portoviejo':6}
    out = {m: [0]*7 for m in MODEL_ORDER}
    for sheet, idx in sheet_to_idx.items():
        try:
            df = pd.read_excel(path, sheet_name=sheet, header=None)
        except Exception:
            continue
        # Encontrar el header "Meta Mensual" en col[1]
        header_row = None
        for i in range(len(df)):
            v = df.iloc[i, 1]
            if isinstance(v, str) and 'Meta Mensual' in v:
                header_row = i; break
        if header_row is None: continue
        # Escanear filas siguientes hasta encontrar 'TOTAL' o fila vacía
        for i in range(header_row + 1, len(df)):
            v0 = df.iloc[i, 0]
            if pd.notna(v0) and isinstance(v0, str) and v0.strip().upper() == 'TOTAL':
                break
            key_raw = df.iloc[i, 7]
            if pd.isna(key_raw): continue
            key = str(key_raw).strip().upper()
            if key == 'F150': key = 'F-150'
            if key not in MODEL_ORDER: continue
            meta_raw = df.iloc[i, 1]
            if pd.notna(meta_raw):
                try: out[key][idx] = int(meta_raw)
                except (ValueError, TypeError): pass
    return out

def ford_report(curr_raw, prev_raw, month, year, up_to_day, model_metas=None, extra_non_working=None):
    metas = model_metas if model_metas is not None else MODEL_METAS
    """Builds everything the ford tab needs: KPIs, per-model, per-agency, matrix, movements, at-risk."""
    curr = process_bd_ford(curr_raw)
    prev = process_bd_ford(prev_raw)
    # Versión con TODOS los canales (marketing + asesor) — usada únicamente para construir
    # el cross-tab dealer_model_channel del panel Otros. El resto del reporte sigue siendo
    # marketing-only para mantener compatibilidad con KPIs/metas/proyecciones existentes.
    curr_all = process_bd_ford(curr_raw, channels=ALL_TRAFFIC_CHANNELS)
    # Prev con todos los canales — habilita deltas curr vs prev para filtro Tipo de canal
    # (marketing/asesor/all) en tabs Ford/Brand/Comp.
    prev_all = process_bd_ford(prev_raw, channels=ALL_TRAFFIC_CHANNELS)

    days_lab, days_trans = working_days(month, year, up_to_day, extra_non_working=extra_non_working)
    avance_pct = round(100 * days_trans / days_lab) if days_lab else 0
    total_curr = int(len(curr))
    total_prev = int(len(prev))
    delta_total = total_curr - total_prev
    velocity = total_curr / days_trans if days_trans else 0
    projection_total = round(velocity * days_lab)

    # Lista de modelos: MODEL_ORDER + extras presentes en la data (ej. 'Por definir'
    # para registros con MODELO vacío). Así la matriz suma == total_curr y el tab
    # Ford no pierde registros. Las metas de los extras son 0.
    _extra_models = [m for m in set(list(curr["MODELO_F"].unique()) + list(prev["MODELO_F"].unique()))
                     if m and m not in MODEL_ORDER and m not in ('NAN','nan','','NONE','None')]
    model_order_f = list(MODEL_ORDER) + sorted(_extra_models)
    # Asegurar metas (ceros) para los modelos extra, para no romper indexaciones
    for _m in _extra_models:
        if _m not in metas:
            metas[_m] = [0]*len(DEALERS)

    # Per dealer
    dealer_data = {}
    dealer_model_matrix = {m: {} for m in model_order_f}  # matrix[model][dealer] = pct cumpl
    dealer_model_counts = {m: {} for m in model_order_f}  # matrix[model][dealer] = traffic count
    for i, dealer in enumerate(DEALERS):
        d_curr = get_dealer_df(curr, dealer)
        d_prev = get_dealer_df(prev, dealer)
        c_cnt = int(len(d_curr))
        p_cnt = int(len(d_prev))
        d_velocity = c_cnt / days_trans if days_trans else 0
        d_proj = round(d_velocity * days_lab)
        meta = sum(metas[m][i] for m in model_order_f)
        cumpl_proj = round(100 * d_proj / meta) if meta > 0 else 0
        dealer_data[dealer] = {
            "prev": p_cnt, "curr": c_cnt, "meta": meta,
            "projection": d_proj, "velocity": round(d_velocity,2),
            "cumpl_proj": cumpl_proj,
            "byModel": {m: int(len(d_curr[d_curr["MODELO_F"]==m])) for m in model_order_f},
            "byChannel": dict(d_curr["CANAL"].value_counts().to_dict()),
        }
        # matrix values: cumpl actual = curr / meta * 100
        for m in model_order_f:
            mc = int(len(d_curr[d_curr["MODELO_F"]==m]))
            meta_mc = metas[m][i]
            dealer_model_counts[m][dealer] = mc
            if meta_mc == 0 and mc == 0:
                dealer_model_matrix[m][dealer] = -1  # sentinel: no meta, no traffic
            elif meta_mc == 0 and mc > 0:
                dealer_model_matrix[m][dealer] = 999  # sentinel: no meta, has traffic
            else:
                dealer_model_matrix[m][dealer] = round(100 * mc / meta_mc, 1)

    # "Otros" dealers: everything not in DEALERS (for Ford brand still)
    attributed_mask = False
    for dealer in DEALERS:
        pattern, channels = DEALER_CONFIG[dealer]
        m = (curr["SUCURSAL"].str.contains(pattern, case=False, na=False)) & (curr["CANAL"].isin(channels))
        attributed_mask = m if attributed_mask is False else (attributed_mask | m)
    otros_curr = curr[~attributed_mask]
    # prev otros
    attributed_prev = False
    for dealer in DEALERS:
        pattern, channels = DEALER_CONFIG[dealer]
        m = (prev["SUCURSAL"].str.contains(pattern, case=False, na=False)) & (prev["CANAL"].isin(channels))
        attributed_prev = m if attributed_prev is False else (attributed_prev | m)
    otros_prev = prev[~attributed_prev]
    otros_curr_cnt = int(len(otros_curr))
    otros_prev_cnt = int(len(otros_prev))
    otros_proj = round((otros_curr_cnt/days_trans if days_trans else 0) * days_lab)
    dealer_data["Otros"] = {
        "prev": otros_prev_cnt, "curr": otros_curr_cnt, "meta": 0,
        "projection": otros_proj, "velocity": round(otros_curr_cnt/days_trans if days_trans else 0, 2),
        "cumpl_proj": 0,
        "byModel": {m: int(len(otros_curr[otros_curr["MODELO_F"]==m])) for m in model_order_f},
        "byChannel": dict(otros_curr["CANAL"].value_counts().to_dict()),
    }

    # Per model (aggregate from dealer_model_counts + otros)
    model_data = {}
    for m in model_order_f:
        c = sum(dealer_model_counts[m].values()) + int(len(otros_curr[otros_curr["MODELO_F"]==m]))
        p = int(len(prev[prev["MODELO_F"]==m]))
        meta = sum(metas[m])
        # model projection
        vel = c / days_trans if days_trans else 0
        proj = round(vel * days_lab)
        cumpl_proj = round(100*proj/meta) if meta > 0 else 0
        model_data[m] = {
            "prev": p, "curr": c, "delta": c-p, "meta": meta,
            "projection": proj, "velocity": round(vel,2), "cumpl_proj": cumpl_proj,
            "byDealer": {d: dealer_model_counts[m][d] for d in DEALERS},
        }

    # Zones
    zone_data = {}
    for z, dealers in ZONES.items():
        zc = sum(dealer_data[d]["curr"] for d in dealers)
        zp = sum(dealer_data[d]["prev"] for d in dealers)
        zone_data[z] = {
            "dealers": dealers, "prev": zp, "curr": zc, "delta": zc-zp,
            "pct_total": round(100*zc/total_curr,1) if total_curr else 0,
        }

    # Dominant channel across Ford curr
    ch_counts = curr["CANAL"].value_counts().to_dict()
    dominant_channel = max(ch_counts, key=ch_counts.get) if ch_counts else "—"
    channel_pct = round(100*ch_counts.get(dominant_channel,0)/total_curr) if total_curr else 0

    # At-risk
    at_risk_models = [m for m in model_order_f if model_data[m]["meta"]>0 and model_data[m]["cumpl_proj"]<100]
    at_risk_agencies = [d for d in DEALERS if dealer_data[d]["meta"]>0 and dealer_data[d]["cumpl_proj"]<100]

    # Movements (sorted by abs delta desc)
    movements = []
    for m in model_order_f:
        md = model_data[m]
        if md["delta"] != 0:
            mv_prev = md["prev"]; curr_c = md["curr"]; d = md["delta"]
            pct = (abs(d)/mv_prev*100) if mv_prev>0 else None
            movements.append({"model":m, "prev":mv_prev, "curr":curr_c, "delta":d, "pct": round(pct,1) if pct is not None else None})
    movements.sort(key=lambda x: abs(x["delta"]), reverse=True)

    # Model × agency matrix (pct & counts)
    matrix_pct = {m: {d: dealer_model_matrix[m][d] for d in DEALERS} for m in model_order_f}
    matrix_cnt = {m: {d: dealer_model_counts[m][d] for d in DEALERS} for m in model_order_f}
    matrix_meta = {m: {d: metas[m][i] for i,d in enumerate(DEALERS)} for m in model_order_f}
    total_meta = sum(sum(v) for v in metas.values())

    # Daily breakdown: {dealer: {model: {day: count}}} — para chart "Avance día a día" filtrable
    # Channel breakdown: {dealer: {model: {channel: count}}} — para chart "Distribución por canal" filtrable
    # matrix_cnt_prev: {model: {dealer: count}} en el corte anterior — para deltas exactos por filtro
    daily_breakdown = {}
    dealer_model_channel = {}
    # Mismo shape que dealer_model_channel pero para el corte anterior — permite
    # que el filtro "Tipo de canal" (marketing/asesor/all) en tabs Ford/Brand/Comp
    # calcule deltas curr vs prev para canal no-marketing también.
    dealer_model_channel_prev = {}
    # Nuevo: avance diario por canal por dealer. {dealer: {channel: {day: count}}}
    # Lo usa el chart "Avance diario por canal" en el Comparativo.
    daily_dealer_channel = {}
    matrix_cnt_prev = {m: {d: 0 for d in DEALERS} for m in model_order_f}
    # All-channel filter para Otros (marketing + asesor) — captura los ~20% que vienen
    # de asesor comercial y se pierden en el filtro marketing-only.
    all_channels_set = set(ALL_TRAFFIC_CHANNELS)
    for dealer in DEALERS:
        pattern, channels = DEALER_CONFIG[dealer]
        mask_c = (curr["SUCURSAL"].str.contains(pattern, case=False, na=False)) & (curr["CANAL"].isin(channels))
        mask_p = (prev["SUCURSAL"].str.contains(pattern, case=False, na=False)) & (prev["CANAL"].isin(channels))
        # Para dealer_model_channel usamos curr_all/prev_all (todos los canales válidos),
        # filtrado sólo por SUCURSAL (no por canal del DEALER_CONFIG que limita a marketing).
        mask_c_all = curr_all["SUCURSAL"].str.contains(pattern, case=False, na=False)
        mask_p_all = prev_all["SUCURSAL"].str.contains(pattern, case=False, na=False)
        d_curr = curr[mask_c]
        d_prev = prev[mask_p]
        d_curr_all = curr_all[mask_c_all]
        d_prev_all = prev_all[mask_p_all]
        daily_breakdown[dealer] = {}
        dealer_model_channel[dealer] = {}
        dealer_model_channel_prev[dealer] = {}
        # daily_dealer_channel: agrupa por canal × día para este dealer
        # (canales válidos = ALL_TRAFFIC_CHANNELS, sumando marketing + asesor)
        ddc = {}
        if len(d_curr_all):
            tmp = d_curr_all.dropna(subset=['FECHA']).copy()
            if len(tmp):
                tmp['DAY'] = tmp['FECHA'].dt.day
                tmp = tmp[tmp['CANAL'].isin(all_channels_set)]
                for (canal, day), n in tmp.groupby(['CANAL','DAY']).size().items():
                    ddc.setdefault(canal, {})[int(day)] = int(n)
        daily_dealer_channel[dealer] = ddc
        for m in model_order_f:
            sub_c = d_curr[d_curr['MODELO_F']==m]
            # daily (marketing only — usado en chart "Avance día a día" de Ford tab)
            sub_dt = sub_c.dropna(subset=['FECHA'])
            if len(sub_dt):
                s2 = sub_dt.copy()
                s2['DAY'] = s2['FECHA'].dt.day
                dd = s2.groupby('DAY').size().to_dict()
                daily_breakdown[dealer][m] = {int(k): int(v) for k,v in dd.items()}
            else:
                daily_breakdown[dealer][m] = {}
            # channels (marketing + asesor para filtro Otros y tabs Ford/Brand/Comp)
            sub_c_all = d_curr_all[d_curr_all['MODELO_F']==m]
            ch = sub_c_all['CANAL'].value_counts().to_dict() if len(sub_c_all) else {}
            dealer_model_channel[dealer][m] = {k: int(v) for k,v in ch.items() if k in all_channels_set}
            # prev — mismo shape para deltas del filtro canal
            sub_p_all = d_prev_all[d_prev_all['MODELO_F']==m]
            chp = sub_p_all['CANAL'].value_counts().to_dict() if len(sub_p_all) else {}
            dealer_model_channel_prev[dealer][m] = {k: int(v) for k,v in chp.items() if k in all_channels_set}
            # prev count (marketing-only para compat existente)
            matrix_cnt_prev[m][dealer] = int(len(d_prev[d_prev['MODELO_F']==m]))
    # Otros (current and prev for completeness)
    daily_breakdown['Otros'] = {}
    dealer_model_channel['Otros'] = {}
    dealer_model_channel_prev['Otros'] = {}
    daily_dealer_channel['Otros'] = {}
    otros_prev_by_model = {}
    # Otros all-channel (records con MARCA=FORD pero fuera de DEALER_CONFIG patrones)
    attributed_all = False
    attributed_p_all = False
    for dealer in DEALERS:
        pattern, _channels = DEALER_CONFIG[dealer]
        mm = curr_all["SUCURSAL"].str.contains(pattern, case=False, na=False)
        attributed_all = mm if attributed_all is False else (attributed_all | mm)
        mp = prev_all["SUCURSAL"].str.contains(pattern, case=False, na=False)
        attributed_p_all = mp if attributed_p_all is False else (attributed_p_all | mp)
    otros_curr_all = curr_all[~attributed_all]
    otros_prev_all = prev_all[~attributed_p_all]
    # daily_dealer_channel['Otros']: agrupa canal × día para Otros
    if len(otros_curr_all):
        tmp = otros_curr_all.dropna(subset=['FECHA']).copy()
        if len(tmp):
            tmp['DAY'] = tmp['FECHA'].dt.day
            tmp = tmp[tmp['CANAL'].isin(all_channels_set)]
            for (canal, day), n in tmp.groupby(['CANAL','DAY']).size().items():
                daily_dealer_channel['Otros'].setdefault(canal, {})[int(day)] = int(n)
    for m in model_order_f:
        sub_c = otros_curr[otros_curr['MODELO_F']==m]
        sub_dt = sub_c.dropna(subset=['FECHA'])
        if len(sub_dt):
            s2 = sub_dt.copy()
            s2['DAY'] = s2['FECHA'].dt.day
            dd = s2.groupby('DAY').size().to_dict()
            daily_breakdown['Otros'][m] = {int(k): int(v) for k,v in dd.items()}
        else:
            daily_breakdown['Otros'][m] = {}
        sub_c_all = otros_curr_all[otros_curr_all['MODELO_F']==m]
        ch = sub_c_all['CANAL'].value_counts().to_dict() if len(sub_c_all) else {}
        dealer_model_channel['Otros'][m] = {k: int(v) for k,v in ch.items() if k in all_channels_set}
        sub_p_all = otros_prev_all[otros_prev_all['MODELO_F']==m]
        chp = sub_p_all['CANAL'].value_counts().to_dict() if len(sub_p_all) else {}
        dealer_model_channel_prev['Otros'][m] = {k: int(v) for k,v in chp.items() if k in all_channels_set}
        otros_prev_by_model[m] = int(len(otros_prev[otros_prev['MODELO_F']==m]))

    return {
        "cut_date": f"{up_to_day:02d}/{month:02d}/{year}",
        "prev_date": None,  # filled in by caller from filename
        "days_lab": days_lab, "days_trans": days_trans, "avance_pct": avance_pct,
        "total_curr": total_curr, "total_prev": total_prev, "delta_total": delta_total,
        "velocity": round(velocity,2), "projection_total": projection_total,
        "meta_total": total_meta,
        "dominant_channel": dominant_channel, "channel_pct": channel_pct,
        "models": model_data,
        "dealers": dealer_data,
        "zones": zone_data,
        "matrix_pct": matrix_pct,
        "matrix_cnt": matrix_cnt,
        "matrix_meta": matrix_meta,
        "at_risk_models": at_risk_models,
        "at_risk_agencies": at_risk_agencies,
        "movements": movements,
        "daily": daily_cum_filtered(curr),
        "daily_breakdown": daily_breakdown,
        "daily_dealer_channel": daily_dealer_channel,
        "dealer_model_channel": dealer_model_channel,
        "dealer_model_channel_prev": dealer_model_channel_prev,
        "matrix_cnt_prev": matrix_cnt_prev,
        "otros_prev_by_model": otros_prev_by_model,
        "pace": expected_pace_calendar(month, year, total_meta, days_lab, extra_non_working=extra_non_working),
        "month": month, "year": year, "cut_day": up_to_day,
        "model_order": model_order_f,
        "dealer_order": DEALERS,
        "zone_order": list(ZONES.keys()),
    }

# ---------------- OTHER BRANDS ----------------
BRANDS = ['DONGFENG_ORGU', 'CHERY_ORGU', 'MAZDA_ORGU', 'RAM_ORGU']
BRAND_DISPLAY = {
    'DONGFENG_ORGU': 'DongFeng',
    'CHERY_ORGU':    'Chery',
    'MAZDA_ORGU':    'Mazda',
    'RAM_ORGU':      'RAM',
}
BRAND_DEALERS = {
    'DONGFENG_ORGU': ['La Y', 'Machala'],
    'CHERY_ORGU':    ['Machala'],
    'MAZDA_ORGU':    ['Machala', 'Portoviejo'],
    'RAM_ORGU':      ['Machala', 'Portoviejo'],
}
BRAND_DEALER_PATTERNS = {
    'DONGFENG_ORGU': {'La Y': 'LA Y',   'Machala': 'MACHALA'},
    'CHERY_ORGU':    {'Machala': 'MACHALA'},
    'MAZDA_ORGU':    {'Machala': 'MACHALA', 'Portoviejo': 'PORTOVIEJO'},
    'RAM_ORGU':      {'Machala': 'MACHALA', 'Portoviejo': 'PORTOVIEJO'},
}
# Keyword en SUCURSAL que confirma que el record pertenece a la marca (filtro estricto).
# Aplicado en process_bd_brand para excluir records mal clasificados (e.g. MARCA=DONGFENG_ORGU
# pero SUCURSAL=AUTOSHARECORP LA Y, que es una agencia Ford).
BRAND_SUCURSAL_KEYWORDS = {
    'DONGFENG_ORGU': 'DONGFENG',
    'CHERY_ORGU':    'CHERY',
    'MAZDA_ORGU':    'MAZDA',
    'RAM_ORGU':      'STELLANTIS',
}
# Meta row label (as in METAS_MARCAS) → display model label
BRAND_META_ROWS = {
    'DONGFENG_ORGU': {
        'Huge': 'HUGE', 'Mage': 'MAGE', 'Paladin': 'PALADIN',
        'Rich 6 4x2 TM GAS': 'RICH 6', 'Rich 6 4x2 TM DSL': 'RICH 6', 'Rich 6 4x4 TM DSL': 'RICH 6',
        'Rich 7 4x2 TM DSL': 'RICH 7', 'Rich 7 4x4 TM DSL': 'RICH 7',
        'Z9': 'Z9',
    },
    'MAZDA_ORGU': {
        'BT-50 3.0 4x4 TM Diesel': 'NEW BT-50',
        'CX-3 Entry 2.0': 'CX3',
        'CX-30 Core 2.0': 'CX-30',
        'CX-5 Core 2.0': 'CX5', 'CX-5 High 2.0': 'CX5',
        'CX-60 Core 2.5': 'CX-60',
        'CX-90 Core 3.3': 'CX-90',
    },
    'CHERY_ORGU': {
        'Arrizo 5 Pro Max 1.5': 'ARRIZO',
        'Tiggo 2 Pro Max Sport': 'TIGGO 2',
        'Tiggo 4 Pro Max Luxury': 'TIGGO 4',
        'Tiggo 7 Pro Max Luxury': 'TIGGO 7',
        'Tiggo 8 Pro Max Luxury': 'TIGGO 8',
        'HIMLA': 'HIMLA',
    },
    'RAM_ORGU': {
        '1500': 'RAM 1500',
        '700':  'RAM 700',
    },
}
META_PARENT_PATTERNS = {
    'Dong Feng': 'DONGFENG_ORGU',
    'Mazda':     'MAZDA_ORGU',
    'Chery':     'CHERY_ORGU',
    'RAM':       'RAM_ORGU',
}

def load_brand_metas(path):
    """Parse METAS_MARCAS: returns {brand: {modelo_display: {agency: meta}}}
    Sheet has 3 sections: VENTAS, PRESUPUESTO DE TRÁFICO, PRESUPUESTO DE TRÁFICO MARKETING.
    We use PRESUPUESTO DE TRÁFICO (total traffic budget), consistent with Ford's MODEL_METAS.
    """
    df = pd.read_excel(path, sheet_name='METAS_MARCAS', header=None)
    AGENCIES = ['CJA','Orellana','La Y','Tumbaco','Manta','Machala','Portoviejo']
    metas = {b: {} for b in BRANDS}

    # Locate all "Modelo" header rows and their associated section title
    headers = []
    for i in range(len(df)):
        if str(df.iloc[i,0]).strip() == 'Modelo':
            title = None
            for j in range(i-1, max(i-4,-1), -1):
                t = str(df.iloc[j,0]).strip()
                if t and t.lower() != 'nan':
                    title = t; break
            headers.append((i, title or ''))
    # Pick "PRESUPUESTO DE TRÁFICO" (not MARKETING) — same semantics as Ford MODEL_METAS
    start = None
    for i, title in headers:
        t = title.upper()
        if 'PRESUPUESTO' in t and 'TRÁFICO' in t and 'MARKETING' not in t:
            start = i + 1; break
    if start is None:
        # fallback: first section with "PRESUPUESTO"
        for i, title in headers:
            if 'PRESUPUESTO' in title.upper():
                start = i + 1; break
    if start is None:
        return metas
    # Section end: next Modelo header, or EOF
    end = len(df)
    for i, _ in headers:
        if i > start:
            end = i - 1; break

    active = None
    for i in range(start, end):
        raw = df.iloc[i, 0]
        if pd.isna(raw): continue
        label = str(raw).strip()
        if not label or label.lower()=='nan': continue
        hit = None
        for pat, b in META_PARENT_PATTERNS.items():
            if label.startswith(pat):
                hit = b; break
        if hit:
            active = hit; continue
        if active and active in BRAND_META_ROWS:
            display = BRAND_META_ROWS[active].get(label)
            if display is None: continue
            if display not in metas[active]:
                metas[active][display] = {a: 0 for a in AGENCIES}
            for col_idx, ag in enumerate(AGENCIES, start=2):
                val = df.iloc[i, col_idx]
                if pd.notna(val):
                    try: metas[active][display][ag] += int(round(float(val)))
                    except (ValueError, TypeError): pass
    return metas

def process_bd_brand(df, brand, channels=None):
    """Filtra registros de una marca específica para conteo de negocios.

    Fuente de verdad: columna MARCA. NO se filtra por SUCURSAL keyword
    (cambio 2026-05-19: el filtro defensivo anterior descartaba negocios
    reales mal categorizados — ej: DongFeng en SUCURSAL=AUTOSHARECORP).

    Dedupe por SOLO CEDULA: 1 persona = 1 negocio. Aunque haya cotizado
    múltiples modelos, al final es la misma persona explorando opciones.
    El último registro cronológico determina el modelo asignado.
    """
    if channels is None:
        channels = VALID_TRAFFIC_CHANNELS
    df = df[df['MARCA'] == brand].copy()
    df['MODELO_F'] = df['MODELO'].astype(str).str.strip().str.upper()
    df.loc[df['MODELO_F']=='F150','MODELO_F'] = 'F-150'
    df.loc[df['MODELO_F'].isin(['NAN','NONE','']) | df['MODELO_F'].isna(), 'MODELO_F'] = 'Por definir'
    # ► Dedup por cédula: preferir la fila que TENGA modelo válido cuando hay
    # varias del mismo cliente (mismo razonamiento que get_traffic_df).
    df['_has_model'] = (~df['MODELO_F'].isin(['Por definir'])).astype(int)
    df = df.sort_values(['FECHA','_has_model'])
    df = df.drop_duplicates(subset=['CEDULA'], keep='last')
    df = df.drop(columns=['_has_model'])
    df = df[df['CANAL'].isin(channels)]
    return df

def get_dealer_df_brand(df, brand, dealer):
    pat = BRAND_DEALER_PATTERNS[brand].get(dealer)
    if not pat: return df.iloc[0:0]
    return df[df['SUCURSAL'].str.contains(pat, case=False, na=False)]

def brand_report(brand, curr_raw, prev_raw, brand_metas, month=4, year=2026, up_to_day=30, prev_date='29/04/2026', extra_non_working=None):
    curr = process_bd_brand(curr_raw, brand)
    prev = process_bd_brand(prev_raw, brand)
    curr_all = process_bd_brand(curr_raw, brand, channels=ALL_TRAFFIC_CHANNELS)
    prev_all = process_bd_brand(prev_raw, brand, channels=ALL_TRAFFIC_CHANNELS)
    days_lab, days_trans = working_days(month, year, up_to_day, extra_non_working=extra_non_working)
    total_curr = int(len(curr)); total_prev = int(len(prev))
    delta_total = total_curr - total_prev
    velocity = total_curr / days_trans if days_trans else 0
    projection_total = round(velocity * days_lab)

    dealers = BRAND_DEALERS[brand]
    # All models: metas ordered first, then any extras from BD
    meta_models = []
    for lbl in BRAND_META_ROWS[brand].values():
        if lbl not in meta_models: meta_models.append(lbl)
    bd_models = [m for m in set(list(curr['MODELO_F'].unique()) + list(prev['MODELO_F'].unique()))
                 if m and m not in ('NAN','nan','')]
    ordered = list(meta_models)
    for m in sorted(bd_models):
        if m not in ordered: ordered.append(m)

    dealer_data = {}
    matrix_cnt = {m: {d: 0 for d in dealers} for m in ordered}
    matrix_cnt_prev = {m: {d: 0 for d in dealers} for m in ordered}
    daily_breakdown = {}
    dealer_model_channel = {}
    dealer_model_channel_prev = {}
    daily_dealer_channel = {}  # {dealer: {canal: {day: n}}} para chart "Avance diario por canal"
    all_channels_set = set(ALL_TRAFFIC_CHANNELS)
    for d in dealers:
        d_curr = get_dealer_df_brand(curr, brand, d)
        d_prev = get_dealer_df_brand(prev, brand, d)
        d_curr_all = get_dealer_df_brand(curr_all, brand, d)
        d_prev_all = get_dealer_df_brand(prev_all, brand, d)
        c = int(len(d_curr)); p = int(len(d_prev))
        vel = c/days_trans if days_trans else 0
        proj = round(vel*days_lab)
        meta = sum(brand_metas.get(brand,{}).get(m,{}).get(d,0) for m in ordered)
        cumpl = round(100*proj/meta) if meta>0 else 0
        dealer_data[d] = {
            'prev': p, 'curr': c, 'meta': meta,
            'projection': proj, 'velocity': round(vel,2),
            'cumpl_proj': cumpl,
            'byModel': {m: int(len(d_curr[d_curr['MODELO_F']==m])) for m in ordered},
            'byChannel': dict(d_curr['CANAL'].value_counts().to_dict()),
        }
        daily_breakdown[d] = {}
        dealer_model_channel[d] = {}
        dealer_model_channel_prev[d] = {}
        ddc = {}
        if len(d_curr_all):
            tmp = d_curr_all.dropna(subset=['FECHA']).copy()
            if len(tmp):
                tmp['DAY'] = tmp['FECHA'].dt.day
                tmp = tmp[tmp['CANAL'].isin(all_channels_set)]
                for (canal, day), n in tmp.groupby(['CANAL','DAY']).size().items():
                    ddc.setdefault(canal, {})[int(day)] = int(n)
        daily_dealer_channel[d] = ddc
        for m in ordered:
            sub_c = d_curr[d_curr['MODELO_F']==m]
            mc = int(len(sub_c))
            matrix_cnt[m][d] = mc
            matrix_cnt_prev[m][d] = int(len(d_prev[d_prev['MODELO_F']==m]))
            sub_dt = sub_c.dropna(subset=['FECHA'])
            if len(sub_dt):
                s2 = sub_dt.copy()
                s2['DAY'] = s2['FECHA'].dt.day
                dd = s2.groupby('DAY').size().to_dict()
                daily_breakdown[d][m] = {int(k): int(v) for k,v in dd.items()}
            else:
                daily_breakdown[d][m] = {}
            sub_c_all = d_curr_all[d_curr_all['MODELO_F']==m]
            ch = sub_c_all['CANAL'].value_counts().to_dict() if len(sub_c_all) else {}
            dealer_model_channel[d][m] = {k: int(v) for k,v in ch.items() if k in all_channels_set}
            sub_p_all = d_prev_all[d_prev_all['MODELO_F']==m]
            chp = sub_p_all['CANAL'].value_counts().to_dict() if len(sub_p_all) else {}
            dealer_model_channel_prev[d][m] = {k: int(v) for k,v in chp.items() if k in all_channels_set}

    model_data = {}
    for m in ordered:
        c = sum(matrix_cnt[m].values())
        p = int(len(prev[prev['MODELO_F']==m]))
        meta = sum(brand_metas.get(brand,{}).get(m,{}).get(d,0) for d in dealers)
        vel = c/days_trans if days_trans else 0
        proj = round(vel*days_lab)
        cumpl = round(100*proj/meta) if meta>0 else 0
        model_data[m] = {'prev':p,'curr':c,'delta':c-p,'meta':meta,'projection':proj,
                         'velocity':round(vel,2),'cumpl_proj':cumpl,
                         'byDealer':{d: matrix_cnt[m][d] for d in dealers}}

    matrix_meta = {m:{d: brand_metas.get(brand,{}).get(m,{}).get(d,0) for d in dealers} for m in ordered}
    matrix_pct = {}
    for m in ordered:
        matrix_pct[m] = {}
        for d in dealers:
            mc = matrix_cnt[m][d]; mm = matrix_meta[m][d]
            if mm==0 and mc==0: matrix_pct[m][d] = -1
            elif mm==0 and mc>0: matrix_pct[m][d] = 999
            else: matrix_pct[m][d] = round(100*mc/mm,1)

    ch = curr['CANAL'].value_counts().to_dict()
    dominant_channel = max(ch, key=ch.get) if ch else '—'
    channel_pct = round(100*ch.get(dominant_channel,0)/total_curr) if total_curr else 0

    at_risk_models = [m for m in ordered if model_data[m]['meta']>0 and model_data[m]['cumpl_proj']<100]
    at_risk_agencies = [d for d in dealers if dealer_data[d]['meta']>0 and dealer_data[d]['cumpl_proj']<100]

    movements = []
    for m in ordered:
        md = model_data[m]
        if md['delta']!=0 or md['curr']>0 or md['prev']>0:
            pct = abs(md['delta'])/md['prev']*100 if md['prev']>0 else None
            movements.append({'model':m,'prev':md['prev'],'curr':md['curr'],'delta':md['delta'],
                              'pct': round(pct,1) if pct is not None else None})
    movements.sort(key=lambda x: abs(x['delta']), reverse=True)

    total_meta = sum(dealer_data[d].get('meta',0) for d in dealers)
    overall_cumpl = round(100*projection_total/total_meta) if total_meta>0 else None

    return {
        'brand': brand, 'display': BRAND_DISPLAY[brand],
        'cut_date': f'{up_to_day:02d}/{month:02d}/{year}',
        'prev_date': prev_date,
        'days_lab': days_lab, 'days_trans': days_trans,
        'avance_pct': round(100*days_trans/days_lab) if days_lab else 0,
        'total_curr': total_curr, 'total_prev': total_prev, 'delta_total': delta_total,
        'velocity': round(velocity,2), 'projection_total': projection_total,
        'meta_total': total_meta, 'cumpl_proj': overall_cumpl,
        'dominant_channel': dominant_channel, 'channel_pct': channel_pct,
        'models': model_data, 'dealers': dealer_data,
        'matrix_pct': matrix_pct, 'matrix_cnt': matrix_cnt, 'matrix_meta': matrix_meta,
        'at_risk_models': at_risk_models, 'at_risk_agencies': at_risk_agencies,
        'movements': movements,
        'daily': daily_cum_filtered(curr),
        'daily_breakdown': daily_breakdown,
        'daily_dealer_channel': daily_dealer_channel,
        'dealer_model_channel': dealer_model_channel,
        'dealer_model_channel_prev': dealer_model_channel_prev,
        'matrix_cnt_prev': matrix_cnt_prev,
        'pace': expected_pace_calendar(month, year, total_meta, days_lab, extra_non_working=extra_non_working),
        'month': month, 'year': year, 'cut_day': up_to_day,
        'model_order': ordered, 'dealer_order': dealers,
    }

# ---------------- MAIN ----------------
# Cortes históricos disponibles para Reporte Ford y Reporte Marcas.
# El último de la lista es el corte "actual" (default seleccionado).
MONTHS_CONFIG = [
    {"key": "octubre_2025", "label": "Octubre 2025", "month": 10, "year": 2025, "cut_day": 31,
     "curr_file": "BD_MAYO/BD_OCT_31_10_25.xlsx",
     "prev_file": "BD_MAYO/BD_OCT_31_10_25.xlsx",
     "prev_date": "31/10/2025", "no_metas": True},
    {"key": "noviembre_2025", "label": "Noviembre 2025", "month": 11, "year": 2025, "cut_day": 30,
     "curr_file": "BD_MAYO/BD_NOV_30_11_25.xlsx",
     "prev_file": "BD_MAYO/BD_OCT_31_10_25.xlsx",
     "prev_date": "31/10/2025", "no_metas": True},
    {"key": "diciembre_2025", "label": "Diciembre 2025", "month": 12, "year": 2025, "cut_day": 31,
     "curr_file": "BD_MAYO/BD_DIC_31_12_25.xlsx",
     "prev_file": "BD_MAYO/BD_NOV_30_11_25.xlsx",
     "prev_date": "30/11/2025", "no_metas": True},
    {"key": "enero_2026", "label": "Enero 2026", "month": 1, "year": 2026, "cut_day": 31,
     "curr_file": "BD_MAYO/BD_ENE_31_01_26.xlsx",
     "prev_file": "BD_MAYO/BD_DIC_31_12_25.xlsx",
     "prev_date": "31/12/2025",
     "ford_metas_file": str(ENE_FORD_METAS_FILE)},
    {"key": "febrero_2026", "label": "Febrero 2026", "month": 2, "year": 2026, "cut_day": 28,
     "curr_file": "BD_MAYO/BD_FEB_28_02_26.xlsx",
     "prev_file": "BD_MAYO/BD_FEB_28_02_26.xlsx",
     "prev_date": "28/02/2026",
     "ford_metas_file": str(FEB_FORD_METAS_FILE)},
    {"key": "marzo_2026", "label": "Marzo 2026", "month": 3, "year": 2026, "cut_day": 31,
     "curr_file": "BD_MAYO/BD_MARZO_31_03_26.xlsx",
     "prev_file": "BD_MAYO/BD_MARZO_30_03_26.xlsx",
     "prev_date": "30/03/2026",
     "ford_metas_file": str(MAR_FORD_METAS_FILE)},
    {"key": "abril_2026", "label": "Abril 2026", "month": 4, "year": 2026, "cut_day": 30,
     "curr_file": "BD_MAYO/BD_ABR_30_04_26.xlsx",
     "prev_file": "BD_MAYO/BD_ABR_29_04_26.xlsx",
     "prev_date": "29/04/2026",
     "ford_metas_file": str(ABR_FORD_METAS_FILE)},
    {"key": "mayo_2026", "label": "Mayo 2026", "month": 5, "year": 2026, "cut_day": 31,
     "curr_file": "BD_MAYO/BD_MAY_31_05_26.xlsx",
     "prev_file": "BD_MAYO/BD_MAY_29_05_26.xlsx",
     "prev_date": "29/05/2026",
     "ford_metas_file": str(MAY_FORD_METAS_FILE),
     "brand_metas_file": str(MAY_BRAND_METAS_FILE),
     # Override: Sábado 2 de mayo no se trabajó (puente con feriado del Día del Trabajo)
     "extra_non_working_days": [(5, 2)]},
    {"key": "junio_2026", "label": "Junio 2026", "month": 6, "year": 2026, "cut_day": 22,
     "curr_file": "../Junio/BD_JUNIO/BD_JUN_22_06_26.xlsx",
     "prev_file": "../Junio/BD_JUNIO/BD_JUN_18_06_26.xlsx",
     "prev_date": "18/06/2026",
     "ford_metas_file": str(JUN_FORD_METAS_FILE),
     "brand_metas_file": str(JUN_BRAND_METAS_FILE)},
]

def _marca_group(marca):
    """Agrupa la MARCA a un código de marca para la clave de identidad.
    Ford y todas las marcas ORGU se tratan como marcas independientes —
    un cliente que tocó Ford y luego DongFeng cuenta como NUEVO para DongFeng."""
    m = (str(marca) or '').upper().strip()
    if m.startswith('FORD'): return 'FORD'
    if 'DONGFENG' in m: return 'DONGFENG'
    if 'MAZDA' in m: return 'MAZDA'
    if 'CHERY' in m: return 'CHERY'
    if 'RAM' in m: return 'RAM'
    return m or 'NA'


def _build_first_ym_index(months_config):
    """Construye un mapeo {client_key_robusto: first_ym} usando identidad robusta
    POR MARCA: (cédula base ∪ email ∪ celular) × marca.

    Definición B POR MARCA: cada (cliente, marca) cuenta solo en su primer mes
    de toque PARA ESA MARCA. Si el cliente cotizó Ford antes y ahora cotiza
    DongFeng, cuenta como NUEVO para DongFeng (oportunidad nueva para la marca).
    Dentro de la misma marca, regresar en otro mes no suma (sigue siendo 1 toque).
    """
    first_ym_by_id = {}
    for cfg in months_config:
        path = BASE / cfg['curr_file']
        try:
            df = load_raw(path)
        except Exception:
            continue
        ym = f"{cfg['year']:04d}-{cfg['month']:02d}"
        for _, r in df.iterrows():
            ced = _conv_norm_ced(r.get('CEDULA'))
            base = _conv_cedula_base(ced) if ced else None
            email = _conv_norm_email(r.get('CORREO'))
            cel = _conv_norm_cel(r.get('CELULAR'))
            mg = _marca_group(r.get('MARCA'))
            ids = [x for x in [f'ced:{base}|{mg}' if base else None,
                               f'email:{email}|{mg}' if email else None,
                               f'cel:{cel}|{mg}' if cel else None] if x]
            for x in ids:
                if x not in first_ym_by_id or first_ym_by_id[x] > ym:
                    first_ym_by_id[x] = ym
    return first_ym_by_id


def _filter_to_new_clients(df, this_ym, first_ym_by_id):
    """Filtra el df a SOLO clientes cuyo first_ym (para SU marca) es este mes.
    Un cliente "viejo" PARA ESA MARCA (ya cotizó la misma marca en mes anterior)
    se excluye. Pero si tocó OTRA marca antes, cuenta como nuevo para ésta."""
    if df is None or len(df) == 0:
        return df
    keep_mask = []
    for _, r in df.iterrows():
        ced = _conv_norm_ced(r.get('CEDULA'))
        base = _conv_cedula_base(ced) if ced else None
        email = _conv_norm_email(r.get('CORREO'))
        cel = _conv_norm_cel(r.get('CELULAR'))
        mg = _marca_group(r.get('MARCA'))
        ids = [x for x in [f'ced:{base}|{mg}' if base else None,
                           f'email:{email}|{mg}' if email else None,
                           f'cel:{cel}|{mg}' if cel else None] if x]
        # Si ALGUNO de los ids (de esta marca) ya apareció en mes anterior → descartar
        is_new = True
        for x in ids:
            fym = first_ym_by_id.get(x)
            if fym and fym < this_ym:
                is_new = False
                break
        keep_mask.append(is_new)
    return df[keep_mask].copy()


def main():
    marzo = load_raw(MARZO)
    abril = load_raw(ABRIL)
    # Definición B: construimos índice de identidad robusta cross-mes UNA sola vez.
    # Cada cliente queda asignado a su mes de primer toque; en meses posteriores se excluye.
    print('Construyendo índice de identidad robusta cross-mes (Definición B)...')
    _FIRST_YM_IDX = _build_first_ym_index(MONTHS_CONFIG)
    print(f'  {len(_FIRST_YM_IDX)} identificadores únicos indexados')

    # Cache for brand metas (avoid re-reading same file)
    brand_metas_cache = {}
    def get_brand_metas(file_path):
        key = str(file_path)
        if key not in brand_metas_cache:
            brand_metas_cache[key] = load_brand_metas(file_path)
        return brand_metas_cache[key]

    # Per-month Ford and Brand reports
    ford_months = {}
    brands_months = {}
    ford_meta_breakdown = {}  # {mk: {modelo: {meta_ventas, reservas_pre}}} para diagnóstico "cobertura por reservas"
    for cfg in MONTHS_CONFIG:
        curr_raw = load_raw(BASE / cfg["curr_file"])
        prev_raw = load_raw(BASE / cfg["prev_file"])
        # Si prev usa el mismo archivo acumulativo que curr, filtra prev a la fecha del corte anterior
        if cfg.get("prev_cutoff_date"):
            cutoff = pd.Timestamp(cfg["prev_cutoff_date"])
            prev_raw = prev_raw[prev_raw["FECHA"] < cutoff].copy()
        # DEFINICIÓN B: descartar clientes que ya aparecieron en BD de meses anteriores.
        # Cada persona única cuenta solo en su primer mes de toque.
        this_ym = f"{cfg['year']:04d}-{cfg['month']:02d}"
        curr_raw = _filter_to_new_clients(curr_raw, this_ym, _FIRST_YM_IDX)
        prev_raw = _filter_to_new_clients(prev_raw, this_ym, _FIRST_YM_IDX)
        # Ford metas: si no_metas, todos cero (cumpl=N/A). Si hay file, leer.
        # Si nada, default MODEL_METAS (hardcoded 2026).
        if cfg.get("no_metas"):
            ford_metas = {m: [0]*7 for m in MODEL_ORDER}
        elif cfg.get("ford_metas_file"):
            ford_metas = load_ford_metas(cfg["ford_metas_file"])
            ford_meta_breakdown[cfg["key"]] = load_ford_meta_breakdown(cfg["ford_metas_file"])
        else:
            ford_metas = None
        # Brand metas: si no_metas pasa empty dict (cumpl=0); else per-month o default Abril
        if cfg.get("no_metas"):
            bmetas = {b: {} for b in BRANDS}
        else:
            bmetas_file = cfg.get("brand_metas_file") or str(DEFAULT_BRAND_METAS_FILE)
            bmetas = get_brand_metas(bmetas_file)
        # Días no laborables extra (overrides puntuales por mes)
        extra_nw = cfg.get("extra_non_working_days")

        f = ford_report(curr_raw, prev_raw, month=cfg["month"], year=cfg["year"],
                        up_to_day=cfg["cut_day"], model_metas=ford_metas,
                        extra_non_working=extra_nw)
        f["prev_date"] = cfg["prev_date"]
        f["month_key"] = cfg["key"]
        f["month_label"] = cfg["label"]
        ford_months[cfg["key"]] = f
        bd = {}
        for b in BRANDS:
            bd[b] = brand_report(b, curr_raw, prev_raw, bmetas,
                                 month=cfg["month"], year=cfg["year"],
                                 up_to_day=cfg["cut_day"], prev_date=cfg["prev_date"],
                                 extra_non_working=extra_nw)
        brands_months[cfg["key"]] = bd

    # Default = último mes (corte actual)
    default_key = MONTHS_CONFIG[-1]["key"]
    ford = ford_months[default_key]
    brands_data = brands_months[default_key]

    out = {
        "marzo": summarize(marzo, "Marzo 2026 (cierre)"),
        "abril": summarize(abril, "Abril 2026 (cierre 30/04)"),
        "meta": {
            "marzo": {"report_date":"31/03/2026","days_lab":26,"total_traffic_curr":416,"meta_total":363},
            "abril": {"report_date":"20/04/2026","days_lab":ford["days_lab"],"days_trans":ford["days_trans"],
                      "total_traffic_curr":ford["total_curr"],"projection_total":ford["projection_total"],
                      "meta_total":313,"velocity":ford["velocity"]},
        },
        "ford": ford,
        "brands": brands_data,
        "brand_list": BRANDS,
        "brand_display": BRAND_DISPLAY,
        "ford_months": ford_months,
        "ford_meta_breakdown": ford_meta_breakdown,
        "brands_months": brands_months,
        "months_config": [{"key":c["key"], "label":c["label"]} for c in MONTHS_CONFIG],
        "default_month_key": default_key,
        "channel_categories": {
            "marketing": MARKETING_CHANNELS,
            "asesor":    ASESOR_CHANNELS,
            "all":       ALL_TRAFFIC_CHANNELS,
        },
        # Snapshot de inventario (REPORTE DE INVENTARIO.xlsm): oferta por modelo/agencia
        # + reservas en cola + pipeline USA/Nac + cruce mes-a-mes (snapshots históricos).
        # ► is_current: True solo si la fecha actual cae DENTRO del mes del config.
        # Antes lo marcábamos al último mes del array, pero eso seguía mostrando "en curso"
        # para meses ya cerrados (ej. mayo cuando ya estamos en junio).
        "inventario": (load_inventario(months_config=[
            {'key':c['key'], 'label':c['label'], 'year':c['year'], 'month':c['month'],
             'cut_day':c['cut_day'],
             'is_current': (datetime.now().year == c['year'] and datetime.now().month == c['month'])}
            for c in MONTHS_CONFIG
        ]) if DEFAULT_INVENTORY_PATH.exists() else None),
        # Análisis competitivo de importaciones Ford: ORGU vs QM
        "competencia_data": compute_competencia_data(),
        # Embudo (funnel) de ventas por modelo y concesionario (CJA por ahora)
        "embudo_data": _compute_embudo_safe(),
        # Análisis de conversión tráfico → venta (módulo aislado, no afecta el resto).
        # ► Fuente de ventas: archivo "Base de ventas YTD ...xlsx" (ventas netas).
        # El inventario sigue siendo la fuente de stock/reservas (eso no cambia).
        "conversion_data": (
            (lambda _ventas: ({
                # Ford + cada marca ORGU. Tab Conversión usa el filtro brand para switchear.
                # Brand-key mapping: aggregate emite con sufijo _ORGU (DONGFENG_ORGU, etc.)
                # pero compute_conversion_metrics filtra por columna 'marca' de ventas que
                # contiene los nombres limpios (DONGFENG, CHERY, MAZDA, RAM).
                k: compute_conversion_metrics(
                    bd_dir=str(BASE / 'BD_MAYO'),
                    sales_df=_ventas,
                    marca_filter=mf,
                )
                for (k, mf) in [
                    ('FORD',          'FORD'),
                    ('DONGFENG_ORGU', 'DONGFENG'),
                    ('CHERY_ORGU',    'CHERY'),
                    ('MAZDA_ORGU',    'MAZDA'),
                    ('RAM_ORGU',      'RAM'),
                ]
            }) if _ventas is not None else None)(__import__('ventas').load_ventas())
        ),
        # Panel de Ventas mensual · pivot por marca/modelo/asesor con NETOS (sum Cantidad).
        # Permite ver ventas mes a mes y desplegar por modelo o por asesor comercial.
        "ventas_mensual": _compute_ventas_mensual(__import__('ventas').load_ventas()),
        # matrix_meta carga la meta marketing (80%). Para escalar la meta cuando se
        # filtra por categoría de canal en la pestaña Otros, JS aplica estos ratios.
        "meta_split": {
            "marketing_pct": META_MARKETING_PCT,   # 0.80
            "asesor_pct":    META_ASESOR_PCT,      # 0.20
            "base_in_matrix_meta": "marketing",    # qué representa matrix_meta
        },
    }
    # Merge de inversión publicitaria Xiy (si existe data_xiy.json con el bloque
    # consolidated_for_panel listo). Lo metemos como out["xiy"] para que el panel
    # lo lea desde DATA.xiy en el tab Inversión.
    xiy_path = ABRIL_BASE / "panel-trafico/data_xiy.json"
    if xiy_path.exists():
        try:
            with open(xiy_path, "r", encoding="utf-8") as f:
                data_xiy = json.load(f)
            cfp = data_xiy.get("consolidated_for_panel")
            if cfp:
                # Adjuntar lines_flat compactado para que el panel pueda
                # filtrar dinámicamente por mes/modelo/agencia/campaña.
                flat = data_xiy.get("lines_flat") or []
                compact = [{
                    "month":    L.get("month"),
                    "campaign": L.get("campaign"),
                    "modelo":   L.get("modelo"),
                    "audience": L.get("audience"),
                    "media":    L.get("media"),
                    "amount":   L.get("amount"),
                    "investment": L.get("investment"),
                    "conversiones_esperadas": L.get("conversiones_esperadas"),
                } for L in flat]
                cfp["_lines_flat"] = compact
                out["xiy"] = cfp
                out["xiy_meta"] = {
                    "fetched_at": data_xiy.get("fetched_at"),
                    "source": data_xiy.get("source"),
                    "n_campaigns": data_xiy.get("n_campaigns"),
                    "n_lines": data_xiy.get("n_lines"),
                }
                print(f"Merged Xiy investment: USD {cfp.get('total_general',0):,.2f} "
                      f"({data_xiy.get('n_campaigns')} campaigns, "
                      f"{data_xiy.get('n_lines')} lines)")
            else:
                print(f"WARN: {xiy_path} exists but has no consolidated_for_panel; skipping")
        except Exception as e:
            print(f"WARN: failed to merge {xiy_path}: {e}")
    else:
        print(f"INFO: no data_xiy.json at {xiy_path}; tab Inversión quedará vacío")

    # ─── Digital · HubSpot · pipeline Ventas-Ford ───
    digital_path = ABRIL_BASE / "panel-trafico/digital.json"
    if digital_path.exists():
        try:
            with open(digital_path, "r", encoding="utf-8") as f:
                out["digital"] = json.load(f)
            print(f"Merged digital snapshot from {digital_path.name}")
        except Exception as e:
            print(f"WARN: failed to load {digital_path}: {e}")
    else:
        print(f"INFO: no digital.json at {digital_path}; tab Seguimiento Digital quedará vacío")

    outpath = ABRIL_BASE / "panel-trafico/data.json"
    # ► Sanea NaN/Infinity antes de serializar. Python json.dump por default
    # escribe los tokens literales NaN/Infinity (no son JSON válido). El
    # navegador (JSON.parse) los rechaza con SyntaxError y rompe el IIFE
    # principal del panel — TODAS las pestañas quedan en blanco. Este saneo
    # blinda el panel ante cualquier división 0/0 que se cuele en el output.
    import math as _math
    def _json_safe(o):
        if isinstance(o, float):
            return None if (_math.isnan(o) or _math.isinf(o)) else o
        if isinstance(o, dict):
            return {k: _json_safe(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_json_safe(v) for v in o]
        return o
    out = _json_safe(out)
    with open(outpath,"w",encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=None, separators=(",", ":"))
    print("Wrote", outpath)
    print("Ford total curr:", ford["total_curr"], "prev:", ford["total_prev"])
    print("Model totals:", {m: ford["models"][m]["curr"] for m in MODEL_ORDER})
    print("Agency totals:", {d: ford["dealers"][d]["curr"] for d in DEALERS})
    print("At risk models:", ford["at_risk_models"])
    print("At risk agencies:", ford["at_risk_agencies"])
    for b in BRANDS:
        bd = brands_data[b]
        print(f"\n[{BRAND_DISPLAY[b]}] total={bd['total_curr']} (prev {bd['total_prev']}) meta={bd['meta_total']} cumpl={bd['cumpl_proj']}%")
        print(f"  Models curr: {[(m, bd['models'][m]['curr'], bd['models'][m]['meta']) for m in bd['model_order']]}")
        print(f"  Dealers: {[(d, bd['dealers'][d]['curr'], bd['dealers'][d]['meta']) for d in bd['dealer_order']]}")

if __name__ == "__main__":
    main()
