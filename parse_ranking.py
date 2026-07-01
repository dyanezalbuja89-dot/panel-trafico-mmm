"""Parser para archivos RANKING DE VENTAS mensuales.
Produce flat de TXs {marca, agencia, asesor, modelo, cantidad, mes} desde
sheets 'RANKING POR MODELO FORD' y 'RANKING POR MODELO MULTIMARCAS'.

Cada RANKING representa el conteo NETO OFICIAL de un mes cerrado (incluye NCs).
Se usa como fuente de verdad para meses cerrados en aggregate.py.
"""
import warnings
warnings.filterwarnings('ignore')
import pandas as pd
from pathlib import Path

AGENCIA_MAP = {
    'VEHICULOS CARLOS JULIO AROSEMENA': 'CJA',
    'VEHICULOS LA Y': 'La Y',
    'VEHICULOS TUMBACO': 'Tumbaco',
    'VEHICULOS MACHALA': 'Machala',
    'VEHICULOS MANTA': 'Manta',
    'VEHICULOS MANTA II': 'Manta',
    'VEHICULOS ORELLANA': 'Orellana',
    'VEHICULOS PORTOVIEJO': 'Portoviejo',
    'VEHICULOS LA MACHALA': 'Machala',
}

MULTI_MARCA_PATS = [
    ('HUGE', 'DONGFENG_ORGU'), ('MAGE', 'DONGFENG_ORGU'), ('PALADIN', 'DONGFENG_ORGU'),
    ('RICH 6', 'DONGFENG_ORGU'), ('RICH 7', 'DONGFENG_ORGU'), ('Z9', 'DONGFENG_ORGU'),
    ('CX-30', 'MAZDA_ORGU'), ('CX30', 'MAZDA_ORGU'), ('CX-3', 'MAZDA_ORGU'), ('CX3', 'MAZDA_ORGU'),
    ('CX-5', 'MAZDA_ORGU'), ('CX5', 'MAZDA_ORGU'), ('CX-60', 'MAZDA_ORGU'), ('CX60', 'MAZDA_ORGU'),
    ('CX-90', 'MAZDA_ORGU'), ('CX90', 'MAZDA_ORGU'), ('BT-50', 'MAZDA_ORGU'), ('BT50', 'MAZDA_ORGU'),
    ('ARRIZO', 'CHERY_ORGU'), ('TIGGO', 'CHERY_ORGU'), ('HIMLA', 'CHERY_ORGU'),
    ('RAM DT', 'RAM_ORGU'), ('RAM ', 'RAM_ORGU'), ('1500', 'RAM_ORGU'), ('700', 'RAM_ORGU'),
]

def _modelo_to_marca(modelo):
    u = str(modelo or '').upper()
    for pat, brand in MULTI_MARCA_PATS:
        if pat in u: return brand
    return None

def _parse_modelo_sheet(df, marca_default=None):
    """
    Estructura típica:
    row 0: agencia headers (dispersos + 'Total AGENCIA' cols)
    row 1: asesores por columna
    rows 2..N-1: modelo + conteos
    row N-1: 'Total general'
    """
    txs = []
    # Row 0 tiene agencias. Forward-fill.
    ag_row = df.iloc[0].tolist()
    asesor_row = df.iloc[1].tolist()
    # Build column → (agencia, asesor)
    col_map = {}
    cur_ag = None
    for i, v in enumerate(ag_row):
        if pd.notna(v):
            s = str(v).strip()
            if s.startswith('VEHICULOS'):
                cur_ag = AGENCIA_MAP.get(s, s.replace('VEHICULOS ','').title())
        if i == 0: continue  # col 0 = modelo
        asesor = asesor_row[i] if i < len(asesor_row) and pd.notna(asesor_row[i]) else None
        if asesor is None: continue
        if str(asesor).upper() in ('MODELO', 'TOTAL AGENCIA'): continue
        col_map[i] = (cur_ag, str(asesor).strip().upper())
    # Model rows
    for r in range(2, len(df)):
        modelo = df.iloc[r, 0]
        if pd.isna(modelo): continue
        modelo_s = str(modelo).strip()
        if not modelo_s or modelo_s.upper() in ('TOTAL GENERAL', 'TOTAL'): continue
        marca = marca_default or _modelo_to_marca(modelo_s)
        if not marca: continue
        for col, (ag, asesor) in col_map.items():
            v = df.iloc[r, col]
            if pd.isna(v) or v == 0: continue
            try:
                cant = int(v)
            except Exception:
                continue
            if cant == 0: continue
            txs.append({
                'marca': marca,
                'agencia': ag,
                'asesor': asesor,
                'modelo': modelo_s,
                'cantidad': cant,
            })
    return txs

def parse_ranking(xl_path, mes_ym):
    """Parse xl file and return list of flat TXs with mes=mes_ym."""
    xl_path = Path(xl_path)
    if not xl_path.exists():
        return []
    all_txs = []
    # FORD sheet
    try:
        df = pd.read_excel(xl_path, sheet_name='RANKING POR MODELO FORD', header=None)
        all_txs.extend(_parse_modelo_sheet(df, marca_default='FORD'))
    except Exception as e:
        print(f'[ranking] FORD sheet err: {e}')
    # MULTI sheet
    try:
        df = pd.read_excel(xl_path, sheet_name='RANKING POR MODELO MULTIMARCAS', header=None)
        all_txs.extend(_parse_modelo_sheet(df, marca_default=None))
    except Exception as e:
        print(f'[ranking] MULTI sheet err: {e}')
    for t in all_txs:
        t['mes'] = mes_ym
    return all_txs

if __name__ == '__main__':
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else 'RANKING_JUNIO_2026.xlsx'
    txs = parse_ranking(p, '2026-06')
    from collections import Counter
    per_marca = Counter()
    for t in txs: per_marca[t['marca']] += t['cantidad']
    print(f'Total TXs: {len(txs)}')
    for m, c in per_marca.items(): print(f'  {m}: {c}')
    print(f'GRAND TOTAL: {sum(per_marca.values())}')
