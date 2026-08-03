"""Presupuestos BP2026 (Mix Vehículos V.4) → bloque `presupuesto` de data.json.

Dos archivos con la misma estructura: Financiero (piso, lo comprometido al
negocio) y Comercial (techo, lo que empuja ventas). Cada hoja de marca trae
bloques por agencia (versión × PVP × mes) y un bloque final "Total Orgu".

El nombre de los archivos dice "Machala" pero traen las 7 agencias — es la V.4
corporativa completa.
"""
import pandas as pd
from pathlib import Path

BP_DIR = Path.home() / 'dev' / 'panel-datos' / 'presupuesto'
BP_FILES = {
    'financiero': 'Mix Vehículos BP2026 V.4 - Financiero - Machala.xlsx',
    'comercial':  'Mix Vehículos BP2026 V.4 - Comercial - Machala.xlsx',
}
# Hoja del archivo → clave de marca del panel
BP_MARCAS = {
    'Ford':       'FORD',
    'Dongfeng':   'DONGFENG_ORGU',
    'Chery':      'CHERY_ORGU',
    'Mazda':      'MAZDA_ORGU',
    'Stellantis': 'RAM_ORGU',
}
# Nombre de agencia del presupuesto → agencia del panel
BP_AGENCIAS = {
    'Carlos Julio Arosemena': 'CJA',
    'Orellana':   'Orellana',
    'Machala':    'Machala',
    'Manta':      'Manta',
    'Portoviejo': 'Portoviejo',
    'La Y':       'La Y',
    'Tumbaco':    'Tumbaco',
    'Total Orgu': '_total',
}
_MESES = [f'2026-{m:02d}' for m in range(1, 13)]


def _parse_hoja(df):
    """Devuelve {agencia: {'uds': [12 meses], 'usd': [12 meses]}}.

    La hoja son bloques apilados: fila con el nombre de la agencia (col 1, resto
    vacío), luego encabezado Modelo|PVP|Enero..Diciembre|FY, filas de versiones y
    una fila Total. Se suman las versiones (no se usa la fila Total del archivo,
    así el resultado queda validado contra ella).
    """
    out = {}
    agencia = None
    for i in range(len(df)):
        c1 = df.iloc[i, 1]
        if pd.isna(c1):
            continue
        v = str(c1).strip()
        if v in BP_AGENCIAS:
            agencia = BP_AGENCIAS[v]
            out[agencia] = {'uds': [0] * 12, 'usd': [0.0] * 12, '_chk': None}
            continue
        if agencia is None or v in ('Modelo',):
            continue
        if v == 'Total':
            fy = df.iloc[i, 15]
            out[agencia]['_chk'] = int(fy) if pd.notna(fy) else None
            continue
        # fila de versión: col 2 = PVP, cols 3..14 = meses
        pvp = df.iloc[i, 2]
        pvp = float(pvp) if pd.notna(pvp) else 0.0
        for m in range(12):
            q = df.iloc[i, 3 + m]
            if pd.notna(q) and q != 0:
                out[agencia]['uds'][m] += int(q)
                out[agencia]['usd'][m] += int(q) * pvp
    return out


def load_presupuesto():
    """{tipo: {marca: {agencia: {uds:[12], usd:[12]}}}} + metadata de meses.

    Valida cada bloque contra la fila Total del archivo; si algo no cuadra se
    reporta y se aborta ese archivo (mejor sin banda que con banda mentirosa).
    """
    res = {'meses': _MESES, 'tipos': {}}
    for tipo, fname in BP_FILES.items():
        path = BP_DIR / fname
        if not path.exists():
            print(f'[presupuesto] WARN no existe {fname} — se omite {tipo}')
            continue
        marcas = {}
        ok = True
        for hoja, marca in BP_MARCAS.items():
            df = pd.read_excel(path, sheet_name=hoja, header=None)
            bloques = _parse_hoja(df)
            for ag, b in bloques.items():
                suma = sum(b['uds'])
                if b['_chk'] is not None and suma != b['_chk']:
                    print(f'[presupuesto] ERROR {tipo}/{hoja}/{ag}: suma {suma} ≠ Total {b["_chk"]}')
                    ok = False
                del b['_chk']
                b['usd'] = [round(x) for x in b['usd']]
            # No todas las hojas traen bloque "Total Orgu" (Dongfeng solo tiene
            # Machala y La Y). Se sintetiza sumando las agencias presentes.
            if '_total' not in bloques and bloques:
                tot = {'uds': [0] * 12, 'usd': [0] * 12}
                for ag, b in bloques.items():
                    for m in range(12):
                        tot['uds'][m] += b['uds'][m]
                        tot['usd'][m] += b['usd'][m]
                bloques['_total'] = tot
            marcas[marca] = bloques
        if ok:
            res['tipos'][tipo] = marcas
            tot = sum(sum(b['uds']) for m in marcas.values() for a, b in m.items() if a != '_total')
            print(f'[presupuesto] {tipo}: {len(marcas)} marcas · {tot} uds FY (sin _total)')
        else:
            print(f'[presupuesto] {tipo} DESCARTADO por descuadre')
    return res if res['tipos'] else None


if __name__ == '__main__':
    import json
    r = load_presupuesto()
    if r:
        for tipo, marcas in r['tipos'].items():
            for marca in ('FORD', 'DONGFENG_ORGU'):
                t = marcas[marca].get('_total', {})
                print(tipo, marca, 'FY', sum(t.get('uds', [])), '· ene-jul', sum(t.get('uds', [0]*12)[:7]))
