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


# ═══════════════ Mix por versión ═══════════════
# Diccionario de matching entre el nombre de versión del presupuesto y el string
# de la factura. Ford baja a trim; Dongfeng necesita eje+combustible en los Rich
# y separar Mage EV/HEV; Chery/Mazda/RAM van a nivel modelo (volumen chico).

_MODELOS = {
    'FORD':          ['TERRITORY', 'ESCAPE', 'EVEREST', 'EXPEDITION', 'EXPLORER', 'BRONCO', 'F150', 'F-150', 'RANGER'],
    'DONGFENG_ORGU': ['HUGE', 'MAGE', 'PALADIN', 'RICH 6', 'RICH 7', 'Z9', 'AX7'],
    'CHERY_ORGU':    ['ARRIZO', 'TIGGO 2', 'TIGGO 4', 'TIGGO 7', 'TIGGO 8', 'HIMLA'],
    'MAZDA_ORGU':    ['BT-50', 'BT50', 'CX-90', 'CX90', 'CX-60', 'CX60', 'CX-30', 'CX30',
                      'CX-5', 'CX5', 'CX-3', 'CX3', 'MAZDA 2', 'MAZDA 3'],
    'RAM_ORGU':      ['RAM 1500', '1500', 'RAM 700', '700', 'COMPASS', 'GRAND CHEROKEE', 'PULSE'],
}
# Alias para que las dos grafías caigan en la misma llave
_MODELO_CANON = {'F-150': 'F150', 'BT50': 'BT-50', 'CX90': 'CX-90', 'CX60': 'CX-60',
                 'CX30': 'CX-30', 'CX5': 'CX-5', 'CX3': 'CX-3', '1500': 'RAM 1500', '700': 'RAM 700'}
# Orden importa: el trim más largo primero (XLT antes que XL, ST LINE antes que nada).
_TRIMS_FORD = ['ST LINE', 'BADLANDS', 'TITANIUM', 'TREND', 'ACTIVE', 'PLATIN', 'LARIAT', 'RAPTOR', 'XLT', 'XL']


def version_key(marca, texto):
    """Llave canónica de versión. None si no se reconoce el modelo."""
    t = ' ' + ' '.join(str(texto).upper().replace('+', ' ').split()) + ' '
    modelo = None
    for m in _MODELOS.get(marca, []):
        if f' {m} ' in t or t.strip().startswith(m + ' '):
            modelo = _MODELO_CANON.get(m, m)
            break
    if not modelo:
        return None
    if marca == 'FORD':
        for tr in _TRIMS_FORD:
            if tr in t:
                return f'{modelo}|{tr}'
        return modelo
    if marca == 'DONGFENG_ORGU':
        if modelo == 'MAGE':
            es_ev = ' EV ' in t and 'HEV' not in t and 'HYBRID' not in t
            return 'MAGE|EV' if es_ev else 'MAGE|HEV'
        if modelo in ('RICH 6', 'RICH 7'):
            eje = '4X4' if '4X4' in t else '4X2'
            fuel = 'DIESEL' if 'DIESEL' in t else 'GAS'
            return f'{modelo}|{eje}|{fuel}' if modelo == 'RICH 6' else f'{modelo}|{eje}'
        return modelo
    return modelo   # Chery / Mazda / RAM: nivel modelo


