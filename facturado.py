#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FACTURADO de Finanzas: fuente PARALELA de ventas, enriquecida. No reemplaza a nadie.

Daniel entregó el 09-sep-2026 dos bases nuevas:

  * `FACTURADO MARZ 2024 A SEP 2026.xlsx` (hoja `Sheet`): una línea por documento
    (factura o nota de crédito) por VIN, desde feb-2024. Trae lo que el panel no
    tenía: INST. FINANCIERA + TERCERO (venta a crédito y con quién), Porcentaje y
    Valor Descuento, MSC (versión), Año Modelo, colores, Usuario Vende, Contacto,
    Nit Tercero al 100 % y `notas_internas` con el id de negocio de GUC.
  * `ventas_vehiculos act.xlsx`: el parque de dueños sep-2012 → feb-2024 (VIN,
    cédula, celular, email, fecha de factura y de entrega). Termina donde empieza
    FACTURADO.

## Lo que FACTURADO NO trae (medido 09-sep-2026 contra data.json y la Base de Ventas)

1. Los EXONERADOS. Cero líneas de vehículo sin MSC; la Base de Ventas tiene 15
   unidades Ford 2026 sin chasis. Por eso Ford ene–ago da 741 aquí y 757 en el
   panel (= Finanzas); DF 116 vs 119. Mazda y RAM cuadran exacto.
2. La AGENCIA de facturación (efecto placa). Solo trae BODEGA. Tumbaco feb 16
   vs 13, Machala feb 3 vs 6 son ventas hechas en una agencia y facturadas por
   la bodega de otra. Aquí la agencia oficial se HEREDA de la Base por chasis.

Por las dos cosas, **la Base de Ventas sigue mandando** en `ventas_mensual` y
`conversion_data`. Este módulo escribe claves NUEVAS y no toca esas.

## Regla de conteo (la que cuadra con Finanzas)

`Cantidad` YA viene signada: Factura +1, Nota de Crédito −1. No volver a
firmarla. Unidad neta del mes = Σ Cantidad de las líneas con `Tipo Documento` de
vehículos (F?01 factura, F?02 NC; fuera MPSI mantenimiento prepagado y FV
seminuevos), SIN filtro > 0: la NC resta en su mes y en su bodega, igual que la
Base. La regla "Σ por VIN×mes > 0" pierde la NC que cae en otro mes que la
factura y cuenta el VIN dos veces: 80 casos Ford en 2026.

Misma unidad para todo lo que se derive: % crédito del mes = Σ Cantidad de
líneas a crédito ÷ Σ Cantidad total, ambas signadas; acumulados = suma de
meses. Nunca "VIN con Σ del periodo > 0".

## Firma de salida (data.json) — la escribe `build(out)`

    out['facturado_corte'] = 'aaaa-mm-dd'          # max(Fecha) del archivo
    out['facturado'] = {
      '_estado': 'esqueleto' | 'activo',            # el check falla solo en 'activo'
      '_doc': {...},
      '_cuadre': {marca: {mes: {'facturado', 'exonerados', 'solo_base', 'panel', 'dif', 'ok'}}},
      '_solo_base': [ {vin, marca, mes, agencia, modelo, cantidad} ],   # en la Base y no en FACTURADO
      '_placa': {marca: {mes: {'bodega→agencia': n}}},   # movimientos por placa
      marca: {
        'months': [...], 'totals': {mes: n},
        'by_agencia': {ag: {mes: n}},   # agencia OFICIAL heredada de la Base (fallback bodega)
        'by_bodega':  {bod: {mes: n}},
        'by_asesor':  {asesor: {mes: n}},  # asesores.canonizar lo unifica solo
        'by_modelo':  {modelo: {mes: n}},  # modelo canónico (normalize_familia)
        'credito':   {...},   # ← ANALISTA ORGU 3.0
        'descuento': {...},   # ← ANALISTA ORGU 3.0
        'flat': [ {...} ],    # solo meses del panel (2026+), una línea por documento
      }
    }
    out['recompra']   = {'_estado', '_doc', marca: {...}}   # ← ANALISTA ORGU 3.0
    out['renovacion'] = {'_estado', '_doc', 'por_modelo': {...}, 'por_plaza': {...}}  # ← idem

