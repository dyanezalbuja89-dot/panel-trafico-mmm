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
    if 'TERRITORY TREND' in n:
        return 'TERRITORY TREND'
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
    if ('F150' in n or 'F-150' in n) and 'XLT' in n:
        return 'F150 XLT'
    if ('F150' in n or 'F-150' in n) and 'LARIAT' in n:
        return 'F150 LARIAT'
    if ('F150' in n or 'F-150' in n) and 'PLATINUM' in n:
        return 'F150 PLATINUM'
    if 'MAVERICK' in n:
        return 'MAVERICK'
    if 'BRONCO' in n:
        return 'BRONCO'
    if 'EDGE' in n:
        return 'EDGE'

    # No matched → devolver el original (para revisar manualmente luego)
    return raw_name.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Parseo de archivos aduaneros crudos (formato 2026: BD AUTOSHARECORP / BD QM)
#   - Una fila por importación (cada fila = 1 vehículo)
#   - 3 hojas: 2024, 2025, 2026
#   - Columnas: DIA, MES, AÑO, MARCA, MODELO MERCADERIA, CANTIDAD, US$ CIF, ...
# ─────────────────────────────────────────────────────────────────────────────
# Archivos aduaneros: (nombre_que_contiene, distribuidor)
_ADUANA_FILES = [
    ('BD AUTOSHARECORP', 'ORGU'),
    ('BD QM', 'QM'),
]
_ADUANA_DIRS = [
    Path("/Users/danielyanezalbuja/Downloads"),
    Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Inventrario"),
]


def find_aduana_files():
    """Devuelve {distribuidor: path} para los archivos aduaneros ORGU/QM."""
    found = {}
    for needle, dist in _ADUANA_FILES:
        for d in _ADUANA_DIRS:
            if not d.exists():
                continue
            cands = [p for p in d.glob('*.xlsx')
                     if needle.upper() in p.name.upper() and not p.name.startswith('~$')]
            if cands:
                cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                found[dist] = cands[0]
                break
    return found


def parse_aduana_file(path, distribuidor):
    """Lee las 3 hojas (2024/2025/2026) de un archivo aduanero y devuelve filas
    planas. Cada fila = 1 vehículo (se cuenta por registro, robusto ante el
    error de captura donde CANTIDAD=100000 en algunos lotes)."""
    rows = []
    xl = pd.ExcelFile(path)
    for sheet in xl.sheet_names:
        try:
            anio_sheet = int(str(sheet).strip())
        except (ValueError, TypeError):
            continue
        df = pd.read_excel(path, sheet_name=sheet)
        cols = {str(c).strip().upper(): c for c in df.columns}
        col_marca  = cols.get('MARCA')
        col_modelo = cols.get('MODELO MERCADERIA') or cols.get('MODELO')
        col_mes    = cols.get('MES')
        col_anio   = cols.get('AÑO') or cols.get('ANO') or cols.get('AÑO ')
        col_cant   = cols.get('CANTIDAD')
        col_cif    = cols.get('US$ CIF') or cols.get('US$CIF')
        if col_modelo is None:
            continue
        for _, r in df.iterrows():
            marca = str(r.get(col_marca, '')).upper()
            if 'FORD' not in marca:
                continue
            modelo_raw = r.get(col_modelo)
            if pd.isna(modelo_raw):
                continue
            mes = r.get(col_mes)
            anio = r.get(col_anio)
            try:
                anio = int(anio) if pd.notna(anio) else anio_sheet
            except (ValueError, TypeError):
                anio = anio_sheet
            try:
                mes = int(mes) if pd.notna(mes) else 0
            except (ValueError, TypeError):
                mes = 0
            ym = f"{anio:04d}-{mes:02d}" if mes else f"{anio:04d}-00"
            # cantidad: cada fila = 1 vehículo (el campo CANTIDAD tiene errores
            # de captura tipo 100000; contamos por registro)
            cant = 1
            cif = 0.0
            if col_cif is not None:
                try:
                    cif_raw = float(r.get(col_cif) or 0)
                    # Si la cantidad capturada era anómala, el CIF también puede
                    # estar inflado; lo descartamos para no contaminar el total.
                    cant_raw = r.get(col_cant)
                    cant_raw = float(cant_raw) if pd.notna(cant_raw) else 1
                    cif = cif_raw if cant_raw < 1000 else 0.0
                except (ValueError, TypeError):
                    cif = 0.0
            rows.append({
                'modelo_raw': str(modelo_raw).strip(),
                'modelo': consolidate_model(str(modelo_raw)),
                'distribuidor': distribuidor,
                'anio': anio,
                'ym': ym,
                'cantidad': cant,
                'cif': cif,
            })
    return rows