def build_mix(bp, ventas_mensual):
    """Cruza presupuesto por versión contra ventas reales 2026.

    Devuelve {marca: {'versiones': [...], 'extras': [...], 'meses_ytd': N}}.
    Cada versión: nombre del presupuesto, PVP, ppto fin/com YTD y FY, real YTD.
    'extras' = versiones facturadas que el presupuesto no contempla.
    """
    if not bp or not bp.get('tipos'):
        return None
    out = {}
    for marca in _MODELOS:
        # ── presupuesto por versión (releyendo los archivos, ahora sin agregar) ──
        vers = {}
        for tipo, fname in BP_FILES.items():
            path = BP_DIR / fname
            if not path.exists():
                continue
            hoja = [h for h, mk in BP_MARCAS.items() if mk == marca]
            if not hoja:
                continue
            df = pd.read_excel(path, sheet_name=hoja[0], header=None)
            agencia = None
            for i in range(len(df)):
                c1 = df.iloc[i, 1]
                if pd.isna(c1):
                    continue
                v = str(c1).strip()
                if v in BP_AGENCIAS:
                    agencia = BP_AGENCIAS[v]
                    continue
                if v in ('Modelo', 'Total') or agencia in (None, '_total'):
                    continue
                pvp = df.iloc[i, 2]
                if pd.isna(pvp):
                    continue
                k = version_key(marca, v)
                if k is None:
                    print(f'[mix] WARN versión de presupuesto sin modelo: {marca} · {v!r}')
                    continue
                if k not in vers:
                    vers[k] = {'nombre': v, 'pvp': float(pvp), '_noms': set(),
                               'financiero': [0] * 12, 'comercial': [0] * 12, '_ag': {}}
                vers[k]['_noms'].add(v)
                _agd = vers[k]['_ag'].setdefault(agencia, {'financiero': [0] * 12, 'comercial': [0] * 12})
                for m in range(12):
                    q = df.iloc[i, 3 + m]
                    if pd.notna(q) and q != 0:
                        vers[k][tipo][m] += int(q)
                        _agd[tipo][m] += int(q)
        # ── real 2026 por versión ──
        vm = (ventas_mensual or {}).get(marca) or {}
        meses26 = sorted({str(r.get('mes')) for r in vm.get('flat', [])
                          if str(r.get('mes', '')).startswith('2026')})
        n_ytd = len(meses26)
        real = {}
        real_ag = {}
        extras = {}
        extras_ag = {}
        for r in vm.get('flat', []):
            if not str(r.get('mes', '')).startswith('2026'):
                continue
            q = r.get('cantidad', 0) or 0
            ag = r.get('agencia') or 'Sin agencia'
            k = version_key(marca, r.get('modelo', ''))
            if k in vers:
                real[k] = real.get(k, 0) + q
                real_ag.setdefault(k, {})[ag] = real_ag.get(k, {}).get(ag, 0) + q
            else:
                nom = ' '.join(str(r.get('modelo', '')).split())
                extras[nom] = extras.get(nom, 0) + q
                extras_ag.setdefault(nom, {})[ag] = extras_ag.get(nom, {}).get(ag, 0) + q
        filas = []
        for k, v in vers.items():
            # Si varias versiones del presupuesto caen en la misma llave (CX-90
            # Core/High/High+, RAM 1500 Full/Premium...) el nombre de una sola
            # engaña: se etiqueta por la llave y se dice cuántas agrupa.
            _n = len(v['_noms'])
            _nom = v['nombre'] if _n == 1 else f"{k.replace('|', ' ')} · {_n} versiones ppto"
            # Desglose por agencia: presupuesto y real de esta versión en cada una.
            _ag_out = {}
            for ag in set(list(v['_ag'].keys()) + list(real_ag.get(k, {}).keys())):
                bag = v['_ag'].get(ag, {'financiero': [0]*12, 'comercial': [0]*12})
                _ag_out[ag] = {
                    'fin_ytd': sum(bag['financiero'][:n_ytd]), 'fin_fy': sum(bag['financiero']),
                    'com_ytd': sum(bag['comercial'][:n_ytd]), 'com_fy': sum(bag['comercial']),
                    'real': real_ag.get(k, {}).get(ag, 0),
                }
            filas.append({
                'nombre': _nom, 'pvp': round(v['pvp']),
                'fin_ytd': sum(v['financiero'][:n_ytd]), 'com_ytd': sum(v['comercial'][:n_ytd]),
                'fin_fy': sum(v['financiero']), 'com_fy': sum(v['comercial']),
                'real': real.get(k, 0),
                'ag': _ag_out,
            })
        filas.sort(key=lambda x: -x['fin_fy'])
        out[marca] = {
            'versiones': filas,
            'extras': sorted(([n, q, extras_ag.get(n, {})] for n, q in extras.items() if q != 0),
                             key=lambda x: -x[1]),
            'meses_ytd': n_ytd,
        }
    return out


# ═══════════════ Accesorios por versión (PBD Ford FCST 4+8, ago-2026) ═══════════════
# En Ecuador el no-híbrido paga arancel/ICE sobre el precio del vehículo, así que
# la venta se parte en DOS facturas: vehículo (en DATOS 2) + accesorios (serie
# aparte que el reporte de inventario NO trae). Los híbridos facturan completo.
# Estos son los valores estándar del PBD oficial; se suman al revenue por unidad
# para que la facturación de un ICE sea comparable con la de un híbrido y con el
# PVP total del BP2026.
ACCESORIOS_FORD = {
    'TERRITORY|TREND': 0,      'TERRITORY|TITANIUM': 1000,
    'ESCAPE|ST LINE': 0,       'ESCAPE|TITANIUM': 6000,
    'ESCAPE|PLATIN': 0,
    'EVEREST|ACTIVE': 10000,   'EVEREST|SPORT': 10000,   'EVEREST|PLATIN': 10000,
    'EXPLORER|ACTIVE': 15000,  'EXPLORER|PLATIN': 15000,
    'BRONCO|BADLANDS': 20000,
    'EXPEDITION|PLATIN': 20000,
    'RANGER|XL': 8000,         'RANGER|XLT': 12000,      'RANGER|RAPTOR': 13000,
    'F150|XLT': 0,             'F150|LARIAT': 0,
    'F150|PLATIN': 0,          'F150|RAPTOR': 25000,
}

def accesorios_unidad(marca, texto_version):
    """USD de accesorios estándar por unidad para una versión facturada."""
    if marca != 'FORD':
        return 0
    k = version_key('FORD', texto_version)
    return ACCESORIOS_FORD.get(k, 0)