Los bloques marcados los llena ANALISTA ORGU 3.0 sobre esta firma (acuerdo
09-sep-2026). Cuando estén, cambiar `_estado` a 'activo' para que
`verificar.check_facturado_vs_panel` pase de aviso a invariante duro.

Ingesta: el archivo es ACUMULADO y Finanzas lo reemplaza; se toma el más reciente
por mtime entre las carpetas de Finanzas (`base_ventas._DIRS`) y el caché
`~/dev/panel-datos/facturado/`. `pauta._materializar` obliga a OneDrive a bajar
los bytes. `Fecha` se lee como datetime (un serial de Excel ya nos mandó a 1970).
"""
import re
from pathlib import Path

import pandas as pd

import base_ventas
from conversion import norm_ced, cedula_base          # sin main: importar es seguro
from inventario import fact_agency_norm, normalize_familia

LOCAL = Path.home() / 'dev' / 'panel-datos' / 'facturado'
_DIRS = list(base_ventas._DIRS) + [LOCAL]

MARCAS = ['FORD', 'DONGFENG_ORGU', 'CHERY_ORGU', 'MAZDA_ORGU', 'RAM_ORGU']
_MARCA = {'FORD': 'FORD', 'DONGFENG': 'DONGFENG_ORGU', 'DONG FENG': 'DONGFENG_ORGU',
          'CHERY': 'CHERY_ORGU', 'MAZDA': 'MAZDA_ORGU', 'RAM': 'RAM_ORGU'}
_RX_GUC = re.compile(r'negocio\s*:\s*(\d+)', re.I)
CREDITO_TXT = 'CRÉDITO FINANCIERA'        # INST. FINANCIERA = '3 - Crédito financiera'
PANEL_DESDE = '2026-01'                    # `flat` y el cuadre solo cubren los meses del panel


# ── Archivos ────────────────────────────────────────────────────────────────

def _mas_reciente(prefijo):
    cands = []
    for d in _DIRS:
        if d.exists():
            cands += [q for q in d.iterdir()
                      if q.is_file() and not q.name.startswith('~$')
                      and q.suffix.lower().startswith('.xls')
                      and q.name.lower().startswith(prefijo)]
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None


def archivo():
    """El FACTURADO más reciente, o None."""
    return _mas_reciente('facturado')


def archivo_parque():
    """El parque de dueños 2012–2024 más reciente, o None."""
    return _mas_reciente('ventas_vehiculos')


def _leer(path):
    try:
        from pauta import _materializar
        _materializar(Path(path))
    except Exception:
        pass
    return pd.read_excel(path)


# ── Normalización ───────────────────────────────────────────────────────────

def _marca(m):
    u = str(m or '').upper()
    for k, v in _MARCA.items():
        if k in u:
            return v
    return None


def _bodega(b):
    """Agencia corta de la bodega. MANTA II es Portoviejo y va ANTES que MANTA."""
    u = str(b or '').upper()
    if 'MANTA II' in u:
        return 'Portoviejo'
    return fact_agency_norm(u) or 'Sin bodega'


def _modelo(desc, marca):
    """Modelo canónico del panel: el mismo `normalize_familia` que usa aggregate."""
    corta = (marca or '').replace('_ORGU', '')
    return normalize_familia(str(desc or ''), corta) or str(desc or '').strip().upper()


def _cedula(v):
    """Cédula base (RUC natural → 10 dígitos) con la normalización de conversion.py.
    `Nit Tercero` viene como float ('925473795001.0'); norm_ced ya quita el .0."""
    return cedula_base(norm_ced(v))


def cargar(path=None):
    """FACTURADO normalizado (todas las líneas, todos los años), o None.

    Columnas: fecha · mes ('aaaa-mm') · marca (clave del panel) · bodega_raw ·
    bodega (corta) · modelo_raw · modelo (canónico) · version (MSC) · vin ·
    cantidad (signada) · es_nc · es_vehiculo · doc · tipo_doc · asesor ·
    cedula_vendedor · cedula (base) · nombre · contacto · credito (bool) ·
    financiera · pct_desc · val_desc · ventas_netas · guc_id · anio_modelo ·
    color · exonerado_tipo · _archivo.
    """
    p = Path(path) if path else archivo()
    if not p or not p.exists():
        return None
    raw = _leer(p)
    if raw is None or raw.empty:
        return None

    df = pd.DataFrame()
    df['fecha'] = pd.to_datetime(raw['Fecha'], errors='coerce')
    df['mes'] = df['fecha'].dt.strftime('%Y-%m')
    df['marca'] = raw['Marca'].map(_marca)
    df['bodega_raw'] = raw['Descripcion Bodega'].astype(str).str.strip()
    df['bodega'] = df['bodega_raw'].map(_bodega)
    df['modelo_raw'] = raw['Descripción Modelo'].astype(str).str.strip()
    df['modelo'] = [_modelo(d, m) for d, m in zip(df['modelo_raw'], df['marca'])]
    df['version'] = raw['MSC'].astype(str).str.strip().where(raw['MSC'].notna(), None)
    df['vin'] = raw['Vin'].astype(str).str.strip().str.upper().where(raw['Vin'].notna(), None)
    df['cantidad'] = pd.to_numeric(raw['Cantidad'], errors='coerce').fillna(0)
    df['es_nc'] = raw['Tipo Transacción'].astype(str).str.upper().str.contains('CR')
    td = raw['Tipo Documento'].astype(str).str.upper()
    df['tipo_doc'] = td.str.strip()
    df['es_vehiculo'] = td.str.contains('VEH') & ~td.str.contains('SEMINUEVO')
    df['doc'] = raw['Numero Factura'].astype(str).str.strip()
    df['asesor'] = raw['Usuario Vende'].astype(str).str.strip().str.upper().replace({'NAN': 'Sin asesor', '': 'Sin asesor'})
    df['cedula_vendedor'] = raw['Cedula Vendedor'].map(norm_ced)
    df['cedula'] = raw['Nit Tercero'].map(_cedula)
    df['nombre'] = raw['Nombres'].astype(str).str.strip()
    df['contacto'] = raw['Contacto'].astype(str).str.strip().where(raw['Contacto'].notna(), None)
    df['credito'] = raw['INST. FINANCIERA'].astype(str).str.upper().str.contains(CREDITO_TXT)
    df['financiera'] = raw['TERCERO'].astype(str).str.strip().where(raw['TERCERO'].notna(), None)
    df['pct_desc'] = pd.to_numeric(raw['Porcentaje Descuento'], errors='coerce').fillna(0)
    df['val_desc'] = pd.to_numeric(raw['Valor Descuento'], errors='coerce').fillna(0)
    df['ventas_netas'] = pd.to_numeric(raw['Valor Ventas Netas'], errors='coerce').fillna(0)
    df['guc_id'] = raw['notas_internas'].astype(str).str.extract(_RX_GUC.pattern, flags=re.I)[0]
    df['anio_modelo'] = pd.to_numeric(raw['Año Modelo'], errors='coerce')
    df['color'] = raw['Color Externo Vehiculo'].astype(str).str.strip().where(raw['Color Externo Vehiculo'].notna(), None)
    df['exonerado_tipo'] = raw['Tipo Exonerado'].astype(str).str.strip().where(raw['Tipo Exonerado'].notna(), None)
    df['_archivo'] = p.name
    return df


def cargar_parque(path=None):
    """Parque de dueños 2012–feb-2024 normalizado, o None. Se carga una vez.

    Columnas: vin · cedula (base) · nombre · celular · email · modelo_raw · modelo ·
    anio · fecha_factura · fecha_entrega · vendedor · bodega_raw.
    """
    p = Path(path) if path else archivo_parque()
    if not p or not p.exists():
        return None
    raw = _leer(p)
    if raw is None or raw.empty:
        return None
    cols = {c.lower().strip(): c for c in raw.columns}

    def col(*nombres):
        for n in nombres:
            if n in cols:
                return raw[cols[n]]
        return pd.Series([None] * len(raw))

    df = pd.DataFrame()
    df['vin'] = col('vin', 'chasis').astype(str).str.strip().str.upper()
    df['cedula'] = col('cedula', 'identificacion', 'nit', 'ruc').map(_cedula)
    df['nombre'] = col('nombre', 'nombres', 'cliente').astype(str).str.strip()
    df['celular'] = col('celular', 'telefono', 'contacto').astype(str).str.strip()
    df['email'] = col('email', 'correo', 'mail').astype(str).str.strip()
    df['modelo_raw'] = col('descripcion', 'descripcion_vehiculo', 'modelo', 'vehiculo').astype(str).str.strip()
    df['modelo'] = [_modelo(d, 'FORD') for d in df['modelo_raw']]
    df['anio'] = pd.to_numeric(col('anio', 'año', 'ano', 'anio_modelo', 'año modelo'), errors='coerce')
    df['fecha_factura'] = pd.to_datetime(col('fecha_factura', 'fecha factura', 'fecha'), errors='coerce')
    df['fecha_entrega'] = pd.to_datetime(col('fecha_entrega', 'fecha entrega'), errors='coerce')
    df['vendedor'] = col('vendedor', 'asesor', 'usuario_vende').astype(str).str.strip().str.upper()
    df['bodega_raw'] = col('bodega', 'agencia', 'descripcion_bodega').astype(str).str.strip()
    df['_archivo'] = p.name
    df['_columnas_origen'] = ', '.join(raw.columns)
    return df


# ── Agencia oficial y cuadre ────────────────────────────────────────────────

def heredar_agencia(df, base):
    """`agencia` oficial y `marca` por chasis desde la Base de Ventas (la Base manda).

    Si el VIN no está en la Base, quedan la bodega y la marca de FACTURADO;
    `agencia_fuente` dice cuál fue. La marca también se hereda porque el maestro
    de FACTURADO trae errores: el 09-sep-2026 una Territory híbrida de Manta
    (LJXCU2BB5THF82618) venía como marca CHERY y descripción "SEMINUEVOS FORD 2026".
    """
    df = df.copy()
    m_ag, m_mk = {}, {}
    if base is not None and len(base):
        b = base[base['chasis'].notna()]
        for ch, ag, mk in zip(b['chasis'].astype(str).str.strip().str.upper(), b['agencia'], b['marca']):
            if isinstance(ag, str) and ag:
                m_ag.setdefault(ch, ag)
            if isinstance(mk, str) and mk:
                m_mk.setdefault(ch, mk)
    df['agencia'] = df['vin'].map(m_ag)
    df['agencia_fuente'] = df['agencia'].notna().map({True: 'base', False: 'bodega'})
    df['agencia'] = df['agencia'].where(df['agencia'].notna(), df['bodega'])
    mk_base = df['vin'].map(m_mk)
    df['marca_facturado'] = df['marca']
    df['marca'] = mk_base.where(mk_base.notna(), df['marca'])
    if (df['marca'] != df['marca_facturado']).any():
        df['modelo'] = [_modelo(d, m) if m != mf else mo
                        for d, m, mf, mo in zip(df['modelo_raw'], df['marca'], df['marca_facturado'], df['modelo'])]
    return df


def _solo_base(veh, base):
    """{marca: {mes: n}} y la lista de chasis que la Base de Ventas tiene y FACTURADO
    no trae en ningún mes (el 09-sep-2026: una Mage de Machala, LDP35F90XVG504486)."""
    tot, vins = {}, []
    if base is None or not len(base):
        return tot, vins
    en_fac = set(veh['vin'].dropna())
    b = base[base['chasis'].notna() & base['marca'].notna() & base['mes'].notna()]
    b = b[~b['chasis'].astype(str).str.strip().str.upper().isin(en_fac)]
    for (mk, mes), n in b.groupby(['marca', 'mes'])['cantidad'].sum().items():
        if n:
            tot.setdefault(mk, {})[mes] = int(n)
    for _, r in b.iterrows():
        vins.append({'vin': str(r['chasis']).strip().upper(), 'marca': r['marca'], 'mes': r['mes'],
                     'agencia': r.get('agencia'), 'modelo': r.get('version') or r.get('modelo'), 'cantidad': int(r['cantidad'])})
    return tot, vins


def _exonerados(base):
    """{marca: {mes: n}} unidades de la Base SIN chasis (los exonerados que FACTURADO no trae)."""
    out = {}
    if base is None or not len(base):
        return out
    b = base[base['chasis'].isna() & base['marca'].notna() & base['mes'].notna()]
    for (m, mes), n in b.groupby(['marca', 'mes'])['cantidad'].sum().items():
        out.setdefault(m, {})[mes] = int(n)
    return out


def cuadre(veh, base, ventas_mensual, corte=None):
    """Por marca y mes del panel: facturado + exonerados vs `ventas_mensual.totals`.

    `veh` = líneas de vehículo ya normalizadas. `ok` = la diferencia es cero.
    Solo meses CERRADOS de ventas (≤ `corte`, el `ventas_corte` del panel): un mes
    cuya Base de Ventas no llegó vale 0 en el panel y no es un desajuste.
    """
    hasta = str(corte)[:7] if corte else None
    exo = _exonerados(base)
    sb, _ = _solo_base(veh, base)
    res = {}
    for mk in MARCAS:
        vm = (ventas_mensual or {}).get(mk) or {}
        tot = vm.get('totals') or {}
        if isinstance(tot, list):
            tot = dict(zip(vm.get('months', []), tot))
        s = veh[(veh['marca'] == mk) & (veh['mes'] >= PANEL_DESDE)]
        fac = s.groupby('mes')['cantidad'].sum().astype(int).to_dict()
        meses = sorted(set(fac) | {m for m in tot if str(m) >= PANEL_DESDE and not str(m).startswith('_')})
        if hasta:
            meses = [m for m in meses if m <= hasta]
        res[mk] = {}
        for m in meses:
            f, e, p = int(fac.get(m, 0)), int(exo.get(mk, {}).get(m, 0)), int(tot.get(m, 0) or 0)
            s0 = int(sb.get(mk, {}).get(m, 0))
            res[mk][m] = {'facturado': f, 'exonerados': e, 'solo_base': s0, 'panel': p,
                          'dif': f + e + s0 - p, 'ok': (f + e + s0 == p)}
    return res


def placa(veh):
    """{marca: {mes: {'bodega→agencia': n}}} — unidades cuya agencia oficial no es la bodega."""
    out = {}
    s = veh[(veh['mes'] >= PANEL_DESDE) & (veh['agencia'] != veh['bodega'])]
    for (mk, mes, b, a), n in s.groupby(['marca', 'mes', 'bodega', 'agencia'])['cantidad'].sum().items():
        if n:
            out.setdefault(mk, {}).setdefault(mes, {})[f'{b}→{a}'] = int(n)
    return out


# ── Series para el panel ────────────────────────────────────────────────────

def _serie(s, col):
    """{clave: {mes: Σ cantidad}} sin claves vacías ni meses en cero para todos."""
    out = {}
    for (k, mes), n in s.groupby([col, 'mes'])['cantidad'].sum().items():
        if k is None or (isinstance(k, float) and pd.isna(k)):
            k = 'Sin dato'
        out.setdefault(str(k), {})[mes] = int(n)
    return out


def _flat(s):
    cols = ['fecha', 'mes', 'vin', 'agencia', 'bodega', 'asesor', 'modelo', 'version',
            'cantidad', 'es_nc', 'doc', 'credito', 'financiera', 'pct_desc', 'val_desc',
            'ventas_netas', 'cedula', 'guc_id', 'anio_modelo', 'color']
    f = s[cols].copy()
    f['fecha'] = f['fecha'].dt.strftime('%Y-%m-%d')
    f = f.astype(object).where(f.notna(), None)
    for c in ('cantidad', 'anio_modelo'):
        f[c] = f[c].map(lambda v: int(v) if v is not None else None)
    for c in ('pct_desc', 'val_desc', 'ventas_netas'):
        f[c] = f[c].map(lambda v: round(float(v), 2) if v is not None else None)
    return f.to_dict('records')


# ── Bloques que llena ANALISTA ORGU 3.0 ─────────────────────────────────────

def credito(s):
    """% crédito y mix de financieras, por mes × agencia × asesor × modelo.

    Unidad: Σ cantidad signada (ver docstring del módulo). Firma sugerida:
      {'totals': {mes: {'n': uds_credito, 'de': uds_total, 'pct': %}},
       'by_agencia': {ag: {mes: {...}}}, 'by_asesor': {...}, 'by_modelo': {...},
       'financieras': {mes: {financiera: uds}}}
    """
    return {'_todo': 'ANALISTA ORGU 3.0'}


def descuento(s):
    """Descuento medio (Σ val_desc ÷ Σ (ventas_netas + val_desc), signados) y las
    facturas sobre tope. Firma sugerida:
      {'totals': {mes: {'pct': %, 'valor': $}}, 'by_agencia', 'by_modelo', 'by_asesor',
       'sobre_tope': [{vin, fecha, agencia, asesor, modelo, pct, valor, anulada}]}
    """
    return {'_todo': 'ANALISTA ORGU 3.0'}


def recompra(veh, parque):
    """Ventas del mes a clientes que ya compraron en ORGU (llave = `cedula` base).
    Firma sugerida por marca: {'months', 'totals': {mes: {'ventas', 'previos', 'pct'}},
    'by_agencia': {...}, 'anios_mediana', 'migracion': {agencia_anterior: {agencia: n}}}
    """
    return {'_estado': 'esqueleto', '_todo': 'ANALISTA ORGU 3.0'}


def renovacion(parque, veh):
    """Pozo 4–8 años por modelo y plaza, y cuántos ya renovaron.
    Firma sugerida: {'corte', 'por_modelo': {modelo: {'vehiculos', 'duenos', 'con_celular',
    'ya_renovaron'}}, 'por_plaza': {...}}
    """
    return {'_estado': 'esqueleto', '_todo': 'ANALISTA ORGU 3.0'}


# ── Asesores: el panel manda ─────────────────────────────────────────────────

def _canonizar_asesores(out):
    """Mapea las grafías de asesor de FACTURADO a las que el panel YA muestra.

    Nunca al revés. `asesores.canonizar(out)` elige la grafía más frecuente, y
    FACTURADO trae una línea por factura: el 09-sep-2026 dos asesoras de Ford
    cambiaron de nombre en el panel (Carla Montoya → Carla Melissa Montoya) sin
    mover un número. Por eso este módulo se enchufa DESPUÉS de canonizar el resto
    y aquí los canónicos del panel pesan más que cualquier grafía nueva.
    """
    import asesores
    resto = {k: v for k, v in out.items() if k not in ('facturado', 'recompra', 'renovacion')}
    canon = asesores.frecuencias(resto)
    freq = {n: c + 10**6 for n, c in canon.items()}          # el panel gana siempre
    nuevas = asesores.frecuencias(out.get('facturado') or {})
    for n, c in nuevas.items():
        freq.setdefault(n, c)
    mapa = {a: c for a, c in asesores.construir_mapa(freq).items() if a in nuevas and a not in canon}
    celdas = asesores.aplicar(out['facturado'], mapa)
    return len(mapa), celdas


# ── Enchufe en aggregate ────────────────────────────────────────────────────

def build(out, base=None, corte=None):
    """Escribe out['facturado'], out['facturado_corte'], out['recompra'], out['renovacion'].
    Devuelve un resumen imprimible. Si no hay archivo, no toca `out`."""
    df = cargar()
    if df is None or df.empty:
        return 'sin archivo FACTURADO'
    if base is None:
        try:
            base = base_ventas.cargar()
        except Exception:
            base = None
    veh = heredar_agencia(df[df['es_vehiculo'] & df['marca'].notna()], base)
    parque = cargar_parque()

    cu = cuadre(veh, base, out.get('ventas_mensual'), corte or out.get('ventas_corte'))
    fac = {
        '_estado': 'esqueleto',
        '_doc': {
            'fuente': df['_archivo'].iloc[0],
            'regla': 'Σ Cantidad signada por mes, líneas con Tipo Documento de vehículos; '
                     'sin MPSI ni seminuevos; sin filtro > 0. La NC resta en su mes y bodega.',
            'no_trae': 'exonerados (sin MSC) ni AGENCIA de placa (solo bodega). '
                       'La Base de Ventas manda en ventas_mensual y conversion_data.',
            'by_agencia': 'agencia OFICIAL heredada de la Base de Ventas por chasis; '
                          'si el VIN no está, la bodega (agencia_fuente en flat).',
            'cuadre': 'facturado + exonerados (Base sin chasis) + solo_base (chasis de la Base '
                      'ausentes en FACTURADO) == panel, por marca y mes cerrado.',
        },
        '_cuadre': cu,
        '_solo_base': _solo_base(veh, base)[1],
        '_marca_corregida': int((veh['marca'] != veh['marca_facturado']).sum()),
        '_placa': placa(veh),
    }
    for mk in MARCAS:
        s = veh[veh['marca'] == mk]
        sp = s[s['mes'] >= PANEL_DESDE]
        if sp.empty:
            continue
        fac[mk] = {
            'months': sorted(sp['mes'].unique()),
            'totals': sp.groupby('mes')['cantidad'].sum().astype(int).to_dict(),
            'by_agencia': _serie(sp, 'agencia'),
            'by_bodega': _serie(sp, 'bodega'),
            'by_asesor': _serie(sp, 'asesor'),
            'by_modelo': _serie(sp, 'modelo'),
            'credito': credito(s),
            'descuento': descuento(s),
            'flat': _flat(sp),
        }
    out['facturado'] = fac
    out['facturado_corte'] = str(df['fecha'].max().date())
    out['recompra'] = recompra(veh, parque)
    out['renovacion'] = renovacion(parque, veh)

    try:
        _alias, _celdas = _canonizar_asesores(out)
    except Exception as _e:
        _alias, _celdas = 0, f'WARN {_e}'

    malos = [(mk, m, c['dif']) for mk, meses in cu.items() for m, c in meses.items() if not c['ok']]
    return (f"{len(veh)} líneas de vehículo · corte {out['facturado_corte']} · "
            f"parque {'sí' if parque is not None else 'no'} · asesores→panel {_alias} grafías/{_celdas} celdas · "
            f"cuadre: {sum(len(v) for v in cu.values()) - len(malos)} meses ok, {len(malos)} con diferencia"
            + (' → ' + ', '.join(f'{mk} {m} {d:+d}' for mk, m, d in malos) if malos else ''))


if __name__ == '__main__':
    import json
    d = json.loads((Path(__file__).parent / 'data.json').read_text(encoding='utf-8'))
    out = {'ventas_mensual': d.get('ventas_mensual'), 'ventas_corte': d.get('ventas_corte')}
    print(build(out))
    for mk, meses in out['facturado']['_cuadre'].items():
        print(f'\n{mk}')
        for m, c in meses.items():
            suma = c['facturado'] + c['exonerados'] + c['solo_base']
            print(f"  {m}  facturado {c['facturado']:>4} + exo {c['exonerados']:>2} + solo_base {c['solo_base']:>2} = {suma:>4}"
                  f"  panel {c['panel']:>4}  " + ('✓' if c['ok'] else '✗ %+d' % c['dif']))
    print('\nsolo en la Base:', out['facturado']['_solo_base'], '· marcas corregidas desde la Base:', out['facturado']['_marca_corregida'])
    pl = out['facturado']['_placa']
    print('\nplaca (bodega→agencia):', {mk: sum(sum(v.values()) for v in meses.values()) for mk, meses in pl.items()})
    print('bytes de facturado en JSON:', len(json.dumps(out['facturado'], ensure_ascii=False, default=str)))
