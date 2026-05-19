"""Análisis competitivo de importaciones Ford: ORGU vs QM (Quito Motors).

Parsea el archivo BDD IMPORTACIONES con estructura de tabla dinámica:
  - Filas modelo (padre)
  - Subfilas AUTOSHARECORP (=ORGU) y QUITO MOTORS S.A. (=QM)
  - Columnas: 17 meses (Ene 2025 a May 2026) + Total general

Consolida ~30 SKUs distintos en 15 grupos comerciales (Daniel definió las reglas).
Calcula:
  - Volumen ORGU/QM/Total por modelo, por año, total
  - Share % y delta de share entre 2025 y 2026
  - Serie temporal mensual (para gráfica)
  - Insights automáticos (modelos en ascenso, caída, ancla, lanzamientos)
"""
import re
from pathlib import Path
import pandas as pd

# Carpeta donde busca el archivo (más reciente)
_IMPORT_DIRS = [
    Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Inventrario"),
    Path("/Users/danielyanezalbuja/Downloads"),
]


def find_latest_imports():
    """Busca el archivo de importaciones más reciente."""
    candidates = []
    for d in _IMPORT_DIRS:
        if not d.exists():
            continue
        for ext in ('*.xlsx', '*.xlsm'):
            for p in d.glob(ext):
                if p.name.startswith('~$'):
                    continue
                up = p.name.upper()
                if 'IMPORTACI' in up or 'BDD IMPORT' in up:
                    candidates.append(p)
        if candidates:
            break
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


# ─────────────────────────────────────────────────────────────────────────────
# Mapeo modelo SKU → grupo consolidado
# ─────────────────────────────────────────────────────────────────────────────
def consolidate_model(raw_name):
    """Aplica las reglas de consolidación definidas por Daniel."""
    if not isinstance(raw_name, str):
        return None
    n = raw_name.upper().strip()

    # Reglas con prioridad (más específicas primero)
    if 'TERRITORY TITANIUM' in n:
        return 'TERRITORY TITANIUM'
    if 'EVEREST ACTIVE' in n:
        return 'EVEREST ACTIVE'
    if 'EVEREST TITANIUM' in n:
        return 'EVEREST TITANIUM'
    if 'ESCAPE ST' in n:
        return 'ESCAPE ST'
    if 'ESCAPE PLATINUM' in n and 'HEV' in n:
        return 'ESCAPE PLATINUM HEV'
    # Escape Titanium (1.5 gasolina) vs Escape 2.5/HEV (genérico sin Titanium en el nombre)
    if 'ESCAPE TITANIUM' in n:
        if '1.5' in n:
            return 'ESCAPE TITANIUM 1.5 4X2'
        if '2.5' in n or 'HEV' in n or 'FHEV' in n:
            return 'ESCAPE TITANIUM 2.5 HEV/FHEV'
        return 'ESCAPE TITANIUM 1.5 4X2'
    if 'ESCAPE' in n and ('2.5' in n or 'HEV' in n or 'FHEV' in n):
        return 'ESCAPE TITANIUM 2.5 HEV/FHEV'
    if 'RANGER RAPTOR' in n:
        return 'RANGER RAPTOR'
    if 'RANGER XL' in n and 'XLT' not in n and 'DIESEL' in n:
        return 'RANGER XL Diésel'
    if 'RANGER XLT' in n and 'DIESEL' in n:
        return 'RANGER XLT Diésel'
    if 'EXPLORER ACTIVE' in n:
        return 'EXPLORER ACTIVE'
    if 'EXPLORER PLATINUM' in n:
        return 'EXPLORER PLATINUM'
    if 'EXPEDITION PLATINUM' in n or ('EXPEDITION' in n and 'PLATIN' in n):
        return 'EXPEDITION PLATINUM'
    if 'BRONCO' in n and '2.7' in n:
        return 'BRONCO 2.7'
    if 'F150 RAPTOR' in n or 'F-150 RAPTOR' in n:
        return 'F150 RAPTOR'

    # No matched → devolver el original (para revisar manualmente luego)
    return raw_name.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Parseo del archivo
# ─────────────────────────────────────────────────────────────────────────────
def is_distributor_row(label):
    if not isinstance(label, str):
        return None
    up = label.upper()
    if 'AUTOSHARECORP' in up:
        return 'ORGU'
    if 'QUITO MOTORS' in up:
        return 'QM'
    return None


