"""Aggregates Excel traffic data into anonymous JSON for the dashboard.
Includes Ford-specific processed data matching ford_traffic_generator.py logic.
"""
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from inventario import (load_inventario, DEFAULT_INVENTORY_PATH, _INVENTORY_DIRS,
                        SIN_MODELO, SIN_MODELO_FORD, normalize_familia)
from conversion import compute_conversion_metrics, norm_ced as _conv_norm_ced, cedula_base as _conv_cedula_base, norm_email as _conv_norm_email, norm_cel as _conv_norm_cel
from competencia import compute_competencia_data
from embudo import compute_embudo_data

def _compute_embudo_safe():
    _emb_local = Path.home() / 'dev' / 'panel-datos' / 'embudo'
    _emb_count = len(list(_emb_local.rglob('*.xlsx'))) if _emb_local.exists() else 0
    if _emb_count < 30:
        print(f"WARN: embudo skipped (cache local solo tiene {_emb_count} archivos, min 30)")
        return None
    try:
        return compute_embudo_data()
    except Exception as e:
        print(f"WARN: embudo no disponible: {e}")
        return None

# ============================================================
# Cache local de datos (evita depender de OneDrive on-demand)
# Ver ~/dev/panel-datos/ para snapshot local de BDs, inventario y metas.
# ============================================================
LOCAL_DATA_DIR = Path.home() / 'dev' / 'panel-datos'

def _resolve_local(path):
    """Redirige lectura a copia local si existe. OneDrive queda como fallback."""
    try:
        p = Path(path)
        name = p.name
        for sub in ('bd', 'inv', 'metas'):
            local = LOCAL_DATA_DIR / sub / name
            if local.exists():
                return local
    except Exception:
        pass
    return path

def _parse_brand_meta_breakdown(file_path):
    file_path = _resolve_local(file_path)
    """Parsea hoja METAS_OM del archivo NUEVO_AI_MARCAS y devuelve:
       {brand_key: {modelo_canonico: {meta_ventas, por_agencia: {ag: meta_ventas}}}}.
    El archivo lista total por marca seguido de sus modelos (Dong Feng total, Huge, Mage...).
    """
    try:
        xl = pd.ExcelFile(file_path)
        sheet = 'METAS_MARCAS' if 'METAS_MARCAS' in xl.sheet_names else 'METAS_OM'
        df = pd.read_excel(file_path, sheet_name=sheet, header=1)
    except Exception as e:
        print(f'[brand_meta_breakdown] WARN {file_path}: {e}')
        return {}
    AG_COLS = ['CJA','Orellana','La Y','Tumbaco','Manta','Machala','Portoviejo']
    # Mapping brand-header → brand_key (uppercase keyword search)
    BRAND_KEY = {
        'DONG FENG': 'DONGFENG_ORGU', 'DONGFENG': 'DONGFENG_ORGU',
        'MAZDA': 'MAZDA_ORGU', 'CHERY': 'CHERY_ORGU', 'RAM': 'RAM_ORGU',
    }
    # Mapping modelo → familia canónica (alineado con normalize_familia + ventas_mensual modeloKey)
    # OJO: patrones más específicos PRIMERO (CX-30 antes que CX-3, RICH 7 antes que RICH)
    MODELO_FAM = {
        'HUGE':'HUGE','MAGE':'MAGE','PALADIN':'PALADIN',
        'RICH 6':'RICH 6','RICH 7':'RICH 7','Z9':'Z9',
        'BT-50':'NEW BT-50','BT50':'NEW BT-50',
        'CX-30':'CX30','CX30':'CX30','CX-3':'CX3',
        'CX-60':'CX60','CX60':'CX60','CX-90':'CX90','CX90':'CX90','CX-5':'CX5','CX5':'CX5',
        'ARRIZO':'ARRIZO','TIGGO 2':'TIGGO 2','TIGGO 4':'TIGGO 4',
        'TIGGO 7':'TIGGO 7','TIGGO 8':'TIGGO 8','HIMLA':'HIMLA',
        '1500':'RAM 1500','700':'RAM 700',
    }
    def model_to_fam(name):
        u = str(name or '').upper().strip()
        for kw, fam in MODELO_FAM.items():
            if kw in u: return fam
        return None
    result = {}
    current_brand = None
    for _, row in df.iterrows():
        modelo_raw = str(row.get('Modelo', '')).strip()
        if not modelo_raw or modelo_raw.lower() == 'nan':
            continue
        u = modelo_raw.upper()
        if u == 'TOTAL':
            break
        # Brand header?
        matched_brand = None
        for kw, bk in BRAND_KEY.items():
            if kw in u and len(u) <= len(kw) + 2:  # row "Dong Feng" pero no "Dong Feng XYZ"
                matched_brand = bk; break
        if matched_brand:
            current_brand = matched_brand
            if current_brand not in result:
                result[current_brand] = {}
            continue
        if not current_brand:
            continue
        # Modelo row
        fam = model_to_fam(modelo_raw)
        if not fam:
            continue
        total = 0
        por_ag = {}
        for ag in AG_COLS:
            try:
                v = int(row.get(ag, 0) or 0)
            except Exception:
                v = 0
            por_ag[ag] = {'meta_ventas': v}
            total += v
        # Acumular (si ya existe la fam, sumar)
        prev = result[current_brand].get(fam, {'meta_ventas':0, 'por_agencia':{}})
        prev['meta_ventas'] = prev.get('meta_ventas',0) + total
        for ag, d in por_ag.items():
            pa = prev['por_agencia'].setdefault(ag, {'meta_ventas':0})
            pa['meta_ventas'] = pa.get('meta_ventas',0) + d['meta_ventas']
        result[current_brand][fam] = prev
    return result

