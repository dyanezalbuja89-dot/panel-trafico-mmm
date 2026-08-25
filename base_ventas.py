#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Base de ventas de Finanzas — la fuente oficial de VENTAS del panel.

Finanzas publica un Excel mensual (`Base de Ventas a <Mes>.xlsx`) que es una tabla
dinámica. Los datos de origen NO están en ninguna hoja: viven en el **pivotCache**
dentro del .xlsx, con 73 campos por factura. Este módulo los saca de ahí.

Por qué esta fuente y no `DATOS 2` del reporte de inventario:

  1. **Trae el canal.** `DATOS 2` solo tiene unidades con chasis, así que se comía las
     ventas EXONERADAS — 12 unidades Ford ene–jul 2026 (2 de La Y) que no aparecían
     en el panel y sí en el cierre de Finanzas.
  2. **Trae la agencia ya resuelta**, distinta de la bodega en 50 de 915 filas: es el
     efecto placa (se factura desde otra vitrina por la placa "P" de Pichincha).
  3. **Trae costo y utilidad por chasis.**
  4. **Está más al día.** El reporte de inventario corta a mitad de mes; esta base
     llegó al 24-ago cuando el inventario iba al 15 (57 ventas Ford contra 10).
  5. No sufre el problema de los snapshots: no es una foto de stock, es un libro de
     facturas.

⚠ Solo tiene el año en curso. Para 2025 y para todo lo de producto —stock, reservas,
  arribos, cola, wait times— la fuente sigue siendo el reporte de inventario.
