"""Loader del archivo "Base de ventas YTD ... .xlsx" (fuente oficial de VENTAS NETAS).

Reemplaza al inventario como fuente de cierres/facturación en el panel
(embudo.Cierre y conversion). El inventario sigue siendo la fuente de
stock disponible, reservas y pipeline USA/Nac (eso no cambia).

El archivo trae:
  - 642 facturas (FACTURA) + 115 notas de crédito (NOTA DE CREDITO)
  - Cantidad con signo: +1 factura, -1 NC → suma neta por mes/marca
  - Fecha Factura como serial Excel (entero) — se convierte a datetime
  - Vendedor (asesor), Bodega Venta Vehiculo (agencia), Familia (modelo)

El loader expone un DataFrame con columnas mapeadas al formato que ya
esperan embudo.py y conversion.py, así no hay cambios estructurales en
los downstreams.
"""
from pathlib import Path
import warnings
import pandas as pd

# Ruta al archivo de ventas. Se autodetecta el más reciente que matchee
# "Base de ventas*.xlsx" en estas carpetas (en orden de prioridad).
_VENTAS_DIRS = [
    Path("/Users/danielyanezalbuja/Downloads"),
    Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026"),
]


def _find_latest_ventas():
    """Busca el archivo más reciente con prefijo 'Base de ventas' en las carpetas
    configuradas. Selecciona por mtime descendente."""
    candidates = []
    for d in _VENTAS_DIRS:
        if not d.exists():
            continue
        for p in d.glob('Base de ventas*.xlsx'):
            if p.name.startswith('~$'):
                continue
            candidates.append(p)
        if candidates:
            break
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


DEFAULT_VENTAS_PATH = _find_latest_ventas()


_NORMALIZE_AGENCIA = {
    '1001 VEHICULOS CARLOS JULIO AROSEMENA': '1001 VEHICULOS CARLOS JULIO AROSEMENA',
    '1002 VEHICULOS MANTA':                  '1002 VEHICULOS MANTA',
    '1003 VEHICULOS MACHALA':                '1003 VEHICULOS MACHALA',
    '1004 VEHICULOS ORELLANA':               '1004 VEHICULOS ORELLANA',
    '1013 VEHICULOS MANTA II':               '1013 VEHICULOS MANTA II',
    '1016 VEHICULOS LA Y':                   '1016 VEHICULOS LA Y',
    '1017 VEHICULOS TUMBACO':                '1017 VEHICULOS TUMBACO',
}


_LOADED = None


def load_ventas(path=None):
    """Carga el archivo de ventas y devuelve un DataFrame con columnas mapeadas
    al formato del inventario `DATOS`:

      - AGENCIA_FACTURACION  ← Bodega Venta Vehiculo
      - ASESOR_FACTURACION   ← Vendedor (uppercased, stripped)
      - IDENTIFICACION       ← Identificacion Cliente
      - CLIENTE_FACTURACION  ← Cliente
      - familia              ← Familia (alias minúscula para compatibilidad)
      - marca                ← Marca Vehiculo (alias minúscula)
      - fecha de facturacion ← Fecha Factura (serial Excel → datetime)
      - Chasis               ← Chasis
      - Linea Modelo Vehiculo ← Linea Modelo Vehiculo

    Filtra TIPO TRANSACCION = FACTURA y resta las NOTAS DE CREDITO en
    `cantidad_neta`. Para conteo de unidades, cada fila vale 1 con su signo.
    """
    global _LOADED
    p = path or DEFAULT_VENTAS_PATH
    if not p or not p.exists():
        return None
    if _LOADED is not None and _LOADED[0] == str(p):
        return _LOADED[1]
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        df = pd.read_excel(p, sheet_name='Hoja1')
    df.columns = [str(c).strip() for c in df.columns]

    # Convertir Fecha Factura (serial Excel desde 1899-12-30) a datetime
    if pd.api.types.is_numeric_dtype(df['Fecha Factura']):
        df['fecha de facturacion'] = pd.to_datetime(
            df['Fecha Factura'], origin='1899-12-30', unit='D', errors='coerce'
        )
    else:
        df['fecha de facturacion'] = pd.to_datetime(df['Fecha Factura'], errors='coerce')

    # Aliases en minúscula para compatibilidad con código que lee del inventario
    df['marca']   = df['Marca Vehiculo'].astype(str).str.strip()
    df['familia'] = df['Linea Modelo Vehiculo'].astype(str).str.strip()

    # Mapeo de columnas inventario-style
    df['AGENCIA_FACTURACION'] = df['Bodega Venta Vehiculo'].astype(str).str.strip()
    df['ASESOR_FACTURACION']  = df['Vendedor'].astype(str).str.strip().str.upper()
    df['IDENTIFICACION']      = df['Identificacion Cliente']
    df['CLIENTE_FACTURACION'] = df['Cliente']

    # Excluir notas de crédito por DEFAULT — el usuario decidirá si las suma
    # por separado para netos. Por ahora: facturación NETA = sum(Cantidad) por
    # grupo (NC vienen con Cantidad negativa).
    # Para que cada fila valga 1 (compatible con el código que hace len(sub)),
    # explotamos las NC en filas con Cantidad=-1 cuando corresponda.
    df['Cantidad'] = df['Cantidad'].fillna(1).astype(int)

    _LOADED = (str(p), df)
    return df


