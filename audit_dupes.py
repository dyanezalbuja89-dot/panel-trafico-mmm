#!/usr/bin/env python3
"""Auditoría de duplicados literales en BDs de tráfico 2025-2026.

Un 'duplicado literal' = misma (CEDULA, MODELO, MARCA) registrado >1 vez
en el mismo mes. Eso indica error de digitación (mismo cliente, mismo
interés, contado varias veces).

Output: Excel con los casos detectados.
"""
import pandas as pd
from pathlib import Path

BD_DIR = Path("/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/"
              "Marketing/2026/Análisis de tráfico/2026/Mayo/BD_MAYO")

BD_FILES = [
    ("2025-10", "BD_OCT_31_10_25.xlsx"),
    ("2025-11", "BD_NOV_30_11_25.xlsx"),
    ("2025-12", "BD_DIC_31_12_25.xlsx"),
    ("2026-01", "BD_ENE_31_01_26.xlsx"),
    ("2026-02", "BD_FEB_28_02_26.xlsx"),
    ("2026-03", "BD_MARZO_31_03_26.xlsx"),
    ("2026-04", "BD_ABR_30_04_26.xlsx"),
    ("2026-05", "BD_MAY_19_05_26.xlsx"),
]

VALID_CHANNELS = ['Showroom', 'Hubspot', 'Ferias y Eventos', 'Feria/Eventos',
                  'Ferias', 'Llamada In']

all_dupes = []
summary = []

for mes, fname in BD_FILES:
    path = BD_DIR / fname
    if not path.exists():
        print(f"  ⚠ NO existe: {path}")
        continue
    df = pd.read_excel(path, sheet_name='Negocios')
    df['FECHA_dt'] = pd.to_datetime(df['FECHA'])
    df['ym'] = df['FECHA_dt'].dt.strftime('%Y-%m')
    # Solo registros del mes correspondiente
    df = df[df['ym'] == mes]
    if df.empty:
        continue

    # Normalizar modelo
    df['MODELO_F'] = df['MODELO'].astype(str).str.strip().str.upper()

    # Agrupar por (MARCA, CEDULA, MODELO_F)
    grouped = df.groupby(['MARCA','CEDULA','MODELO_F']).size().reset_index(name='n')
    dupes = grouped[grouped['n'] > 1].copy()
    dupes['mes'] = mes

    # Para cada duplicado, traer también el detalle de las filas
    for _, dup in dupes.iterrows():
        marca, ced, mod, n, m = dup['MARCA'], dup['CEDULA'], dup['MODELO_F'], dup['n'], dup['mes']
        rows = df[(df['MARCA']==marca) & (df['CEDULA']==ced) & (df['MODELO_F']==mod)]
        for _, r in rows.iterrows():
            all_dupes.append({
                'mes': m,
                'fecha': r['FECHA_dt'],
                'cedula': ced,
                'nombres': r.get('NOMBRES',''),
                'apellidos': r.get('APELLIDOS',''),
                'marca': marca,
                'modelo': r['MODELO_F'],
                'canal': r.get('CANAL',''),
                'sucursal': r.get('SUCURSAL',''),
                'asesor': r.get('ASESOR',''),
                'campaña': r.get('CAMPAÑA',''),
                'n_repeticiones': n,
            })

    # Summary por marca
    by_marca = dupes.groupby('MARCA').agg(
        casos=('n', 'count'),
        filas_extra=('n', lambda x: int((x-1).sum())),
    ).reset_index()
    by_marca['mes'] = mes
    summary.append(by_marca)

# Construir DataFrames y exportar
dupes_df = pd.DataFrame(all_dupes)
dupes_df = dupes_df.sort_values(['mes','marca','cedula','modelo','fecha'])
summary_df = pd.concat(summary, ignore_index=True) if summary else pd.DataFrame()
summary_df = summary_df.sort_values(['mes','MARCA']) if not summary_df.empty else summary_df

# Pivot summary: filas marca, columnas mes
pivot_casos = summary_df.pivot_table(index='MARCA', columns='mes', values='casos', fill_value=0).reset_index() if not summary_df.empty else pd.DataFrame()
pivot_filas = summary_df.pivot_table(index='MARCA', columns='mes', values='filas_extra', fill_value=0).reset_index() if not summary_df.empty else pd.DataFrame()

out = "/tmp/auditoria_duplicados_BD.xlsx"
with pd.ExcelWriter(out, engine='openpyxl') as w:
    if not dupes_df.empty:
        dupes_df.to_excel(w, sheet_name='Detalle_duplicados', index=False)
    summary_df.to_excel(w, sheet_name='Resumen_por_mes_marca', index=False)
    if not pivot_casos.empty:
        pivot_casos.to_excel(w, sheet_name='Pivot_casos', index=False)
        pivot_filas.to_excel(w, sheet_name='Pivot_filas_extra', index=False)

print(f"\n✓ Reporte: {out}")
print(f"  Total casos (cédula+modelo+marca duplicados): {len(dupes_df.groupby(['mes','marca','cedula','modelo']))}")
print(f"  Total filas duplicadas (a eliminar): {(dupes_df.groupby(['mes','marca','cedula','modelo']).size() - 1).sum()}")

# Print summary
print(f"\n=== RESUMEN ===")
print(pivot_casos.to_string() if not pivot_casos.empty else "(vacío)")
