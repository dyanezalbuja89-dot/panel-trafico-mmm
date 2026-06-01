"""Módulo de Conversión Tráfico → Venta.

Lógica robusta de "cliente_key" para cruzar BD de tráfico con DATOS de facturación,
manejando los casos reales que el dedupe simple por CEDULA pierde:

  1. Cédula natural ↔ RUC del titular (`XXXXXXXXXX` ↔ `XXXXXXXXXX001`)
  2. Persona ↔ Empresa (mismo email/celular, distinta cédula)
  3. Duplicados exactos en la misma fecha
  4. Progresión de estado (Indagación → Cotización → Cierre → Entrega)

Este módulo es AISLADO: NO modifica las funciones que el resto del panel usa
(`process_bd_ford`, `process_bd_brand` siguen igual). Solo agrega un cálculo
adicional al output del JSON bajo la clave `conversion_data`.
"""
import re
import glob
import unicodedata
from pathlib import Path
from datetime import datetime
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Normalización
# ─────────────────────────────────────────────────────────────────────────────

def norm_ced(v):
    """Normaliza una cédula/RUC: solo dígitos, sin .0, sin espacios.
    Retorna None si tiene menos de 9 dígitos.
    Restaura el cero inicial que Excel descarta cuando guarda la cédula
    como número (provincias Guayas/09 y Pichincha/01 son las más afectadas)."""
    if pd.isna(v):
        return None
    s = str(v).strip()
    if s.endswith('.0'):
        s = s[:-2]
    s = re.sub(r'\D', '', s)
    if not s or len(s) < 9:
        return None
    if len(s) == 9:
        s = '0' + s    # cédula que perdió el cero inicial
    elif len(s) == 12:
        s = '0' + s    # RUC persona natural que perdió el cero
    return s


def cedula_base(ced):
    """Si la cédula es RUC de persona natural (13 dígitos terminados en 001),
    devuelve solo los primeros 10 dígitos. Para RUCs de empresa (sociedades, 0992...001),
    también extrae los primeros 10 dígitos del RUC.
    Para cédula natural (10 dígitos), la devuelve igual."""
    if not ced:
        return None
    if len(ced) == 13 and ced.endswith('001'):
        return ced[:10]
    if len(ced) == 10:
        return ced
    # Otro formato (e.g. pasaporte) — devolver como está
    return ced


def norm_email(s):
    """Normaliza email a lowercase strip. Retorna None si es genérico/inválido."""
    if pd.isna(s):
        return None
    e = str(s).strip().lower()
    # Filtrar valores no-email (e.g. solo dominio)
    if not e or '@' not in e or e.startswith('@') or len(e) < 6:
        return None
    # Filtrar emails dummy comunes
    blacklist = {'noemail@noemail.com', 'sincorreo@sincorreo.com', 'no@no.com'}
    if e in blacklist:
        return None
    return e


def norm_cel(s):
    """Normaliza celular: solo dígitos, últimos 10 (cel Ecuador). Retorna None si no es válido."""
    if pd.isna(s):
        return None
    d = re.sub(r'\D', '', str(s))
    if not d or len(d) < 9:
        return None
    # Tomar últimos 10 dígitos (cubre el caso +593 prefijo)
    d = d[-10:] if len(d) >= 10 else d
    # Validar que sea celular ecuatoriano (empieza con 09)
    if len(d) == 10 and d.startswith('09'):
        return d
    return None


def norm_name(s):
    """Normaliza nombre: sin tildes, lowercase, sin espacios extras."""
    if pd.isna(s):
        return ''
    n = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode('ascii')
    return ' '.join(n.lower().strip().split())


# Sufijos/palabras de empresa que se ignoran al hacer match por nombre
COMPANY_STOPWORDS = {
    's.a.', 'sa', 's.a', 's.a.s.', 'sas', 's.a.s',
    'ltda', 'cia', 'cía', 'c.a.', 'ca', 'c.a',
    'compania', 'compañia', 'compañía', 'sociedad', 'anonima', 'anónima',
    'corp', 'corporacion', 'corporación', 'empresa',
    'de', 'del', 'la', 'el', 'los', 'las', 'y', 'e',
}

def name_tokens(s):
    """Tokens normalizados de un nombre, sin stopwords ni puntuación."""
    if not s:
        return set()
    n = norm_name(s).replace('.', ' ').replace(',', ' ')
    toks = {t for t in n.split() if t and t not in COMPANY_STOPWORDS and len(t) >= 3}
    return toks