def _snap_date_agg(path):
    """Fecha del snapshot desde el nombre del archivo (REPORTE ... 15-8-2026.xlsm)."""
    import re as _re
    m = _re.search(r'(\d{1,2})-(\d{1,2})-(\d{4})', path.name)
    if not m:
        return pd.Timestamp.min
    try:
        return pd.Timestamp(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except Exception:
        return pd.Timestamp.min


# Corte real de la Base de Ventas ('aaaa-mm-dd'). Lo setea _compute_ventas_mensual.
VENTAS_CORTE = None


def _compute_ventas_mensual(sales_df):
    """Pivot mensual de ventas NETAS por marca/modelo/asesor/agencia.
    Devuelve {marca_key: {months, months_labels, by_modelo, by_asesor, by_agencia, totals}}.
    Cantidad ya viene signada (+1 FACTURA, -1 NC) desde ventas.load_ventas().
    Si hay meses no cubiertos por sales_df (ej junio cuando ventas YTD solo va hasta mayo),
    complementamos desde inventario DATOS (STATUS=FACTURADO) — solo unidades, sin revenue.
    """
    if sales_df is None or len(sales_df) == 0:
        return None
    df = sales_df.copy()
    df['fecha_fact'] = pd.to_datetime(df.get('fecha de facturacion'), errors='coerce')
    df = df[df['fecha_fact'].dt.year >= 2025].copy()
    if len(df) == 0:
        return None
    # ► OVERRIDE 1: Base de Ventas de Finanzas = fuente OFICIAL del año en curso.
    #
    # Reemplaza TODOS los meses que cubre. Por qué manda sobre el reporte de inventario:
    #   · trae el CANAL, así que incluye las ventas EXONERADAS — 12 unidades Ford
    #     ene–jul 2026 (2 de La Y) que el inventario no tiene porque no llevan chasis;
    #   · trae la AGENCIA ya resuelta (difiere de la bodega en 50 de 915 filas: es el
    #     efecto placa);
    #   · está más al día: llegó al 24-ago cuando el inventario iba al 15 — 57 ventas
    #     Ford contra 10;
    #   · no sufre el problema de los snapshots: es un libro de facturas, no una foto.
    #
    # ⚠ Solo trae el año en curso. 2025 sigue saliendo del inventario.
    _base_meses = set()
    try:
        import base_ventas as _bv
        _bdf = _bv.cargar()
        if _bdf is not None and len(_bdf):
            _bdf = _bdf[_bdf['marca'].notna() & _bdf['mes'].notna()].copy()
            _base_meses = set(_bdf['mes'].dropna().unique())
            if _base_meses:
                df['_mes_ym'] = df['fecha_fact'].dt.strftime('%Y-%m')
                _before = len(df)
                df = df[~df['_mes_ym'].isin(_base_meses)].drop(columns=['_mes_ym'])
                _drop = _before - len(df)
                _fin_df = pd.DataFrame([{
                    'fecha_fact': r['fecha'],
                    'fecha de facturacion': r['fecha'],
                    'Cantidad': int(r['cantidad']),
                    'marca': str(r['marca']).replace('_ORGU', ''),
                    'familia': r['familia'] if pd.notna(r['familia']) else r['modelo'],
                    # la descripción COMPLETA se conserva: los accesorios del PBD
                    # se cotizan por versión ('ESCAPE TITANIUM AC 1.5…'), no por modelo.
                    'version_txt': r['modelo'],
                    # el nombre LARGO: fact_agency_norm() busca palabras clave
                    # ('CARLOS JULIO AROSEMENA'), no entiende la sigla 'CJA'.
                    'AGENCIA_FACTURACION': r['agencia_raw'],
                    'ASESOR_FACTURACION': str(r['asesor'] or 'Sin asesor').upper(),
                    'Chasis': str(r['chasis'] or ''),
                    'rev_signed': round(float(r['precio_neto'] or 0) * (1 if r['cantidad'] >= 0 else -1), 2),
                    'canal_venta': r['canal'],
                } for _, r in _bdf.iterrows()])
                df = pd.concat([df, _fin_df], ignore_index=True, sort=False)
                # ► Corte REAL de las ventas. No tiene por qué coincidir con el del
                # tráfico ni con el del inventario: el 31-ago-2026 la BD de tráfico
                # llegaba al 31 y la Base de Ventas al 24. Sin esto, agosto quedaba
                # "cerrado" para las vistas de ventas y su cumplimiento se comparaba
                # contra la meta del mes completo con 7 días de facturas faltando.
                globals()['VENTAS_CORTE'] = str(_bdf['fecha'].max().date())
                _exo = int(_bdf.loc[_bdf['exonerado'], 'cantidad'].sum())
                print(f'[ventas_mensual] Base de Ventas ({_bdf["_archivo"].iloc[0]}): '
                      f'{len(_bdf)} filas · {sorted(_base_meses)[0]}–{sorted(_base_meses)[-1]} · '
                      f'{_exo} exonerados incluidos · {_drop} filas de inventario omitidas')
    except Exception as e:
        print(f'[ventas_mensual] WARN Base de Ventas no aplicada: {e}')

    # ► OVERRIDE 2: archivos RANKING_<MES>_<YYYY>.xlsx = fuente OFICIAL de meses cerrados
    # (netos de NCs finales). Reemplazan cualquier cálculo desde inventario para el mes.
    _ranking_meses = set()
    try:
        from parse_ranking import parse_ranking as _parse_ranking
        import re as _re
        _MES_MAP = {'ENERO':'01','FEBRERO':'02','MARZO':'03','ABRIL':'04','MAYO':'05','JUNIO':'06','JULIO':'07','AGOSTO':'08','SEPTIEMBRE':'09','OCTUBRE':'10','NOVIEMBRE':'11','DICIEMBRE':'12'}
        _ranking_txs = []
        for _p in Path(__file__).parent.glob('RANKING_*.xlsx'):
            _m = _re.match(r'RANKING_([A-Z]+)_(\d{4})\.xlsx', _p.name, _re.IGNORECASE)
            if not _m: continue
            _mes_name = _m.group(1).upper()
            _year = _m.group(2)
            if _mes_name not in _MES_MAP: continue
            _ym = f'{_year}-{_MES_MAP[_mes_name]}'
            _txs = _parse_ranking(_p, _ym)
            if _txs:
                _ranking_txs.extend(_txs)
                _ranking_meses.add(_ym)
                print(f'[ventas_mensual] RANKING override: {_p.name} → {_ym} ({sum(t["cantidad"] for t in _txs)} netos, {len(_txs)} TXs)')
        if _ranking_meses:
            df['_mes_ym'] = df['fecha_fact'].dt.strftime('%Y-%m')
            before = len(df)
            df = df[~df['_mes_ym'].isin(_ranking_meses)].drop(columns=['_mes_ym'])
            dropped = before - len(df)
            if dropped > 0:
                print(f'[ventas_mensual] omitidas {dropped} filas de sales_df cubiertas por RANKING')
            _rank_df = pd.DataFrame([{
                'fecha_fact': pd.to_datetime(t['mes']+'-15'),
                'fecha de facturacion': pd.to_datetime(t['mes']+'-15'),
                'Cantidad': t['cantidad'],
                'marca': t['marca'].replace('_ORGU',''),
                'familia': t['modelo'],
                'AGENCIA_FACTURACION': t['agencia'],
                'ASESOR_FACTURACION': t['asesor'].upper(),
                'Chasis': '',
                'rev_signed': 0.0,
            } for t in _ranking_txs])
            df = pd.concat([df, _rank_df], ignore_index=True, sort=False)
    except Exception as e:
        print(f'[ventas_mensual] WARN RANKING override falló: {e}')
    # Complemento desde inventario para meses no cubiertos por ventas.xlsx.
    # Toma facturas STATUS=FACTURADO con fecha posterior al último mes de ventas_df.
    # ► Excluye VINs ya presentes en sales_df (Chasis) — evita doble conteo cuando
    # un chasis facturado en mayo fue NC'd y re-facturado en junio (re-facturación,
    # no venta nueva). El neto correcto es el que ya quedó en sales_df.
    # ► También excluye VINs listados en ventas_overrides.json — para casos donde
    # una factura se anuló intramonth y la NC no llegó al archivo Base de ventas YTD.
    try:
        last_month_sales = df['fecha_fact'].dt.strftime('%Y-%m').max()
        # VINs ya conocidos en sales_df (cualquier mes)
        known_vins = set()
        if 'Chasis' in df.columns:
            for v in df['Chasis'].dropna().astype(str):
                v = v.strip().upper()
                if v: known_vins.add(v)
        # Manual overrides (VINs anulados intramonth sin trace en sales_df)
        override_path = Path(__file__).parent / 'ventas_overrides.json'
        if override_path.exists():
            try:
                with open(override_path, 'r') as f:
                    ov = __import__('json').load(f)
                for v in (ov.get('exclude_vins') or []):
                    v = str(v).strip().upper()
                    if v: known_vins.add(v)
            except Exception as e:
                print(f'[ventas_mensual] WARN reading overrides: {e}')
        # ► NUEVO: leer hoja DATOS 2 del inventario — trae FACTURA + NC con Cantidad
        # SIGNADA (+1/-1). Esto da el neto real intramonth sin necesidad de overrides
        # manuales. Reemplaza el complemento viejo que usaba DATOS (chasis FACTURADO).
        # OJO: cuando cambia el mes, DATOS 2 del archivo actual solo trae TXs del
        # mes nuevo. Para no perder el mes anterior, concat DATOS 2 de TODOS los
        # snapshots de inventario disponibles y dedup por (Vin, Fecha, Cantidad).
        import warnings as _wa
        with _wa.catch_warnings():
            _wa.simplefilter('ignore')
            inv_tx_frames = []
            _seen_paths = set()
            for _inv_dir in _INVENTORY_DIRS:
                if not _inv_dir.exists(): continue
                _found_here = False
                for _ext in ('*.xlsm','*.xlsx'):
                    for _p in _inv_dir.glob(_ext):
                        if _p.name.startswith('~$'): continue
                        if 'INVENTARIO' not in _p.name.upper(): continue
                        if _p in _seen_paths: continue
                        _seen_paths.add(_p)
                        try:
                            _df = pd.read_excel(_p, sheet_name='DATOS 2', header=0)
                            _df['_src'] = _p.name
                            _df['_snap'] = _snap_date_agg(_p)
                            inv_tx_frames.append(_df)
                            _found_here = True
                        except Exception as _e:
                            pass
                if _found_here: break  # ► Stop en primer dir con matches (cache local vs OneDrive)
            if inv_tx_frames:
                inv_tx = pd.concat(inv_tx_frames, ignore_index=True, sort=False)
                # ► Por mes manda el snapshot MÁS RECIENTE que lo cubre. Misma razón
                # que en ventas.load_ventas_completo(): el snapshot es una foto y una
                # factura anulada desaparece de la foto siguiente sin dejar NC que la
                # compense, así que la unión histórica conservaba ventas revertidas.
                # Metía 4 unidades Ford de más en ene-jul 2026 y el panel descuadraba
                # contra finanzas (639 contra 635). El panel debe cuadrar con finanzas.
                if '_snap' in inv_tx.columns and 'Fecha' in inv_tx.columns:
                    _mp = pd.to_datetime(inv_tx['Fecha'], errors='coerce').dt.to_period('M')
                    _kp = inv_tx.groupby(_mp)['_snap'].transform('max')
                    _n0 = len(inv_tx)
                    inv_tx = inv_tx[inv_tx['_snap'] == _kp].copy()
                    print(f'[ventas_mensual] DATOS 2: por mes manda el snapshot más reciente '
                          f'· {_n0 - len(inv_tx)} filas de snapshots superados descartadas')
                    inv_tx = inv_tx.drop(columns=['_snap'])
                if 'Vin' in inv_tx.columns and 'Fecha' in inv_tx.columns and 'Cantidad' in inv_tx.columns:
                    inv_tx = inv_tx.drop_duplicates(subset=['Vin','Fecha','Cantidad'], keep='first')
                print(f'[ventas_mensual] DATOS 2 concat {len(inv_tx_frames)} snapshots → {len(inv_tx)} TXs únicas')
            else:
                inv_tx = pd.read_excel(DEFAULT_INVENTORY_PATH, sheet_name='DATOS 2', header=0)
        inv_tx['fecha_fact'] = pd.to_datetime(inv_tx['Fecha'], errors='coerce')
        inv_tx['mes_str'] = inv_tx['fecha_fact'].dt.strftime('%Y-%m')
        inv_tx['Cantidad'] = inv_tx.get('Cantidad', 0).fillna(0).astype(int)
        # DATOS 2 del archivo 2-jul en adelante trae histórico COMPLETO del año 2026
        # (FACT+NC signadas). Se usa como fuente principal — sales_df queda como fallback.
        # Drop meses cubiertos por sales_df si sales_df tiene detalle transaccional
        # (evitar doble conteo). Priorizar DATOS 2 concat sobre sales_df para 2026.
        _datos2_meses = set(inv_tx[inv_tx['fecha_fact'].dt.year==2026]['mes_str'].unique())
        # ⚠ La Base de Ventas de Finanzas manda sobre DATOS 2 en los meses que cubre:
        # trae el canal (exonerados), la agencia resuelta y llega más lejos en el mes.
        # Sin este descuento, DATOS 2 volvía a pisar el override y se perdían los 12
        # exonerados y las dos semanas de agosto.
        _datos2_meses -= _base_meses
        # Drop de sales_df los meses cubiertos por DATOS 2 (que ahora es más completo)
        if _datos2_meses:
            df['_mes_ym2'] = df['fecha_fact'].dt.strftime('%Y-%m')
            _before = len(df)
            df = df[~df['_mes_ym2'].isin(_datos2_meses)].drop(columns=['_mes_ym2'])
            _dropped = _before - len(df)
            if _dropped > 0:
                print(f'[ventas_mensual] omitidas {_dropped} filas de sales_df cubiertas por DATOS 2 completo')
        inv_tx = inv_tx[(inv_tx['fecha_fact'].dt.year==2026)
                        & (~inv_tx['mes_str'].isin(_ranking_meses))
                        & (~inv_tx['mes_str'].isin(_base_meses))].copy()
        print(f'[ventas_mensual] DATOS 2 fuente principal 2026: {sorted(_datos2_meses)} ({len(inv_tx)} TXs)')
        # No dedup VIN: DATOS 2 = fuente de verdad para meses post-mayo. Cada TX
        # cuenta tal cual (FACT +1, NC -1). User confirma "tengo 79 facturados"
        # = DATOS 2 sum junio 2026 = 79. Si VIN aparece en sales_df mayo y DATOS 2
        # junio tiene FACT (re-fact), ambas son ventas distintas — la NC mayo
        # correspondiente debe estar en sales_df (si no está, es bug del archivo).
        # exclude_vins del override sigue activo (re-facts confirmadas manualmente).
        if 'exclude_vins_set' in dir():
            pass
        if known_vins and 'Vin' in inv_tx.columns:
            override_excl = set()
            if override_path.exists():
                try:
                    with open(override_path, 'r') as f:
                        ov2 = __import__('json').load(f)
                    for v in (ov2.get('exclude_vins') or []):
                        v = str(v).strip().upper()
                        if v: override_excl.add(v)
                except Exception: pass
            if override_excl:
                inv_tx['vin_up'] = inv_tx['Vin'].astype(str).str.strip().str.upper()
                before = len(inv_tx)
                inv_tx = inv_tx[~inv_tx['vin_up'].isin(override_excl)]
                skipped = before - len(inv_tx)
                if skipped > 0:
                    print(f'[ventas_mensual] omitidas {skipped} TXs (exclude_vins override)')
        if len(inv_tx) > 0:
            mapped = pd.DataFrame({
                'fecha_fact': inv_tx['fecha_fact'],
                'fecha de facturacion': inv_tx['fecha_fact'],
                'Cantidad': inv_tx['Cantidad'].fillna(0).astype(int),
                'marca': inv_tx.get('Marca', '').astype(str),
                'familia': inv_tx.get('Descripción Modelo', '').astype(str),
                'AGENCIA_FACTURACION': inv_tx.get('Descripcion Bodega', '').astype(str),
                'ASESOR_FACTURACION': inv_tx.get('Usuario Vende', '').astype(str).str.upper(),
                'Chasis': inv_tx['Vin'].astype(str) if 'Vin' in inv_tx.columns else '',
                'rev_signed': inv_tx.get('Valor Total', 0).fillna(0).astype(float) if 'Valor Total' in inv_tx.columns else 0.0,
            })
            df = pd.concat([df, mapped], ignore_index=True, sort=False)
            netos = int(mapped['Cantidad'].sum())
            print(f'[ventas_mensual] complementado {len(mapped)} transacciones DATOS 2 (NETO={netos}) post-{last_month_sales}')
    except Exception as e:
        print(f'[ventas_mensual] WARN complemento DATOS 2 falló: {e}')

    # ► HISTÓRICO 2025 + meses cerrados 2026: complementar desde DATOS (chasis FACTURADO).
    # Snapshots más recientes se limpian (1-jul solo trae junio+julio, 552 filas).
    # Snapshots antiguos tienen histórico completo (29-jun con 2384 filas).
    # Estrategia: por VIN → filter FACTURADO → keep first (snapshot más reciente que lo tenga).
    try:
        with _wa.catch_warnings():
            _wa.simplefilter('ignore')
            _hist_frames = []
            _seen_p = set()
            for _inv_dir in _INVENTORY_DIRS:
                if not _inv_dir.exists(): continue
                _found_here = False
                for _ext in ('*.xlsm','*.xlsx'):
                    for _p in _inv_dir.glob(_ext):
                        if _p.name.startswith('~$'): continue
                        if 'INVENTARIO' not in _p.name.upper(): continue
                        if _p in _seen_p: continue
                        _seen_p.add(_p)
                        try:
                            _df = pd.read_excel(_p, sheet_name='DATOS', header=0)
                            _df['_src'] = _p.name
                            _df['_mtime'] = _p.stat().st_mtime
                            _hist_frames.append(_df)
                            _found_here = True
                        except Exception: pass
                if _found_here: break
            if _hist_frames:
                inv_hist = pd.concat(_hist_frames, ignore_index=True, sort=False)
                # Filter FACTURADO primero (evita quedarnos con row DISPONIBLE de snapshot reciente)
                inv_hist['STATUS_H'] = inv_hist['STATUS HOMOLOGADO'].astype(str).str.strip().str.upper()
                inv_hist = inv_hist[inv_hist['STATUS_H']=='FACTURADO'].copy()
                # Dedup por VIN: keep first después de sort por _mtime DESC = quedarse con
                # el snapshot MÁS RECIENTE que tenga el VIN FACTURADO.
                if 'vin' in inv_hist.columns:
                    inv_hist = inv_hist.sort_values('_mtime', ascending=False).drop_duplicates(subset=['vin'], keep='first')
                print(f'[ventas_mensual] DATOS concat {len(_hist_frames)} snapshots → {len(inv_hist)} chasis FACTURADO únicos')
            else:
                inv_hist = pd.read_excel(DEFAULT_INVENTORY_PATH, sheet_name='DATOS', header=0)
        inv_hist['STATUS_H'] = inv_hist['STATUS HOMOLOGADO'].astype(str).str.strip().str.upper()
        inv_hist = inv_hist[inv_hist['STATUS_H']=='FACTURADO'].copy()
        inv_hist['fecha_fact'] = pd.to_datetime(inv_hist['fecha de facturacion'], errors='coerce')
        inv_hist['mes_str'] = inv_hist['fecha_fact'].dt.strftime('%Y-%m')
        # Meses (2025 + 2026 cerrados) que no están en sales_df ni DATOS 2 mes actual.
        existing_mes = set(df['fecha_fact'].dt.strftime('%Y-%m').unique())
        inv_hist = inv_hist[(inv_hist['fecha_fact'].dt.year.isin([2025, 2026])) & (~inv_hist['mes_str'].isin(existing_mes))]
        if len(inv_hist) > 0:
            hist_mapped = pd.DataFrame({
                'fecha_fact': inv_hist['fecha_fact'],
                'fecha de facturacion': inv_hist['fecha_fact'],
                'Cantidad': 1,
                'marca': inv_hist.get('marca', '').astype(str),
                # La hoja DATOS trae la descripción completa ('RANGER XLT AC 2.0 CD
                # 4X4 TA DIESEL'). Sin normalizar, 2025 abría 27 filas de modelo que
                # NO se agregaban con las 8 de 2026 en ninguna vista por modelo.
                'familia': [normalize_familia(f, m) or str(f)
                            for f, m in zip(inv_hist.get('familia', '').astype(str),
                                            inv_hist.get('marca', '').astype(str))],
                'version_txt': inv_hist.get('familia', '').astype(str),
                'AGENCIA_FACTURACION': inv_hist.get('AGENCIA_FACTURACION', '').astype(str),
                'ASESOR_FACTURACION': inv_hist.get('ASESOR_FACTURACION', '').astype(str).str.upper(),
                'Chasis': inv_hist.get('vin', '').astype(str),
                'rev_signed': 0.0,
            })
            df = pd.concat([df, hist_mapped], ignore_index=True, sort=False)
            print(f'[ventas_mensual] histórico 2025: {len(hist_mapped)} chasis FACTURADO desde DATOS')
    except Exception as e:
        print(f'[ventas_mensual] WARN histórico 2025 falló: {e}')
    df['mes'] = df['fecha_fact'].dt.strftime('%Y-%m')
    df['Cantidad'] = df['Cantidad'].fillna(1).astype(int)
    # Revenue por fila — Total Factura ya viene signado en el archivo de origen
    # (NC trae Total Factura negativo). Sumar columna directo da el NETO.
    # NO sobrescribir el rev_signed que ya trajeron las filas de DATOS 2 ('Valor Total',
    # negativo en NC). Antes esta línea lo ponía en 0 y la columna "$ Reversado" del
    # detalle de NC salía siempre vacía (bug 29-jul).
    _rev_prev = df['rev_signed'].astype(float) if 'rev_signed' in df.columns else pd.Series(0.0, index=df.index)
    if 'Total Factura' in df.columns:
        df['rev_signed'] = df['Total Factura'].astype(float).fillna(_rev_prev).fillna(0.0)
    else:
        df['rev_signed'] = _rev_prev.fillna(0.0)
    df['marca_up'] = df['marca'].astype(str).str.strip().str.upper()

    # ── Accesorios (Daniel, 4-ago-2026): el no-híbrido Ford se factura en DOS
    # partes — vehículo (esta data) + accesorios (serie de factura que el reporte
    # no trae). Se suma el valor estándar de accesorios del PBD oficial por
    # unidad, con signo (la NC también lo resta). Sin esto, un Ranger parecía
    # venderse con 20% de descuento cuando en realidad facturaba a lista.
    try:
        from presupuesto import accesorios_unidad as _acc_u
        _marca_bp = df['marca_up'].map(lambda m: 'FORD' if str(m).startswith('FORD') else m)
        # ⚠ por VERSIÓN, no por modelo: version_key('FORD', 'ESCAPE') no existe en el
        # PBD y devuelve 0. Pasar el modelo corto borraba $5,5 M de accesorios sin avisar.
        if 'version_txt' not in df.columns:
            df['version_txt'] = df['familia']
        _ver = df['version_txt'].where(df['version_txt'].notna() & (df['version_txt'].astype(str) != ''),
                                       df['familia'])
        df['_acc'] = [
            _acc_u('FORD', ver) * float(q or 0) if str(m).startswith('FORD') else 0.0
            for m, ver, q in zip(df['marca_up'], _ver, df['Cantidad'])
        ]
        df['rev_signed'] = df['rev_signed'] + df['_acc']
        _tot_acc = df.loc[df['_acc'] != 0, '_acc'].sum()
        print(f"[ventas_mensual] accesorios PBD sumados al revenue: ${_tot_acc:,.0f} en {(df['_acc']!=0).sum()} filas Ford")
    except Exception as _e:
        print('[ventas_mensual] WARN accesorios no aplicados:', _e)
    # ── Modelo canónico, punto ÚNICO para todos los orígenes (base de Finanzas,
    # DATOS 2, RANKING, histórico). Cada fuente trae la descripción completa
    # ('MAGE T AC 1.5 5P 4X2 TA HYBRID') y sin esto el mismo modelo abría varias
    # filas: MAGE salía en 3, RICH 6 en 3, HUGE en 2. No cuadraba contra las metas.
    _MARCA_NF = {'DONG FENG': 'DONGFENG', 'DONGFENG_ORGU': 'DONGFENG',
                 'CHERY_ORGU': 'CHERY', 'MAZDA_ORGU': 'MAZDA', 'RAM_ORGU': 'RAM'}
    def _modelo_canon(fam, marca):
        m = str(marca or '').strip().upper()
        m = _MARCA_NF.get(m, m.replace('_ORGU', ''))
        return normalize_familia(fam, m) or str(fam).strip().upper()
    df['familia'] = [_modelo_canon(f, m) for f, m in zip(df['familia'], df['marca'])]
    df['modelo_up'] = df['familia'].astype(str).str.strip().str.upper()
    df['asesor'] = df['ASESOR_FACTURACION'].astype(str).str.strip().str.upper().replace({'NAN': 'Sin asesor', '': 'Sin asesor'})
    # Agencia: el archivo de ventas trae "Bodega Venta Vehiculo" (e.g. "1001 VEHICULOS CARLOS JULIO AROSEMENA").
    # Normalizamos a corto via fact_agency_norm de inventario.py.
    from inventario import fact_agency_norm
    df['agencia_fact'] = df['AGENCIA_FACTURACION'].apply(lambda s: fact_agency_norm(s) or 'Sin agencia')

    # ── Regla de negocio (Daniel, 4-ago-2026): la venta cuenta para la agencia
    # del EQUIPO del asesor, no para la vitrina que emitió la factura. El motivo
    # es la placa: el cliente prefiere placa "P" (Pichincha), así que ventas
    # originadas por Machala/Manta se entregan y facturan vía La Y o Tumbaco.
    # La casa de cada asesor se deriva de sus propias facturas: la agencia donde
    # más factura en positivo. Filas sin asesor conservan la agencia de factura.
    _pos = df[(df['Cantidad'] > 0) & (df['asesor'] != 'Sin asesor') & (df['agencia_fact'] != 'Sin agencia')]
    _home = (_pos.groupby(['asesor', 'agencia_fact'])['Cantidad'].sum()
                 .reset_index()
                 .sort_values('Cantidad', ascending=False)
                 .drop_duplicates('asesor')
                 .set_index('asesor')['agencia_fact'].to_dict())
    # ► Corrección (Daniel, 22-ago-2026): la cifra oficial de ventas de una agencia
    # es la de FINANZAS, o sea la VITRINA que emitió la factura. La Y son 48
    # unidades en ene-jul 2026, no 35. Por eso 'agencia' pasa a ser la vitrina y la
    # atribución por equipo se conserva aparte, en 'agencia_equipo'.
    #
    # La regla de equipo NO se elimina porque sigue siendo la correcta para medir
    # al equipo comercial: existe por el efecto placa (el cliente prefiere placa de
    # Pichincha, así que ventas originadas en Machala o Manta se facturan vía La Y
    # o Tumbaco). Lo que cambia es cuál de las dos es el default del panel.
    df['agencia_equipo'] = df.apply(
        lambda r: _home.get(r['asesor'], r['agencia_fact']), axis=1)
    df['agencia'] = df['agencia_fact']
    _mov = int((df['agencia_equipo'] != df['agencia_fact']).sum())
    print(f'[ventas_mensual] agencia = VITRINA (cuadra con finanzas) · '
          f'{len(_home)} asesores con casa · {_mov} filas donde equipo ≠ vitrina')
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
        nc_rows = []
        for _, r in sub.iterrows():
            row = {
                'mes': str(r['mes']),
                'modelo': str(r['modelo_up']) if r['modelo_up'] and str(r['modelo_up']).lower() not in ('nan','none','') else 'Sin modelo',
                'asesor': str(r['asesor']) if r['asesor'] and str(r['asesor']).lower() not in ('nan','sin asesor','none','') else 'Sin asesor',
                'agencia': str(r['agencia']),
                # Alias de 'agencia' — se mantiene por compatibilidad con consumidores
                # que ya leen este nombre.
                'agencia_fact': str(r['agencia_fact']),
                # Agencia del EQUIPO del asesor (regla de placa). Sirve para medir
                # desempeño del equipo comercial, NO para cuadrar contra finanzas.
                'agencia_equipo': str(r['agencia_equipo']),
                'zona': str(r['zona']),
                'cantidad': int(r['Cantidad']),
                'revenue': round(float(r.get('rev_signed') or 0), 2),
            }
            flat.append(row)
            # NC detail (Cantidad < 0)
            if int(r['Cantidad']) < 0:
                nc_rows.append({
                    'mes': row['mes'],
                    'modelo': row['modelo'],
                    'asesor': row['asesor'],
                    'agencia': row['agencia'],
                    'zona': row['zona'],
                    'revenue': row['revenue'],
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
        # by_agencia = VITRINA: es la cifra oficial, la que cuadra con finanzas.
        by_agencia = _pivot_dim(sub, 'agencia')
        by_agencia_fact = by_agencia          # alias por compatibilidad
        # Atribución por equipo del asesor, para medir al equipo comercial.
        by_agencia_equipo = _pivot_dim(sub, 'agencia_equipo')
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
            'by_agencia_fact': by_agencia_fact,
            'by_agencia_equipo': by_agencia_equipo,
            'by_zona': by_zona,
            'flat': flat,
            'nc': nc_rows,
            # Meses en los que `revenue` es el valor REAL de la factura. Fuera de esta
            # lista solo hay accesorios del PBD: la hoja DATOS del inventario, única
            # fuente de 2025, no trae valor de factura. Sin esta marca, la métrica
            # "Facturación ($)" daba un ticket promedio de $6.539 en 2025 contra
            # $71.952 en 2026 — un crecimiento inventado de 11x.
            'revenue_meses': sorted(_base_meses & set(months_all)),
        }
    return result

BASE = Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Análisis de tráfico/2026/Mayo")
ABRIL_BASE = Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Análisis de tráfico/2026/Abril")
# Files used for Dashboard tab "Marzo (cierre) vs Abril (cierre)" comparison
MARZO  = BASE / "../Julio/BD_JULIO/BD_MARZO_31_03_26.xlsx"
ABRIL  = BASE / "../Julio/BD_JULIO/BD_ABR_30_04_26.xlsx"
ABRIL_PREV = BASE / "../Julio/BD_JULIO/BD_ABR_29_04_26.xlsx"
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
JUL_BASE = Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Análisis de tráfico/2026/Julio")
JUL_BRAND_METAS_FILE = JUL_BASE / "TRAFICO_DY/JULIO_NUEVO_AI_MARCAS.xlsx"
JUL_FORD_METAS_FILE = JUL_BASE / "TRAFICO_DY/JULIO_NUEVO_AI_FORD.xlsx"
# Agosto: las metas viven en METAS/ (los meses anteriores usaban TRAFICO_DY/)
AGO_BASE = Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Análisis de tráfico/2026/Agosto")
AGO_BRAND_METAS_FILE = AGO_BASE / "METAS/AGOSTO_NUEVO_AI_MARCAS.xlsx"
AGO_FORD_METAS_FILE  = AGO_BASE / "METAS/AGOSTO_NUEVO_AI_FORD.xlsx"

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
    # Preferir cache local ~/dev/panel-datos/bd/ sobre OneDrive
    path = _resolve_local(path)
    import time as _t
    _last_err = None
    for _attempt in range(4):
        try:
            df = pd.read_excel(path, sheet_name="Negocios")
            break
        except (TimeoutError, OSError) as _e:
            _last_err = _e
            print(f'[load_raw] timeout {Path(path).name} attempt {_attempt+1}/4, warming up sync...')
            try:
                with open(path, 'rb') as _fh: _fh.read(4096)
            except Exception: pass
            _t.sleep(3 + _attempt * 5)
    else:
        raise _last_err
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
    df["_has_model"] = (~df["MODELO_F"].isin([SIN_MODELO])).astype(int)
    df = df.sort_values(["FECHA", "_has_model"])  # con modelo va al final
    df = df.drop_duplicates(subset=["CEDULA"], keep="last")
    df = df.drop(columns=["_has_model"])
    # ► 'Por definir' se pliega a ESCAPE — DESPUÉS del dedupe (ver inventario.py).
    df.loc[df["MODELO_F"] == SIN_MODELO, "MODELO_F"] = SIN_MODELO_FORD
    df = df[df["CANAL"].isin(channels)]
    return df

def get_dealer_df(df, dealer):
    pattern, channels = DEALER_CONFIG[dealer]
    mask = (df["SUCURSAL"].str.contains(pattern, case=False, na=False)) & (df["CANAL"].isin(channels))
    return df[mask]

# Mapeo modelo específico del Excel METAS_FORD → modelo del panel
FORD_META_MODEL_MAP = {
    'Territory Trend FHEV':           'TERRITORY',
    'Territory Titanium FHEV':        'TERRITORY',
    'Territory Titanium Plus FHEV':   'TERRITORY',
    'Escape Titanium 1.5 GAS':        'ESCAPE',
    'Escape ST':                      'ESCAPE',
    'Escape Titanium':                'ESCAPE',
    'Escape Platinum':                'ESCAPE',
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
    path = _resolve_local(path)
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

def _extract_traffic_meta_from_metas_ford(path):
    path = _resolve_local(path)
    """Extrae la sección 'PRESUPUESTO DE TRÁFICO POR CONCESIONARIO MARKETING' de METAS_FORD.
    Devuelve (meta_total, matrix_meta {modelo: {agencia: meta_trafico_marketing}}, per_agencia).
    Regla ORGU: usar SIEMPRE la sección MARKETING (~80%), no la TOTAL.
    """
    try:
        df = pd.read_excel(path, sheet_name='METAS_FORD', header=None)
    except Exception:
        return 0, {}, {}
    AGENCIAS_ORDER = ['CJA','Orellana','La Y','Tumbaco','Manta','Machala','Portoviejo']
    # Priorizar sección MARKETING; fallback a total si no existe.
    h = None
    for i in range(min(200, len(df))):
        v = df.iloc[i, 0]
        if isinstance(v, str) and 'TRÁFICO' in v.upper() and 'MARKETING' in v.upper():
            h = i; break
    if h is None:
        for i in range(min(200, len(df))):
            v = df.iloc[i, 0]
            if isinstance(v, str) and 'TRÁFICO POR CONCESIONARIO' in v.upper():
                h = i; break
    if h is None: return 0, {}, {}
    total = 0
    matrix_meta = {m: {a: 0 for a in AGENCIAS_ORDER} for m in MODEL_ORDER}
    per_ag = {a: 0 for a in AGENCIAS_ORDER}
    for i in range(h+2, min(h+30, len(df))):
        label = df.iloc[i, 0]
        if pd.isna(label): continue
        label = str(label).strip()
        if label.upper() == 'TOTAL': break
        modelo = FORD_META_MODEL_MAP.get(label)
        if not modelo or modelo not in MODEL_ORDER: continue
        for ag_idx, ag in enumerate(AGENCIAS_ORDER, start=2):
            v = df.iloc[i, ag_idx]
            if pd.notna(v):
                try:
                    iv = int(round(float(v)))
                    matrix_meta[modelo][ag] += iv
                    per_ag[ag] += iv
                    total += iv
                except (ValueError, TypeError): pass
    return total, matrix_meta, per_ag

# Familias canónicas de las marcas ORGU. Vive fuera de las funciones porque el
# TRÁFICO tiene que normalizar igual que las METAS: Mazda traía la meta en 'CX30' y
# el tráfico en 'CX-30', así que el mismo modelo salía en dos filas — una con meta y
# sin tráfico, la otra al revés.
# OJO: patrones más específicos PRIMERO (CX-30 antes que CX-3, RICH 7 antes que RICH).
MODELO_FAM_ORGU = {
    'HUGE': 'HUGE', 'MAGE': 'MAGE', 'PALADIN': 'PALADIN',
    'RICH 6': 'RICH 6', 'RICH 7': 'RICH 7', 'Z9': 'Z9',
    'BT-50': 'NEW BT-50', 'BT50': 'NEW BT-50',
    'CX-30': 'CX30', 'CX30': 'CX30', 'CX-3': 'CX3',
    'CX-60': 'CX60', 'CX60': 'CX60', 'CX-90': 'CX90', 'CX90': 'CX90',
    'CX-5': 'CX5', 'CX5': 'CX5',
    'ARRIZO': 'ARRIZO', 'TIGGO 2': 'TIGGO 2', 'TIGGO 4': 'TIGGO 4',
    'TIGGO 7': 'TIGGO 7', 'TIGGO 8': 'TIGGO 8', 'HIMLA': 'HIMLA',
    '1500': 'RAM 1500', '700': 'RAM 700',
}


def familia_orgu(nombre):
    """Familia canónica de un modelo de marca ORGU, o None si no reconoce el patrón."""
    u = str(nombre or '').upper().strip()
    for kw, fam in MODELO_FAM_ORGU.items():
        if kw in u:
            return fam
    return None


def _extract_traffic_meta_marcas(path):
    path = _resolve_local(path)
    """Lee sección 'PRESUPUESTO DE TRÁFICO POR CONCESIONARIO MARKETING' de METAS_MARCAS.
    Devuelve {brand_key: {meta_total, matrix_meta {modelo: {ag: meta}}, per_agencia}}.
    Regla ORGU: SIEMPRE usar sección MARKETING.
    """
    try:
        xl = pd.ExcelFile(path)
        sh = 'METAS_MARCAS' if 'METAS_MARCAS' in xl.sheet_names else 'METAS_OM'
        df = pd.read_excel(path, sheet_name=sh, header=None)
    except Exception:
        return {}
    AGS = ['CJA','Orellana','La Y','Tumbaco','Manta','Machala','Portoviejo']
    # Find MARKETING header
    h = None
    for i in range(len(df)):
        v = df.iloc[i, 0]
        if isinstance(v, str) and 'TRÁFICO' in v.upper() and 'MARKETING' in v.upper():
            h = i; break
    if h is None: return {}
    BRAND_KEY = {'DONG FENG':'DONGFENG_ORGU','DONGFENG':'DONGFENG_ORGU',
                 'MAZDA':'MAZDA_ORGU','CHERY':'CHERY_ORGU','RAM':'RAM_ORGU'}
    MODELO_FAM = {
        'HUGE':'HUGE','MAGE':'MAGE','PALADIN':'PALADIN',
        'RICH 6':'RICH 6','RICH 7':'RICH 7','Z9':'Z9',
        'BT-50':'NEW BT-50','BT50':'NEW BT-50',
        'CX-30':'CX30','CX30':'CX30','CX-3':'CX3',
        'CX-60':'CX60','CX60':'CX60','CX-90':'CX90','CX90':'CX90','CX-5':'CX5','CX5':'CX5',
        'ARRIZO':'ARRIZO','TIGGO 2':'TIGGO 2','TIGGO 4':'TIGGO 4',
        'TIGGO 7':'TIGGO 7','TIGGO 8':'TIGGO 8','HIMLA':'HIMLA',
        '1500':'RAM 1500','700':'RAM 700',
    }
    def model_to_fam(name):
        u = str(name or '').upper().strip()
        for kw, fam in MODELO_FAM.items():
            if kw in u: return fam
        return None
    out = {}
    current_brand = None
    for i in range(h+2, min(h+50, len(df))):
        label = df.iloc[i, 0]
        if pd.isna(label): continue
        u = str(label).strip().upper()
        if u == 'TOTAL': break
        matched = None
        for kw, bk in BRAND_KEY.items():
            if kw in u and len(u) <= len(kw) + 2:
                matched = bk; break
        if matched:
            current_brand = matched
            if current_brand not in out: out[current_brand] = {'meta_total':0,'matrix_meta':{},'per_agencia':{a:0 for a in AGS}}
            continue
        if not current_brand: continue
        fam = model_to_fam(label)
        if not fam: continue
        row_matrix = out[current_brand]['matrix_meta'].setdefault(fam, {a:0 for a in AGS})
        for ag_idx, ag in enumerate(AGS, start=2):
            v = df.iloc[i, ag_idx]
            if pd.notna(v):
                try:
                    iv = int(round(float(v)))
                    row_matrix[ag] += iv
                    out[current_brand]['per_agencia'][ag] += iv
                    out[current_brand]['meta_total'] += iv
                except (ValueError, TypeError): pass
    return out

_FORD_MKTG_SECTION = 'PRESUPUESTO DE TRÁFICO POR CONCESIONARIO MARKETING'
_FORD_AG_ORDER = ['CJA', 'Orellana', 'LA Y', 'Tumbaco', 'Manta', 'Machala', 'Portoviejo']

def _canon_ford_model(name):
    """Nombre de versión del Excel → modelo canónico. F-150 antes que Ranger porque
    'F-150 RAPTOR' contiene 'RAPT' y 'All new ranger' contiene 'RANGER'."""
    u = str(name).strip().upper()
    if not u or u == 'NAN':          return None
    if u.startswith(('F-150', 'F150')): return 'F-150'
    if 'RANGER' in u:                return 'RANGER'
    for m in ('TERRITORY', 'ESCAPE', 'EVEREST', 'EXPLORER', 'EXPEDITION', 'BRONCO'):
        if u.startswith(m):          return m
    return None

def _load_ford_metas_marketing(path):
    """Lee la matriz del bloque MARKETING (80%) de la hoja METAS_FORD, ubicando las
    columnas POR NOMBRE.

    Es la fuente oficial de la meta. Las hojas por agencia la copian por posición
    fija, así que cuando alguien reordena columnas en METAS_FORD quedan corridas:
    en el archivo de agosto 2026 movieron Machala del puesto 6 al 3 y La Y,
    Tumbaco, Manta y Machala terminaron leyendo la meta del vecino. Julio, con el
    orden viejo, da idéntico por las dos vías.
    Devuelve None si no encuentra la sección o alguna columna (→ cae a las hojas).
    """
    try:
        df = pd.read_excel(path, sheet_name='METAS_FORD', header=None)
    except Exception:
        return None
    hi = next((i for i in range(len(df))
               if str(df.iloc[i, 0]).strip().upper().startswith(_FORD_MKTG_SECTION)), None)
    if hi is None:
        return None
    hdr = [str(x).strip().upper() for x in df.iloc[hi + 1].tolist()]
    try:
        cols = {ag: hdr.index(ag.upper()) for ag in _FORD_AG_ORDER}
    except ValueError:
        return None
    out = {m: [0.0] * 7 for m in MODEL_ORDER}
    for i in range(hi + 2, len(df)):
        n0 = str(df.iloc[i, 0]).strip()
        if n0.upper() == 'TOTAL':
            break
        m = _canon_ford_model(n0)
        if not m:
            continue
        for j, ag in enumerate(_FORD_AG_ORDER):
            v = df.iloc[i, cols[ag]]
            if pd.notna(v):
                # Se redondea CADA versión antes de sumar, igual que el cuadro verde,
                # que muestra celdas ya redondeadas (10.67 → 11). Sumar los decimales
                # y redondear al final daba 1-2 unidades menos por modelo.
                try: out[m][j] += round(float(v))
                except (ValueError, TypeError): pass
    return {m: [int(x) for x in v] for m, v in out.items()}

def load_ford_metas(path):
    path = _resolve_local(path)
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

    # La sección MARKETING manda: es la meta oficial y se lee por nombre de columna.
    mk = _load_ford_metas_marketing(path)
    if mk:
        for j, ag in enumerate(_FORD_AG_ORDER):
            a = sum(mk[m][j] for m in MODEL_ORDER)
            b = sum(out[m][j] for m in MODEL_ORDER)
            if abs(a - b) > 2:
                print(f'[ford_metas] {Path(path).name}: hoja "{ag}" dice {b} y la sección '
                      f'MARKETING dice {a} — se usa {a} (la hoja copia por posición fija)')
        return mk
    print(f'[ford_metas] {Path(path).name}: sin sección MARKETING, se usan las hojas por agencia')
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
    # MAZDA y RAM: sí venden en Portoviejo pero no gestionan tráfico → solo Machala
    # en el reporte para no distorsionar cumplimiento (Daniel 2026-07-24).
    'MAZDA_ORGU':    ['Machala'],
    'RAM_ORGU':      ['Machala'],
}
BRAND_DEALER_PATTERNS = {
    'DONGFENG_ORGU': {'La Y': 'LA Y',   'Machala': 'MACHALA'},
    'CHERY_ORGU':    {'Machala': 'MACHALA'},
    'MAZDA_ORGU':    {'Machala': 'MACHALA'},
    'RAM_ORGU':      {'Machala': 'MACHALA'},
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
def _brand_meta_row_lookup(brand, label):
    """Resuelve el label de una fila del Excel de metas a su modelo del panel.
    1) match exacto; 2) prefijo más largo (el archivo agrega variantes al final:
    'Mage EV'/'Mage FHEV' → 'Mage'). Sin esto esas filas se perdían y la meta
    de DongFeng salía 157 en vez de 170 (bug 29-jul).
    """
    rows = BRAND_META_ROWS.get(brand) or {}
    if label in rows:
        return rows[label]
    lab_u = label.upper()
    best_k = None
    for k in rows:
        ku = k.upper()
        if lab_u.startswith(ku) and (best_k is None or len(ku) > len(best_k)):
            best_k = ku
    if best_k:
        for k, v in rows.items():
            if k.upper() == best_k:
                return v
    return None


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
        'CX-30 Core 2.0': 'CX30',
        'CX-5 Core 2.0': 'CX5', 'CX-5 High 2.0': 'CX5',
        'CX-60 Core 2.5': 'CX60',
        'CX-90 Core 3.3': 'CX90',
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
    path = _resolve_local(path)
    """Parse METAS_MARCAS: returns {brand: {modelo_display: {agency: meta}}}
    Sheet has 3 sections: VENTAS, PRESUPUESTO DE TRÁFICO, PRESUPUESTO DE TRÁFICO MARKETING.
    We use PRESUPUESTO DE TRÁFICO MARKETING (80% marketing budget) — el que aplica al panel.
    """
    try:
        xl = pd.ExcelFile(path)
        sh = 'METAS_MARCAS' if 'METAS_MARCAS' in xl.sheet_names else 'METAS_OM'
        df = pd.read_excel(path, sheet_name=sh, header=None)
    except Exception:
        return {b: {} for b in BRANDS}
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
    # Pick "PRESUPUESTO DE TRÁFICO ... MARKETING" — regla ORGU (Daniel confirmó).
    start = None
    for i, title in headers:
        t = title.upper()
        if 'PRESUPUESTO' in t and 'TRÁFICO' in t and 'MARKETING' in t:
            start = i + 1; break
    if start is None:
        # fallback: first section con PRESUPUESTO DE TRÁFICO (no MARKETING)
        for i, title in headers:
            t = title.upper()
            if 'PRESUPUESTO' in t and 'TRÁFICO' in t:
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
            display = _brand_meta_row_lookup(active, label)
            if display is None: continue
            if display not in metas[active]:
                metas[active][display] = {a: 0.0 for a in AGENCIES}
            for col_idx, ag in enumerate(AGENCIES, start=2):
                val = df.iloc[i, col_idx]
                if pd.notna(val):
                    # Acumular FLOAT y redondear al final: el archivo trae fracciones
                    # (5.333 por celda) y redondear celda a celda pierde unidades.
                    try: metas[active][display][ag] += float(val)
                    except (ValueError, TypeError): pass
    # Redondeo que PRESERVA EL TOTAL por agencia (método del mayor residuo):
    # el archivo trae fracciones (5.333 por modelo) y redondear cada una por separado
    # perdía unidades — Mazda Machala daba 31 en vez de 32 (bug 29-jul).
    for b in metas:
        for ag in AGENCIES:
            vals = {disp: float(metas[b][disp].get(ag, 0) or 0) for disp in metas[b]}
            total_exacto = int(round(sum(vals.values())))
            base = {d: int(v // 1) for d, v in vals.items()}
            faltan = total_exacto - sum(base.values())
            # Repartir las unidades faltantes a los modelos con mayor parte decimal
            orden = sorted(vals, key=lambda d: (vals[d] - base[d]), reverse=True)
            for d in orden[:max(0, faltan)]:
                base[d] += 1
            for d in metas[b]:
                metas[b][d][ag] = base[d]
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
    # Misma familia canónica que las metas, o el modelo se parte en dos filas.
    df['MODELO_F'] = df['MODELO_F'].apply(lambda x: familia_orgu(x) or x)
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
    # ── 2025 ene-sep ──────────────────────────────────────────────────────────
    # Cargados 17-ago-2026 desde Agosto/BD_AGOSTO. El prefijo del nombre no es
    # confiable (hay archivos "BD_SEP_" con fecha de julio y de agosto): el mes se
    # verificó leyendo la columna FECHA de cada archivo. Tres meses venían
    # duplicados y se tomó el más completo:
    #   junio  → BD_JUN_30_06_25 (761) sobre BD_JUN_31_06_25 (754)
    #   julio  → BD_SEP_31_07_25 (803) sobre BD_JUL_30_07_25 (801)
    #   agosto → BD_SEP_31_08_25 (645) sobre BD_AGO_31_08_25 (639)
    # Sin metas: no existe archivo de presupuesto 2025, así que el cumplimiento
    # queda en N/A y solo se usa el tráfico como histórico comparable.
    {"key": "enero_2025", "label": "Enero 2025", "month": 1, "year": 2025, "cut_day": 31,
     "curr_file": "../Agosto/BD_AGOSTO/BD_ENE_31_01_25.xlsx",
     "prev_file": "../Agosto/BD_AGOSTO/BD_ENE_31_01_25.xlsx",
     "prev_date": "31/01/2025", "no_metas": True},
    {"key": "febrero_2025", "label": "Febrero 2025", "month": 2, "year": 2025, "cut_day": 28,
     "curr_file": "../Agosto/BD_AGOSTO/BD_FEB_28_02_25.xlsx",
     "prev_file": "../Agosto/BD_AGOSTO/BD_ENE_31_01_25.xlsx",
     "prev_date": "31/01/2025", "no_metas": True},
    {"key": "marzo_2025", "label": "Marzo 2025", "month": 3, "year": 2025, "cut_day": 31,
     "curr_file": "../Agosto/BD_AGOSTO/BD_MAR_31_03_25.xlsx",
     "prev_file": "../Agosto/BD_AGOSTO/BD_FEB_28_02_25.xlsx",
     "prev_date": "28/02/2025", "no_metas": True},
    {"key": "abril_2025", "label": "Abril 2025", "month": 4, "year": 2025, "cut_day": 30,
     "curr_file": "../Agosto/BD_AGOSTO/BD_ABR_31_04_25.xlsx",
     "prev_file": "../Agosto/BD_AGOSTO/BD_MAR_31_03_25.xlsx",
     "prev_date": "31/03/2025", "no_metas": True},
    {"key": "mayo_2025", "label": "Mayo 2025", "month": 5, "year": 2025, "cut_day": 31,
     "curr_file": "../Agosto/BD_AGOSTO/BD_MAY_30_05_25.xlsx",
     "prev_file": "../Agosto/BD_AGOSTO/BD_ABR_31_04_25.xlsx",
     "prev_date": "30/04/2025", "no_metas": True},
    {"key": "junio_2025", "label": "Junio 2025", "month": 6, "year": 2025, "cut_day": 30,
     "curr_file": "../Agosto/BD_AGOSTO/BD_JUN_30_06_25.xlsx",
     "prev_file": "../Agosto/BD_AGOSTO/BD_MAY_30_05_25.xlsx",
     "prev_date": "31/05/2025", "no_metas": True},
    {"key": "julio_2025", "label": "Julio 2025", "month": 7, "year": 2025, "cut_day": 31,
     "curr_file": "../Agosto/BD_AGOSTO/BD_SEP_31_07_25.xlsx",
     "prev_file": "../Agosto/BD_AGOSTO/BD_JUN_30_06_25.xlsx",
     "prev_date": "30/06/2025", "no_metas": True},
    {"key": "agosto_2025", "label": "Agosto 2025", "month": 8, "year": 2025, "cut_day": 31,
     "curr_file": "../Agosto/BD_AGOSTO/BD_SEP_31_08_25.xlsx",
     "prev_file": "../Agosto/BD_AGOSTO/BD_SEP_31_07_25.xlsx",
     "prev_date": "31/07/2025", "no_metas": True},
    {"key": "septiembre_2025", "label": "Septiembre 2025", "month": 9, "year": 2025, "cut_day": 30,
     "curr_file": "../Agosto/BD_AGOSTO/BD_SEP_30_09_25.xlsx",
     "prev_file": "../Agosto/BD_AGOSTO/BD_SEP_31_08_25.xlsx",
     "prev_date": "31/08/2025", "no_metas": True},
    {"key": "octubre_2025", "label": "Octubre 2025", "month": 10, "year": 2025, "cut_day": 31,
     "curr_file": "../Julio/BD_JULIO/BD_OCT_31_10_25.xlsx",
     "prev_file": "../Julio/BD_JULIO/BD_OCT_31_10_25.xlsx",
     "prev_date": "31/10/2025", "no_metas": True},
    {"key": "noviembre_2025", "label": "Noviembre 2025", "month": 11, "year": 2025, "cut_day": 30,
     "curr_file": "../Julio/BD_JULIO/BD_NOV_30_11_25.xlsx",
     "prev_file": "../Julio/BD_JULIO/BD_OCT_31_10_25.xlsx",
     "prev_date": "31/10/2025", "no_metas": True},
    {"key": "diciembre_2025", "label": "Diciembre 2025", "month": 12, "year": 2025, "cut_day": 31,
     "curr_file": "../Julio/BD_JULIO/BD_DIC_31_12_25.xlsx",
     "prev_file": "../Julio/BD_JULIO/BD_NOV_30_11_25.xlsx",
     "prev_date": "30/11/2025", "no_metas": True},
    {"key": "enero_2026", "label": "Enero 2026", "month": 1, "year": 2026, "cut_day": 31,
     "curr_file": "../Julio/BD_JULIO/BD_ENE_31_01_26.xlsx",
     "prev_file": "../Julio/BD_JULIO/BD_DIC_31_12_25.xlsx",
     "prev_date": "31/12/2025",
     "ford_metas_file": str(ENE_FORD_METAS_FILE)},
    {"key": "febrero_2026", "label": "Febrero 2026", "month": 2, "year": 2026, "cut_day": 28,
     "curr_file": "../Julio/BD_JULIO/BD_FEB_28_02_26.xlsx",
     "prev_file": "../Julio/BD_JULIO/BD_FEB_28_02_26.xlsx",
     "prev_date": "28/02/2026",
     "ford_metas_file": str(FEB_FORD_METAS_FILE)},
    {"key": "marzo_2026", "label": "Marzo 2026", "month": 3, "year": 2026, "cut_day": 31,
     "curr_file": "../Julio/BD_JULIO/BD_MARZO_31_03_26.xlsx",
     "prev_file": "../Julio/BD_JULIO/BD_MARZO_30_03_26.xlsx",
     "prev_date": "30/03/2026",
     "ford_metas_file": str(MAR_FORD_METAS_FILE)},
    {"key": "abril_2026", "label": "Abril 2026", "month": 4, "year": 2026, "cut_day": 30,
     "curr_file": "../Julio/BD_JULIO/BD_ABR_30_04_26.xlsx",
     "prev_file": "../Julio/BD_JULIO/BD_ABR_29_04_26.xlsx",
     "prev_date": "29/04/2026",
     "ford_metas_file": str(ABR_FORD_METAS_FILE)},
    {"key": "mayo_2026", "label": "Mayo 2026", "month": 5, "year": 2026, "cut_day": 31,
     "curr_file": "../Julio/BD_JULIO/BD_MAY_31_05_26.xlsx",
     "prev_file": "../Julio/BD_JULIO/BD_MAY_29_05_26.xlsx",
     "prev_date": "29/05/2026",
     "ford_metas_file": str(MAY_FORD_METAS_FILE),
     "brand_metas_file": str(MAY_BRAND_METAS_FILE),
     # Override: Sábado 2 de mayo no se trabajó (puente con feriado del Día del Trabajo)
     "extra_non_working_days": [(5, 2)]},
    {"key": "junio_2026", "label": "Junio 2026", "month": 6, "year": 2026, "cut_day": 30,
     "curr_file": "../Junio/BD_JUNIO/BD_JUN_30_06_26.xlsx",
     "prev_file": "../Junio/BD_JUNIO/BD_JUN_28_06_26.xlsx",
     "prev_date": "28/06/2026",
     "ford_metas_file": str(JUN_FORD_METAS_FILE),
     "brand_metas_file": str(JUN_BRAND_METAS_FILE)},
    {"key": "julio_2026", "label": "Julio 2026", "month": 7, "year": 2026, "cut_day": 31,
     "curr_file": "../Julio/BD_JULIO/BD_JUL_31_07_26.xlsx",
     "prev_file": "../Julio/BD_JULIO/BD_JUL_28_07_26.xlsx",
     "prev_date": "28/07/2026",
     "ford_metas_file": str(JUL_FORD_METAS_FILE),
     "brand_metas_file": str(JUL_BRAND_METAS_FILE)},
    # Primer corte de agosto: no hay corte previo del mes, así que prev = curr y el
    # delta arranca en 0 (mismo criterio que se usó en febrero).
    {"key": "agosto_2026", "label": "Agosto 2026", "month": 8, "year": 2026, "cut_day": 31,
     "curr_file": "../Agosto/BD_AGOSTO/BD_AGO_31_08_26.xlsx",
     "prev_file": "../Agosto/BD_AGOSTO/BD_AGO_25_08_26.xlsx",
     "prev_date": "25/08/2026",
     "ford_metas_file": str(AGO_FORD_METAS_FILE),
     "brand_metas_file": str(AGO_BRAND_METAS_FILE)},
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
        if not cfg.get('curr_file'):
            continue
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


DIAS_REINGRESO = 60   # el cliente vuelve a contar recién a los 60 días de su última visita contada

def _build_reingreso_index(months_config):
    """Índice de (cédula, marca, mes) que SÍ cuentan como tráfico.

    Regla ORGU, definida por Daniel 17-ago-2026:
      · Dentro del mismo mes el cliente cuenta UNA vez, entre las veces que entre.
      · Vuelve a contar solo si pasaron >= DIAS_REINGRESO desde su última visita
        CONTADA (no desde la primera). Puede contar 3 o más veces en el año.
      · Se evalúa POR MARCA: mirar un Ford y luego un DongFeng son dos negocios
        distintos aunque sea la misma persona.

    Identidad = cédula. El celular NO agrupa: es del hogar y fusiona personas
    distintas → memoria feedback_orgu_cruce_identidad.
    """
    visitas = {}          # (ced, marca) -> {ym: primera fecha de ese mes}
    for cfg in months_config:
        if not cfg.get('curr_file'):
            continue
        try:
            df = load_raw(BASE / cfg['curr_file'])
        except Exception:
            continue
        ym = f"{cfg['year']:04d}-{cfg['month']:02d}"
        for _, r in df.iterrows():
            ced = _conv_norm_ced(r.get('CEDULA'))
            f = r.get('FECHA')
            if not ced or pd.isna(f):
                continue
            m = visitas.setdefault((ced, _marca_group(r.get('MARCA'))), {})
            if ym not in m or f < m[ym]:
                m[ym] = f
    cuentan = set()
    for (ced, mg), meses in visitas.items():
        ultima = None
        for ym in sorted(meses):
            f = meses[ym]
            if ultima is None or (f - ultima).days >= DIAS_REINGRESO:
                cuentan.add((ced, mg, ym))
                ultima = f
    return cuentan


def _filter_reingreso(df, this_ym, idx):
    """Deja solo los clientes cuyo (cédula, marca, mes) cuenta según la regla.
    Sin cédula se cuenta igual: no se castiga al registro por un dato que falta
    en el origen."""
    if df is None or len(df) == 0 or not idx:
        return df
    keep = [True if not (c := _conv_norm_ced(r.get('CEDULA')))
            else (c, _marca_group(r.get('MARCA')), this_ym) in idx
            for _, r in df.iterrows()]
    return df[keep].copy()


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
    # Índice de reingreso a 60 días. Reemplaza a la vieja "Definición B", que
    # contaba a cada persona una sola vez en todo el histórico.
    print('Construyendo índice de reingreso (60 días, por marca)...')
    _REING_IDX = _build_reingreso_index(MONTHS_CONFIG)
    print(f'  {len(_REING_IDX)} visitas contables indexadas')

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
    brand_meta_breakdown = {}  # {mk: {brand_key: {modelo: {meta_ventas, por_agencia}}}}
    for cfg in MONTHS_CONFIG:
        # Meses sin BD de tráfico aún (ej. julio recién empezó): cargar solo metas
        # y generar entradas mínimas para que aparezcan en Meta Ventas.
        if not cfg.get("curr_file"):
            if cfg.get("ford_metas_file"):
                try:
                    ford_meta_breakdown[cfg["key"]] = load_ford_meta_breakdown(cfg["ford_metas_file"])
                    # Metas de tráfico Ford para mes sin BD aún
                    tot_traf, mat_meta, per_ag_meta = _extract_traffic_meta_from_metas_ford(cfg["ford_metas_file"])
                    if tot_traf > 0:
                        try:
                            _dl, _ = working_days(cfg["month"], cfg["year"],
                                                  extra_non_working=cfg.get("extra_non_working_days"))
                        except Exception: _dl = 26
                        AGS = ['CJA','Orellana','La Y','Tumbaco','Manta','Machala','Portoviejo']
                        ZONE_TO_AGS = {'Quito':['La Y','Tumbaco'],'Guayaquil':['CJA','Orellana'],'Manta':['Manta','Portoviejo'],'Machala':['Machala']}
                        _zones_dict = {}
                        for _z, _ags_z in ZONE_TO_AGS.items():
                            _zones_dict[_z] = {"curr": 0, "prev": 0,
                                                "meta": sum(per_ag_meta.get(a,0) for a in _ags_z),
                                                "dealers": list(_ags_z)}
                        # Pace array (día 1..N) para que widget Avance día a día pinte eje X
                        # y ritmo ideal (todo en 0 antes de que llegue BD).
                        _pace = expected_pace_calendar(cfg["month"], cfg["year"], tot_traf, _dl,
                                                        extra_non_working=cfg.get("extra_non_working_days"))
                        ford_months[cfg["key"]] = {
                            "month": cfg["month"], "year": cfg["year"], "cut_day": 0,
                            "month_key": cfg["key"],
                            "month_label": cfg.get("label", ""),
                            "cut_date": None, "prev_date": None,
                            "pace": _pace,
                            "days_lab": _dl, "days_trans": 0,
                            "total_curr": 0, "total_prev": 0, "delta_total": 0,
                            "meta_total": tot_traf,
                            "matrix_meta": mat_meta,
                            "matrix_cnt": {m: {a: 0 for a in AGS} for m in MODEL_ORDER},
                            "matrix_cnt_prev": {m: {a: 0 for a in AGS} for m in MODEL_ORDER},
                            "matrix_pct": {m: {a: 0 for a in AGS} for m in MODEL_ORDER},
                            "otros_prev_by_model": {m: 0 for m in MODEL_ORDER},
                            "dealer_model_channel_prev": {a: {m: {} for m in MODEL_ORDER} for a in AGS + ['Otros']},
                            "models": {m: {"curr": 0, "prev": 0, "meta": sum(mat_meta.get(m,{}).values()),
                                            "delta": 0, "projection": 0, "velocity": 0, "cumpl_proj": 0,
                                            "byDealer": {a: 0 for a in AGS}} for m in MODEL_ORDER},
                            "model_order": list(MODEL_ORDER),
                            "dealers": {
                                **{a: {"curr": 0, "prev": 0, "meta": per_ag_meta.get(a,0),
                                        "delta": 0, "projection": 0, "velocity": 0, "cumpl_proj": 0,
                                        "byModel": {m: 0 for m in MODEL_ORDER}} for a in AGS},
                                "Otros": {"curr": 0, "prev": 0, "meta": 0,
                                          "delta": 0, "projection": 0, "velocity": 0, "cumpl_proj": 0,
                                          "byModel": {m: 0 for m in MODEL_ORDER}},
                            },
                            "dealer_order": AGS,
                            "zones": _zones_dict,
                            "zone_order": list(ZONE_TO_AGS.keys()),
                            "dominant_channel": None, "channel_pct": 0,
                            "avance_pct": 0, "velocity": 0, "projection_total": 0,
                            "at_risk_models": [], "at_risk_agencies": [],
                            "movements": [], "daily": {}, "daily_breakdown": {},
                            "daily_dealer_channel": {}, "dealer_model_channel": {},
                            "_traffic_meta_per_agencia": per_ag_meta,
                            "_pending_bd": True,
                        }
                        print(f'[metas] {cfg["key"]} tráfico Ford meta cargada: {tot_traf} uds')
                except Exception as e:
                    print(f'[metas] {cfg["key"]} ford breakdown fail: {e}')
            if cfg.get("brand_metas_file"):
                try:
                    bmb = _parse_brand_meta_breakdown(cfg["brand_metas_file"])
                    brand_meta_breakdown[cfg["key"]] = bmb
                    # META TRÁFICO MARKETING para brands (sección MARKETING del archivo).
                    brand_traf_meta = _extract_traffic_meta_marcas(cfg["brand_metas_file"])
                    try: _dl, _ = working_days(cfg["month"], cfg["year"],
                                                extra_non_working=cfg.get("extra_non_working_days"))
                    except Exception: _dl = 26
                    AGS_ALL = ['CJA','Orellana','La Y','Tumbaco','Manta','Machala','Portoviejo']
                    brands_dict = {}
                    # Iterar sobre las brands que tengan meta traffic O meta_ventas (VENTAS breakdown)
                    all_brand_keys = set(bmb.keys()) | set(brand_traf_meta.keys())
                    for brand_key in all_brand_keys:
                        traf = brand_traf_meta.get(brand_key, {'meta_total':0,'matrix_meta':{},'per_agencia':{a:0 for a in AGS_ALL}})
                        # matrix_meta y per_agencia vienen de la sección TRÁFICO MARKETING
                        matrix_meta_b = traf['matrix_meta'] or {}
                        per_ag = traf['per_agencia']
                        meta_total = traf['meta_total']
                        models_dict = {m: {"curr":0,"prev":0,"meta":sum(matrix_meta_b[m].values()),
                                            "delta":0,"projection":0,"velocity":0,"cumpl_proj":0,
                                            "byDealer":{a:0 for a in AGS_ALL}} for m in matrix_meta_b}
                        dealers_dict = {a: {"curr":0,"prev":0,"meta":per_ag[a],
                                             "delta":0,"projection":0,"velocity":0,"cumpl_proj":0} for a in AGS_ALL}
                        _brand_pace = expected_pace_calendar(cfg["month"], cfg["year"], meta_total, _dl,
                                                              extra_non_working=cfg.get("extra_non_working_days"))
                        brands_dict[brand_key] = {
                            "brand": brand_key, "display": BRAND_DISPLAY.get(brand_key, brand_key.replace('_ORGU','')),
                            "month": cfg["month"], "year": cfg["year"], "cut_day": 0,
                            "cut_date": None, "prev_date": None,
                            "pace": _brand_pace,
                            "model_order": list(matrix_meta_b.keys()),
                            "dealer_order": list(AGS_ALL),
                            "days_lab": _dl, "days_trans": 0,
                            "avance_pct": 0,
                            "total_curr": 0, "total_prev": 0, "delta_total": 0,
                            "velocity": 0, "projection_total": 0,
                            "meta_total": meta_total, "cumpl_proj": 0,
                            "dominant_channel": None, "channel_pct": 0,
                            "models": models_dict, "dealers": dealers_dict,
                            "matrix_pct": {m:{a:-1 for a in AGS_ALL} for m in matrix_meta_b},
                            "matrix_cnt": {m:{a:0 for a in AGS_ALL} for m in matrix_meta_b},
                            "matrix_meta": matrix_meta_b,
                            "at_risk_models": [], "at_risk_agencies": [],
                            "movements": [], "daily": {}, "daily_breakdown": {},
                            "_pending_bd": True,
                        }
                    if brands_dict:
                        brands_months[cfg["key"]] = brands_dict
                        print(f'[metas] {cfg["key"]} brands_months entries vacías creadas ({len(brands_dict)} marcas)')
                except Exception as e:
                    print(f'[metas] {cfg["key"]} brand breakdown fail: {e}')
            continue
        # ► CACHE INCREMENTAL: si el mes ya fue procesado y los BDs no cambiaron, reusar.
        # Cache key: (curr_file_mtime, prev_file_mtime, cfg["cut_day"]). Miss ⇒ compute.
        _cache_path = LOCAL_DATA_DIR / 'cache' / 'months_cache.json'
        _cache = {}
        if _cache_path.exists():
            try: _cache = json.loads(_cache_path.read_text())
            except Exception: _cache = {}
        _cp = _resolve_local(BASE / cfg["curr_file"])
        _pp = _resolve_local(BASE / cfg["prev_file"])
        try:
            # Las metas entran en la llave: si no, cambiar el archivo de metas (o la
            # forma de leerlo) deja el mes servido desde cache con las metas viejas.
            _mt = []
            for _k in ('ford_metas_file', 'brand_metas_file'):
                _f = cfg.get(_k)
                _mt.append(str(Path(_resolve_local(_f)).stat().st_mtime_ns) if _f else '-')
            _cache_key = (f"{Path(_cp).stat().st_mtime_ns}|{Path(_pp).stat().st_mtime_ns}"
                          f"|{cfg['cut_day']}|{'|'.join(_mt)}|v7-familias-orgu")
        except Exception:
            _cache_key = None
        _cached_entry = _cache.get(cfg['key']) if _cache_key else None
        if _cached_entry and _cached_entry.get('_key') == _cache_key:
            print(f'[cache] {cfg["key"]} hit — reusando reporte cacheado')
            ford_months[cfg['key']] = _cached_entry['ford']
            brands_months[cfg['key']] = _cached_entry['brands']
            if _cached_entry.get('ford_meta_breakdown'):
                ford_meta_breakdown[cfg['key']] = _cached_entry['ford_meta_breakdown']
            if _cached_entry.get('brand_meta_breakdown'):
                brand_meta_breakdown[cfg['key']] = _cached_entry['brand_meta_breakdown']
            continue
        curr_raw = load_raw(BASE / cfg["curr_file"])
        prev_raw = load_raw(BASE / cfg["prev_file"])
        # Si prev usa el mismo archivo acumulativo que curr, filtra prev a la fecha del corte anterior
        if cfg.get("prev_cutoff_date"):
            cutoff = pd.Timestamp(cfg["prev_cutoff_date"])
            prev_raw = prev_raw[prev_raw["FECHA"] < cutoff].copy()
        # El tráfico cuenta TODAS las visitas, cada una en su mes. Un cliente que
        # entró en enero y volvió en marzo es tráfico de enero Y de marzo: se
        # enfrió y volvió a entrar, así que la agencia lo atendió dos veces.
        #
        # Antes se aplicaba "Definición B" (cada persona solo en su primer mes de
        # toque) y eso metía un sesgo que crecía con el histórico: en octubre-25
        # descartaba 0 y en julio-26 ya descartaba 128 registros (12%). Julio no
        # bajó de 1.099 a 971 por menos afluencia, sino por acumulación de historia.
        # Confirmado por Daniel 17-ago-2026.
        #
        # La lógica de primer toque sigue viva en conversión, donde sí corresponde:
        # ahí se mide "de los que entraron en marzo, cuántos compraron" y contar a
        # la misma persona como oportunidad nueva cada mes diluiría la tasa.
        this_ym = f"{cfg['year']:04d}-{cfg['month']:02d}"
        curr_raw = _filter_reingreso(curr_raw, this_ym, _REING_IDX)
        prev_raw = _filter_reingreso(prev_raw, this_ym, _REING_IDX)
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
            # Brand meta_ventas breakdown (hoja METAS_OM del mismo archivo)
            try:
                bb = _parse_brand_meta_breakdown(Path(bmetas_file))
                if bb:
                    brand_meta_breakdown[cfg["key"]] = bb
            except Exception as e:
                print(f'[brand_meta_breakdown] WARN mes {cfg["key"]}: {e}')
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
        # Persistir en cache incremental (evita recomputar meses sin cambios en próxima corrida)
        if _cache_key:
            _cache[cfg['key']] = {
                '_key': _cache_key,
                'ford': f,
                'brands': bd,
                'ford_meta_breakdown': ford_meta_breakdown.get(cfg['key']),
                'brand_meta_breakdown': brand_meta_breakdown.get(cfg['key']),
            }
            _cache_path.parent.mkdir(parents=True, exist_ok=True)
            _cache_path.write_text(json.dumps(_cache, ensure_ascii=False, default=str))

    # Default = último mes con BD (evita entries pending como default seguro).
    default_key = next((c["key"] for c in reversed(MONTHS_CONFIG)
                        if c["key"] in ford_months and c["key"] in brands_months and c.get("curr_file")),
                       MONTHS_CONFIG[-1]["key"])
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
        "brand_meta_breakdown": brand_meta_breakdown,
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
        # Arribos supply-chain (ETD/ETA/FACT) — data de embarques futuros y históricos.
        "arribos": (lambda: (__import__('arribos').load_arribos()))(),
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
                    bd_dir=str(LOCAL_DATA_DIR / 'bd') if (LOCAL_DATA_DIR / 'bd').exists() else str(BASE / '../Julio/BD_JULIO'),
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
            }) if _ventas is not None else None)(__import__('ventas').load_ventas_completo())
        ),
        # Panel de Ventas mensual · pivot por marca/modelo/asesor con NETOS (sum Cantidad).
        # Permite ver ventas mes a mes y desplegar por modelo o por asesor comercial.
        "ventas_mensual": _compute_ventas_mensual(__import__('ventas').load_ventas()),
        # Presupuesto de pauta digital por modelo, mes y zona. Es lo PLANIFICADO
        # (los Excel mensuales de OneDrive), no lo ejecutado en Ads Manager.
        "pauta": (lambda: (lambda m: m.build_pauta())(__import__('pauta')))(),
        # Nodo hermano, NO dentro de ventas_mensual: el panel hace
        # Object.keys(VENTAS_MENSUAL) y trata cada clave como una marca, así que
        # una nota ahí adentro saldría como marca fantasma en el selector.
        "ventas_mensual_doc": {
            "by_agencia": "CIFRA OFICIAL. Vitrina que emitió la factura — la base que "
                          "cuadra contra finanzas (hoja DATOS 2 del reporte de inventario, "
                          "agrupada por Descripcion Bodega y restando notas de crédito). "
                          "Ford La Y ene-jul 2026 = 48 unidades.",
            "by_agencia_fact": "Alias de by_agencia. Se mantiene por compatibilidad.",
            "by_agencia_equipo": "Agencia del EQUIPO del asesor: la venta cuenta para su "
                                 "casa (la vitrina donde más factura en positivo). Existe "
                                 "por el efecto placa — el cliente prefiere placa de "
                                 "Pichincha, así que ventas originadas en Machala o Manta "
                                 "se facturan vía La Y o Tumbaco. Sirve para medir al "
                                 "equipo comercial, NO para cuadrar contra finanzas. "
                                 "Ford La Y ene-jul 2026 = 35 unidades.",
            "para_cruzar_con_trafico": "Usar by_agencia (vitrina). El tráfico se registra "
                                       "donde entró la persona, así que las dos bases "
                                       "coinciden.",
            "campos_flat": "Cada fila trae 'agencia' (vitrina, oficial), 'agencia_fact' "
                           "(alias) y 'agencia_equipo'. Los totales de red coinciden entre "
                           "las dos bases; el reparto por agencia no.",
        },
        # Presupuestos BP2026 (financiero = piso, comercial = techo) por
        # marca/agencia/mes. Alimenta la banda y el cumplimiento en Ventas Históricas.
        "presupuesto": __import__('presupuesto').load_presupuesto(),
        # matrix_meta carga la meta marketing (80%). Para escalar la meta cuando se
        # filtra por categoría de canal en la pestaña Otros, JS aplica estos ratios.
        "meta_split": {
            "marketing_pct": META_MARKETING_PCT,   # 0.80
            "asesor_pct":    META_ASESOR_PCT,      # 0.20
            "base_in_matrix_meta": "marketing",    # qué representa matrix_meta
        },
    }
    # ── Ventas del cruce: la cifra OFICIAL, no un reconteo del inventario ──────
    # monthly_cross contaba las facturas presentes en el snapshot de inventario, y una
    # unidad vendida y entregada hace meses ya no está en esa foto: el cruce mostraba
    # 542 unidades Ford ene-jul contra las 635 de la pestaña Ventas (-15%), y junio
    # salía 71 ("incumplió") contra 110 ("cumplió"). Es la misma familia del bug de
    # snapshots ya corregido en ventas.py, _compute_ventas_mensual y checks_asesores;
    # este era el cuarto archivo que quedó fuera.
    #
    # Se sobrescribe con ventas_mensual, que sale de DATOS 2 y cuadra con finanzas.
    try:
        _mc = (out.get("inventario") or {}).get("monthly_cross") or {}
        _vm = out.get("ventas_mensual") or {}
        _MARCA_INV = {"FORD": "FORD", "DONGFENG_ORGU": "DONGFENG", "CHERY_ORGU": "CHERY",
                      "MAZDA_ORGU": "MAZDA", "RAM_ORGU": "RAM"}
        _reemplazos = 0
        for _marca, _meses in _mc.items():
            _flat = ((_vm.get(_marca) or {}).get("flat")) or []
            if not _flat:
                continue
            # {ym: total}, {(ym, familia): n}, {(ym, familia, agencia): n}
            _tot, _porMod, _porModAg = {}, {}, {}
            for _r in _flat:
                _ym = str(_r.get("mes") or "")
                if not _ym:
                    continue
                _q = _r.get("cantidad") or 0
                # El TOTAL del mes suma SIEMPRE, aunque el modelo no normalice: si no,
                # una descripción rara se cae del total y el cruce vuelve a diferir de
                # la pestaña Ventas (así perdía 2 unidades en dic-2025).
                _tot[_ym] = _tot.get(_ym, 0) + _q
                _f = normalize_familia(_r.get("modelo"), _MARCA_INV.get(_marca, _marca))
                if not _f:
                    continue
                _ag = _r.get("agencia")
                _porMod[(_ym, _f)] = _porMod.get((_ym, _f), 0) + _q
                if _ag:
                    _porModAg[(_ym, _f, _ag)] = _porModAg.get((_ym, _f, _ag), 0) + _q
            for _mk, _mv in _meses.items():
                _ym = str(_mv.get("mes_start") or "")[:7]
                if not _ym:
                    continue
                _mv["ventas"] = int(round(_tot.get(_ym, 0)))
                for _mod, _md in (_mv.get("por_modelo") or {}).items():
                    _md["ventas"] = int(round(_porMod.get((_ym, _mod), 0)))
                    for _ag, _ad in (_md.get("por_agencia") or {}).items():
                        _ad["ventas"] = int(round(_porModAg.get((_ym, _mod, _ag), 0)))
                _reemplazos += 1
        print(f"[monthly_cross] ventas tomadas de ventas_mensual en {_reemplazos} mes×marca")
    except Exception as _e:
        print(f"[monthly_cross] WARN no se pudo reconciliar ventas: {_e}")

    # Merge de inversión publicitaria Xiy (si existe data_xiy.json con el bloque
    # consolidated_for_panel listo). Lo metemos como out["xiy"] para que el panel
    # lo lea desde DATA.xiy en el tab Inversión.
    # El repo salió de OneDrive y esta ruta se quedó apuntando al lugar viejo, así
    # que el nodo `xiy` no se generaba y los tres filtros de Inversión Digital
    # quedaban muertos (xiyInitFilters hace `return` sin _lines_flat). Se busca
    # primero junto al script.
    xiy_path = Path(__file__).resolve().parent / "data_xiy.json"
    if not xiy_path.exists():
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
    # Lee digital.json del directorio del script (lo escribe el cron horario
    # digital_hourly.sh). Antes apuntaba a la carpeta de OneDrive: tras la mudanza a
    # ~/dev/ dejó de encontrarlo y las pestañas Seguimiento Digital (Ford y DF)
    # quedaron sin DATA.digital — lo que además desactiva el re-fetch en runtime.
    digital_path = Path(__file__).resolve().parent / "digital.json"
    if digital_path.exists():
        try:
            with open(digital_path, "r", encoding="utf-8") as f:
                out["digital"] = json.load(f)
            print(f"Merged digital snapshot from {digital_path.name}")
        except Exception as e:
            print(f"WARN: failed to load {digital_path}: {e}")
    else:
        print(f"INFO: no digital.json at {digital_path}; tab Seguimiento Digital quedará vacío")

    # Escribir data.json al directorio del script (~/dev/panel-trafico/), no a OneDrive
    # Mix por versión: cruza el presupuesto contra las ventas reales ya calculadas.
    if out.get('presupuesto'):
        from presupuesto import build_mix
        out['presupuesto']['mix'] = build_mix(out['presupuesto'], out.get('ventas_mensual'))

    # ► IDENTIDAD ÚNICA DEL ASESOR. Regla de Daniel: una persona = una fila, sin
    # importar cómo esté escrito el nombre. En el origen conviven 98 grafías para
    # 64 personas — Doménica en cuatro formas, Karen y Anthony en tres. Sin este
    # pase cada grafía abría su propia fila con los números partidos.
    # Va ANTES de marcar a los salidos, para que el badge caiga sobre el nombre
    # canónico y no sobre un alias que ya no existe.
    try:
        import asesores as _ases
        _pers, _alias, _celdas = _ases.canonizar(out)
        if _alias:
            print(f'[asesores] identidad única: {_pers} personas · '
                  f'{_alias} grafías fusionadas · {_celdas} celdas reescritas')
    except Exception as _e:
        print('[asesores] WARN no se pudo canonizar:', _e)

    # ► Asesores que ya salieron de la red. Se resuelven CONTRA EL OUTPUT YA ARMADO
    # para cubrir todas las grafías que de verdad quedaron (Karen vive en 3, Ivana
    # en 3 incluida un typo). El panel solo hace lookup exacto: si mañana aparece
    # una grafía nueva, la recoge el próximo aggregate y no hay que tocar el JS.
    try:
        from asesores_salidos import resolver as _resolver_salidos
        _nombres = set()

        def _rec_asesores(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if 'asesor' in str(k).lower():   # hay dicts con claves int
                        if isinstance(v, str):
                            _nombres.add(v)
                        elif isinstance(v, dict):
                            _nombres.update(x for x in v if isinstance(x, str))
                    _rec_asesores(v)
            elif isinstance(o, list):
                for v in o:
                    _rec_asesores(v)

        _rec_asesores(out)
        out['asesores_salidos'] = _resolver_salidos(n for n in _nombres if n and len(n) > 3)
        print(f"[asesores] {len(set(out['asesores_salidos'].values()))} salidos "
              f"· {len(out['asesores_salidos'])} grafías marcadas")
    except Exception as _e:
        print('[asesores] WARN no se pudo marcar salidos:', _e)
        out['asesores_salidos'] = {}

    # ► El corte de VENTAS viaja aparte del de tráfico e inventario: cada vista usa
    # el de su propia fuente para decidir qué meses están cerrados.
    if VENTAS_CORTE:
        out['ventas_corte'] = VENTAS_CORTE
        print(f'[ventas_mensual] corte de ventas: {VENTAS_CORTE}')

    outpath = Path(__file__).parent / "data.json"
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
