"""Procesa REPORTE DE INVENTARIO.xlsm y produce JSON con cobertura oferta vs demanda.

Lógica:
- Oferta = DISPONIBLE (stock listo) + RESERVADO (stock comprometido) + tránsito/pipeline.
- Demanda = tráfico marketing del mes actual + reservas pendientes en cola.
- Cobertura = días de inventario disponible al ritmo de tráfico actual.
- Reservas en cola (RES-COLA) sin VIN asignado = demanda diferida (clientes esperando que llegue su unidad).
"""
import pandas as pd
from pathlib import Path
import glob as _glob

# Carpeta oficial donde se sube el archivo de inventario.
# Busca automáticamente el archivo más reciente (.xlsm/.xlsx) con "INVENTARIO" en el nombre.
_INVENTORY_DIRS = [
    Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Inventrario"),
    # Fallback histórico
    Path("/Users/danielyanezalbuja/Downloads"),
]

def _find_latest_inventory():
    """Devuelve el path al archivo de inventario más reciente, buscando en las carpetas
    configuradas en orden de prioridad. Filtra por nombre que contenga 'INVENTARIO' y
    extensión .xlsm/.xlsx. Selecciona por fecha de modificación (mtime)."""
    candidates = []
    for d in _INVENTORY_DIRS:
        if not d.exists():
            continue
        for ext in ('*.xlsm', '*.xlsx'):
            for p in d.glob(ext):
                # Excluir archivos temporales de Excel (~$...)
                if p.name.startswith('~$'):
                    continue
                if 'INVENTARIO' in p.name.upper():
                    candidates.append(p)
        if candidates:
            # Si encontramos en la carpeta de prioridad alta, no seguimos buscando
            break
    if not candidates:
        # Último fallback: nombre fijo antiguo
        legacy = Path("/Users/danielyanezalbuja/Downloads/REPORTE DE INVENTARIO.xlsm")
        return legacy if legacy.exists() else None
    # Ordenar por mtime descendente
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]

DEFAULT_INVENTORY_PATH = _find_latest_inventory() or Path("/Users/danielyanezalbuja/Downloads/REPORTE DE INVENTARIO.xlsm")

# Mapeo UBICACIÓN FÍSICA / BODEGA / AGENCIA → agencia del panel
LOCATION_TO_AGENCY = {
    'INGRESO VEHICULOS CARLOS JULIO AROSEMENA': 'CJA',
    'INGRESO VEHICULOS ORELLANA':               'Orellana',
    'INGRESO VEHICULOS QUITO LA Y':             'La Y',
    'INGRESO VEHICULOS TUMBACO':                'Tumbaco',
    'RECEPCION CONCESIONARIO VEHICULOS TUMBACO':'Tumbaco',
    'INGRESO VEHICULOS MANTA':                  'Manta',
    'INGRESO BODEGA MANTA ORGU':                'Manta',
    'INGRESO VEHICULOS MACHALA':                'Machala',
    'RECEPCION CONCESIONARIO ORGU MACHALA':     'Machala',
    'INGRESO VEHICULOS PORTOVIEJO':             'Portoviejo',
    # Tránsito centralizado / sin agencia final asignada
    'INGRESO COMEXPORT - GUAYAQUIL':            'Tránsito',
    'INGRESO BODEGA ORGU QUITO':                'Tránsito',
    'INGRESO CENTRO DE DISTRIBUCION COSTA':     'Tránsito',
    'TRANSITO':                                 'Tránsito',
    'RECEPCION CLIENTE FINAL':                  'Entregado',
}
RES_AGENCY_NORM = {
    'CARLOS JULIO':  'CJA',
    'CARLOS JULIO AROSEMENA': 'CJA',
    'ORELLANA':      'Orellana',
    'LA Y':          'La Y',
    'QUITO LA Y':    'La Y',
    'TUMBACO':       'Tumbaco',
    'MANTA':         'Manta',
    'MACHALA':       'Machala',
    'PORTOVIEJO':    'Portoviejo',
}

# AGENCIA_FACTURACION viene como "1001 VEHICULOS CARLOS JULIO AROSEMENA". Mapeamos por keyword.
FACT_AGENCY_KEYWORDS = [
    ('CARLOS JULIO',  'CJA'),
    ('ORELLANA',      'Orellana'),
    ('LA Y',          'La Y'),
    ('TUMBACO',       'Tumbaco'),
    ('MANTA',         'Manta'),
    ('MACHALA',       'Machala'),
    ('PORTOVIEJO',    'Portoviejo'),
]
def fact_agency_norm(s):
    if not isinstance(s, str): return None
    su = s.upper()
    for kw, ag in FACT_AGENCY_KEYWORDS:
        if kw in su: return ag
    return None