def name_match(name_a, name_b, min_common=2):
    """Match estricto entre dos nombres: requiere al menos `min_common` tokens
    significativos compartidos Y que >=50% de los tokens del más corto estén
    en el más largo. Esto evita falsos positivos tipo "Miguel Angel X" matcheando
    con cualquier otro "Miguel Angel"."""
    ta, tb = name_tokens(name_a), name_tokens(name_b)
    if not ta or not tb:
        return False
    common = ta & tb
    if len(common) < min_common:
        return False
    shorter = min(len(ta), len(tb))
    return len(common) / shorter >= 0.5


# ─────────────────────────────────────────────────────────────────────────────
# Union-Find para agrupar registros del mismo cliente
# ─────────────────────────────────────────────────────────────────────────────

class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
            return x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.parent[rx] = ry


def build_client_keys(df, ced_col='CEDULA', email_col='CORREO', cel_col='CELULAR'):
    """Asigna un `client_key` a cada fila del df, agrupando registros del mismo cliente.

    Returns una Series con el MISMO index del df original.
    """
    n = len(df)
    if n == 0:
        return pd.Series([], dtype=object)
    uf = UnionFind()
    row_ids = [f'r{i}' for i in range(n)]   # IDs posicionales

    ced_to_rows  = {}
    base_to_rows = {}
    email_to_rows = {}
    cel_to_rows = {}

    # Pre-extraer columnas como arrays para velocidad y posicionar por iloc
    ced_arr   = df[ced_col].values   if ced_col in df.columns else [None]*n
    email_arr = df[email_col].values if email_col in df.columns else [None]*n
    cel_arr   = df[cel_col].values   if cel_col in df.columns else [None]*n

    for i in range(n):
        rid = row_ids[i]
        uf.find(rid)
        ced = norm_ced(ced_arr[i])
        base = cedula_base(ced) if ced else None
        email = norm_email(email_arr[i])
        cel = norm_cel(cel_arr[i])
        if ced:   ced_to_rows.setdefault(ced, []).append(rid)
        if base:  base_to_rows.setdefault(base, []).append(rid)
        if email: email_to_rows.setdefault(email, []).append(rid)
        if cel:   cel_to_rows.setdefault(cel, []).append(rid)

    for groups in (ced_to_rows.values(), base_to_rows.values(),
                   email_to_rows.values(), cel_to_rows.values()):
        for rids in groups:
            if len(rids) > 1:
                first = rids[0]
                for other in rids[1:]:
                    uf.union(first, other)

    keys = [uf.find(rid) for rid in row_ids]
    # IMPORTANTE: usar el index ORIGINAL del df, no uno reseteado
    return pd.Series(keys, index=df.index)


# ─────────────────────────────────────────────────────────────────────────────
# Carga de tráfico histórico
# ─────────────────────────────────────────────────────────────────────────────

ESTADO_ORDEN = {'Indagación': 1, 'Cotización': 2, 'Demostración': 3,
                'Cierre': 4, 'Entrega': 5}


def _normalize_modelo_bd(m):
    """Normaliza el MODELO del BD tráfico para unificar variantes (F150 / F-150 = mismo modelo)."""
    if not isinstance(m, str):
        return m
    s = m.upper().strip()
    if s in ('F150', 'F-150', 'F 150'):
        return 'F-150'
    return s


def load_all_traffic(bd_dir):
    """Carga TODOS los archivos BD_*.xlsx del directorio bd_dir y los combina.
    No deduplica. Cada fila tiene su origen (mes_key inferido del filename)."""
    files = sorted(glob.glob(str(Path(bd_dir) / 'BD_*.xlsx')))
    parts = []
    for f in files:
        try:
            bd = pd.read_excel(f, sheet_name='Negocios')
            bd['_source_file'] = Path(f).name
            parts.append(bd)
        except Exception:
            continue
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)
    df['FECHA'] = pd.to_datetime(df['FECHA'], errors='coerce')
    # Normalizar MODELO para unificar variantes (e.g. F150 ↔ F-150)
    if 'MODELO' in df.columns:
        df['MODELO'] = df['MODELO'].apply(_normalize_modelo_bd)
    # Estado numérico para tomar el más avanzado por cliente
    df['ESTADO_RANK'] = df['ESTADO'].map(ESTADO_ORDEN).fillna(0).astype(int)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Cruce tráfico → venta
# ─────────────────────────────────────────────────────────────────────────────

