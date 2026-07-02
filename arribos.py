"""Parser ARRIBOS AL <fecha>.xlsx — supply chain data (ETD/ETA/facturación).
Sheet 'AUTOSHARECORP' con historial + futuro de embarques.
"""
import warnings
warnings.filterwarnings('ignore')
import pandas as pd
from pathlib import Path
from datetime import datetime

ARRIBOS_PATH = Path(__file__).parent / 'ARRIBOS.xlsx'

BRAND_MAP = {
    'FORD': 'FORD', 'FORD TH': 'FORD', 'FORD ARG': 'FORD', 'FORD USA': 'FORD',
    'DONGFENG': 'DONGFENG_ORGU', 'DONG FENG': 'DONGFENG_ORGU',
    'CHERY': 'CHERY_ORGU', 'MAZDA': 'MAZDA_ORGU', 'RAM': 'RAM_ORGU',
}

def _norm_marca(m):
    if not isinstance(m, str): return None
    u = m.upper().strip()
    for k, v in BRAND_MAP.items():
        if u.startswith(k): return v
    return None

def load_arribos():
    if not ARRIBOS_PATH.exists():
        return {'available': False}
    try:
        df = pd.read_excel(ARRIBOS_PATH, sheet_name='AUTOSHARECORP', header=1)
    except Exception as e:
        return {'available': False, 'error': str(e)}
    df.columns = [str(c).strip() for c in df.columns]
    df = df[df['MARCA'].notna()].copy()
    df['marca_key'] = df['MARCA'].apply(_norm_marca)
    df = df[df['marca_key'].notna()]
    df['ETA_dt'] = pd.to_datetime(df.get('ETA'), errors='coerce')
    df['ETD_dt'] = pd.to_datetime(df.get('ETD'), errors='coerce')
    df['FACT_dt'] = pd.to_datetime(df.get('FACTURACIÓN'), errors='coerce')
    df['RETAIL'] = pd.to_numeric(df.get('RETAIL'), errors='coerce').fillna(0).astype(int)
    df = df[df['RETAIL'] > 0]
    df = df[df['ETA_dt'].notna()]
    # Split
    hoy = pd.Timestamp(datetime.now().date())
    futuros = df[df['ETA_dt'] >= hoy].copy()
    llegados = df[df['ETA_dt'] < hoy].copy()
    # Group por mes de ETA + marca + puerto
    def _to_list(sub, limit=None):
        rows = []
        for _, r in sub.iterrows():
            rows.append({
                'marca': r['marca_key'],
                'marca_raw': str(r.get('MARCA', '')),
                'modelo': str(r.get('MODELO', '')),
                'retail': int(r['RETAIL']),
                'anio': int(r['AÑO']) if pd.notna(r.get('AÑO')) else None,
                'puerto': str(r.get('PUERTO', '')),
                'etd': r['ETD_dt'].strftime('%Y-%m-%d') if pd.notna(r['ETD_dt']) else None,
                'eta': r['ETA_dt'].strftime('%Y-%m-%d'),
                'facturacion': r['FACT_dt'].strftime('%Y-%m-%d') if pd.notna(r['FACT_dt']) else None,
                'observaciones': str(r.get('OBSERVACIONES', '')).strip() if pd.notna(r.get('OBSERVACIONES')) else '',
            })
        rows.sort(key=lambda x: x['eta'])
        if limit: rows = rows[:limit]
        return rows
    def _agg_mes_marca(sub):
        agg = {}
        for _, r in sub.iterrows():
            ym = r['ETA_dt'].strftime('%Y-%m')
            m = r['marca_key']
            key = (ym, m)
            if key not in agg: agg[key] = 0
            agg[key] += int(r['RETAIL'])
        rows = [{'ym': ym, 'marca': m, 'unidades': u} for (ym, m), u in agg.items()]
        rows.sort(key=lambda x: (x['ym'], x['marca']))
        return rows
    def _agg_puerto(sub):
        agg = {}
        for _, r in sub.iterrows():
            p = str(r.get('PUERTO', 'S/D')).strip() or 'S/D'
            agg[p] = agg.get(p, 0) + int(r['RETAIL'])
        return [{'puerto': p, 'unidades': u} for p, u in sorted(agg.items(), key=lambda x: -x[1])]
    total_futuro = int(futuros['RETAIL'].sum())
    total_historico = int(llegados['RETAIL'].sum())
    return {
        'available': True,
        'snapshot_date': datetime.now().strftime('%Y-%m-%d'),
        'total_futuro_retail': total_futuro,
        'total_historico_retail': total_historico,
        'futuros': _to_list(futuros),
        'por_mes_marca_futuros': _agg_mes_marca(futuros),
        'por_mes_marca_hist': _agg_mes_marca(llegados),
        'por_puerto_futuros': _agg_puerto(futuros),
    }

if __name__ == '__main__':
    import json
    r = load_arribos()
    if not r.get('available'):
        print('archivo no disponible'); exit(1)
    print(f'snapshot: {r["snapshot_date"]}')
    print(f'total futuro retail: {r["total_futuro_retail"]}')
    print(f'total histórico retail: {r["total_historico_retail"]}')
    print(f'futuros count: {len(r["futuros"])}')
    print('por mes/marca futuros:')
    for row in r['por_mes_marca_futuros']: print(f'  {row}')
    print('por puerto:')
    for row in r['por_puerto_futuros']: print(f'  {row}')