# Familia técnica → MODELO_PANEL (Ford + brands)
def normalize_familia(fam, marca):
    """Mapea una descripción de familia (e.g. 'ESCAPE ST LINE X FHEV AC 2.5 5P 4X2 TA HYBRID')
    al modelo simple usado en el panel ('ESCAPE'). marca normalizada en mayúsculas."""
    if not isinstance(fam, str):
        return None
    s = fam.upper().strip()
    marca = (marca or '').upper().strip()

    if marca == 'FORD':
        for k, v in [
            ('TERRITORY','TERRITORY'), ('ESCAPE','ESCAPE'), ('EVEREST','EVEREST'),
            ('EXPLORER','EXPLORER'),
            ('NEW EXPEDITION','EXPEDITION'), ('EXPEDITION','EXPEDITION'),
            ('BRONCO','BRONCO'),
            ('F150','F-150'), ('F-150','F-150'),
            ('RANGER','RANGER'),
        ]:
            if s.startswith(k): return v
        return None

    if marca == 'DONGFENG':
        if s.startswith('HUGE'): return 'HUGE'
        if s.startswith('MAGE'): return 'MAGE'
        if s.startswith('PALADIN'): return 'PALADIN'
        if s.startswith('RICH 6'): return 'RICH 6'
        if s.startswith('RICH 7'): return 'RICH 7'
        if s.startswith('Z9'): return 'Z9'
        return None

    if marca == 'CHERY':
        if 'ARRIZO' in s: return 'ARRIZO'
        if 'TIGGO 8' in s: return 'TIGGO 8'
        if 'TIGGO 7' in s: return 'TIGGO 7'
        if 'TIGGO 4' in s: return 'TIGGO 4'
        if 'TIGGO 2' in s: return 'TIGGO 2'
        if 'HIMLA' in s: return 'HIMLA'
        return None

    if marca == 'MAZDA':
        if 'BT-50' in s or 'BT50' in s: return 'NEW BT-50'
        if 'CX-30' in s or 'CX30' in s: return 'CX-30'
        if 'CX-3' in s or 'CX3' in s: return 'CX3'
        if 'CX-5' in s or 'CX5' in s: return 'CX5'
        if 'CX-60' in s: return 'CX-60'
        if 'CX-90' in s: return 'CX-90'
        return None

    if marca == 'RAM':
        if '1500' in s: return 'RAM 1500'
        if '700' in s:  return 'RAM 700'
        return None

    return None

def normalize_res_cola_modelo(modelo, marca):
    """RES-COLA usa nombres más cortos. e.g. 'TERRITORY 1.5L FHEV AT TITANIU' → TERRITORY"""
    if not isinstance(modelo, str): return None
    s = modelo.upper().strip()
    marca = (marca or '').upper().strip()
    if marca == 'FORD':
        for k, v in [
            ('TERRITORY','TERRITORY'), ('ESCAPE','ESCAPE'), ('EVEREST','EVEREST'),
            ('EXPLORER','EXPLORER'),
            ('NEW EXPEDITION','EXPEDITION'), ('EXPEDITION','EXPEDITION'),
            ('BRONCO','BRONCO'),
            ('F150','F-150'), ('F-150','F-150'),
            ('RANGER','RANGER'),
        ]:
            if s.startswith(k): return v
    if marca == 'DONGFENG':
        if s.startswith('HUGE'): return 'HUGE'
        if s.startswith('MAGE'): return 'MAGE'
        if s.startswith('PALADIN'): return 'PALADIN'
        if s.startswith('RICH 6'): return 'RICH 6'
        if s.startswith('RICH 7'): return 'RICH 7'
        if s.startswith('Z9'): return 'Z9'
    if marca == 'RAM':
        if '1500' in s: return 'RAM 1500'
        if '700' in s:  return 'RAM 700'
    if marca == 'CHERY':
        if 'ARRIZO' in s: return 'ARRIZO'
        if 'TIGGO 8' in s: return 'TIGGO 8'
        if 'TIGGO 7' in s: return 'TIGGO 7'
        if 'TIGGO 4' in s: return 'TIGGO 4'
        if 'TIGGO 2' in s: return 'TIGGO 2'
    if marca == 'MAZDA':
        if 'CX-30' in s or 'CX30' in s: return 'CX-30'
        if 'CX-3' in s or 'CX3' in s: return 'CX3'
        if 'CX-5' in s or 'CX5' in s: return 'CX5'
        if 'CX-60' in s: return 'CX-60'
        if 'CX-90' in s: return 'CX-90'
        if 'BT-50' in s or 'BT50' in s: return 'NEW BT-50'
    return None