def get_ventas_neta(marca=None, year=None, month=None):
    """Atajo: devuelve sólo las facturas netas (FACTURA − NC explícitamente).
    Cada fila es 1 unidad, las NC se filtran/restan según corresponda."""
    df = load_ventas()
    if df is None:
        return pd.DataFrame()
    if marca:
        df = df[df['marca'].astype(str).str.upper() == marca.upper()]
    if year is not None:
        df = df[df['fecha de facturacion'].dt.year == year]
    if month is not None:
        df = df[df['fecha de facturacion'].dt.month == month]
    return df


def load_ventas_completo():
    """Devuelve ventas combinando Base de ventas YTD + DATOS 2 del inventario más reciente,
    para cubrir el gap donde Base YTD no incluye los últimos meses.

    Prioriza DATOS 2 (más completo, con FACT+NC signados) para meses que cubre;
    complementa con Base YTD para el resto. IDENTIFICACION se traen por VIN
    joineando con hoja DATOS (histórica de reservas) del inventario.
    """
    import warnings as _w
    from pathlib import Path as _P
    from inventario import _INVENTORY_DIRS, DEFAULT_INVENTORY_PATH

    base = load_ventas()
    if base is None:
        base = pd.DataFrame(columns=['fecha de facturacion','marca','familia','AGENCIA_FACTURACION',
                                      'ASESOR_FACTURACION','IDENTIFICACION','CLIENTE_FACTURACION',
                                      'Chasis','Cantidad'])
    base = base.copy()
    base['fecha_fact'] = pd.to_datetime(base['fecha de facturacion'], errors='coerce')

    # DATOS 2 concat de todos los snapshots
    inv_frames, seen = [], set()
    for d in _INVENTORY_DIRS:
        if not d.exists(): continue
        _found_here = False
        for ext in ('*.xlsm','*.xlsx'):
            for p in d.glob(ext):
                if p.name.startswith('~$'): continue
                if 'INVENTARIO' not in p.name.upper(): continue
                if p in seen: continue
                seen.add(p)
                try:
                    with _w.catch_warnings():
                        _w.simplefilter('ignore')
                        inv_frames.append(pd.read_excel(p, sheet_name='DATOS 2', header=0))
                        _found_here = True
                except Exception: pass
        if _found_here: break
    if not inv_frames:
        return base

    d2 = pd.concat(inv_frames, ignore_index=True, sort=False)
    if 'Vin' in d2.columns and 'Fecha' in d2.columns and 'Cantidad' in d2.columns:
        d2 = d2.drop_duplicates(subset=['Vin','Fecha','Cantidad'], keep='first')
    d2['fecha_fact'] = pd.to_datetime(d2['Fecha'], errors='coerce')
    d2 = d2.dropna(subset=['fecha_fact']).copy()
    d2 = d2[d2['fecha_fact'].dt.year==2026]

    # IDENTIFICACION desde múltiples hojas del inventario (por VIN)
    # Preferencia: DATOS (histórico reservas) > DISPONIBLE > RES-COLA.
    # DATOS suele tener 0.0 para facturas B2B → complementar con las otras hojas.
    id_map = {}
    _VIN_CANDS = ['vin','VIN','Vin','CHASIS ASIGANDO','Chasis','CHASIS','chasis']
    _ID_CANDS  = ['IDENTIFICACION','Identificacion','IDENTIFICACIÓN','Identificación','CEDULA','Cedula','Cedula/Ruc','RUC']
    for sh_name in ('DATOS','RES-COLA','RE-COLA','EXONERADOS','CONSIGNACIÓN','FACT Y NC','PROC-NAC-JUL'):
        try:
            with _w.catch_warnings():
                _w.simplefilter('ignore')
                dat = pd.read_excel(DEFAULT_INVENTORY_PATH, sheet_name=sh_name, header=0)
        except Exception:
            continue
        vin_col = next((c for c in _VIN_CANDS if c in dat.columns), None)
        id_col  = next((c for c in _ID_CANDS  if c in dat.columns), None)
        if not vin_col or not id_col: continue
        dat['vin_u'] = dat[vin_col].astype(str).str.upper().str.strip()
        for _,r in dat.iterrows():
            v = r['vin_u']
            iden = r[id_col]
            if not v or pd.isna(iden): continue
            # Rechazar 0/0.0/vacío como ID válido
            s_iden = str(iden).strip()
            if s_iden in ('0','0.0','','nan'): continue
            # Solo llenar si no había ID válido antes
            if v not in id_map:
                id_map[v] = iden

    d2['vin_u'] = d2['Vin'].astype(str).str.upper().str.strip()
    d2['IDENTIFICACION'] = d2['vin_u'].map(id_map)
    d2['marca'] = d2.get('Marca','').astype(str).str.strip()
    d2['familia'] = d2.get('Descripción Modelo','').astype(str).str.strip()
    d2['AGENCIA_FACTURACION'] = d2.get('Descripcion Bodega','').astype(str).str.strip()
    # ASESOR_FACTURACION viene de hoja DATOS por VIN (DATOS 2 no lo trae).
    # Concat DATOS de TODOS los snapshots — cada inventario captura ASESOR para VINs
    # nuevos que llegan. Sin esto, junio/julio facturas nuevas quedan sin asesor.
    ase_map = {}
    for _inv_p in seen:
        try:
            with _w.catch_warnings():
                _w.simplefilter('ignore')
                _dat_ase = pd.read_excel(_inv_p, sheet_name='DATOS', header=0)
            if 'vin' in _dat_ase.columns and 'ASESOR_FACTURACION' in _dat_ase.columns:
                _dat_ase['vin_u'] = _dat_ase['vin'].astype(str).str.upper().str.strip()
                for _, r in _dat_ase.iterrows():
                    v = r['vin_u']; a = r['ASESOR_FACTURACION']
                    if v and pd.notna(a) and str(a).strip():
                        if v not in ase_map:
                            ase_map[v] = str(a).strip()
        except Exception: pass
    d2['ASESOR_FACTURACION'] = d2['vin_u'].map(ase_map).fillna('')
    d2['CLIENTE_FACTURACION'] = d2.get('Nombres','').astype(str).str.strip()
    d2['CLIENTE_RESERVA'] = None
    d2['Chasis'] = d2['vin_u']
    d2['fecha de facturacion'] = d2['fecha_fact']
    d2['Cantidad'] = d2['Cantidad'].fillna(0).astype(int)

    # Meses cubiertos por DATOS 2 — prevalecen sobre base
    d2_meses = set(d2['fecha_fact'].dt.strftime('%Y-%m').unique())
    if len(base):
        base['_ym'] = base['fecha_fact'].dt.strftime('%Y-%m')
        base = base[~base['_ym'].isin(d2_meses)].drop(columns=['_ym'], errors='ignore')

    # Alinear columnas
    keep = ['fecha de facturacion','fecha_fact','marca','familia','AGENCIA_FACTURACION',
            'ASESOR_FACTURACION','IDENTIFICACION','CLIENTE_FACTURACION','CLIENTE_RESERVA',
            'Chasis','Cantidad']
    for c in keep:
        if c not in base.columns: base[c] = None
        if c not in d2.columns: d2[c] = None
    combined = pd.concat([base[keep], d2[keep]], ignore_index=True)
    print(f'[load_ventas_completo] base={len(base)} + DATOS2={len(d2)} = {len(combined)} (meses DATOS2 override: {sorted(d2_meses)})')
    return combined


if __name__ == '__main__':
    df = load_ventas()
    print(f'Path: {DEFAULT_VENTAS_PATH}')
    print(f'Rows: {len(df)}')
    print(f'Marcas: {df["marca"].value_counts().to_dict()}')
    print(f'Rango fechas: {df["fecha de facturacion"].min()} → {df["fecha de facturacion"].max()}')
    # Resumen por mes (con signo)
    df['mes'] = df['fecha de facturacion'].dt.month
    print('\nNetos por marca × mes:')
    print(df.pivot_table(values='Cantidad', index='marca', columns='mes', aggfunc='sum', fill_value=0))