"""
import glob
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

# Dónde puede vivir el archivo. El primero que exista manda.
_DIRS = [
    Path.home() / 'Downloads',
    Path.home() / 'Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Ventas',
    Path.home() / 'Library/CloudStorage/OneDrive-Maresa/Marketing/2026',
]
_PATRON = 'Base de Ventas*.xls*'

# Los nombres que usa el panel
AGENCIA = {
    'CARLOS JULIO AROSEMENA': 'CJA', 'ORELLANA': 'Orellana', 'LA Y': 'La Y',
    'TUMBACO': 'Tumbaco', 'MANTA': 'Manta', 'MACHALA': 'Machala',
    'PORTOVIEJO': 'Portoviejo',
}
FAMILIA = {
    'TERRITORY': 'TERRITORY', 'ESCAPE': 'ESCAPE', 'EVEREST': 'EVEREST',
    'EXPLORER': 'EXPLORER', 'EXPEDITION': 'EXPEDITION', 'BRONCO': 'BRONCO',
    'F150': 'F-150', 'F-150': 'F-150', 'RANGER': 'RANGER',
}
MARCA_KEY = {
    'FORD': 'FORD', 'DONGFENG': 'DONGFENG_ORGU', 'DONG FENG': 'DONGFENG_ORGU',
    'CHERY': 'CHERY_ORGU', 'MAZDA': 'MAZDA_ORGU', 'RAM': 'RAM_ORGU',
}

# Campos del caché que nos interesan → nombre de salida
CAMPOS = {
    'Chasis': 'chasis', 'Marca Vehiculo': 'marca_raw', 'Descripcion Vehiculo': 'modelo',
    'Fecha Factura': '_serial', 'Mes': 'mes_num', 'Cantidad': 'cantidad',
    'AGENCIA': 'agencia_raw', 'FAMILIA': 'familia_raw', 'CANAL': 'canal',
    'Vendedor': 'asesor', 'Tipo Documento': 'tipo_doc',
    'Bodega Venta Vehiculo': 'bodega', 'Costo Unidad': 'costo',
    'Valor Utilidad': 'utilidad', 'Precio Neto': 'precio_neto',
}


def archivo_base():
    """El `Base de Ventas` más reciente. None si no hay ninguno."""
    cands = []
    for d in _DIRS:
        if d.exists():
            cands += [Path(p) for p in glob.glob(str(d / _PATRON))
                      if not Path(p).name.startswith('~$')]
    if not cands:
        return None
    # El más reciente por fecha de modificación: Finanzas reemplaza el archivo cada mes.
    return max(cands, key=lambda p: p.stat().st_mtime)


def _leer_pivot_cache(path):
    """Saca los registros del pivotCache. Devuelve DataFrame crudo."""
    with zipfile.ZipFile(path) as z:
        nombres = z.namelist()
        defi = next((n for n in nombres if 'pivotCacheDefinition' in n and n.endswith('.xml')), None)
        recs = next((n for n in nombres if 'pivotCacheRecords' in n and n.endswith('.xml')), None)
        if not defi or not recs:
            return None
        cd = ET.fromstring(z.read(defi))
        cflds = cd.findall('.//m:cacheField', NS)
        campos = [f.get('name') for f in cflds]
        # sharedItems: los valores a los que apuntan los <x v="i"/> de cada registro
        shared = [[it.get('v') for it in f.findall('.//m:sharedItems/*', NS)] for f in cflds]
        quiero = {i: CAMPOS[c] for i, c in enumerate(campos) if c in CAMPOS}
        filas = []
        for r in ET.fromstring(z.read(recs)):
            row = {}
            for i, ch in enumerate(r):
                if i not in quiero:
                    continue
                tag = ch.tag.split('}')[-1]
                if tag == 'x':
                    j = int(ch.get('v'))
                    row[quiero[i]] = shared[i][j] if j < len(shared[i]) else None
                elif tag == 'm':
                    row[quiero[i]] = None
                else:
                    row[quiero[i]] = ch.get('v')
            filas.append(row)
    return pd.DataFrame(filas) if filas else None


def _fam(v):
    u = re.sub(r'[^A-Z0-9-]', '', str(v or '').upper())
    return FAMILIA.get(u) or FAMILIA.get(u.replace('-', ''))


def cargar(path=None):
    """DataFrame normalizado de ventas, o None si no se pudo leer.

    Columnas: chasis · marca (clave del panel) · modelo · familia · agencia · canal ·
    asesor · fecha · mes ('aaaa-mm') · cantidad (con signo: NC negativa) · costo ·
    utilidad · precio_neto · exonerado (bool).
    """
    p = Path(path) if path else archivo_base()
    if not p or not p.exists():
        return None
    df = _leer_pivot_cache(p)
    if df is None or df.empty:
        return None

    for c in ('cantidad', 'costo', 'utilidad', 'precio_neto', '_serial', 'mes_num'):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    df['cantidad'] = df['cantidad'].fillna(0)

    # El serial de Excel arranca el 1899-12-30
    df['fecha'] = pd.to_datetime(df['_serial'], unit='D', origin='1899-12-30', errors='coerce')
    df['mes'] = df['fecha'].dt.strftime('%Y-%m')

    df['marca'] = df['marca_raw'].astype(str).str.upper().str.strip().map(MARCA_KEY)
    df['agencia'] = df['agencia_raw'].astype(str).str.upper().str.strip().map(AGENCIA)
    df['familia'] = df['familia_raw'].apply(_fam)
    df['canal'] = df['canal'].astype(str).str.upper().str.strip()
    df['exonerado'] = df['canal'].eq('EXONERADO')

    df['_archivo'] = p.name
    return df.drop(columns=[c for c in ('_serial',) if c in df.columns])


if __name__ == '__main__':
    p = archivo_base()
    print(f'archivo: {p}')
    d = cargar()
    if d is None:
        raise SystemExit('no se pudo leer la base')
    print(f'registros: {len(d)} · rango {d["fecha"].min().date()} → {d["fecha"].max().date()}')
    print(f'sin agencia mapeada: {d["agencia"].isna().sum()} · sin familia: {d["familia"].isna().sum()}')
    ford = d[d['marca'] == 'FORD']
    print(f'\nFord por canal:\n{ford.groupby("canal")["cantidad"].sum().astype(int).to_string()}')
    print(f'\nFord por mes:\n{ford.groupby("mes")["cantidad"].sum().astype(int).to_string()}')
    print(f'\nFord por agencia:\n{ford.groupby("agencia")["cantidad"].sum().astype(int).to_string()}')