def loc_to_agency(loc):
    if not isinstance(loc, str): return 'Tránsito'
    return LOCATION_TO_AGENCY.get(loc.strip(), 'Otros')

def res_agency_norm(ag):
    if not isinstance(ag, str): return None
    s = ag.strip().replace('\xa0', '').upper()
    return RES_AGENCY_NORM.get(s)

def load_inventario(path=None, today=None, months_config=None):
    """Carga DATOS, RES-COLA, USA, PROC-NAC-MAY y retorna estructura agregada.
    today: pd.Timestamp para calcular aging de reservas (default = hoy).
    months_config: lista [{key, label, year, month, cut_day}] para calcular el cruce
                   mensual de inventario × ventas × reservas (para tabla 'mes a mes')."""
    path = Path(path) if path else DEFAULT_INVENTORY_PATH
    today = today or pd.Timestamp.now().normalize()

    # === DATOS — inventario VIN por VIN ===
    df = pd.read_excel(path, sheet_name='DATOS', header=0)
    df['marca_up'] = df['marca'].astype(str).str.strip().str.upper()
    df['MODELO'] = df.apply(lambda r: normalize_familia(r['familia'], r['marca_up']), axis=1)
    df['AGENCIA'] = df['UBICACIÓN FÍSICA SISCAL'].apply(loc_to_agency)
    df['STATUS_H'] = df['STATUS HOMOLOGADO'].astype(str).str.strip().str.upper()
    # COMPATIBILIDAD entre formatos:
    #   Formato viejo: DISPONIBLE / RESERVADO / FACTURADO / CONSIGNACIÓN
    #   Formato nuevo: SIN HN ASIGNADA (engloba DISPONIBLE y RESERVADO) / FACTURADO / CONSIGNACIÓN
    # Derivamos STATUS_CALC unificando ambos. Para SIN HN ASIGNADA:
    #   - Con FECHA_DE_RESERVA real (>2020) → RESERVADO
    #   - Sin FECHA_DE_RESERVA real          → DISPONIBLE
    _f_res_calc = pd.to_datetime(df['FECHA_DE_RESERVA'], errors='coerce')
    _has_real_reservation = _f_res_calc.notna() & (_f_res_calc.dt.year > 2020)
    def _derive_status(row_idx):
        s = df['STATUS_H'].iloc[row_idx]
        if s == 'SIN HN ASIGNADA':
            return 'RESERVADO' if _has_real_reservation.iloc[row_idx] else 'DISPONIBLE'
        return s
    df['STATUS_CALC'] = [_derive_status(i) for i in range(len(df))]
    # Usar STATUS_CALC como source of truth en el resto del módulo
    df['STATUS_H'] = df['STATUS_CALC']

    # Ventana temporal (usada para tiempos de espera y ventas históricas)
    current_month_start = today.replace(day=1)

    # === TIEMPO DE ESPERA reserva → factura (y factura → entrega) ===
    # Para cada vehículo facturado con fecha de reserva válida, calcular cuánto demoró
    # desde que el cliente reservó hasta que se le facturó (días). Métrica clave para
    # entender el "tiempo de cola" real del cliente, no solo del stock.
    #
    # VENTANA EXPANDING desde 1 Mayo 2025: cada vez que se regenera el panel la ventana
    # crece (no rolling). Eso preserva el histórico completo desde que empezamos a medir
    # y permite tracking de tendencia a largo plazo (12m, 24m, 36m, ...).
    WAIT_WINDOW_START = pd.Timestamp('2025-05-01')
    df['f_reserva']  = pd.to_datetime(df['FECHA_DE_RESERVA'], errors='coerce')
    df['f_factura']  = pd.to_datetime(df['fecha de facturacion'], errors='coerce')
    df['f_entrega']  = pd.to_datetime(df['fecha de entrega'], errors='coerce')
    wait = df[df['f_reserva'].notna() & df['f_factura'].notna() &
              (df['f_reserva'].dt.year > 2000) & (df['f_factura'].dt.year > 2000)].copy()
    wait['days_res_fact'] = (wait['f_factura'] - wait['f_reserva']).dt.days
    # Filtrar negativos (errores de captura) y outliers extremos (>2 años)
    wait = wait[(wait['days_res_fact'] >= 0) & (wait['days_res_fact'] <= 730)]
    wait_win = wait[wait['f_factura'] >= WAIT_WINDOW_START].copy()
    # Factura → entrega (tiempo logístico, complementario)
    ent = wait[wait['f_entrega'].notna()].copy()
    ent['days_fact_ent'] = (ent['f_entrega'] - ent['f_factura']).dt.days
    ent = ent[(ent['days_fact_ent'] >= 0) & (ent['days_fact_ent'] <= 180)]
    ent_win = ent[ent['f_factura'] >= WAIT_WINDOW_START]
    # Meses completos en la ventana (para mostrar al usuario)
    wait_window_months = (today.year - WAIT_WINDOW_START.year) * 12 + (today.month - WAIT_WINDOW_START.month)

    def _wait_stats(sub):
        # Mediana/promedio/p75/max se devuelven en DÍAS; el JS convierte a meses al mostrar.
        # Buckets están definidos en MESES (1m=30d): <1m, 1-2m, 2-3m, 3-6m, >6m.
        if len(sub) == 0:
            return {'n': 0, 'mediana': None, 'promedio': None, 'p75': None, 'max': None,
                    'buckets': {'m0_1':0,'m1_2':0,'m2_3':0,'m3_6':0,'m6_plus':0}}
        s = sub['days_res_fact']
        b_0_1   = int((s < 30).sum())
        b_1_2   = int(((s >= 30) & (s < 60)).sum())
        b_2_3   = int(((s >= 60) & (s < 90)).sum())
        b_3_6   = int(((s >= 90) & (s < 180)).sum())
        b_6_plus= int((s >= 180).sum())
        return {
            'n': int(len(s)),
            'mediana':  float(s.median()),
            'promedio': round(float(s.mean()), 1),
            'p75':      float(s.quantile(0.75)),
            'max':      int(s.max()),
            'buckets':  {'m0_1':b_0_1,'m1_2':b_1_2,'m2_3':b_2_3,'m3_6':b_3_6,'m6_plus':b_6_plus},
        }
    def _wait_stats_fe(sub):
        if len(sub) == 0:
            return {'n': 0, 'mediana': None, 'promedio': None}
        s = sub['days_fact_ent']
        return {'n': int(len(s)), 'mediana': float(s.median()), 'promedio': round(float(s.mean()),1)}

    wait_data = {
        '_window': {
            'start_date': WAIT_WINDOW_START.strftime('%Y-%m-%d'),
            'months':     int(wait_window_months),
        },
    }
    for marca_panel, marca_inv in [('FORD','FORD'),('DONGFENG_ORGU','DONGFENG'),
                                    ('CHERY_ORGU','CHERY'),('MAZDA_ORGU','MAZDA'),
                                    ('RAM_ORGU','RAM')]:
        sub_all = wait[wait['marca_up']==marca_inv]
        sub_win = wait_win[wait_win['marca_up']==marca_inv]
        sub_ent = ent_win[ent_win['marca_up']==marca_inv]
        per_modelo = {}
        entrega_por_modelo = {}
        for m in sub_win.dropna(subset=['MODELO'])['MODELO'].unique():
            per_modelo[m] = _wait_stats(sub_win[sub_win['MODELO']==m])
            entrega_por_modelo[m] = _wait_stats_fe(sub_ent[sub_ent['MODELO']==m])
        wait_data[marca_panel] = {
            'global_window': _wait_stats(sub_win),
            'global_all':    _wait_stats(sub_all),
            'por_modelo':    per_modelo,
            'entrega_window':       _wait_stats_fe(sub_ent),
            'entrega_por_modelo':   entrega_por_modelo,
        }

    # === VENTAS HISTÓRICAS (DATOS con status FACTURADO) ===
    # Para calcular Days of Supply realista: basado en velocidad de facturación,
    # no en tráfico. La industria automotriz no vende diariamente — los DOS deben
    # reflejar cuánto tiempo dura el stock al ritmo histórico de cierres.
    fact = df[df['STATUS_H']=='FACTURADO'].copy()
    fact['fecha_fact'] = pd.to_datetime(fact['fecha de facturacion'], errors='coerce')
    fact = fact.dropna(subset=['fecha_fact'])
    # Ventana: últimos 6 meses cerrados (excluye mes actual incompleto)
    window_start = current_month_start - pd.DateOffset(months=6)
    last6 = fact[(fact['fecha_fact'] >= window_start) & (fact['fecha_fact'] < current_month_start)]
    last3 = fact[(fact['fecha_fact'] >= current_month_start - pd.DateOffset(months=3)) & (fact['fecha_fact'] < current_month_start)]

    # Ventas por modelo (marca + modelo normalizado)
    def ventas_por_modelo(sub_df, marca_up):
        s = sub_df[sub_df['marca_up']==marca_up]
        if len(s)==0: return {}
        return s.dropna(subset=['MODELO']).groupby('MODELO').size().to_dict()
    ventas_6m = {marca: ventas_por_modelo(last6, marca) for marca in ['FORD','DONGFENG','CHERY','MAZDA','RAM']}
    ventas_3m = {marca: ventas_por_modelo(last3, marca) for marca in ['FORD','DONGFENG','CHERY','MAZDA','RAM']}
    # Ventas mes en curso (parcial)
    cur_month = fact[fact['fecha_fact'] >= current_month_start]
    ventas_actual = {marca: ventas_por_modelo(cur_month, marca) for marca in ['FORD','DONGFENG','CHERY','MAZDA','RAM']}
    # Serie temporal por mes (para mostrar tendencia si hace falta luego)
    fact['ym'] = fact['fecha_fact'].dt.to_period('M').astype(str)

    # === RES-COLA — reservas (algunas con VIN, otras 'SIN VIN') ===
    rc = pd.read_excel(path, sheet_name='RES-COLA', header=0)
    rc['marca_up'] = rc['MARCA'].astype(str).str.strip().str.upper()
    rc['MODELO_RAW'] = rc['MODELO'].astype(str).str.strip()  # texto original de la versión
    rc['MODELO'] = rc.apply(lambda r: normalize_res_cola_modelo(r['MODELO_RAW'], r['marca_up']), axis=1)
    rc['AGENCIA'] = rc['AGENCIA DE RESERVA'].apply(res_agency_norm)
    rc['FECHA'] = pd.to_datetime(rc['FECHA DE RESERVA'], errors='coerce')
    rc['aging'] = (today - rc['FECHA']).dt.days
    rc['SIN_VIN'] = rc['SIN VIN'].astype(str).str.upper().str.contains('SIN VIN', na=False)
    # Filtro: solo reservas con todos los campos clave llenos (cliente real).
    # Las reservas sin agencia o sin modelo normalizado se descartan — corresponden a
    # registros incompletos del Excel que el negocio no considera clientes confirmados.
    rc = rc[rc['AGENCIA'].notna() & rc['MODELO'].notna()].copy()

    # === USA + PROC-NAC-MAY — pipeline de oferta futura ===
    try:
        usa = pd.read_excel(path, sheet_name='USA', header=0)
        usa['marca_up'] = usa['marca'].astype(str).str.strip().str.upper()
        usa['MODELO'] = usa.apply(lambda r: normalize_familia(r['familia'], r['marca_up']), axis=1)
    except Exception:
        usa = pd.DataFrame(columns=['MODELO','marca_up'])
    try:
        proc = pd.read_excel(path, sheet_name='PROC-NAC-MAY', header=0)
        proc['marca_up'] = proc['marca'].astype(str).str.strip().str.upper()
        proc['MODELO'] = proc.apply(lambda r: normalize_familia(r['familia'], r['marca_up']), axis=1)
    except Exception:
        proc = pd.DataFrame(columns=['MODELO','marca_up'])

    # === Construir estructura por MARCA → MODELO → agencia ===
    out = {}
    for marca_panel, marca_inv in [
        ('FORD','FORD'),
        ('DONGFENG_ORGU','DONGFENG'),
        ('CHERY_ORGU','CHERY'),
        ('MAZDA_ORGU','MAZDA'),
        ('RAM_ORGU','RAM'),
    ]:
        sub_df = df[df['marca_up']==marca_inv]
        sub_rc = rc[rc['marca_up']==marca_inv]
        sub_usa = usa[usa['marca_up']==marca_inv] if len(usa) else usa
        sub_proc = proc[proc['marca_up']==marca_inv] if len(proc) else proc

        # Por modelo
        modelos = sorted(set(
            list(sub_df.dropna(subset=['MODELO'])['MODELO'].unique()) +
            list(sub_rc.dropna(subset=['MODELO'])['MODELO'].unique())
        ))
        if not modelos:
            continue

        modelos_data = {}
        for m in modelos:
            mdf = sub_df[sub_df['MODELO']==m]
            mrc = sub_rc[sub_rc['MODELO']==m]
            mus = sub_usa[sub_usa['MODELO']==m] if len(sub_usa) else pd.DataFrame()
            mpr = sub_proc[sub_proc['MODELO']==m] if len(sub_proc) else pd.DataFrame()

            # Disponible (stock listo en bodegas, status DISPONIBLE)
            disp = mdf[mdf['STATUS_H']=='DISPONIBLE']
            disp_by_ag = disp.groupby('AGENCIA').size().to_dict()
            disp_transito = int(disp_by_ag.get('Tránsito', 0))
            disp_agencias = {a: int(c) for a, c in disp_by_ag.items() if a not in ('Tránsito','Otros','Entregado')}
            disp_total = int(disp.shape[0])

            # Reservado (stock con VIN ya asignado a cliente — no facturado aún)
            res_v = mdf[mdf['STATUS_H']=='RESERVADO']
            res_by_ag = res_v.groupby('AGENCIA').size().to_dict()
            res_agencias = {a: int(c) for a, c in res_by_ag.items() if a not in ('Tránsito','Otros','Entregado')}
            res_total = int(res_v.shape[0])

            # Reservas en cola (RES-COLA — pueden tener VIN o no)
            mrc_sinvin = mrc[mrc['SIN_VIN']==True]
            mrc_conv = mrc[mrc['SIN_VIN']==False]
            cola_by_ag = mrc.dropna(subset=['AGENCIA']).groupby('AGENCIA').size().to_dict()
            cola_agencias = {a: int(c) for a, c in cola_by_ag.items()}
            cola_total = int(len(mrc))
            cola_sinvin = int(len(mrc_sinvin))
            # Desglose por versión: clave = nombre tal cual en RES-COLA, value = count
            # Útil para modelos con múltiples versiones (F-150 XLT/Lariat/Platinium/Raptor, etc.)
            cola_versions_raw = mrc['MODELO_RAW'].astype(str).str.strip().value_counts().to_dict() if 'MODELO_RAW' in mrc.columns else {}
            cola_versions = {str(k).strip(): int(v) for k, v in cola_versions_raw.items() if str(k).strip().lower() not in ('nan','')}

            # Aging de reservas (todas las de RES-COLA con fecha)
            aging_30 = int(((mrc['aging']>=0) & (mrc['aging']<=30)).sum())
            aging_60 = int(((mrc['aging']>30) & (mrc['aging']<=60)).sum())
            aging_90 = int(((mrc['aging']>60) & (mrc['aging']<=90)).sum())
            aging_old = int((mrc['aging']>90).sum())

            # Ventas históricas para velocity de MOS
            v6m = ventas_6m.get(marca_inv, {}).get(m, 0)
            v3m = ventas_3m.get(marca_inv, {}).get(m, 0)
            vAct = ventas_actual.get(marca_inv, {}).get(m, 0)

            modelos_data[m] = {
                # Oferta inmediata
                'disp_total': disp_total,
                'disp_agencias': disp_agencias,
                'disp_transito': disp_transito,
                # Reservado con VIN
                'res_total': res_total,
                'res_agencias': res_agencias,
                # Pipeline futuro
                'pipeline_nac': int(len(mpr)),
                'pipeline_usa': int(len(mus)),
                # Reservas en cola (demanda comprometida sin facturar)
                'cola_total': cola_total,
                'cola_sin_vin': cola_sinvin,
                'cola_agencias': cola_agencias,
                'cola_versions': cola_versions,  # desglose por versión específica
                'cola_aging': {
                    '0_30': aging_30, '31_60': aging_60,
                    '61_90': aging_90, '90_plus': aging_old,
                },
                # Ventas para velocity de MOS
                # Velocidad oficial = promedio últimos 3 meses cerrados (refleja ritmo
                # actual, no picos de despacho viejos). En la industria automotriz
                # los lotes llegan agrupados; promedio 6m+ infla el ritmo.
                'ventas_6m': int(v6m),
                'ventas_3m': int(v3m),
                'ventas_mes_actual': int(vAct),
                'ventas_avg_mensual': round(v3m/3, 2) if v3m else 0,  # promedio últ 3m
                'ventas_avg_6m': round(v6m/6, 2) if v6m else 0,       # comparativa 6m
                # Flag: limitado por stock (hay cola sin VIN → demanda real es mayor que ventas observadas)
                'venta_limitada_por_stock': cola_sinvin > 0,
            }

        out[marca_panel] = {'modelos': modelos_data}

    # Metadata + lista de RES-COLA para tabla detalle.
    # rc ya está filtrado a clientes reales (agencia + modelo válidos).
    cola_detail = []
    for _, r in rc.iterrows():
        aging = r['aging'] if pd.notna(r['aging']) else None
        cola_detail.append({
            'marca': r['marca_up'], 'modelo': r['MODELO'], 'agencia': r['AGENCIA'],
            'cliente': str(r['CLIENTE DE RESERVA']) if pd.notna(r['CLIENTE DE RESERVA']) else '',
            'asesor': str(r['ASESOR']) if pd.notna(r['ASESOR']) else '',
            'valor': (lambda v: (float(v) if isinstance(v,(int,float)) or (isinstance(v,str) and v.replace('.','').replace(',','').isdigit()) else None))(r['VALOR DE RESERVA']) if pd.notna(r['VALOR DE RESERVA']) else None,
            'fecha': r['FECHA'].strftime('%Y-%m-%d') if pd.notna(r['FECHA']) else None,
            'aging_days': int(aging) if aging is not None and not pd.isna(aging) else None,
            'modalidad': str(r['MODALIDAD']) if pd.notna(r['MODALIDAD']) else None,
            'sin_vin': bool(r['SIN_VIN']),
        })

    # === CRUCE MES A MES — snapshots históricos por marca ===
    # Para cada mes en months_config, reconstruimos:
    #   - ventas del mes (facturas con fecha_factura dentro del mes)
    #   - arribos del mes (vehículos que entraron al inventario)
    #   - disponible al cierre del mes (no facturado, no reservado, ya en inventario)
    #   - reservados al cierre del mes (con cliente asignado, no facturado aún)
    #   - mismo snapshot al INICIO del mes (para "stock al empezar el mes")
    df['f_arribo']  = pd.to_datetime(df['FECHA DE ARRIBO'], errors='coerce')
    df['f_reserva_inv'] = pd.to_datetime(df['FECHA_DE_RESERVA'], errors='coerce')
    df['f_factura_inv'] = pd.to_datetime(df['fecha de facturacion'], errors='coerce')
    # Fallback: si no hay fecha de arribo, usar Fecha Registro (cuándo entró al sistema)
    df['f_arribo'] = df['f_arribo'].fillna(pd.to_datetime(df['Fecha Registro'], errors='coerce'))
    # Agencia normalizada para reserva y facturación (para filtrado en monthly_cross)
    df['AGENCIA_RES_N']  = df['AGENCIA_DE_RESERVA'].apply(res_agency_norm)
    df['AGENCIA_FACT_N'] = df['AGENCIA_FACTURACION'].apply(fact_agency_norm)

    def _snapshots_marca(marca_inv, months):
        """months: list of dicts con keys year, month, cut_day, key, label.
        Devuelve por mes los snapshots globales de la marca + desglose por modelo."""
        sub = df[df['marca_up']==marca_inv]
        modelos_marca = sorted(sub.dropna(subset=['MODELO'])['MODELO'].unique())
        out = {}
        for cfg in months:
            y, mo = cfg['year'], cfg['month']
            mes_start = pd.Timestamp(year=y, month=mo, day=1)
            if cfg.get('is_current'):
                eom = pd.Timestamp(year=y, month=mo, day=cfg['cut_day'])
            elif mo == 12:
                eom = pd.Timestamp(year=y+1, month=1, day=1) - pd.Timedelta(days=1)
            else:
                eom = pd.Timestamp(year=y, month=mo+1, day=1) - pd.Timedelta(days=1)
            som_minus1 = mes_start - pd.Timedelta(days=1)
            include_som = som_minus1.year >= 2024

            def _calc_for(slice_df):
                """Calcula los 6 indicadores para un slice del DataFrame.
                IMPORTANTE: FECHA_DE_RESERVA con año <= 2020 es un placeholder dummy
                (e.g. 1900-01-01) — NO es una reserva real. Filtramos esos."""
                f_res_valid = slice_df['f_reserva_inv'].notna() & (slice_df['f_reserva_inv'].dt.year > 2020)
                def _disp_at(ts):
                    mask_arr     = slice_df['f_arribo'].notna() & (slice_df['f_arribo'] <= ts)
                    mask_no_fact = slice_df['f_factura_inv'].isna() | (slice_df['f_factura_inv'] > ts)
                    mask_no_res  = (~f_res_valid) | (slice_df['f_reserva_inv'] > ts)
                    return int((mask_arr & mask_no_fact & mask_no_res).sum())
                def _res_at(ts):
                    mask_res     = f_res_valid & (slice_df['f_reserva_inv'] <= ts)
                    mask_no_fact = slice_df['f_factura_inv'].isna() | (slice_df['f_factura_inv'] > ts)
                    return int((mask_res & mask_no_fact).sum())
                ventas = int(((slice_df['f_factura_inv'] >= mes_start) & (slice_df['f_factura_inv'] <= eom)).sum())
                arribos = int(((slice_df['f_arribo'] >= mes_start) & (slice_df['f_arribo'] <= eom)).sum())
                return {
                    'ventas': ventas, 'arribos': arribos,
                    'disp_eom': _disp_at(eom),
                    'reserv_eom': _res_at(eom),
                    'disp_som':   _disp_at(som_minus1) if include_som else None,
                    'reserv_som': _res_at(som_minus1) if include_som else None,
                }

            def _calc_por_agencia(slice_df):
                """Desglose por agencia: ventas (AGENCIA_FACTURACION), reservas
                (AGENCIA_DE_RESERVA), arribos. Disp NO se desglosa por agencia
                porque los VINs disponibles no están atribuidos a una agencia
                hasta que se reserven/facturen."""
                f_res_valid = slice_df['f_reserva_inv'].notna() & (slice_df['f_reserva_inv'].dt.year > 2020)
                out_ag = {}
                # Agencias del panel + cualquier otra que aparezca
                agencias = ['CJA','Orellana','La Y','Tumbaco','Manta','Machala','Portoviejo']
                for ag in agencias:
                    sub_v   = slice_df[slice_df['AGENCIA_FACT_N']==ag]
                    sub_r   = slice_df[slice_df['AGENCIA_RES_N']==ag]
                    ventas  = int(((sub_v['f_factura_inv'] >= mes_start) & (sub_v['f_factura_inv'] <= eom)).sum())
                    # Reservas activas al cierre EOM (filtradas por agencia de reserva)
                    res_valid_ag = sub_r['f_reserva_inv'].notna() & (sub_r['f_reserva_inv'].dt.year > 2020)
                    res_eom = int((res_valid_ag & (sub_r['f_reserva_inv'] <= eom)
                                   & (sub_r['f_factura_inv'].isna() | (sub_r['f_factura_inv'] > eom))).sum())
                    if include_som:
                        res_som = int((res_valid_ag & (sub_r['f_reserva_inv'] <= som_minus1)
                                       & (sub_r['f_factura_inv'].isna() | (sub_r['f_factura_inv'] > som_minus1))).sum())
                    else:
                        res_som = None
                    out_ag[ag] = {'ventas': ventas, 'reserv_eom': res_eom, 'reserv_som': res_som}
                return out_ag

            global_stats = _calc_for(sub)
            por_modelo = {}
            for m in modelos_marca:
                m_slice = sub[sub['MODELO']==m]
                stats = _calc_for(m_slice)
                stats['por_agencia'] = _calc_por_agencia(m_slice)
                por_modelo[m] = stats

            out[cfg['key']] = {
                'mes_label':   cfg['label'],
                'mes_start':   mes_start.strftime('%Y-%m-%d'),
                'mes_end':     eom.strftime('%Y-%m-%d'),
                'is_current':  bool(cfg.get('is_current')),
                **global_stats,
                'por_modelo':  por_modelo,
            }
        return out

    monthly_cross = {}
    if months_config:
        for marca_panel, marca_inv in [('FORD','FORD'),('DONGFENG_ORGU','DONGFENG'),
                                        ('CHERY_ORGU','CHERY'),('MAZDA_ORGU','MAZDA'),
                                        ('RAM_ORGU','RAM')]:
            monthly_cross[marca_panel] = _snapshots_marca(marca_inv, months_config)

    return {
        'snapshot_date': today.strftime('%Y-%m-%d'),
        'brands': out,
        'cola_detail': cola_detail,
        'wait_times': wait_data,  # tiempo reserva→factura por marca/modelo (últ 12m + histórico)
        'monthly_cross': monthly_cross,  # cruce mes a mes para diagnóstico de caídas de tráfico
        'totals': {
            'disponible_total': int((df['STATUS_H']=='DISPONIBLE').sum()),
            'reservado_total':  int((df['STATUS_H']=='RESERVADO').sum()),
            'cola_total':       int(len(rc)),
            'pipeline_usa':     int(len(usa)),
            'pipeline_nac':     int(len(proc)),
        },
    }
