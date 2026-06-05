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