def cross_traffic_sales(traffic_df, sales_df):
    """Cruza tráfico con ventas usando client_key.

    traffic_df: DataFrame con BDs históricas combinadas
    sales_df: DataFrame de DATOS con status FACTURADO

    Returns:
      dict con métricas agregadas + lista de matches (para drill-down).
    """
    # Construir client_key para tráfico
    traffic_df = traffic_df.copy()
    traffic_df['client_key'] = build_client_keys(traffic_df, 'CEDULA', 'CORREO', 'CELULAR')

    # Para ventas, el "cliente" es la cédula del comprador. Construimos client_key con
    # cedula_base para que cruce con cédula natural o RUC.
    sales_df = sales_df.copy()
    sales_df['ced_norm'] = sales_df['IDENTIFICACION'].apply(norm_ced)
    sales_df['ced_base'] = sales_df['ced_norm'].apply(cedula_base)

    # Mapeo cliente_key → cualquier cédula o cédula_base del tráfico
    traffic_df['ced_norm'] = traffic_df['CEDULA'].apply(norm_ced)
    traffic_df['ced_base'] = traffic_df['ced_norm'].apply(cedula_base)

    # Indexar tráfico por ced_base para lookup rápido
    # Por cada client_key, qué ced_base usa
    ck_to_ced_base = {}
    for _, row in traffic_df.iterrows():
        ck = row['client_key']
        if row['ced_base']:
            ck_to_ced_base.setdefault(ck, set()).add(row['ced_base'])

    # Por cada venta, ver si su ced_base pertenece a algún client_key de tráfico
    ced_base_to_ck = {}
    for ck, bases in ck_to_ced_base.items():
        for b in bases:
            ced_base_to_ck.setdefault(b, set()).add(ck)

    # Cruzar: si la venta.ced_base aparece en ced_base_to_ck, está atribuible
    sales_df['matched_ck'] = sales_df['ced_base'].apply(
        lambda b: next(iter(ced_base_to_ck.get(b, set())), None) if b else None
    )
    sales_df['match_method'] = sales_df['matched_ck'].apply(lambda x: 'cedula' if x else None)

    # Agrupar facturas por COMPRADOR (no por fila) para que clientes con varias
    # facturas se atribuyan correctamente las múltiples ventas si el comprador matchea.
    # buyer_key = ced_base si existe, sino CLIENTE_FACTURACION normalizado.
    def _buyer_key(row):
        if pd.notna(row.get('ced_base')) and row.get('ced_base'):
            return f'ced:{row["ced_base"]}'
        cf = row.get('CLIENTE_FACTURACION')
        if pd.notna(cf):
            n = norm_name(cf)
            if n: return f'name:{n}'
        cr = row.get('CLIENTE_RESERVA')
        if pd.notna(cr):
            n = norm_name(cr)
            if n: return f'name:{n}'
        return None
    sales_df['buyer_key'] = sales_df.apply(_buyer_key, axis=1)

    # Propagar matched_ck a TODAS las facturas del mismo comprador.
    # Si una fila ya tiene matched_ck (vía cédula), todas las del mismo buyer_key heredan.
    buyer_to_ck = {}
    for _, row in sales_df[sales_df['matched_ck'].notna()].iterrows():
        bk = row.get('buyer_key')
        if bk: buyer_to_ck.setdefault(bk, row['matched_ck'])
    for idx in sales_df[sales_df['matched_ck'].isna()].index:
        bk = sales_df.at[idx, 'buyer_key']
        if bk and bk in buyer_to_ck:
            sales_df.at[idx, 'matched_ck'] = buyer_to_ck[bk]
            sales_df.at[idx, 'match_method'] = 'cedula_propagado'

    # FALLBACK por NOMBRE: para ventas sin match por cédula (típicamente porque
    # IDENTIFICACION está vacío en DATOS), buscar al cliente por CLIENTE_FACTURACION
    # o CLIENTE_RESERVA contra NOMBRES+APELLIDOS de BD tráfico.
    #
    # Estrategia con 2 reglas:
    #   A. >=2 tokens compartidos + >=60% overlap del set más corto.
    #   B. 1 token único "raro" (>=6 letras, e.g. nombre de empresa "RICADUTEF").
    if 'CLIENTE_FACTURACION' in sales_df.columns or 'CLIENTE_RESERVA' in sales_df.columns:
        traffic_df['name_full'] = (
            traffic_df['NOMBRES'].astype(str).fillna('') + ' ' +
            traffic_df['APELLIDOS'].astype(str).fillna('')
        )
        # Tokens precomputados por client_key
        ck_name_tokens = {}
        # Frecuencia global de cada token (para identificar "raros")
        token_freq = {}
        for _, row in traffic_df.iterrows():
            ck = row['client_key']
            toks = name_tokens(row['name_full'])
            if not toks: continue
            ck_name_tokens.setdefault(ck, set()).update(toks)
            for t in toks:
                token_freq[t] = token_freq.get(t, 0) + 1

        # Un token es "raro" si tiene >=6 letras Y aparece en <=5 client_keys
        # (probablemente razón social de empresa o apellido poco común)
        def is_rare_token(t):
            return len(t) >= 6 and token_freq.get(t, 0) <= 5

        unmatched_idx = sales_df[sales_df['matched_ck'].isna()].index
        for idx in unmatched_idx:
            row = sales_df.loc[idx]
            cand_names = []
            for col in ('CLIENTE_FACTURACION', 'CLIENTE_RESERVA'):
                if col in row.index and pd.notna(row[col]):
                    cand_names.append(str(row[col]))
            if not cand_names: continue
            buyer_toks = set()
            for n in cand_names:
                buyer_toks |= name_tokens(n)
            if not buyer_toks: continue

            best_ck, best_score, best_method = None, 0, None

            # REGLA A: >=2 tokens compartidos + >=60% overlap
            if len(buyer_toks) >= 2:
                for ck, traf_toks in ck_name_tokens.items():
                    common = buyer_toks & traf_toks
                    if len(common) < 2: continue
                    shorter = min(len(buyer_toks), len(traf_toks))
                    if shorter == 0: continue
                    score = len(common) / shorter
                    if score >= 0.6 and score > best_score:
                        best_score = score
                        best_ck = ck
                        best_method = 'nombre'

            # REGLA B: 1 solo token compartido pero raro (>=6 letras y poco común en BD)
            if best_ck is None:
                rare_buyer = {t for t in buyer_toks if is_rare_token(t)}
                if rare_buyer:
                    # Encontrar client_keys que comparten al menos 1 token raro
                    for ck, traf_toks in ck_name_tokens.items():
                        common_rare = rare_buyer & traf_toks
                        if common_rare:
                            # Match seguro: 1 token raro compartido
                            best_ck = ck
                            best_method = 'nombre_raro'
                            break

            if best_ck:
                sales_df.loc[idx, 'matched_ck'] = best_ck
                sales_df.loc[idx, 'match_method'] = best_method
                # Propagar a todas las facturas del mismo comprador
                bk = sales_df.at[idx, 'buyer_key']
                if bk:
                    same_buyer = sales_df[(sales_df['buyer_key']==bk) & (sales_df['matched_ck'].isna())].index
                    for sidx in same_buyer:
                        sales_df.at[sidx, 'matched_ck'] = best_ck
                        sales_df.at[sidx, 'match_method'] = best_method + '_propagado'

    # ATRIBUCIÓN B2B: las facturas sin match (típicamente flotas/rentcar) se atribuyen
    # al ASESOR_FACTURACION con canal "Gestión Externa". El cliente no pasó por GUC
    # tradicional pero la venta SÍ tiene un responsable comercial — asignar el crédito.
    sales_df['attr_canal']   = None
    sales_df['attr_modelo']  = None
    sales_df['attr_agencia'] = None
    sales_df['attr_asesor']  = None
    unmatched_mask = sales_df['matched_ck'].isna()
    if unmatched_mask.any():
        from aggregate import short_agency
        for idx in sales_df[unmatched_mask].index:
            row = sales_df.loc[idx]
            asesor = row.get('ASESOR_FACTURACION') if pd.notna(row.get('ASESOR_FACTURACION')) else None
            if not asesor or str(asesor).strip()=='':
                continue
            # Sintético: cliente B2B
            ck_b2b = 'b2b:' + str(row.get('buyer_key') or row.get('CLIENTE_FACTURACION') or f'idx{idx}')
            # Normalizar agencia desde AGENCIA_FACTURACION (formato "1001 VEHICULOS X")
            from inventario import fact_agency_norm as _fact_ag
            ag_fact = row.get('AGENCIA_FACTURACION') if pd.notna(row.get('AGENCIA_FACTURACION')) else None
            ag_norm = _fact_ag(ag_fact) if ag_fact else None
            # Normalizar modelo desde familia (en facturas la columna se llama 'familia')
            marca = row.get('marca_up') if pd.notna(row.get('marca_up')) else None
            familia = row.get('familia') if pd.notna(row.get('familia')) else None
            from inventario import normalize_familia as _norm_fam
            modelo_norm = _norm_fam(familia, marca) if familia else None
            sales_df.at[idx, 'matched_ck']   = ck_b2b
            sales_df.at[idx, 'match_method'] = 'b2b_gestion_externa'
            sales_df.at[idx, 'attr_canal']   = 'Gestión Externa'
            sales_df.at[idx, 'attr_modelo']  = modelo_norm
            sales_df.at[idx, 'attr_agencia'] = ag_norm
            sales_df.at[idx, 'attr_asesor']  = str(asesor).strip().upper()

    matched_sales = sales_df[sales_df['matched_ck'].notna()].copy()

    # Tomar la fila de tráfico más temprana por client_key (primer toque)
    traffic_df_sorted = traffic_df.sort_values('FECHA')
    first_touch = traffic_df_sorted.groupby('client_key').agg(
        first_fecha=('FECHA', 'first'),
        first_canal=('CANAL', 'first'),
        first_marca=('MARCA', 'first'),
        first_modelo=('MODELO', 'first'),
        first_agencia=('AGENCIA', 'first'),
        first_asesor=('ASESOR', 'first'),
        max_estado=('ESTADO_RANK', 'max'),
        n_toques=('FECHA', 'count'),
    ).to_dict('index')
    # Para clientes B2B sintéticos (sin pasar por GUC), agregar entradas con datos
    # tomados de la factura (canal Gestión Externa, asesor de facturación).
    b2b_rows = sales_df[sales_df['match_method']=='b2b_gestion_externa']
    for _, row in b2b_rows.iterrows():
        ck = row['matched_ck']
        if ck in first_touch: continue
        first_touch[ck] = {
            'first_fecha':  row.get('fecha_fact'),
            'first_canal':  row.get('attr_canal'),
            'first_marca':  row.get('marca_up'),
            'first_modelo': row.get('attr_modelo'),
            'first_agencia':row.get('attr_agencia'),
            'first_asesor': row.get('attr_asesor'),
            'max_estado': 5,
            'n_toques': 1,
        }

    return {
        'traffic_df': traffic_df,
        'sales_df': sales_df,
        'matched_sales': matched_sales,
        'first_touch_by_ck': first_touch,
        'ck_to_ced_base': ck_to_ced_base,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Métricas agregadas para el panel
# ─────────────────────────────────────────────────────────────────────────────

# Solo agencias Ford válidas. "Machala (DF)", "La Y (Chery)" etc son de otras marcas.
FORD_AGENCIES = ['CJA','Orellana','La Y','Tumbaco','Manta','Machala','Portoviejo']
ZONAS = {
    'Quito':     ['La Y','Tumbaco'],
    'Guayaquil': ['CJA','Orellana'],
    'Manta':     ['Manta','Portoviejo'],
    'Machala':   ['Machala'],
}
def agencia_to_zona(ag):
    for z, ags in ZONAS.items():
        if ag in ags: return z
    return 'Otra'


def compute_conversion_metrics(bd_dir, sales_df_path, marca_filter=None):
    """Calcula métricas de conversión global y por dimensión.

    Solo considera facturas DENTRO del período donde tenemos BDs de tráfico.
    Cruzar facturas viejas (e.g. 2024) contra BD tráfico que solo existe desde
    oct 2025 daría falsos no-matches.
    """
    traffic = load_all_traffic(bd_dir)
    if traffic.empty:
        return None

    if marca_filter:
        traffic = traffic[traffic['MARCA'].astype(str).str.upper().str.contains(marca_filter.upper())]
    from aggregate import short_agency, norm_channel
    traffic['AGENCIA'] = traffic['SUCURSAL'].apply(short_agency)
    traffic['CANAL'] = traffic['CANAL'].apply(norm_channel)

    # Período de FACTURAS analizadas: solo año en curso (2026).
    # El tráfico se usa completo (oct 2025+) porque un cliente puede haber entrado a
    # BD en 2025 y comprado en 2026 — la atribución cubre toda su trayectoria.
    period_start = pd.Timestamp('2026-01-01')

    # Cargar facturas (DATOS con status=FACTURADO)
    inv = pd.read_excel(sales_df_path, sheet_name='DATOS', header=0)
    inv['STATUS_H'] = inv['STATUS HOMOLOGADO'].astype(str).str.strip().str.upper()
    facturas = inv[inv['STATUS_H'] == 'FACTURADO'].copy()
    facturas['fecha_fact'] = pd.to_datetime(facturas['fecha de facturacion'], errors='coerce')
    facturas['marca_up'] = facturas['marca'].astype(str).str.strip().str.upper()
    if marca_filter:
        facturas = facturas[facturas['marca_up'] == marca_filter.upper()]
    # Filtrar a período donde tenemos BDs
    facturas_all_count = int(len(facturas))
    if period_start is not None:
        facturas = facturas[facturas['fecha_fact'] >= period_start]
    facturas_in_period = int(len(facturas))

    result = cross_traffic_sales(traffic, facturas)
    traffic_df = result['traffic_df']
    matched_sales = result['matched_sales']
    first_touch = result['first_touch_by_ck']
    # FILTRO ESTRICTO 2026: solo clientes cuyo first_touch fue en 2026
    # (clientes pre-2026 que compraron en 2026 no son "leads generados en 2026").
    first_touch = {ck: ft for ck, ft in first_touch.items()
                   if pd.notna(ft.get('first_fecha')) and ft['first_fecha'].year >= 2026}
    # Asignar zona a cada first_touch
    for ck, ft in first_touch.items():
        ag = ft.get('first_agencia')
        ft['first_zona'] = agencia_to_zona(ag) if ag in FORD_AGENCIES else 'Otra'

    # Total clientes únicos en tráfico (después de dedupe por client_key)
    n_clientes_traffic = traffic_df['client_key'].nunique()
    n_clientes_matched = matched_sales['matched_ck'].nunique()
    conv_rate = (100 * n_clientes_matched / n_clientes_traffic) if n_clientes_traffic else 0
    # Cobertura inversa: % de FACTURAS (ventas) atribuidas a tráfico
    sales_df_after = result['sales_df']
    n_facturas_total = int(len(sales_df_after))
    n_facturas_atribuidas = int(sales_df_after['matched_ck'].notna().sum())
    n_facturas_sin_atribuir = n_facturas_total - n_facturas_atribuidas
    cov_rate = (100 * n_facturas_atribuidas / n_facturas_total) if n_facturas_total else 0
    # También conservamos cobertura por cliente único (para análisis)
    n_clientes_unicos_total = int(sales_df_after['ced_base'].nunique())
    n_clientes_unicos_matched = int(sales_df_after[sales_df_after['matched_ck'].notna()]['ced_base'].nunique())

    # Tiempo de ciclo: días entre primer toque (tráfico) y factura
    ciclo_dias = []
    for _, row in matched_sales.iterrows():
        ck = row['matched_ck']
        ft = first_touch.get(ck)
        if not ft or pd.isna(ft['first_fecha']) or pd.isna(row['fecha_fact']):
            continue
        d = (row['fecha_fact'] - ft['first_fecha']).days
        if 0 <= d <= 730:
            ciclo_dias.append(d)
    import statistics
    ciclo = {
        'n': len(ciclo_dias),
        'mediana_dias': statistics.median(ciclo_dias) if ciclo_dias else None,
        'promedio_dias': round(statistics.mean(ciclo_dias), 1) if ciclo_dias else None,
        'p75_dias': statistics.quantiles(ciclo_dias, n=4)[2] if len(ciclo_dias) >= 4 else None,
    }

    # Por canal de primer toque
    canal_breakdown = {}
    for ck, ft in first_touch.items():
        canal = ft.get('first_canal') or 'Sin canal'
        canal_breakdown.setdefault(canal, {'traffic': 0, 'matched': 0})
        canal_breakdown[canal]['traffic'] += 1
    for _, row in matched_sales.iterrows():
        ck = row['matched_ck']
        ft = first_touch.get(ck)
        if not ft:
            continue
        canal = ft.get('first_canal') or 'Sin canal'
        if canal in canal_breakdown:
            canal_breakdown[canal]['matched'] += 1
    # Añadir % conversión
    for canal in canal_breakdown:
        d = canal_breakdown[canal]
        d['conv_pct'] = round(100*d['matched']/d['traffic'], 1) if d['traffic'] else 0

    # Por modelo de primer toque
    modelo_breakdown = {}
    for ck, ft in first_touch.items():
        modelo = (ft.get('first_modelo') or 'Por definir').upper().strip()
        modelo_breakdown.setdefault(modelo, {'traffic': 0, 'matched': 0})
        modelo_breakdown[modelo]['traffic'] += 1
    for _, row in matched_sales.iterrows():
        ck = row['matched_ck']
        ft = first_touch.get(ck)
        if not ft:
            continue
        modelo = (ft.get('first_modelo') or 'Por definir').upper().strip()
        if modelo in modelo_breakdown:
            modelo_breakdown[modelo]['matched'] += 1
    for m in modelo_breakdown:
        d = modelo_breakdown[m]
        d['conv_pct'] = round(100*d['matched']/d['traffic'], 1) if d['traffic'] else 0

    # Por agencia
    agencia_breakdown = {}
    for ck, ft in first_touch.items():
        ag = ft.get('first_agencia') or 'Sin agencia'
        agencia_breakdown.setdefault(ag, {'traffic': 0, 'matched': 0})
        agencia_breakdown[ag]['traffic'] += 1
    for _, row in matched_sales.iterrows():
        ck = row['matched_ck']
        ft = first_touch.get(ck)
        if not ft:
            continue
        ag = ft.get('first_agencia') or 'Sin agencia'
        if ag in agencia_breakdown:
            agencia_breakdown[ag]['matched'] += 1
    for a in agencia_breakdown:
        d = agencia_breakdown[a]
        d['conv_pct'] = round(100*d['matched']/d['traffic'], 1) if d['traffic'] else 0

    # Top asesores
    asesor_breakdown = {}
    for ck, ft in first_touch.items():
        ase = ft.get('first_asesor') or 'Sin asesor'
        asesor_breakdown.setdefault(ase, {'traffic': 0, 'matched': 0})
        asesor_breakdown[ase]['traffic'] += 1
    for _, row in matched_sales.iterrows():
        ck = row['matched_ck']
        ft = first_touch.get(ck)
        if not ft:
            continue
        ase = ft.get('first_asesor') or 'Sin asesor'
        if ase in asesor_breakdown:
            asesor_breakdown[ase]['matched'] += 1
    for a in asesor_breakdown:
        d = asesor_breakdown[a]
        d['conv_pct'] = round(100*d['matched']/d['traffic'], 1) if d['traffic'] else 0

    # Quedarnos con asesores que tienen al menos 5 leads (filtrar ruido)
    asesor_breakdown = {k: v for k, v in asesor_breakdown.items() if v['traffic'] >= 5}

    # =========================================================
    #  BREAKDOWN FILTRADO POR CANALES DE MARKETING
    #  Para el cruce con Inversión Digital, solo cuentan clientes
    #  cuyo first_canal es atribuible a marketing pagado / activación digital.
    #  Showroom va incluido porque la única forma de generar walk-in
    #  es vía publicidad digital (no hay otros canales pagados).
    # =========================================================
    MKT_CHANNELS = {
        'Showroom', 'Hubspot', 'Ferias y Eventos', 'Feria/Eventos',
        'Ferias', 'Llamada In', 'Mailing',
    }
    modelo_mkt = {}
    agencia_mkt = {}
    canal_mkt = {}
    matched_cks_set = set(matched_sales['matched_ck'].dropna().tolist()) \
        if 'matched_ck' in matched_sales.columns else set()
    for ck, ft in first_touch.items():
        canal = ft.get('first_canal') or 'Sin canal'
        if canal not in MKT_CHANNELS:
            continue
        modelo = ft.get('first_modelo') or 'Por definir'
        ag = ft.get('first_agencia') or 'Sin agencia'
        cerro = ck in matched_cks_set
        for bd, key in [(modelo_mkt, modelo), (agencia_mkt, ag), (canal_mkt, canal)]:
            bd.setdefault(key, {'traffic': 0, 'matched': 0})
            bd[key]['traffic'] += 1
            if cerro:
                bd[key]['matched'] += 1
    for bd in (modelo_mkt, agencia_mkt, canal_mkt):
        for k, v in bd.items():
            v['conv_pct'] = round(100 * v['matched'] / v['traffic'], 1) if v['traffic'] else 0

    # ========== TABLA PLANA DE CLIENTES ==========
    # Para que JS pueda filtrar/agregar dinámicamente sin recalcular en backend.
    matched_ck_set = set(matched_sales['matched_ck'].dropna().unique())
    # ► Mantenemos toda la lista de facturas por client_key (no solo el count)
    # para poder filtrar por fecha de primer toque cuando armamos n_ventas.
    # Antes contábamos TODAS las facturas históricas del cliente (n_ventas=count),
    # lo cual atribuía erróneamente al cohorte de primer toque ventas ANTERIORES
    # a ese primer toque (caso típico: B2B/flotas que compran varias veces al año,
    # ej. MAREAUTO S.A. en La Y).
    sales_by_ck = matched_sales[matched_sales['matched_ck'].notna()] \
                    .groupby('matched_ck')['fecha_fact'].apply(list).to_dict()
    # Calcular n_toques mensuales por client_key (un toque = aparece en BD en un mes
    # distinto). Esto es equivalente a la suma cross-mes de cédulas únicas del panel
    # principal (dealer_model_channel) que muestra "tráfico atendido".
    traffic_df['ym'] = traffic_df['FECHA'].dt.to_period('M').astype(str)
    toques_mensuales = traffic_df.drop_duplicates(['client_key','ym']) \
                                  .groupby('client_key').size().to_dict()

    clientes_flat = []
    for ck, ft in first_touch.items():
        ag = ft.get('first_agencia')
        # Filtrar agencias no-Ford (Machala DF, La Y Chery, etc.)
        if ag and ag not in FORD_AGENCIES and ag != 'Gestión Externa':
            continue
        cerro = ck in matched_ck_set
        n_ventas = 0
        ciclo_d = None
        if cerro:
            fechas_fact = sales_by_ck.get(ck, [])
            first_t = ft.get('first_fecha')
            if pd.notna(first_t):
                # ► Solo contar facturas posteriores (o iguales) al primer toque.
                # Las facturas anteriores al touch no son atribuibles a esa cohorte.
                fechas_post = [f for f in fechas_fact if pd.notna(f) and f >= first_t]
                n_ventas = len(fechas_post)
                if fechas_post:
                    primera_fact = min(fechas_post)
                    d = (primera_fact - first_t).days
                    if 0 <= d <= 730:
                        ciclo_d = int(d)
                else:
                    # Si no hay facturas posteriores al toque → no es conversión real
                    cerro = False
            else:
                # Sin fecha de toque (raro), usar count total como fallback
                n_ventas = len(fechas_fact)
        # n_toques: cuántos meses distintos vino el cliente. Para B2B sintéticos sin
        # tráfico, asumimos 1 (la "venta" cuenta como un toque atendido).
        n_toques = int(toques_mensuales.get(ck, 1)) if str(ck).startswith('r') else 1
        first_ym = ft['first_fecha'].strftime('%Y-%m') if pd.notna(ft.get('first_fecha')) else None
        clientes_flat.append({
            'canal':    ft.get('first_canal'),
            'modelo':   (ft.get('first_modelo') or '').upper().strip() or 'Por definir',
            'agencia':  ag or 'Sin agencia',
            'zona':     ft.get('first_zona') or 'Otra',
            'asesor':   ft.get('first_asesor') or 'Sin asesor',
            'first_ym': first_ym,
            'cerro':    bool(cerro),
            'n_ventas': n_ventas,
            'n_toques': n_toques,
            'ciclo_dias': ciclo_d,
        })

    n_clients_2026 = len(clientes_flat)
    n_clients_2026_cerro = sum(1 for c in clientes_flat if c['cerro'])
    conv_2026 = round(100 * n_clients_2026_cerro / n_clients_2026, 1) if n_clients_2026 else 0

    return {
        'global': {
            'periodo_inicio': period_start.strftime('%Y-%m-%d') if period_start is not None else None,
            'n_clientes_traffic': n_clients_2026,
            'n_clientes_matched': n_clients_2026_cerro,
            'conv_rate_pct': conv_2026,
            'n_facturas_total': n_facturas_total,
            'n_facturas_atribuidas': n_facturas_atribuidas,
            'n_facturas_sin_atribuir': n_facturas_sin_atribuir,
            'cov_rate_pct': round(cov_rate, 1),
            'n_clientes_unicos_total': n_clientes_unicos_total,
            'n_clientes_unicos_matched': n_clientes_unicos_matched,
            'n_ventas_clientes_total': n_clientes_unicos_total,
            'n_ventas_atribuidas': n_facturas_atribuidas,
            'n_facturas_en_periodo': facturas_in_period,
            'n_facturas_total_historico': facturas_all_count,
            'ciclo': ciclo,
        },
        'clientes_flat': clientes_flat,
        'por_canal':   canal_breakdown,
        'por_modelo':  modelo_breakdown,
        'por_agencia': agencia_breakdown,
        'por_asesor':  asesor_breakdown,
        # Breakdown filtrado SOLO por canales atribuibles a marketing
        # (Showroom + Hubspot + Ferias + Llamada In + Mailing)
        'por_modelo_mkt':   modelo_mkt,
        'por_agencia_mkt':  agencia_mkt,
        'por_canal_mkt':    canal_mkt,
        'mkt_channels':     sorted(MKT_CHANNELS),
    }
