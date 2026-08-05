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


# Celulares "de relleno" que el equipo escribe cuando no tiene el dato real.
# NO pueden usarse para unir identidades: agrupan a personas distintas bajo un
# mismo cliente y la fecha del primer toque del grupo pasa a ser la del registro
# más viejo (caso Ariana Torres: su lead de abr-2026 se fusionó con un registro
# "PRUEBA PRUEBA" de oct-2025 y su venta quedó fuera de la cohorte 2026).
_CEL_BASURA = {
    '0999999999', '0900000000', '0000000000', '0912345678', '0987654321',
    '0911111111', '0922222222', '0933333333', '0944444444', '0955555555',
    '0966666666', '0977777777', '0988888888', '0999999998', '0993333333',
}

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
    if len(d) != 10 or not d.startswith('09'):
        return None
    # Descartar placeholders y cualquier número de un solo dígito repetido.
    if d in _CEL_BASURA or len(set(d[1:])) == 1:
        return None
    return d


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

# Jefes de venta — se EXCLUYEN del cálculo de conversión (atienden poco pero venden
# mucho como B2B/decisor, distorsionan tasa por agencia). Daniel confirmó 2026-07-29.
# Match por normalización sin tildes y busca substring de "nombre + apellido" en el
# ASESOR completo (que puede traer nombre compuesto tipo "ANDY JIMENEZ LEON").
JEFES_VENTA_RAW = [
    'Andy Jimenez',
    'Jose Hervas',
    'Jaime Loor',
    'Marilu Brito',
    'Paola Erazo',
    'Damian Proaño',
    'Margarita Molina',
    'Tatiana Salinas',   # ex-jefa La Y (ya salió) — Daniel 2026-07-29
]

def _norm_jefe(s):
    """Lowercase sin tildes, un solo espacio."""
    if not s: return ''
    n = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode('ascii')
    return ' '.join(n.lower().strip().split())

_JEFES_NORM = [_norm_jefe(x) for x in JEFES_VENTA_RAW]

def is_jefe_venta(asesor):
    """True si asesor coincide con algún jefe de venta (match tokens ambos)."""
    if asesor is None or (isinstance(asesor, float) and pd.isna(asesor)):
        return False
    n = _norm_jefe(asesor)
    if not n: return False
    for jefe in _JEFES_NORM:
        j_toks = jefe.split()
        if all(tok in n for tok in j_toks):
            return True
    return False


