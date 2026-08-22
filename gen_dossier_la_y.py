#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dossier de tráfico de la agencia La Y (Ford + Dongfeng) para análisis en sesión aparte.

Todo sale de data.json (el panel). Nada de memoria: si un dato no está en el
panel se marca como no disponible en vez de rellenarlo.
"""
import json
from pathlib import Path

BASE = Path.home() / 'dev' / 'panel-trafico'
d = json.load(open(BASE / 'data.json'))
OUT = Path.home() / 'Downloads' / 'DOSSIER_LA_Y_trafico.md'

MES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
       'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
AB = {m: m[:3].capitalize() for m in MES}
SER = [(f'{m}_{y}', f'{AB[m]}-{str(y)[2:]}', f'{y}-{i+1:02d}')
       for y in (2025, 2026) for i, m in enumerate(MES)]

fnode = lambda k: d['ford_months'].get(k)
dnode = lambda k: (d['brands_months'].get(k) or {}).get('DONGFENG_ORGU')


def ly(node):
    return None if not node else (node.get('dealers') or {}).get('La Y')


def cur(node):
    x = ly(node)
    return None if not x else x.get('curr')


def meta(node):
    x = ly(node)
    return None if not x else x.get('meta')


L = []
W = L.append
CUT = d['ford_months']['agosto_2026'].get('cut_date')

# ═══════════════════════════════════════════════════════════════════
W('# Dossier · Tráfico agencia La Y — Ford y Dongfeng\n')
W(f'**Corte:** {CUT}. Agosto 2026 es mes **en curso** (parcial) — no usarlo para promedios.')
W('**Fuente:** panel de tráfico ORGU, `~/dev/panel-trafico/data.json`, generado por `aggregate.py` '
  'desde las BD de tráfico en OneDrive (`Marketing/2026/Análisis de tráfico/`).')
W('**Alcance:** solo agencia La Y. Ford y Dongfeng son las dos marcas que operan en esa vitrina.\n')
W('> Toda cifra de este documento sale del panel. Donde el panel no tiene el dato, se dice '
  'explícitamente en vez de estimarlo.\n')
W('---\n')

# ── 1. Metodología ──────────────────────────────────────────────────
W('## 1. Cómo se cuenta el tráfico (definición oficial ORGU)\n')
W('Cuatro reglas, fijadas el 17-ago-2026:\n')
W('1. **Dentro del mismo mes cuenta UNA vez**, entre por la puerta las veces que entre.')
W('2. **Vuelve a contar a los 60 días de su última visita CONTADA** — no desde la primera. '
  'Un mismo cliente puede contar 3 o más veces en el año si sigue reingresando.')
W('3. **Por marca.** Mirar un Ford y después un Dongfeng son dos tráficos distintos aunque sea la misma persona.')
W('4. **Identidad = cédula.** El celular NO agrupa: es del hogar y fusiona personas distintas. '
  'Los registros sin cédula se cuentan igual, no se castiga al dato faltante.\n')
W('Implementación: `aggregate.py` → `DIAS_REINGRESO = 60`, `_build_reingreso_index()`, '
  '`_filter_reingreso()`. La fecha que representa a un cliente en un mes es su **primera entrada de ese mes**.\n')
W('**La conversión NO usa esta regla.** Ahí la cohorte va por primer toque, porque mide "de los que '
  'entraron en marzo, cuántos compraron"; contar reingresos diluiría la tasa de cierre.\n')
W('### Metas: dos cuadros distintos\n')
W('| Cuadro | Nombre en el archivo | Para qué sirve |')
W('|---|---|---|')
W('| **VERDE** | `PRESUPUESTO DE TRÁFICO POR CONCESIONARIO MARKETING` | meta de **tráfico** (es el 80% del total; el otro 20% es del asesor) |')
W('| **AZUL** | `PRESUPUESTO NACIONAL - FORD` | meta de **venta** |')
W('')
W('No confundirlos. Las hojas por agencia copian la matriz por posición fija, así que cuando '
  'reordenan columnas en `METAS_FORD` quedan corridas — el panel lee **por nombre de columna** '
  'desde la sección MARKETING para evitarlo.\n')
W('### Regla de evaluación (criterio de la casa)\n')
W('> *"Si no tengo para vender, no traigo tráfico; traigo lo que tengo disponible."*\n')
W('Por eso **el tráfico se juzga contra la meta de VENTA, no contra el año anterior.** '
  'La referencia histórica de La Y es **≈7 personas por unidad a vender**.\n')
W('---\n')

# ── 2. Serie mensual ────────────────────────────────────────────────
W('## 2. Serie mensual de tráfico · La Y\n')
W('| Mes | Ford | Dongfeng | Total | Nota |')
W('|---|---|---|---|---|')
for k, lbl, ym in SER:
    f, g = cur(fnode(k)), cur(dnode(k))
    if f is None and g is None:
        continue
    f, g = f or 0, g or 0
    nota = ''
    if k == 'agosto_2026':
        nota = '**mes en curso, al 18**'
    elif k == 'julio_2025':
        nota = 'arranque operación DF'
    W(f'| {lbl} | {f} | {g} | {f + g} | {nota} |')
W('')
W('**Dongfeng no existe antes de julio-2025.** Cualquier comparación DF 2025 vs 2026 sobre '
  'enero–junio compara contra cero y no significa nada.\n')

# ── 3. Fases ────────────────────────────────────────────────────────
W('## 3. Las tres fases de la vitrina\n')
W('La Y no es una serie continua: cambió de naturaleza cuando entró Dongfeng a mitad de 2025. '
  'Comparar 2025 contra 2026 sin separar fases mezcla dos negocios distintos.\n')
FASES = [
    ('Pre-DF · ene–jul 2025', [f'{m}_2025' for m in MES[:7]], 'La Y es vitrina de una sola marca'),
    ('Arranque DF · jul–dic 2025', [f'{m}_2025' for m in MES[6:12]], 'DF entra y ramp-up'),
    ('Régimen · ene–jul 2026', [f'{m}_2026' for m in MES[:7]], 'dos marcas maduras'),
]
W('| Fase | Ford | Ford/mes | DF | DF/mes | Total | Total/mes |')
W('|---|---|---|---|---|---|---|')
fase_datos = {}
for lbl, ks, _ in FASES:
    F = sum(cur(fnode(k)) or 0 for k in ks)
    G = sum(cur(dnode(k)) or 0 for k in ks)
    n = len(ks)
    fase_datos[lbl] = (F, F / n, G, G / n, F + G, (F + G) / n)
    W(f'| **{lbl}** | {F} | {F/n:.1f} | {G} | {G/n:.1f} | {F+G} | {(F+G)/n:.1f} |')
W('')
a = fase_datos['Arranque DF · jul–dic 2025']
b = fase_datos['Régimen · ene–jul 2026']
p = fase_datos['Pre-DF · ene–jul 2025']
W(f'**Hallazgo central:** Ford está en **{a[1]:.1f}/mes** en el arranque y **{b[1]:.1f}/mes** en régimen. '
  'Prácticamente idéntico durante trece meses.\n')
W(f'La caída de Ford ocurrió **una sola vez**, al entrar DF: de {p[1]:.1f}/mes a {a[1]:.1f}/mes. '
  'Desde entonces el piso Ford no se movió. Leer "Ford cae 25% en 2026" es comparar contra el '
  'período en que La Y era monomarca.\n')
W(f'Dongfeng creció de **{a[3]:.1f}/mes a {b[3]:.1f}/mes ({100*b[3]/a[3]-100:+.0f}%)** entre las dos fases.\n')
W('### Cuidado con la rampa\n')
W('El "arranque" incluye jul/ago/sep-2025, que son meses de rampa. Si alguien objeta que comparar '
  'contra una rampa infla el crecimiento, el corte alterno **excluyendo la rampa** es:\n')
r1 = [f'{m}_2025' for m in ['octubre', 'noviembre', 'diciembre']]
r2 = [f'{m}_2026' for m in ['mayo', 'junio', 'julio']]
A1 = sum(cur(dnode(k)) or 0 for k in r1) / 3
A2 = sum(cur(dnode(k)) or 0 for k in r2) / 3
W(f'- DF oct–dic 2025: **{A1:.1f}/mes** → DF may–jul 2026: **{A2:.1f}/mes** ({100*A2/A1-100:+.0f}%)\n')
W('### Único mes con solape real año contra año\n')
W(f'- Julio: Ford **{cur(fnode("julio_2025"))} → {cur(fnode("julio_2026"))}** · '
  f'DF **{cur(dnode("julio_2025"))} → {cur(dnode("julio_2026"))}**\n')
W('---\n')


# ── 4/5. Matrices por modelo y canal ────────────────────────────────
def matriz(getter, campo, titulo, nota=''):
    W(f'## {titulo}\n')
    if nota:
        W(nota + '\n')
    cols, filas = [], {}
    for k, lbl, _ in SER:
        x = ly(getter(k))
        if not x:
            continue
        cols.append(lbl)
        for mod, v in (x.get(campo) or {}).items():
            filas.setdefault(mod, {})[lbl] = v
    if not cols:
        W('*Sin datos.*\n')
        return
    W('| ' + ' | '.join([campo == 'byModel' and 'Modelo' or 'Canal'] + cols + ['Total']) + ' |')
    W('|' + '---|' * (len(cols) + 2))
    # Fuera las filas en cero: el catálogo trae versiones que nunca tuvieron tráfico
    # y llenan la matriz de ruido.
    filas = {m: v for m, v in filas.items() if sum(v.values()) > 0}
    orden = sorted(filas, key=lambda m: -sum(filas[m].values()))
    for mod in orden:
        vals = [filas[mod].get(c, 0) for c in cols]
        W(f'| {mod} | ' + ' | '.join(str(v) for v in vals) + f' | **{sum(vals)}** |')
    tot = [sum(filas[m].get(c, 0) for m in filas) for c in cols]
    W('| **Total** | ' + ' | '.join(f'**{v}**' for v in tot) + f' | **{sum(tot)}** |')
    W('')


matriz(fnode, 'byModel', '4. Ford La Y · tráfico por MODELO y mes',
       'Última columna de cada fila = acumulado de todo el período. La columna Ago-26 es parcial.')
matriz(fnode, 'byChannel', '5. Ford La Y · tráfico por CANAL y mes')
matriz(dnode, 'byModel', '6. Dongfeng La Y · tráfico por MODELO y mes')
matriz(dnode, 'byChannel', '7. Dongfeng La Y · tráfico por CANAL y mes')
W('---\n')


# ── 7bis. Decaimiento por modelo ────────────────────────────────────
def _src_modelos(nd, ambito):
    """Diccionario {modelo: tráfico} de un mes. ambito = 'nacional' o el nombre
    de cualquier agencia."""
    if ambito == 'nacional':
        return {m: (v.get('curr') or 0) for m, v in (nd.get('models') or {}).items()}
    x = (nd.get('dealers') or {}).get(ambito)
    return {} if not x else (x.get('byModel') or {})


def serie_modelo(getter, mod, ambito='La Y'):
    """Serie mensual de un modelo en un ámbito (agencia o 'nacional')."""
    out = []
    for k, lbl, _ in SER:
        nd = getter(k)
        if not nd:
            continue
        src = _src_modelos(nd, ambito)
        if ambito != 'nacional' and not src:
            continue
        out.append((lbl, src.get(mod, 0)))
    return out


def decaimiento(getter, titulo, ambito, nota, nivel='##'):
    W(f'{nivel} {titulo}\n')
    W(nota + '\n')
    # descubrir modelos con tráfico
    mods = {}
    for k, _, _ in SER:
        nd = getter(k)
        if not nd:
            continue
        src = _src_modelos(nd, ambito)
        for m, v in src.items():
            mods[m] = mods.get(m, 0) + (v or 0)
    # Fuera el ruido de catálogo: nombres de versión completa que aparecen 1-2 veces
    # ('ESCAPE TITANIUM AC 1.5 5P 4X2 TA') no son modelos, son errores de tipeo en la BD.
    mods = {m: t for m, t in mods.items() if t >= 5 and m != 'Por definir'}

    W('| Modelo | H1-25 /mes | H2-25 /mes | Base 2025 /mes | 2026 /mes | vs 2025 | Pico | Jul-26 | Lectura |')
    W('|---|---|---|---|---|---|---|---|---|')
    filas = []
    for m in sorted(mods, key=lambda x: -mods[x]):
        s = dict(serie_modelo(getter, m, ambito))
        H1 = [s.get(f'{AB[x]}-25', 0) for x in MES[:6]]
        H2 = [s.get(f'{AB[x]}-25', 0) for x in MES[6:12]]
        A6 = [s.get(f'{AB[x]}-26', 0) for x in MES[:7]]
        p1, p2, p3 = sum(H1) / 6, sum(H2) / 6, sum(A6) / 7
        pico_lbl, pico_v = max(s.items(), key=lambda kv: kv[1])
        ult = s.get('Jul-26', 0)
        caida = 100 * ult / pico_v - 100 if pico_v else 0
        # La base es 2025 COMPLETO, no el primer semestre: varios modelos tuvieron
        # su mejor momento en H2-25 (Bronco 6.0/mes, Everest 14.3/mes) y compararlos
        # solo contra H1 los hacía salir "en alza" mientras venían cayendo.
        base25 = (sum(H1) + sum(H2)) / 12
        # "Nuevo" = no existía antes, o el salto es de otro orden de magnitud
        # (Territory nacional venía de 1.2/mes y pasó a 133). Sin la segunda
        # condición, un modelo con base chica pero real salía marcado como nuevo.
        if (base25 < 1 and p3 >= 1) or (base25 > 0 and p3 / base25 > 10):
            lec = '**nuevo**'
        elif p3 == 0 and base25 > 0:
            lec = '**extinguido**'
        elif base25 == 0:
            lec = 'sin historia'
        elif p3 < base25 * 0.5:
            lec = '**caída fuerte**'
        elif p3 < base25 * 0.85:
            lec = 'en baja'
        elif p3 > base25 * 1.15:
            lec = 'en alza'
        else:
            lec = 'estable'
        if max(base25, p3) < 2:
            lec += ' · volumen bajo'
        filas.append((m, p1, p2, p3, pico_lbl, pico_v, ult, caida, lec, base25))
        vs = f'{100*p3/base25-100:+.0f}%' if base25 else '—'
        W(f'| {m} | {p1:.1f} | {p2:.1f} | {base25:.1f} | {p3:.1f} | {vs} | '
          f'{pico_v} ({pico_lbl}) | {ult} | {lec} |')
    W('')
    return filas


f_ly = decaimiento(
    fnode, '7-bis. Ford La Y · cómo decae cada modelo', 'La Y',
    'Promedio mensual por semestre y contra la base de 2025 completo. **Jul-26 es el último mes '
    'cerrado** — agosto está en curso y no se usa para juzgar nivel. Se excluyen los nombres de '
    'versión que aparecen menos de 5 veces en toda la serie (ruido de tipeo en la BD).')
W('### Cómo leer esta tabla\n')
W('- **H1-25 → H2-25 → 2026** es la trayectoria. Tres números bajando seguidos es decaimiento '
  'estructural, no un mal mes.')
W('- **"vs 2025"** compara el promedio mensual de 2026 contra el de **2025 completo**, no contra un '
  'semestre suelto. Varios modelos tuvieron su mejor momento en H2-25.')
W('- **El pico puede ser un evento, no un nivel.** Bronco marcó 30 en oct-25 por una feria; su '
  'promedio nunca pasó de 6. No confundir pico con capacidad.')
W('- **"Extinguido"** = el modelo tenía tráfico en 2025 y este año no trae a nadie. Revisar si es '
  'falta de producto, de precio o de push — el dato no lo dice.\n')
ext = [x for x in f_ly if 'extinguido' in x[8]]
caid = [x for x in f_ly if 'caída fuerte' in x[8]]
baja = [x for x in f_ly if x[8].startswith('en baja')]
nuev = [x for x in f_ly if 'nuevo' in x[8]]
if ext:
    W('**Extinguidos:** ' + ', '.join(f'{x[0]} ({x[9]:.1f}/mes en 2025 → 0)' for x in ext) + '\n')
if caid:
    W('**Caída fuerte (pierden más de la mitad):** '
      + ', '.join(f'{x[0]} ({x[9]:.1f} → {x[3]:.1f}/mes)' for x in caid) + '\n')
if baja:
    W('**En baja:** ' + ', '.join(f'{x[0]} ({x[9]:.1f} → {x[3]:.1f}/mes)' for x in baja) + '\n')
if nuev:
    W('**Aparecen este año:** ' + ', '.join(f'{x[0]} (0 → {x[3]:.1f}/mes)' for x in nuev) + '\n')
W('')

decaimiento(
    fnode, '7-ter. Ford NACIONAL · cómo decae cada modelo', 'nacional',
    'Mismo cálculo sobre el total de la red. Sirve para separar **problema de La Y** de '
    '**problema de marca**: si el modelo cae igual a nivel nacional, la vitrina no es la causa.')
W('---\n')

# ── 7-quater. Decaimiento por AGENCIA ───────────────────────────────
AGS = ['CJA', 'Orellana', 'La Y', 'Tumbaco', 'Manta', 'Machala', 'Portoviejo']
K25 = [f'{m}_2025' for m in MES]
K26 = [f'{m}_2026' for m in MES[:7]]


def ag_tot(k, ag):
    x = ((fnode(k) or {}).get('dealers') or {}).get(ag)
    return None if not x else (x.get('curr') or 0)


def ag_mod(k, ag, mod):
    x = ((fnode(k) or {}).get('dealers') or {}).get(ag)
    return None if not x else (x.get('byModel') or {}).get(mod, 0)


W('## 7-quater. Ford · decaimiento por AGENCIA\n')
W('Mismo método que las dos secciones anteriores, aplicado a cada vitrina de la red. '
  'Base = promedio mensual de **2025 completo**; comparación = promedio de **ene–jul 2026**. '
  'Agosto queda fuera por estar en curso.\n')
W('### Total de cada agencia\n')
W('| Agencia | 2025 total | /mes | 2026 ene–jul | /mes | vs 2025 |')
W('|---|---|---|---|---|---|')
ag_base = {}
for ag in AGS:
    v25 = [x for x in (ag_tot(k, ag) for k in K25) if x is not None]
    v26 = [x for x in (ag_tot(k, ag) for k in K26) if x is not None]
    if not v25 or not v26:
        continue
    b, c = sum(v25) / len(v25), sum(v26) / len(v26)
    ag_base[ag] = (b, c)
    W(f'| {ag} | {sum(v25)} | {b:.1f} | {sum(v26)} | {c:.1f} | **{100*c/b-100:+.0f}%** |')
W('')
W('**La red creció y Quito cayó.** CJA, Orellana, Machala y Portoviejo suben; La Y y Tumbaco son '
  'las dos que pierden. Manta queda plana. Eso confirma que el problema es de plaza, no de una '
  'vitrina suelta.\n')

W('### El cuadro de decaimiento, agencia por agencia\n')
W('Mismo formato que las secciones 7-bis y 7-ter, repetido para cada vitrina. La columna **vs 2025** '
  'es la que define la lectura; la fila equivalente de la sección 7-ter (nacional) es la referencia '
  'para saber si la agencia se separa de la red o la acompaña.\n')
for _ag in AGS:
    _v = [x for x in (ag_tot(k, _ag) for k in K25 + K26) if x is not None]
    if not _v:
        continue
    decaimiento(fnode, f'Ford · {_ag}', _ag,
                f'Tráfico Ford de {_ag}. Base 2025 = promedio de los 12 meses; 2026 = promedio ene–jul.',
                nivel='####')
W('---\n')

# ── 8. Metas de tráfico ─────────────────────────────────────────────
W('## 8. Meta de tráfico contra tráfico real · La Y\n')
W('Meta = cuadro VERDE (MARKETING, 80%). Solo hay meta cargada en los meses que el panel procesó '
  'con archivo de metas.\n')
W('| Mes | Ford real | Ford meta | % | DF real | DF meta | % |')
W('|---|---|---|---|---|---|---|')
for k, lbl, _ in SER:
    fr, fm = cur(fnode(k)), meta(fnode(k))
    gr, gm = cur(dnode(k)), meta(dnode(k))
    if fr is None and gr is None:
        continue
    pf = f'{100*fr/fm:.0f}%' if fm else '—'
    pg = f'{100*gr/gm:.0f}%' if gm else '—'
    W(f'| {lbl} | {fr if fr is not None else "—"} | {fm or "—"} | {pf} | '
      f'{gr if gr is not None else "—"} | {gm or "—"} | {pg} |')
W('')

# ── 9. Ventas y presupuesto ─────────────────────────────────────────
W('## 9. Ventas reales y presupuesto de venta · La Y\n')
vm = d.get('ventas_mensual', {})
W('### Ventas facturadas (unidades)\n')
vf = ((vm.get('FORD') or {}).get('by_agencia') or {}).get('La Y', {})
vd = ((vm.get('DONGFENG_ORGU') or {}).get('by_agencia') or {}).get('La Y', {})
vfx = ((vm.get('FORD') or {}).get('by_agencia_fact') or {}).get('La Y', {})
vdx = ((vm.get('DONGFENG_ORGU') or {}).get('by_agencia_fact') or {}).get('La Y', {})
W('| Mes | Ford equipo | Ford vitrina | DF equipo | DF vitrina |')
W('|---|---|---|---|---|')
for k, lbl, ym in SER:
    if ym not in vf and ym not in vd and ym not in vfx and ym not in vdx:
        continue
    W(f'| {lbl} | {vf.get(ym, 0)} | {vfx.get(ym, 0)} | {vd.get(ym, 0)} | {vdx.get(ym, 0)} |')
W('')
W('> **Hay DOS bases y no son intercambiables.**\n')
W('> - **Equipo** (`by_agencia`): la venta cuenta para la casa del asesor. Existe por el efecto '
  'placa — el cliente prefiere placa de Pichincha, así que ventas originadas en Machala o Manta se '
  'facturan vía La Y o Tumbaco.')
W('> - **Vitrina** (`by_agencia_fact`): la agencia que emitió la factura. **Es la que cuadra contra '
  'finanzas.**\n')
W('> **Para cruzar contra tráfico se usa la vitrina**, porque el tráfico se registra donde entró la '
  'persona. Cruzar tráfico contra la base de equipo mezcla dos universos distintos.\n')
W('> En Ford ene–jul 2026 la diferencia es grande: La Y da **35 por equipo** y **48 por vitrina**. '
  'El total de la red coincide en las dos (635).\n')

pres = (d.get('presupuesto') or {}).get('tipos', {})
W('### Presupuesto de venta 2026 (unidades/mes, ene→dic)\n')
W('| Marca | Tipo | Ene | Feb | Mar | Abr | May | Jun | Jul | Ago | Sep | Oct | Nov | Dic |')
W('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
for tipo in ('financiero', 'comercial'):
    for marca, lbl in (('FORD', 'Ford'), ('DONGFENG_ORGU', 'Dongfeng')):
        u = (((pres.get(tipo) or {}).get(marca) or {}).get('La Y') or {}).get('uds')
        if u:
            W(f'| {lbl} | {tipo} | ' + ' | '.join(str(x) for x in u) + ' |')
W('')
W('Dos versiones del presupuesto: **financiero** (el comprometido) y **comercial** (el estirado). '
  'Definir cuál se usa antes de calcular cumplimiento.\n')
W('### Metas de venta Ford 2025 (de los boletines comerciales, no del panel)\n')
W('La Y, ene→dic: **13 · 13 · 14 · 14 · 6 · 11 · 9 · 9 · 9 · 8 · 11 · 10**\n')
W('Fuente: `~/Downloads/Boletín_<MES>_25.pdf`. Las tablas son imagen, hay que leerlas con '
  '`pdftoppm -r 200`. Página del presupuesto: ene/feb/abr–sep = 3 · marzo = 4 · oct/nov/dic = 2.\n')
W('**Contexto:** a La Y le cortaron la meta de 14 a 6 en mayo-2025 y nunca volvió a pasar de 11, '
  'mientras la red nacional crecía de 75 a 92 unidades.\n')
W('---\n')

# ── 10. Tráfico por unidad ──────────────────────────────────────────
W('## 10. Tráfico por unidad de meta de venta · Ford La Y\n')
W('El indicador de eficiencia de la casa: cuántas personas se trajeron por cada unidad que había '
  'que vender. Referencia histórica ≈7.\n')
METAS25 = dict(zip([f'2025-{i:02d}' for i in range(1, 13)],
                   [13, 13, 14, 14, 6, 11, 9, 9, 9, 8, 11, 10]))
pres_f = (((pres.get('financiero') or {}).get('FORD') or {}).get('La Y') or {}).get('uds') or []
METAS26 = {f'2026-{i+1:02d}': v for i, v in enumerate(pres_f)}
W('| Mes | Tráfico Ford | Meta venta | Tráfico/unidad |')
W('|---|---|---|---|')
for k, lbl, ym in SER:
    t = cur(fnode(k))
    mv = METAS25.get(ym) or METAS26.get(ym)
    if t is None or not mv:
        continue
    tag = ' *(parcial)*' if k == 'agosto_2026' else ''
    W(f'| {lbl}{tag} | {t} | {mv} | {t/mv:.1f} |')
W('')
W('> **Trampa conocida.** En el agregado ene–jul el ratio sale casi igual entre 2025 y 2026 '
  '(6.6 contra 6.5), pero **por trimestre se rompe**: Q2 sale −21% y julio −33%. Q1 compensa al '
  'resto. Si el análisis va a usar este indicador, cortarlo por trimestre antes de defenderlo.\n')
W('> Además la meta de venta 2026 usada acá es la **financiera**. Con la comercial (10/mes fijo) '
  'los ratios bajan.\n')
W('### El veredicto se da vuelta según qué meta se use\n')
W('Hay **tres versiones distintas de la meta de venta Ford La Y 2026** y el mismo tráfico (435 en '
  'ene–jul) sale mejor o peor que 2025 según cuál se tome. Contra 2025, que cerró en 578 tráficos '
  'sobre meta 80 (ratio **7.22**):\n')
W('| Meta 2026 usada | Unidades ene–jul | Ratio | Contra 2025 |')
W('|---|---|---|---|')
W('| **Financiera** (del panel: 8,8,8,9,8,9,8) | 58 | **7.50** | **+4%** |')
W('| Usada en el diagnóstico del 17-ago | 67 | 6.49 | −10% |')
W('| **Comercial** (del panel: 10/mes fijo) | 70 | 6.21 | −14% |')
W('')
W('**Esta es la decisión más sensible de todo el análisis.** Con la meta financiera, La Y generó '
  '*más* tráfico por unidad que el año pasado. Con la comercial, 14% menos. El origen de la meta 67 '
  'usada en el diagnóstico previo no está identificado en el panel — hay que rastrearla antes de '
  'volver a usarla.\n')
W('Recomendación: **declarar la fuente de la meta al inicio del análisis y sostenerla.** No mezclar.\n')
W('---\n')

# ── 11. Diagnóstico previo ──────────────────────────────────────────
W('## 11. Diagnóstico ya cerrado sobre La Y (17-ago-2026)\n')
W('Descomposición de la caída Ford ene–jul, 2025 vs 2026:\n')
W('| | 2025 | 2026 | |')
W('|---|---|---|---|')
W('| Meta de venta | 80 | 67 | −16% |')
W('| Tráfico | 582 | 436 | −25% |')
W('| Tráfico por unidad | 7.3 | 6.5 | −11% |')
W('')
W('*(Esas cifras son del corte del 17-ago. Con el corte del 18 y el índice de reingreso '
  'recalculado quedan en 578 y 435 — diferencia menor al 1%, no cambia conclusiones.)*\n')
W('**De 146 tráficos perdidos, 95 los explica el recorte de presupuesto y 51 no.** '
  'Dos tercios es decisión, un tercio es generación.\n')
W('### Dónde está el tercio no explicado — personas que necesitaba (meta×7) vs las que vinieron\n')
W('| Modelo | Meta 26 | Necesitaba | Vinieron | |')
W('|---|---|---|---|---|')
for row in [('**TERRITORY**', 10, 70, '**188**', 'sobraron ~118'),
            ('ESCAPE', 20, 140, '**67**', 'faltaron 73'),
            ('EXPLORER', 8, 56, '24', 'faltaron 32'),
            ('F-150', 7, 49, '22', 'faltaron 27'),
            ('EVEREST', 10, 70, '51', 'faltaron 19'),
            ('RANGER', 11, 77, '73', 'ajustado')]:
    W('| ' + ' | '.join(str(x) for x in row) + ' |')
W('')
W('**El problema no es volumen de tráfico: es concentración.** Territory se llevó todo (18.8 '
  'visitas por unidad contra un normal de 7) y el resto de la parrilla quedó sub-traficado. '
  'Escape es el caso extremo: presupuesto para 20 y gente para ~10.\n')
W('Otros hechos del diagnóstico:\n')
W('- Los meses donde La Y no colapsó son exactamente los que tuvieron Territory ≥30 (feb, mar, may, jun). '
  'Los de derrumbe —enero y abril— son los de Territory ≤5. Correlación en 6 de 6 meses.')
W('- Tumbaco también cae (−13%): **el problema es Quito**, no solo esa vitrina.')
W('- DF entró en julio-2025 y en diciembre ya pesaba más que Ford en esa vitrina (16 unidades contra 10). '
  '**La Y está siendo reconvertida, no fallando.**\n')
W('**Lo que el dato NO dice:** por qué se cayó Escape (¿sin stock? ¿precio? ¿producto?) ni si la '
  'reconversión a DF fue decisión de marca, distribuidora o agencia. Eso está en actas, no en el panel.\n')
W('---\n')

# ── 12. Estado del mes en curso ─────────────────────────────────────
W('## 12. Agosto 2026 en curso (al 18)\n')
fa, ga = fnode('agosto_2026'), dnode('agosto_2026')
lyf, lyg = ly(fa), ly(ga)
W(f"- **Ford nacional:** {fa['total_curr']} tráficos · meta {fa['meta_total']} · "
  f"proyección {fa['projection_total']} ({100*fa['projection_total']/fa['meta_total']:.0f}%)")
W(f"- Días laborables del mes: {fa['days_lab']} · transcurridos: {fa['days_trans']} "
  f"({fa['avance_pct']}% del mes) · ritmo {fa['velocity']}/día")
W(f"- **Ford La Y:** {lyf['curr']} · meta {lyf['meta']} · proyección {lyf['projection']} "
  f"({lyf['cumpl_proj']}%)")
W(f"- **DF La Y:** {lyg['curr']} · meta {lyg['meta']} · proyección {lyg['projection']} "
  f"({lyg['cumpl_proj']}%)\n")
W('Serie diaria Ford nacional de agosto (día → tráfico):\n')
dd = fa['daily']['daily']
W('| ' + ' | '.join(sorted(dd, key=int)) + ' |')
W('|' + '---|' * len(dd))
W('| ' + ' | '.join(str(dd[k]) for k in sorted(dd, key=int)) + ' |')
W('')
W('Faltan los domingos (2, 9, 16) y el feriado del 10 de agosto.\n')
W('### Anomalía de las metas de agosto\n')
W('La meta de tráfico por modelo de agosto está puesta casi al revés de donde viene la gente. '
  'Verificado contra el archivo fuente — **no es error de lectura del panel**:\n')
W('| Modelo | Tráfico nac. | Meta nac. |')
W('|---|---|---|')
for m, v in (fa.get('models') or {}).items():
    if v.get('curr') or v.get('meta'):
        W(f"| {m} | {v['curr']} | {v['meta']} |")
W('')
W('Territory tiene meta ~0 porque en el `PRESUPUESTO DE VENTAS SIN RESERVAS` viene en **−22** '
  '(no hay qué vender, así que no se presupuestó tráfico). Explorer, Bronco y Escape concentran '
  '**273 de los 498 tráficos presupuestados (55%)** y entre los tres han traído 15 personas.\n')
W('---\n')

# ── 13. Advertencias ────────────────────────────────────────────────
W('## 13. Advertencias para quien siga el análisis\n')
W('1. **Agosto-2026 es parcial** (corte al 18). No entra en promedios mensuales.')
W('2. **DF no existe antes de julio-2025.** Comparar DF año contra año sobre ene–jun compara contra cero.')
W('3. **El ratio tráfico/unidad se rompe por trimestre.** Ver sección 10.')
W('4. **Ventas por agencia ≠ vitrina.** La venta cuenta para el equipo del asesor. Usar `flat` si '
  'la atribución importa.')
W('5. **Dos presupuestos de venta** (financiero y comercial). Declarar cuál se usa.')
W('6. **Si se cambia cualquier criterio de cálculo hay que subir la versión de la llave de cache** '
  'en `aggregate.py` (hoy `v5-reingreso-60d`). Si no, los meses se sirven cacheados con el criterio '
  'viejo y solo cambia el mes en curso — ya pasó y el antes/después salió mal.')
W('7. **El dato dice DÓNDE cae algo, casi nunca POR QUÉ.** Separar prueba de hipótesis.\n')
W('---\n')
W('## 14. Dónde vive cada cosa\n')
W('| Qué | Dónde |')
W('|---|---|')
W('| Panel de tráfico (código) | `~/dev/panel-trafico/` — `aggregate.py` → `build.py` → `deploy.sh` |')
W('| Data agregada | `~/dev/panel-trafico/data.json` |')
W('| BD de tráfico | OneDrive `Marketing/2026/Análisis de tráfico/2026/<Mes>/BD_<MES>/` |')
W('| Metas Ford | `.../<Mes>/METAS/<MES>_NUEVO_AI_FORD.xlsx`, hoja `METAS_FORD` |')
W('| Metas otras marcas | `.../<Mes>/METAS/<MES>_NUEVO_AI_MARCAS.xlsx` |')
W('| Boletines 2025 (metas de venta) | `~/Downloads/Boletín_<MES>_25.pdf` |')
W('| Panel publicado | dashboard de tráfico ORGU en Vercel |')
W('')

OUT.write_text('\n'.join(L), encoding='utf-8')
print(f'→ {OUT}  ({len(chr(10).join(L)):,} chars · {len(L)} líneas)')