def parse_imports_file(path):
    """Parsea el archivo y devuelve filas planas:
    [{modelo, distribuidor, ym, cantidad}, ...]"""
    df = pd.read_excel(path, sheet_name=0, header=None)
    # Headers de fecha en fila 5
    header_row = 5
    headers = df.iloc[header_row].tolist()
    # Identificar columnas mes (formato 'M/D/YYYY' como string, o datetime)
    month_cols = []
    for col_idx, h in enumerate(headers):
        if pd.isna(h):
            continue
        ym = None
        if hasattr(h, 'year'):
            ym = h.strftime('%Y-%m')
        elif isinstance(h, str):
            # Formato "M/D/YYYY" típico de pivot table
            try:
                d = pd.to_datetime(h, format='%m/%d/%Y', errors='coerce')
                if pd.isna(d):
                    d = pd.to_datetime(h, errors='coerce')
                if pd.notna(d):
                    ym = d.strftime('%Y-%m')
            except Exception:
                pass
        if ym:
            month_cols.append({'col': col_idx, 'ym': ym})

    # Iterar filas de modelo / distribuidor
    rows = []
    current_model = None
    for r in range(header_row + 1, len(df)):
        label = df.iloc[r, 0]
        if pd.isna(label):
            continue
        label_str = str(label).strip()
        if not label_str or label_str.upper() == 'TOTAL GENERAL':
            continue
        dist = is_distributor_row(label_str)
        if dist is None:
            # Es una fila de modelo
            current_model = label_str
            continue
        if current_model is None:
            continue
        # Es una subfila de distribuidor
        consolidated = consolidate_model(current_model)
        for mc in month_cols:
            v = df.iloc[r, mc['col']]
            if pd.notna(v):
                try:
                    qty = int(v)
                    if qty > 0:
                        rows.append({
                            'modelo_raw': current_model,
                            'modelo': consolidated,
                            'distribuidor': dist,
                            'ym': mc['ym'],
                            'cantidad': qty,
                        })
                except (ValueError, TypeError):
                    pass
    return pd.DataFrame(rows), [mc['ym'] for mc in month_cols]