def norm_asesor(s):
    """Normaliza nombre de asesor. BDs Kombat suelen traer NOMBRES+APELLIDOS
    concatenando el apellido dos veces (ej: 'LUIS RODRIGO HILANO CARRILLO
    HILANO CARRILLO'). Detecta y elimina la duplicación final."""
    if s is None or (isinstance(s, float)):
        return s
    parts = str(s).strip().upper().split()
    n = len(parts)
    # Buscar la mayor k tal que los últimos k tokens == k anteriores
    for k in range(n // 2, 0, -1):
        if parts[-k:] == parts[-2*k:-k]:
            parts = parts[:-k]
            break
    return ' '.join(parts)


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


# ─────────────────────────────────────────────────────────────────────────────
# Flota / B2B
# ─────────────────────────────────────────────────────────────────────────────
# Renting, flotas y venta corporativa directa NO pasan por el tráfico de piso:
# nunca van a tener lead y engordaban el cajón "Gestión Externa" como si fueran
# ventas sin atribuir. Se les da canal propio para que la conversión de showroom
# se lea limpia y este canal se mida por lo que es (relación comercial directa).
# Regla de Daniel, 5-ago-2026.
_RX_RENTING = re.compile(
    r'RENTING|LEASING|MAREAUTO|XPRESSMOTO|DISTRIVEHIC|RENT ?A ?CAR|AUTOSHARE', re.I)
# Sufijos societarios: palabra completa (evita cazar "SAENZ" por "S.A.").
_RX_SOCIEDAD = re.compile(
    r'\b(S\.?A\.?S?|C\.?A\.?|CIA|C[IÍ]A|LTDA|CORP|COMPA[NÑ][IÍ]A)\b\.?', re.I)
# Raíces de giro comercial: prefijo, sin límite final (DISTRIBU → DISTRIBUCION,
# DISTRIBUIDORA; CONSTRU → CONSTRUCTORA, CONSTRUCCIONES).
_RX_GIRO = re.compile(
    r'COMERCIAL|DISTRIBU|INDUSTRI|CONSTRU|CONSULTOR|SERVICIO|GRUPO|IMPORT|EXPORT|'
    r'AGR[IÍ]COLA|TRANSPORT|INMOBILIARI|LABORATORI|COOPERATIV|HOLDING|TRADING|'
    r'SOLUCIONES|PROYECTOS|MANTENIMIENTO|MOTORS|BANANAS|PLASTIC|SHRIMP|OCEAN|'
    r'TECNOLOG|COMPA[NÑ][IÍ]A|SUMINISTRO|ADMINISTRACION', re.I)


def tipo_cliente_venta(nombre):
    """'Flota/Renting' | 'B2B' | None (persona natural).

    Solo mira el nombre de la factura: es la única señal disponible cuando no
    hay lead. No se usa para clientes CON lead — esos conservan su canal real.
    """
    n = ' ' + re.sub(r'[^A-Za-zÑñÁÉÍÓÚáéíóú.& ]', ' ', str(nombre or '')) + ' '
    if _RX_RENTING.search(n):
        return 'Flota/Renting'
    if _RX_SOCIEDAD.search(n) or _RX_GIRO.search(n):
        return 'B2B'
    return None


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

    # El CELULAR no une identidades (regla de Daniel: el teléfono es del hogar o
    # de la empresa, no de la persona — padre e hijo, esposos, o una ferretería y
    # sus tres socios comparten número). Se sigue normalizando por si alguna vista
    # lo necesita, pero fusionar por él mezcla clientes distintos y corre el
    # first_touch del grupo al registro más viejo. Verificado: unía 22 identidades,
    # varias de personas sin relación (0986430882 → Chuqui + Triviño + Marca).
    for groups in (ced_to_rows.values(), base_to_rows.values(),
                   email_to_rows.values()):
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
    # Normalizar ASESOR — BD suele traer duplicación de apellido
    if 'ASESOR' in traffic_df.columns:
        traffic_df['ASESOR'] = traffic_df['ASESOR'].apply(norm_asesor)
    sales_df = sales_df.copy()
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
        # Frecuencia POR CLIENTE ÚNICO (no por fila) — evita que un cliente B2B con
        # decenas de cotizaciones (Mareauto, Q2 Saloon) contamine el conteo y
        # oculte tokens verdaderamente raros.
        for _ck, _toks in ck_name_tokens.items():
            for t in _toks:
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


def compute_conversion_metrics(bd_dir, sales_df_path=None, sales_df=None, marca_filter=None):
    """Calcula métricas de conversión global y por dimensión.

    sales_df: si se pasa un DataFrame ya cargado (con columnas IDENTIFICACION,
              ASESOR_FACTURACION, AGENCIA_FACTURACION, familia, marca,
              fecha de facturacion, CLIENTE_FACTURACION, Chasis, etc.),
              se usa directamente. Esto es lo que hace aggregate.py cuando
              pasa el archivo de ventas netas (ventas.load_ventas()).
    sales_df_path: legacy — path al archivo de inventario DATOS (modo viejo).

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

    # Cargar facturas. Modo nuevo (sales_df pasado) o legacy (sales_df_path).
    # ► VENTAS NETAS: incluimos FACTURA y NOTA DE CREDITO. Cada fila trae 'Cantidad'
    # con signo (+1 FACTURA, -1 NC). Los conteos posteriores usan sum(Cantidad).
    if sales_df is not None:
        facturas = sales_df.copy()
        facturas['fecha_fact'] = pd.to_datetime(facturas['fecha de facturacion'], errors='coerce')
        facturas['marca_up'] = facturas['marca'].astype(str).str.strip().str.upper()
        if 'Cantidad' not in facturas.columns:
            facturas['Cantidad'] = 1
        facturas['Cantidad'] = facturas['Cantidad'].fillna(1).astype(int)
    else:
        # Modo legacy: leer del inventario DATOS (sin NC explícitas, todo cuenta como +1)
        inv = pd.read_excel(sales_df_path, sheet_name='DATOS', header=0)
        inv['STATUS_H'] = inv['STATUS HOMOLOGADO'].astype(str).str.strip().str.upper()
        facturas = inv[inv['STATUS_H'] == 'FACTURADO'].copy()
        facturas['fecha_fact'] = pd.to_datetime(facturas['fecha de facturacion'], errors='coerce')
        facturas['marca_up'] = facturas['marca'].astype(str).str.strip().str.upper()
        facturas['Cantidad'] = 1
    if marca_filter:
        facturas = facturas[facturas['marca_up'] == marca_filter.upper()]
    # Filtrar a período donde tenemos BDs
    facturas_all_count = int(len(facturas))
    if period_start is not None:
        facturas = facturas[facturas['fecha_fact'] >= period_start]
    facturas_in_period = int(len(facturas))
    # ► COPIA de facturas SIN filtro de jefes — se usa SOLO para el conteo
    # agencia_breakdown.ventas (Daniel: ventas de jefes SÍ deben aparecer en las cifras
    # de venta, pero NO en tráfico ni tasa de conversión).
    facturas_full = facturas.copy()

    result = cross_traffic_sales(traffic, facturas)
    traffic_df = result['traffic_df']
    matched_sales = result['matched_sales']
    first_touch = result['first_touch_by_ck']
    # FILTRO 2026: sólo cohortes cuyo primer toque fue en 2026. Clientes pre-2026 que
    # facturaron en 2026 NO se cuentan aquí (Daniel: "Solo estamos evaluando 2026").
    # Las ventas 2026 de esos clientes se reflejan en Ventas Históricas, no en Conversión.
    first_touch = {ck: ft for ck, ft in first_touch.items()
                   if pd.notna(ft.get('first_fecha')) and ft['first_fecha'].year >= 2026}
    # Asignar zona a cada first_touch — primero normalizar el sufijo de marca de la agencia.
    import re as _re_agz
    def _strip_brand_suffix_agz(a):
        if not a: return a
        m = _re_agz.match(r'^(.+?)\s*\([A-Za-z]+\)\s*$', a)
        return m.group(1).strip() if m else a
    for ck, ft in first_touch.items():
        ag_raw = ft.get('first_agencia')
        ag = _strip_brand_suffix_agz(ag_raw)
        # Reescribimos también first_agencia para que las breakdowns posteriores
        # (agencia_breakdown, agencia_mkt) usen el nombre limpio.
        ft['first_agencia'] = ag if ag else ag_raw
        ft['first_zona'] = agencia_to_zona(ag) if ag in FORD_AGENCIES else 'Otra'

    # Total clientes únicos en tráfico (después de dedupe por client_key)
    n_clientes_traffic = traffic_df['client_key'].nunique()
    n_clientes_matched = matched_sales['matched_ck'].nunique()
    conv_rate = (100 * n_clientes_matched / n_clientes_traffic) if n_clientes_traffic else 0
    # Cobertura inversa: % de VENTAS NETAS atribuidas a tráfico.
    # n_facturas_* ahora son NETOS (sum Cantidad con signo FACTURA-NC), no conteo de filas.
    sales_df_after = result['sales_df']
    if 'Cantidad' not in sales_df_after.columns:
        sales_df_after['Cantidad'] = 1
    sales_df_after['Cantidad'] = sales_df_after['Cantidad'].fillna(1).astype(int)
    n_facturas_total = int(sales_df_after['Cantidad'].sum())
    n_facturas_atribuidas = int(sales_df_after.loc[sales_df_after['matched_ck'].notna(), 'Cantidad'].sum())
    n_facturas_sin_atribuir = n_facturas_total - n_facturas_atribuidas
    cov_rate = (100 * n_facturas_atribuidas / n_facturas_total) if n_facturas_total else 0
    # Cobertura por cliente único: sólo clientes con NETO > 0.
    _net_by_ced = sales_df_after.groupby('ced_base')['Cantidad'].sum()
    n_clientes_unicos_total = int((_net_by_ced > 0).sum())
    _net_by_ced_matched = sales_df_after[sales_df_after['matched_ck'].notna()].groupby('ced_base')['Cantidad'].sum()
    n_clientes_unicos_matched = int((_net_by_ced_matched > 0).sum())

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

    # ► Set de client_keys cuya cohorte es real (sí tienen facturas posteriores
    # al primer toque). Igual al filtro que aplicamos abajo en clientes_flat.
    # Antes contábamos matched a NIVEL de fila de factura sin filtrar fecha,
    # inflando el conteo con facturas anteriores al touch (típico B2B).
    valid_ck_to_n_ventas = {}
    if 'Cantidad' not in matched_sales.columns:
        matched_sales['Cantidad'] = 1
    matched_sales['Cantidad'] = matched_sales['Cantidad'].fillna(1).astype(int)
    for ck, ft in first_touch.items():
        first_t = ft.get('first_fecha')
        if pd.isna(first_t):
            continue
        # Buscar facturas+NC posteriores al touch para este ck. NETO = sum(Cantidad).
        if ck in matched_sales['matched_ck'].values:
            sub = matched_sales[
                (matched_sales['matched_ck'] == ck)
                & matched_sales['fecha_fact'].notna()
                & (matched_sales['fecha_fact'] >= first_t)
            ]
            if len(sub):
                neto = int(sub['Cantidad'].sum())
                if neto > 0:
                    valid_ck_to_n_ventas[ck] = neto

    def _build_breakdown(get_key):
        bd = {}
        for ck, ft in first_touch.items():
            k = get_key(ft)
            bd.setdefault(k, {'traffic': 0, 'matched': 0, 'ventas': 0})
            bd[k]['traffic'] += 1
            if ck in valid_ck_to_n_ventas:
                bd[k]['matched'] += 1
                bd[k]['ventas'] += valid_ck_to_n_ventas[ck]
        for k in bd:
            d = bd[k]
            d['conv_pct'] = round(100*d['matched']/d['traffic'], 1) if d['traffic'] else 0
        return bd

    canal_breakdown   = _build_breakdown(lambda ft: ft.get('first_canal') or 'Sin canal')
    modelo_breakdown  = _build_breakdown(lambda ft: (ft.get('first_modelo') or 'Por definir').upper().strip())
    agencia_breakdown = _build_breakdown(lambda ft: ft.get('first_agencia') or 'Sin agencia')

    # Top asesores (mismo patrón cohort-aware)
    asesor_breakdown = _build_breakdown(lambda ft: ft.get('first_asesor') or 'Sin asesor')

    # Quedarnos con asesores que tienen al menos 5 leads (filtrar ruido)
    # Ventas por asesor desde facturas (ASESOR_FACTURACION). Semántica única:
    # ventas = facturas emitidas. Aplica a TODOS los asesores (jefes y regulares).
    jefes_por_agencia = {}                 # legacy — solo jefes
    facturas_por_asesor_agencia = {}       # NUEVO — todos los asesores {asesor: {ag: ventas}}
    from inventario import fact_agency_norm as _fact_ag_norm_local
    _AG_MAP_LOCAL = {'CJA':'CJA','Orellana':'Orellana','La Y':'La Y','Tumbaco':'Tumbaco','Manta':'Manta','Portoviejo':'Portoviejo','Machala':'Machala'}
    def _ag_short_local(raw):
        n = _fact_ag_norm_local(raw) if raw else None
        return _AG_MAP_LOCAL.get(n, n)
    _home_equipo = {}
    if len(facturas):
        _fa = facturas.copy()
        _fa['_ase_norm'] = _fa['ASESOR_FACTURACION'].apply(lambda s: norm_asesor(s) if pd.notna(s) else None)
        _fa['_ag_short'] = _fa['AGENCIA_FACTURACION'].apply(_ag_short_local)
        _fa['Cantidad'] = _fa.get('Cantidad', 1).fillna(0).astype(int)
        # ► Regla de equipo (Daniel, 4-ago-2026): la venta cuenta para la agencia
        # del EQUIPO del asesor, no la vitrina que emitió la factura (efecto placa
        # "P": ventas de Machala/Manta se entregan vía La Y/Tumbaco). Casa del
        # asesor = agencia donde más factura en positivo. Se calcula una vez y se
        # reutiliza en todos los breakdowns de facturas de esta pestaña.
        _pos_eq = _fa[(_fa['Cantidad'] > 0) & _fa['_ase_norm'].notna() & _fa['_ag_short'].notna()]
        _home_equipo = (_pos_eq.groupby(['_ase_norm', '_ag_short'])['Cantidad'].sum()
                        .reset_index().sort_values('Cantidad', ascending=False)
                        .drop_duplicates('_ase_norm').set_index('_ase_norm')['_ag_short'].to_dict())
        _fa['_ag_short'] = _fa.apply(
            lambda r: _home_equipo.get(r['_ase_norm'], r['_ag_short']), axis=1)
        for ase_s, grp in _fa.groupby('_ase_norm'):
            if not ase_s: continue
            _tot = int(grp['Cantidad'].sum())
            asesor_breakdown.setdefault(ase_s, {'traffic': 0, 'matched': 0, 'ventas': 0})
            asesor_breakdown[ase_s]['ventas'] = _tot
            asesor_breakdown[ase_s]['matched'] = _tot
            _by_ag = {ag: int(g['Cantidad'].sum()) for ag, g in grp.groupby('_ag_short') if ag}
            facturas_por_asesor_agencia[ase_s] = _by_ag
            if is_jefe_venta(ase_s):
                asesor_breakdown[ase_s]['_is_jefe'] = True
                jefes_por_agencia[ase_s] = _by_ag
    # Filtro ruido: mostrar TODOS los asesores con ventas > 0 o con traffic >= 5.
    asesor_breakdown = {k: v for k, v in asesor_breakdown.items()
                        if v['traffic'] >= 5 or v.get('ventas', 0) > 0 or is_jefe_venta(k)}

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
    # Usamos valid_ck_to_n_ventas (cohort-aware) en lugar de matched_cks_set crudo
    for ck, ft in first_touch.items():
        canal = ft.get('first_canal') or 'Sin canal'
        if canal not in MKT_CHANNELS:
            continue
        modelo = (ft.get('first_modelo') or 'Por definir').upper().strip()
        ag = ft.get('first_agencia') or 'Sin agencia'
        n_v = valid_ck_to_n_ventas.get(ck, 0)
        cerro = n_v > 0
        for bd, key in [(modelo_mkt, modelo), (agencia_mkt, ag), (canal_mkt, canal)]:
            bd.setdefault(key, {'traffic': 0, 'matched': 0, 'ventas': 0})
            bd[key]['traffic'] += 1
            if cerro:
                bd[key]['matched'] += 1
                bd[key]['ventas'] += n_v
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
    import re as _re
    def _strip_brand_suffix(a):
        if not a: return a
        m = _re.match(r'^(.+?)\s*\([A-Za-z]+\)\s*$', a)
        return m.group(1).strip() if m else a
    # Mapeo AGENCIA_FACTURACION (formato "1016 VEHICULOS LA Y") → nombre corto ("La Y")
    from inventario import fact_agency_norm as _fact_ag_norm
    _AG_FACT_MAP = {
        'CJA':'CJA','Orellana':'Orellana','La Y':'La Y','Tumbaco':'Tumbaco',
        'Manta':'Manta','Portoviejo':'Portoviejo','Machala':'Machala',
    }
    def _ag_fact_short(raw):
        n = _fact_ag_norm(raw) if raw else None
        return _AG_FACT_MAP.get(n, n)

    # Pre-agregar facturas por client_key (para poder emitir 1 entry por factura
    # cuando el cliente facturó en agencia distinta a su primer toque — típico
    # multi-agencia B2B como Mareauto).
    sales_by_ck_agmes = {}
    for _, r in matched_sales.iterrows():
        ck_r = r.get('matched_ck')
        if pd.isna(r.get('fecha_fact')) or not ck_r: continue
        ag_f = _ag_fact_short(r.get('AGENCIA_FACTURACION'))
        ym_f = r['fecha_fact'].strftime('%Y-%m')
        qty  = int(r.get('Cantidad', 1) or 1)
        sales_by_ck_agmes.setdefault(ck_r, []).append({'ag':ag_f,'ym':ym_f,'qty':qty,'fecha':r['fecha_fact']})

    for ck, ft in first_touch.items():
        ag_raw = ft.get('first_agencia')
        ag = _strip_brand_suffix(ag_raw)
        # Filtrar solo cuando NO hay marca_filter (modo legacy Ford-only).
        # Con marca_filter activo confiamos en que traffic ya está filtrado por marca,
        # así que las agencias 'La Y', 'Machala', etc. son legítimas de esa marca.
        if not marca_filter and ag and ag not in FORD_AGENCIES and ag != 'Gestión Externa':
            continue
        cerro = ck in matched_ck_set
        n_ventas = 0
        ciclo_d = None
        if cerro:
            # ► VENTAS NETAS por cliente: sumar Cantidad de filas matched (con signo).
            # Si NC > FACTURA, neto ≤ 0 → no es conversión real (cerro=False).
            first_t = ft.get('first_fecha')
            if pd.notna(first_t):
                sub_ck = matched_sales[
                    (matched_sales['matched_ck'] == ck)
                    & matched_sales['fecha_fact'].notna()
                    & (matched_sales['fecha_fact'] >= first_t)
                ]
                if len(sub_ck):
                    n_ventas = int(sub_ck['Cantidad'].sum())
                    if n_ventas <= 0:
                        cerro = False
                    else:
                        # Para el ciclo usamos la primera FACTURA posterior al toque
                        # (las NC no inician el ciclo de venta).
                        fechas_fact_pos = sub_ck[sub_ck['Cantidad'] > 0]['fecha_fact']
                        if len(fechas_fact_pos):
                            primera_fact = fechas_fact_pos.min()
                            d = (primera_fact - first_t).days
                            if 0 <= d <= 730:
                                ciclo_d = int(d)
                else:
                    cerro = False
            else:
                # Sin fecha de toque (raro), neto sobre todo lo matched.
                sub_ck = matched_sales[matched_sales['matched_ck'] == ck]
                n_ventas = int(sub_ck['Cantidad'].sum()) if len(sub_ck) else 0
                if n_ventas <= 0: cerro = False
        # n_toques: cuántos meses distintos vino el cliente. Para B2B sintéticos sin
        # tráfico, asumimos 1 (la "venta" cuenta como un toque atendido).
        n_toques = int(toques_mensuales.get(ck, 1)) if str(ck).startswith('r') else 1
        first_ym = ft['first_fecha'].strftime('%Y-%m') if pd.notna(ft.get('first_fecha')) else None
        # ► REGLA MULTI-AGENCIA (Daniel): cuando un cliente facturó en agencias distintas
        # a la de su primer toque (típico B2B/flotas como Mareauto), atribuir cada venta
        # a la AGENCIA + MES de facturación, no al cohorte de primer toque. Cada factura
        # se emite como una entry independiente en clientes_flat.
        _facts_all = sales_by_ck_agmes.get(ck, []) if cerro else []
        # Fix #1 auditoría: filtrar facturas anteriores al primer toque (imposibles causalmente).
        _first_t = ft.get('first_fecha')
        _facts = [f for f in _facts_all
                  if pd.notna(f.get('fecha')) and (pd.isna(_first_t) or f['fecha'] >= _first_t)]
        _ags_facturadas = {f['ag'] for f in _facts if f.get('ag')}
        # Fix #2: cliente que facturó en MISMA agencia varias veces se agrupa;
        # solo se split por-factura si son agencias DISTINTAS entre sí (>1 única).
        _multi_ag = cerro and len(_ags_facturadas) > 1
        if _multi_ag:
            # Cliente facturó en >1 agencias — emitir una entry por factura con agencia+mes de facturación.
            for f in _facts:
                if not f.get('ag'): continue
                _ase = ft.get('first_asesor') or 'Sin asesor'
                clientes_flat.append({
                    '_ck':      str(ck),
                    'canal':    ft.get('first_canal'),
                    'modelo':   (ft.get('first_modelo') or '').upper().strip() or 'Por definir',
                    'agencia':  f['ag'],
                    'zona':     ft.get('first_zona') or 'Otra',
                    'asesor':   _ase,
                    'first_ym': f['ym'],
                    'cerro':    True,
                    'n_ventas': f['qty'],
                    'n_toques': n_toques,
                    'ciclo_dias': ciclo_d,
                    '_is_jefe': is_jefe_venta(_ase),
                })
        else:
            # Cliente facturó en 1 sola agencia (o no facturó). Si facturó, usar la agencia
            # de facturación (no first_touch) — resuelve caso "primer toque otra agencia,
            # cerró en X" para que la venta cuente en X.
            _ag_final = ag or 'Sin agencia'
            _ym_final = first_ym
            _n_ventas_final = n_ventas
            if cerro and _facts:
                _the_ag = next(iter(_ags_facturadas), None)
                if _the_ag:
                    _ag_final = _the_ag
                _n_ventas_final = sum(f.get('qty', 0) for f in _facts)
                _min_fecha = min((f['fecha'] for f in _facts if pd.notna(f.get('fecha'))), default=None)
                if _min_fecha is not None:
                    _ym_final = _min_fecha.strftime('%Y-%m')
            _ase = ft.get('first_asesor') or 'Sin asesor'
            clientes_flat.append({
                '_ck':      str(ck),
                'canal':    ft.get('first_canal'),
                'modelo':   (ft.get('first_modelo') or '').upper().strip() or 'Por definir',
                'agencia':  _ag_final,
                'zona':     ft.get('first_zona') or 'Otra',
                'asesor':   _ase,
                'first_ym': _ym_final,
                'cerro':    bool(cerro),
                'n_ventas': _n_ventas_final,
                'n_toques': n_toques,
                'ciclo_dias': ciclo_d,
                '_is_jefe': is_jefe_venta(_ase),
            })

    n_clients_2026 = len(clientes_flat)
    n_clients_2026_cerro = sum(1 for c in clientes_flat if c['cerro'])
    conv_2026 = round(100 * n_clients_2026_cerro / n_clients_2026, 1) if n_clients_2026 else 0

    # Recomputar agencia_breakdown desde clientes_flat (traffic + matched cohorte 2026).
    # DEDUP por _ck para que un cliente multi-agencia cuente 1 sola vez en traffic/matched.
    # INCLUIR jefes: los clientes atendidos por jefes también llegaron por algún canal.
    # (Solo el ranking de asesores separa jefes vs regulares.)
    agencia_breakdown = {}
    _seen_traffic = {}
    _seen_matched = {}
    for c in clientes_flat:
        k = c['agencia']
        agencia_breakdown.setdefault(k, {'traffic': 0, 'matched': 0, 'ventas': 0})
        _key_t = (k, c.get('_ck'))
        if _key_t not in _seen_traffic:
            _seen_traffic[_key_t] = True
            agencia_breakdown[k]['traffic'] += 1
        if c.get('cerro'):
            _key_m = (k, c.get('_ck'))
            if _key_m not in _seen_matched:
                _seen_matched[_key_m] = True
                agencia_breakdown[k]['matched'] += 1
    # Ventas totales por agencia = TODAS las facturas del período (ya filtradas por marca
    # arriba en `facturas`), atribuidas a AGENCIA_FACTURACION independiente de cohorte.
    # Alinea con Ventas Históricas: incluye clientes cohorte pre-2026 que facturaron
    # en 2026 + ventas B2B sin cotización previa en Kombat.
    if len(facturas_full):
        _fact_copy = facturas_full.copy()
        _fact_copy['_ag_short'] = _fact_copy['AGENCIA_FACTURACION'].apply(_ag_fact_short)
        _fact_copy['Cantidad'] = _fact_copy.get('Cantidad', 1).fillna(0).astype(int)
        # Regla de equipo: misma casa que el resto de breakdowns.
        _fact_copy['_ase_norm'] = _fact_copy['ASESOR_FACTURACION'].apply(lambda s: norm_asesor(s) if pd.notna(s) else None)
        _fact_copy['_ag_short'] = _fact_copy.apply(
            lambda r: _home_equipo.get(r['_ase_norm'], r['_ag_short']), axis=1)
        for ag_s, grp in _fact_copy.groupby('_ag_short'):
            if not ag_s: continue
            agencia_breakdown.setdefault(ag_s, {'traffic': 0, 'matched': 0, 'ventas': 0})
            agencia_breakdown[ag_s]['ventas'] = int(grp['Cantidad'].sum())
            # Personas únicas que facturaron en esta agencia (compradores reales).
            # Dedup por IDENTIFICACION si existe válida, sino por CLIENTE_FACTURACION.
            _key_cli = grp['IDENTIFICACION'].apply(
                lambda x: str(x).strip() if pd.notna(x) and str(x).strip() not in ('0','0.0','','nan') else None
            )
            _cli_fallback = grp['CLIENTE_FACTURACION'].apply(
                lambda x: str(x).strip().upper() if pd.notna(x) else None
            )
            _keys = _key_cli.fillna(_cli_fallback).dropna().unique()
            agencia_breakdown[ag_s]['personas_reales'] = int(len(_keys))
    for k in agencia_breakdown:
        d = agencia_breakdown[k]
        d['conv_pct'] = round(100 * d['matched'] / d['traffic'], 1) if d['traffic'] else 0
    # ► Vehículos atribuidos: suma cohort-aware (solo facturas ≥ first_fecha)
    # Antes usábamos n_facturas_atribuidas (count crudo de matched_sales) que
    # incluía facturas anteriores al primer toque — inconsistente con clientes_flat.
    n_vehiculos_atribuidos = sum(c['n_ventas'] for c in clientes_flat if c['cerro'])

    # ═══════════════════════════════════════════════════════════════════════════
    # LISTA MAESTRA DE FACTURAS — fuente única de verdad para TODOS los widgets
    # de conversión. Cada widget deriva de esta lista aplicando group_by distintos.
    # Garantiza que suma de cualquier breakdown = total de facturas.
    # ═══════════════════════════════════════════════════════════════════════════
    master_facturas = []
    # Normalizador de familia → modelo corto (TERRITORY, F-150...). Import perezoso
    # para evitar ciclos. Fallback: primera palabra de la familia.
    try:
        from inventario import normalize_familia as _norm_fam_inv
        def _norm_fam_master(familia, marca):
            try:
                out = _norm_fam_inv(familia, marca or '')
                if out: return str(out).upper()
            except Exception: pass
            return (str(familia).split()[0].upper() if familia else 'Por definir')
    except Exception:
        def _norm_fam_master(familia, marca):
            return (str(familia).split()[0].upper() if familia else 'Por definir')
    if len(facturas_full):
        _mf = facturas_full.copy()
        _mf['_ag_short'] = _mf['AGENCIA_FACTURACION'].apply(_ag_fact_short)
        _mf['_qty'] = _mf.get('Cantidad', 1).fillna(0).astype(int)
        _mf['_ase_norm'] = _mf['ASESOR_FACTURACION'].apply(lambda s: norm_asesor(s) if pd.notna(s) else None)
        # Regla de equipo: la agencia del master es la casa del asesor; la
        # vitrina se preserva en agencia_fact para poder auditar el puente.
        _mf['_ag_vitrina'] = _mf['_ag_short']
        _mf['_ag_short'] = _mf.apply(
            lambda r: _home_equipo.get(r['_ase_norm'], r['_ag_short']), axis=1)
        # persona_id CONSOLIDADO: si el mismo nombre de cliente aparece con cédula en
        # alguna factura, TODAS sus facturas usan esa cédula como pid (caso Nathaly
        # Carrion: 2 autos, una factura con cédula y otra con nombre → 1 persona).
        def _ced_of(r):
            i = r.get('IDENTIFICACION')
            if pd.notna(i):
                s = str(i).replace('.0','').strip()
                if s and s not in ('0','nan'): return s
            return None
        def _nom_of(r):
            n = r.get('CLIENTE_FACTURACION')
            return str(n).strip().upper() if pd.notna(n) else None
        _nombre_a_ced = {}
        for _, r in _mf.iterrows():
            ced, nom = _ced_of(r), _nom_of(r)
            if ced and nom and nom not in _nombre_a_ced:
                _nombre_a_ced[nom] = ced
        def _pid_mf(r):
            ced, nom = _ced_of(r), _nom_of(r)
            if ced: return ced
            if nom: return _nombre_a_ced.get(nom, nom)
            return None
        _mf['_pid'] = _mf.apply(_pid_mf, axis=1)
        # Cross-reference con matched_sales para obtener cohorte (canal/modelo/asesor de tráfico)
        _mch_map = {}  # (VIN, fecha_iso) → (client_key, first_ym, first_canal, first_modelo, first_agencia, first_asesor)
        for _, r in matched_sales.iterrows():
            _v = str(r.get('Chasis','')).upper().strip()
            _fd = r.get('fecha_fact')
            if not _v or pd.isna(_fd): continue
            _ck = r.get('matched_ck')
            _ft = first_touch.get(_ck, {}) if _ck else {}
            _mch_map[(_v, _fd.strftime('%Y-%m-%d'))] = {
                'ck': _ck,
                'first_ym': _ft.get('first_fecha').strftime('%Y-%m') if pd.notna(_ft.get('first_fecha')) else None,
                'first_canal': _ft.get('first_canal'),
                'first_modelo': (_ft.get('first_modelo') or '').upper().strip() or 'Por definir',
                'first_agencia': _ft.get('first_agencia'),
                'first_asesor': _ft.get('first_asesor'),
                'first_zona': _ft.get('first_zona'),
            }
        # Emit lista maestra
        for _, r in _mf.iterrows():
            _v = str(r.get('Chasis','')).upper().strip()
            _fd = r.get('fecha_fact')
            _fd_key = _fd.strftime('%Y-%m-%d') if pd.notna(_fd) else None
            _match = _mch_map.get((_v, _fd_key), {})
            _es_cohorte_2026 = bool(_match) and (_match.get('first_ym','') or '').startswith('2026')
            master_facturas.append({
                'vin': _v,
                'fecha': _fd_key,
                'agencia': r.get('_ag_short') or 'Sin agencia',
                'agencia_fact': r.get('_ag_vitrina') or 'Sin agencia',
                'qty': int(r.get('_qty', 0)),
                'persona_id': r.get('_pid'),
                'cliente': str(r.get('CLIENTE_FACTURACION','')).strip() if pd.notna(r.get('CLIENTE_FACTURACION')) else None,
                'asesor_fact': r.get('_ase_norm') or 'Sin asesor',
                'is_jefe_fact': bool(is_jefe_venta(r.get('_ase_norm'))),
                # Modelo SIEMPRE atribuido: familia normalizada del vehículo facturado
                # (el modelo vendido siempre se conoce — nunca "Sin modelo").
                'modelo_fact': _norm_fam_master(str(r.get('familia','')).strip(), r.get('marca_up')),
                # atribución tráfico si el lead está matched cohorte 2026
                'cohorte_ym': _match.get('first_ym'),
                # Canal SIEMPRE atribuido. Con lead → su canal real. Sin lead →
                # si el nombre es de renting o empresa, canal propio Flota/B2B;
                # el resto queda en "Gestión Externa" (referidos, recompra directa).
                'canal_lead': ((_match.get('first_canal') if _es_cohorte_2026 else None)
                               or tipo_cliente_venta(r.get('CLIENTE_FACTURACION'))
                               or 'Gestión Externa'),
                'tipo_cliente': tipo_cliente_venta(r.get('CLIENTE_FACTURACION')) or 'Persona natural',
                'modelo_lead': _match.get('first_modelo') if _es_cohorte_2026 else None,
                'agencia_lead': _match.get('first_agencia') if _es_cohorte_2026 else None,
                'asesor_lead': _match.get('first_asesor') if _es_cohorte_2026 else None,
                'zona_lead': _match.get('first_zona') if _es_cohorte_2026 else None,
                'ck_lead': _match.get('ck') if _es_cohorte_2026 else None,
                'es_cohorte_2026': _es_cohorte_2026,
            })

    # Breakdowns derivados desde master_facturas — cada uno GARANTIZA que su suma = total
    def _build_from_master(get_key, master):
        """Group by get_key; ventas = sum qty con signo (neto real).
        personas = COMPRADORES: pid con al menos un (pid, VIN) de neto > 0.
        - NC de compra vieja + compra nueva del mismo cliente → sigue siendo comprador
          (caso Vallejo: neto global 0 pero su VIN nuevo es +1).
        - VIN devuelto por A y revendido a B → ambos eventos reales: B comprador,
          A no (su (pid,vin) queda ≤0)."""
        bucket = {}
        for m in master:
            qty = m.get('qty', 0)
            if qty == 0: continue
            k = get_key(m) or 'Sin categoría'
            b = bucket.setdefault(k, {'pv_qty': {}, 'ventas': 0})
            b['ventas'] += qty
            pid = m.get('persona_id')
            if pid:
                pv = (pid, m.get('vin'))
                b['pv_qty'][pv] = b['pv_qty'].get(pv, 0) + qty
        out = {}
        for k, v in bucket.items():
            compradores = {pid for (pid, vin), q in v['pv_qty'].items() if q > 0}
            out[k] = {'personas': len(compradores), 'ventas': v['ventas']}
        return out

    # ► Métricas globales recalculadas desde master (netean NC y nunca superan el total).
    # Antes n_vehiculos_atribuidos venía de clientes_flat sin netear → Chery daba
    # cov_rate 103% y "sin atribuir" negativo (bug 29-jul).
    n_facturas_total_master = sum(m.get('qty', 0) for m in master_facturas)
    # Ventas de flota/B2B SIN lead: las que nunca podían cruzar contra tráfico.
    # (Si una empresa sí pasó por el embudo, conserva su canal y NO cuenta aquí.)
    _n_flota = sum(m.get('qty', 0) for m in master_facturas if m.get('canal_lead') == 'Flota/Renting')
    _n_b2b   = sum(m.get('qty', 0) for m in master_facturas if m.get('canal_lead') == 'B2B')
    n_vehiculos_atribuidos = sum(m.get('qty', 0) for m in master_facturas if m.get('es_cohorte_2026'))
    _pv_all, _pv_coh = {}, {}
    for m in master_facturas:
        pid, q = m.get('persona_id'), m.get('qty', 0)
        if not pid or q == 0: continue
        key = (pid, m.get('vin'))
        _pv_all[key] = _pv_all.get(key, 0) + q
        if m.get('es_cohorte_2026'):
            _pv_coh[key] = _pv_coh.get(key, 0) + q
    n_clientes_unicos_total = len({pid for (pid, _v), q in _pv_all.items() if q > 0})
    n_clientes_unicos_matched = len({pid for (pid, _v), q in _pv_coh.items() if q > 0})

    master_por_agencia = _build_from_master(lambda m: m['agencia'], master_facturas)
    master_por_canal   = _build_from_master(lambda m: m.get('canal_lead') or 'Sin canal atribuido', master_facturas)
    master_por_modelo  = _build_from_master(lambda m: m.get('modelo_lead') or (m.get('modelo_fact') or 'Sin modelo'), master_facturas)
    master_por_asesor  = _build_from_master(lambda m: m.get('asesor_fact') or 'Sin asesor', master_facturas)
    # (Asesor por agencia — para top asesores filtrado por agencia)
    master_por_asesor_agencia = {}
    for m in master_facturas:
        if not m.get('qty') or m['qty'] <= 0: continue
        ase = m.get('asesor_fact') or 'Sin asesor'
        ag = m.get('agencia') or 'Sin agencia'
        d = master_por_asesor_agencia.setdefault(ase, {}).setdefault(ag, {'personas': set(), 'ventas': 0})
        if m.get('persona_id'): d['personas'].add(m['persona_id'])
        d['ventas'] += m['qty']
    for ase, ags in master_por_asesor_agencia.items():
        for ag, v in ags.items():
            v['personas'] = len(v['personas'])
    # HOME AGENCY por asesor: agencia donde el asesor tiene MÁS tráfico cohorte 2026.
    # Sirve para que el ranking por agencia solo muestre asesores DE ese PDV
    # (ej. Carlos Moncayo y Venus Monge son de Tumbaco aunque tengan leads La Y).
    _asesor_ag_count = {}
    for ck, ft in first_touch.items():
        ase = ft.get('first_asesor')
        ag = ft.get('first_agencia')
        if not ase or not ag: continue
        _asesor_ag_count.setdefault(ase, {}).setdefault(ag, 0)
        _asesor_ag_count[ase][ag] += 1
    asesor_home_agencia = {ase: max(ags.items(), key=lambda kv: kv[1])[0]
                           for ase, ags in _asesor_ag_count.items()}

    # Traffic (para tasa conversión) — clientes cohorte 2026 en tráfico (ya lo tenemos: n_clients_2026)
    # Ese denominador aplica global. Para por-agencia, personas cohorte 2026 con primer toque en cada agencia.
    master_traffic_por_agencia = {}
    for ck, ft in first_touch.items():
        ag = ft.get('first_agencia')
        if not ag: continue
        master_traffic_por_agencia[ag] = master_traffic_por_agencia.get(ag, 0) + 1
    # Combinar traffic + ventas en un breakdown final
    for ag in set(list(master_por_agencia.keys()) + list(master_traffic_por_agencia.keys())):
        master_por_agencia.setdefault(ag, {'personas': 0, 'ventas': 0})
        master_por_agencia[ag]['traffic'] = master_traffic_por_agencia.get(ag, 0)
        t = master_por_agencia[ag]['traffic']
        p = master_por_agencia[ag]['personas']
        master_por_agencia[ag]['conv_pct'] = round(100*p/t, 1) if t > 0 else 0

    return {
        'global': {
            'periodo_inicio': period_start.strftime('%Y-%m-%d') if period_start is not None else None,
            'n_clientes_traffic': n_clients_2026,
            'n_clientes_matched': n_clients_2026_cerro,
            'conv_rate_pct': conv_2026,
            # Todo desde master_facturas: vehículos netos (FACT−NC), nunca >100%.
            'n_facturas_total': n_facturas_total_master,
            'n_facturas_atribuidas': n_vehiculos_atribuidos,
            'n_facturas_sin_atribuir': n_facturas_total_master - n_vehiculos_atribuidos,
            'cov_rate_pct': round(100*n_vehiculos_atribuidos/n_facturas_total_master, 1) if n_facturas_total_master else 0,
            # Flota/renting y B2B directo no pasan por tráfico de piso: nunca van a
            # tener lead. Se reportan aparte y la cobertura "real" los descuenta del
            # denominador — si no, el panel se castiga por ventas que jamás iban a cruzar.
            'n_ventas_flota': _n_flota,
            'n_ventas_b2b': _n_b2b,
            'cov_rate_sin_flota_pct': (round(100*n_vehiculos_atribuidos/(n_facturas_total_master - _n_flota - _n_b2b), 1)
                                       if (n_facturas_total_master - _n_flota - _n_b2b) > 0 else 0),
            'n_clientes_unicos_total': n_clientes_unicos_total,
            'n_clientes_unicos_matched': n_clientes_unicos_matched,
            # OJO unidades: *_vehiculos_* son unidades; *_clientes_* son personas.
            'n_vehiculos_total': n_facturas_total_master,
            'n_vehiculos_atribuidos': n_vehiculos_atribuidos,
            'n_ventas_clientes_total': n_clientes_unicos_total,
            'n_ventas_atribuidas': n_vehiculos_atribuidos,
            'n_facturas_en_periodo': facturas_in_period,
            'n_facturas_total_historico': facturas_all_count,
            'ciclo': ciclo,
        },
        'clientes_flat': clientes_flat,
        'por_canal':   canal_breakdown,
        'por_modelo':  modelo_breakdown,
        'por_agencia': agencia_breakdown,
        'por_asesor':  asesor_breakdown,
        'jefes_por_agencia': jefes_por_agencia,
        'facturas_por_asesor_agencia': facturas_por_asesor_agencia,
        'asesor_home_agencia': asesor_home_agencia,
        # ► FUENTE ÚNICA DE VERDAD para widgets de conversión (fase 2 refactor):
        'master_facturas': master_facturas,
        'master_por_agencia': master_por_agencia,
        'master_por_canal': master_por_canal,
        'master_por_modelo': master_por_modelo,
        'master_por_asesor': master_por_asesor,
        'master_por_asesor_agencia': master_por_asesor_agencia,
        # Breakdown filtrado SOLO por canales atribuibles a marketing
        # (Showroom + Hubspot + Ferias + Llamada In + Mailing)
        'por_modelo_mkt':   modelo_mkt,
        'por_agencia_mkt':  agencia_mkt,
        'por_canal_mkt':    canal_mkt,
        'mkt_channels':     sorted(MKT_CHANNELS),
    }