def parse_imports_aduana(files_map):
    """Une los archivos ORGU + QM en un solo DataFrame plano."""
    all_rows = []
    for dist, path in files_map.items():
        all_rows.extend(parse_aduana_file(path, dist))
    df = pd.DataFrame(all_rows)
    if df.empty:
        return df, []
    all_months = sorted([ym for ym in df['ym'].unique() if not ym.endswith('-00')])
    return df, all_months


# ─────────────────────────────────────────────────────────────────────────────
# Agregación para el panel
# ─────────────────────────────────────────────────────────────────────────────
def compute_competencia_data(path=None):
    files_map = find_aduana_files()
    if not files_map:
        return None
    df, all_months = parse_imports_aduana(files_map)
    if df.empty:
        return None

    def _u(sub, dist, anio):
        return int(len(sub[(sub['distribuidor']==dist) & (sub['anio']==anio)]))
    def _cif(sub, dist, anio):
        return float(sub[(sub['distribuidor']==dist) & (sub['anio']==anio)]['cif'].sum())

    # Agregar por modelo
    modelos_data = []
    for modelo in df['modelo'].unique():
        sub = df[df['modelo'] == modelo]
        orgu_24 = _u(sub,'ORGU',2024); qm_24 = _u(sub,'QM',2024)
        orgu_25 = _u(sub,'ORGU',2025); qm_25 = _u(sub,'QM',2025)
        orgu_26 = _u(sub,'ORGU',2026); qm_26 = _u(sub,'QM',2026)
        tot_24 = orgu_24 + qm_24
        tot_25 = orgu_25 + qm_25
        tot_26 = orgu_26 + qm_26
        total  = tot_24 + tot_25 + tot_26
        orgu_total = orgu_24 + orgu_25 + orgu_26
        qm_total   = qm_24 + qm_25 + qm_26
        mensual = {}
        for ym in all_months:
            o = int(len(sub[(sub['distribuidor']=='ORGU') & (sub['ym']==ym)]))
            q = int(len(sub[(sub['distribuidor']=='QM')   & (sub['ym']==ym)]))
            mensual[ym] = {'orgu': o, 'qm': q}
        modelos_data.append({
            'modelo': modelo,
            'orgu_2024': orgu_24, 'qm_2024': qm_24, 'tot_2024': tot_24,
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
            'cif_orgu_2026': round(_cif(sub,'ORGU',2026)),
            'cif_qm_2026': round(_cif(sub,'QM',2026)),
            'mensual': mensual,
        })
    modelos_data.sort(key=lambda m: -m['total'])

    # Totales globales
    tot = {
        'orgu_2024': sum(m['orgu_2024'] for m in modelos_data),
        'qm_2024':   sum(m['qm_2024']   for m in modelos_data),
        'orgu_2025': sum(m['orgu_2025'] for m in modelos_data),
        'qm_2025':   sum(m['qm_2025']   for m in modelos_data),
        'orgu_2026': sum(m['orgu_2026'] for m in modelos_data),
        'qm_2026':   sum(m['qm_2026']   for m in modelos_data),
    }
    tot['tot_2024'] = tot['orgu_2024'] + tot['qm_2024']
    tot['tot_2025'] = tot['orgu_2025'] + tot['qm_2025']
    tot['tot_2026'] = tot['orgu_2026'] + tot['qm_2026']
    tot['total']    = tot['tot_2024'] + tot['tot_2025'] + tot['tot_2026']
    tot['orgu_total'] = tot['orgu_2024'] + tot['orgu_2025'] + tot['orgu_2026']
    tot['qm_total']   = tot['qm_2024'] + tot['qm_2025'] + tot['qm_2026']
    tot['orgu_share_2024'] = round(100*tot['orgu_2024']/tot['tot_2024'], 1) if tot['tot_2024'] else 0
    tot['orgu_share_2025'] = round(100*tot['orgu_2025']/tot['tot_2025'], 1) if tot['tot_2025'] else 0
    tot['orgu_share_2026'] = round(100*tot['orgu_2026']/tot['tot_2026'], 1) if tot['tot_2026'] else 0
    tot['delta_share_total'] = round(tot['orgu_share_2026'] - tot['orgu_share_2025'], 1)
    tot['cif_orgu_2026'] = round(float(df[(df['distribuidor']=='ORGU') & (df['anio']==2026)]['cif'].sum()))
    tot['cif_qm_2026']   = round(float(df[(df['distribuidor']=='QM')   & (df['anio']==2026)]['cif'].sum()))

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
        'source_file': ' + '.join(p.name for p in files_map.values()),
        'modelos': modelos_data,
        'totales': tot,
        'meses': all_months,
        'insights': insights,
    }