# ─────────────────────────────────────────────────────────────────────────────
# Agregación para el panel
# ─────────────────────────────────────────────────────────────────────────────
def compute_competencia_data(path=None):
    if path is None:
        path = find_latest_imports()
    if path is None or not Path(path).exists():
        return None
    df, all_months = parse_imports_file(path)
    if df.empty:
        return None

    # Año desde ym
    df['anio'] = df['ym'].str[:4].astype(int)

    # Agregar por modelo
    modelos_data = []
    for modelo in df['modelo'].unique():
        sub = df[df['modelo'] == modelo]
        orgu_25 = int(sub[(sub['distribuidor']=='ORGU') & (sub['anio']==2025)]['cantidad'].sum())
        qm_25   = int(sub[(sub['distribuidor']=='QM')   & (sub['anio']==2025)]['cantidad'].sum())
        orgu_26 = int(sub[(sub['distribuidor']=='ORGU') & (sub['anio']==2026)]['cantidad'].sum())
        qm_26   = int(sub[(sub['distribuidor']=='QM')   & (sub['anio']==2026)]['cantidad'].sum())
        tot_25 = orgu_25 + qm_25
        tot_26 = orgu_26 + qm_26
        total  = tot_25 + tot_26
        orgu_total = orgu_25 + orgu_26
        qm_total   = qm_25 + qm_26
        # Series mensuales para gráfica (separadas por distribuidor)
        mensual = {}
        for ym in all_months:
            o = int(sub[(sub['distribuidor']=='ORGU') & (sub['ym']==ym)]['cantidad'].sum())
            q = int(sub[(sub['distribuidor']=='QM')   & (sub['ym']==ym)]['cantidad'].sum())
            mensual[ym] = {'orgu': o, 'qm': q}
        modelos_data.append({
            'modelo': modelo,
            'orgu_2025': orgu_25, 'qm_2025': qm_25, 'tot_2025': tot_25,
            'orgu_2026': orgu_26, 'qm_2026': qm_26, 'tot_2026': tot_26,
            'total': total,
            'orgu_total': orgu_total, 'qm_total': qm_total,
            'orgu_share_total': round(100*orgu_total/total, 1) if total else 0,
            'qm_share_total':   round(100*qm_total/total, 1)   if total else 0,
            'orgu_share_2025': round(100*orgu_25/tot_25, 1) if tot_25 else None,
            'orgu_share_2026': round(100*orgu_26/tot_26, 1) if tot_26 else None,
            'delta_share': (round(100*orgu_26/tot_26, 1) - round(100*orgu_25/tot_25, 1)
                            if (tot_25 and tot_26) else None),
            'mensual': mensual,
        })
    modelos_data.sort(key=lambda m: -m['total'])

    # Totales globales
    tot = {
        'orgu_2025': sum(m['orgu_2025'] for m in modelos_data),
        'qm_2025':   sum(m['qm_2025']   for m in modelos_data),
        'orgu_2026': sum(m['orgu_2026'] for m in modelos_data),
        'qm_2026':   sum(m['qm_2026']   for m in modelos_data),
    }
    tot['tot_2025'] = tot['orgu_2025'] + tot['qm_2025']
    tot['tot_2026'] = tot['orgu_2026'] + tot['qm_2026']
    tot['total']    = tot['tot_2025'] + tot['tot_2026']
    tot['orgu_total'] = tot['orgu_2025'] + tot['orgu_2026']
    tot['qm_total']   = tot['qm_2025'] + tot['qm_2026']
    tot['orgu_share_2025'] = round(100*tot['orgu_2025']/tot['tot_2025'], 1) if tot['tot_2025'] else 0
    tot['orgu_share_2026'] = round(100*tot['orgu_2026']/tot['tot_2026'], 1) if tot['tot_2026'] else 0
    tot['delta_share_total'] = round(tot['orgu_share_2026'] - tot['orgu_share_2025'], 1)

    # Insights automáticos
    insights = []
    # Lanzamientos 2026 (sin volumen 2025)
    lanzamientos = [m for m in modelos_data if m['tot_2025']==0 and m['tot_2026']>0]
    if lanzamientos:
        insights.append({
            'tipo': 'lanzamiento',
            'titulo': '🚀 Lanzamientos 2026 (sin histórico 2025)',
            'modelos': [m['modelo'] for m in lanzamientos],
            'detalle': ' · '.join(f"{m['modelo']} ({m['tot_2026']})" for m in lanzamientos[:5]),
        })
    # Modelos en caída (>50% menos en 2026 anualizado)
    # 2026 lleva 5 meses (ene-may), 2025 lleva 12 meses. Comparar mensualizado.
    meses_2026 = len([y for y in all_months if y.startswith('2026')])
    meses_2025 = len([y for y in all_months if y.startswith('2025')])
    caida = []
    for m in modelos_data:
        if m['tot_2025'] < 20 or meses_2026 == 0:
            continue
        v25_mensual = m['tot_2025'] / meses_2025
        v26_mensual = m['tot_2026'] / meses_2026
        if v25_mensual > 0 and v26_mensual / v25_mensual < 0.4:
            caida.append({'modelo': m['modelo'], 'v25m': round(v25_mensual,1), 'v26m': round(v26_mensual,1),
                         'pct_var': round(100*(v26_mensual/v25_mensual - 1), 0)})
    if caida:
        caida.sort(key=lambda x: x['pct_var'])
        insights.append({
            'tipo': 'caida',
            'titulo': '📉 Modelos en caída (volumen mensualizado 2026 vs 2025)',
            'modelos': [c['modelo'] for c in caida],
            'detalle': ' · '.join(f"{c['modelo']} ({c['v25m']:.1f}/m → {c['v26m']:.1f}/m, {c['pct_var']:+.0f}%)" for c in caida[:5]),
        })
    # Modelos en ascenso (>30% más en 2026 mensualizado)
    ascenso = []
    for m in modelos_data:
        if m['tot_2025'] < 10 or meses_2026 == 0:
            continue
        v25_mensual = m['tot_2025'] / meses_2025
        v26_mensual = m['tot_2026'] / meses_2026
        if v25_mensual > 0 and v26_mensual / v25_mensual > 1.3:
            ascenso.append({'modelo': m['modelo'], 'v25m': round(v25_mensual,1), 'v26m': round(v26_mensual,1),
                           'pct_var': round(100*(v26_mensual/v25_mensual - 1), 0)})
    if ascenso:
        ascenso.sort(key=lambda x: -x['pct_var'])
        insights.append({
            'tipo': 'ascenso',
            'titulo': '📈 Modelos en ascenso (volumen mensualizado 2026 vs 2025)',
            'modelos': [c['modelo'] for c in ascenso],
            'detalle': ' · '.join(f"{c['modelo']} ({c['v25m']:.1f}/m → {c['v26m']:.1f}/m, {c['pct_var']:+.0f}%)" for c in ascenso[:5]),
        })
    # Modelos donde QM lidera (oportunidad de robar share)
    qm_lidera = [m for m in modelos_data if m['total']>=30 and m['orgu_share_total']<45]
    if qm_lidera:
        qm_lidera.sort(key=lambda m: m['qm_total'], reverse=True)
        insights.append({
            'tipo': 'oportunidad_qm',
            'titulo': '🎯 QM lidera (oportunidad ORGU para robar share)',
            'modelos': [m['modelo'] for m in qm_lidera],
            'detalle': ' · '.join(f"{m['modelo']} (QM {m['qm_total']} vs ORGU {m['orgu_total']}, {m['qm_share_total']:.0f}%/{m['orgu_share_total']:.0f}%)" for m in qm_lidera[:5]),
        })
    # Modelos donde ORGU lidera (defender)
    orgu_lidera = [m for m in modelos_data if m['total']>=30 and m['orgu_share_total']>55]
    if orgu_lidera:
        orgu_lidera.sort(key=lambda m: m['orgu_total'], reverse=True)
        insights.append({
            'tipo': 'fortaleza_orgu',
            'titulo': '💪 ORGU lidera (fortalezas a defender)',
            'modelos': [m['modelo'] for m in orgu_lidera],
            'detalle': ' · '.join(f"{m['modelo']} (ORGU {m['orgu_total']} vs QM {m['qm_total']}, {m['orgu_share_total']:.0f}%/{m['qm_share_total']:.0f}%)" for m in orgu_lidera[:5]),
        })

    return {
        'source_file': Path(path).name,
        'modelos': modelos_data,
        'totales': tot,
        'meses': all_months,
        'insights': insights,
    }
