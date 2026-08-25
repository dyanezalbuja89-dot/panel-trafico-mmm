#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verificador de invariantes del panel de tráfico ORGU.

Convierte en código las reglas que hasta ahora vivían solo escritas. Cada check
compara el panel contra su fuente de verdad y falla ruidoso.

    python3 verificar.py            # todos los checks
    python3 verificar.py --strict   # exit 1 si algo falla (para deploy.sh)

Por qué existe: las reglas escritas no impiden el error en el momento; un check
que se ejecuta, sí. Los cuatro descuadres reales de agosto 2026 (ventas revertidas
que sobrevivían en la unión de snapshots) los detectó un check, no una nota.
"""
import json
import sys
import warnings
from pathlib import Path

import pandas as pd

warnings.simplefilter('ignore')
BASE = Path(__file__).parent
OK, FAIL, WARN = [], [], []


def ok(nombre, detalle=''):
    OK.append((nombre, detalle))


def fail(nombre, detalle):
    FAIL.append((nombre, detalle))


def warn(nombre, detalle):
    WARN.append((nombre, detalle))


def _data():
    p = BASE / 'data.json'
    if not p.exists():
        return None
    return json.loads(p.read_text())


def _inventario_vigente():
    """Snapshot de inventario más reciente. Es la foto que cuadra con finanzas."""
    import re
    cands = []
    for d in (Path.home() / 'dev' / 'panel-datos' / 'inv',
              Path.home() / 'Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Inventrario'):
        if not d.exists():
            continue
        for p in list(d.glob('*.xlsm')) + list(d.glob('*.xlsx')):
            if p.name.startswith('~$') or 'INVENTARIO' not in p.name.upper():
                continue
            m = re.search(r'(\d{1,2})-(\d{1,2})-(\d{4})', p.name)
            if m:
                cands.append((pd.Timestamp(int(m.group(3)), int(m.group(2)), int(m.group(1))), p))
        if cands:
            break
    return max(cands)[1] if cands else None


# ── 1 · Ventas del panel contra finanzas ─────────────────────────────────────
def check_ventas_vs_finanzas(d):
    """La cifra oficial por agencia es la VITRINA, y tiene que dar igual que
    DATOS 2 agrupado por Descripcion Bodega."""
    inv = _inventario_vigente()
    if inv is None:
        warn('ventas vs finanzas', 'no encontré snapshot de inventario')
        return
    try:
        from inventario import fact_agency_norm
    except Exception as e:
        warn('ventas vs finanzas', f'no pude importar fact_agency_norm: {e}')
        return
    d2 = pd.read_excel(inv, sheet_name='DATOS 2', header=0)
    d2.columns = [str(c) for c in d2.columns]
    d2['_mes'] = pd.to_datetime(d2['Fecha'], errors='coerce').dt.strftime('%Y-%m')
    d2['_ag'] = d2['Descripcion Bodega'].apply(lambda s: fact_agency_norm(s) or str(s))

    MARCAS = {'FORD': 'FORD', 'DONGFENG': 'DONGFENG_ORGU', 'CHERY': 'CHERY_ORGU',
              'MAZDA': 'MAZDA_ORGU', 'RAM': 'RAM_ORGU'}
    for marca_raw, key in MARCAS.items():
        vm = (d.get('ventas_mensual') or {}).get(key)
        if not vm:
            continue
        meses = [m for m in vm.get('months', []) if m.startswith('2026')]
        if not meses:
            continue
        sub = d2[(d2['Marca'].astype(str).str.upper() == marca_raw) & (d2['_mes'].isin(meses))]
        fin = sub.groupby('_ag')['Cantidad'].sum().astype(int).to_dict()
        pan = {a: sum(v.get(m, 0) for m in meses)
               for a, v in (vm.get('by_agencia') or {}).items() if not a.startswith('_')}
        difs = []
        for a in sorted(set(fin) | set(pan)):
            f, p = int(fin.get(a, 0)), int(pan.get(a, 0))
            if f != p:
                difs.append(f'{a}: panel {p} vs finanzas {f}')
        tf, tp = int(sum(fin.values())), int(sum(pan.values()))
        if difs or tf != tp:
            fail(f'ventas {key} vs finanzas',
                 f'total panel {tp} vs finanzas {tf}' + (' · ' + ' · '.join(difs) if difs else ''))
        else:
            ok(f'ventas {key} vs finanzas', f'{tp} uds, {len(pan)} agencias, {len(meses)} meses')


# ── 2 · Las dos bases de atribución suman igual ──────────────────────────────
def check_bases_atribucion(d):
    """by_agencia (vitrina) y by_agencia_equipo reparten distinto pero el total
    de la red tiene que coincidir. Si no, se perdieron filas."""
    for key, vm in (d.get('ventas_mensual') or {}).items():
        eq = vm.get('by_agencia_equipo')
        vi = vm.get('by_agencia')
        if not eq or not vi:
            fail(f'bases {key}', 'falta by_agencia o by_agencia_equipo')
            continue
        meses = vm.get('months', [])
        te = sum(sum(v.get(m, 0) for m in meses) for a, v in eq.items() if not a.startswith('_'))
        tv = sum(sum(v.get(m, 0) for m in meses) for a, v in vi.items() if not a.startswith('_'))
        if te != tv:
            fail(f'bases {key}', f'equipo {te} ≠ vitrina {tv} — se perdieron filas al reasignar')
        else:
            ok(f'bases {key}', f'equipo = vitrina = {tv}')


# ── 3 · Contrato de campos ───────────────────────────────────────────────────
def check_contrato(d):
    """Los consumidores externos (dossiers, otras sesiones) dependen de estos
    campos. Si desaparecen, rompen en silencio."""
    if 'ventas_mensual_doc' not in d:
        fail('contrato', 'falta el nodo ventas_mensual_doc que documenta las bases')
    else:
        ok('contrato', 'ventas_mensual_doc presente')
    for key, vm in (d.get('ventas_mensual') or {}).items():
        faltan = [c for c in ('by_agencia', 'by_agencia_fact', 'by_agencia_equipo', 'flat')
                  if c not in vm]
        if faltan:
            fail(f'contrato {key}', f'faltan claves: {faltan}')
            continue
        f0 = (vm.get('flat') or [{}])[0]
        fc = [c for c in ('agencia', 'agencia_fact', 'agencia_equipo') if c not in f0]
        if fc:
            fail(f'contrato {key}', f'flat sin campos: {fc}')
        else:
            ok(f'contrato {key}', 'flat trae agencia + agencia_fact + agencia_equipo')
    # el panel enumera marcas con Object.keys(ventas_mensual): nada ajeno adentro
    ajenas = [k for k in (d.get('ventas_mensual') or {}) if not k.isupper() and '_ORGU' not in k]
    if ajenas:
        fail('contrato', f'claves que el panel tomaría como marca: {ajenas}')


# ── 4 · Metas contra la fila TOTAL del archivo ───────────────────────────────
def check_metas(d):
    """La meta que el panel leyó tiene que reproducir la fila TOTAL del archivo.
    Las hojas por agencia copian por posición fija y se corren al reordenar."""
    for k, mes in (d.get('ford_months') or {}).items():
        mt = mes.get('meta_total')
        modelos = mes.get('models') or {}
        suma = sum((v.get('meta') or 0) for v in modelos.values())
        if mt and abs(suma - mt) > 2:
            fail(f'metas {k}', f'suma por modelo {suma} ≠ meta_total {mt}')
        dealers = mes.get('dealers') or {}
        sd = sum((v.get('meta') or 0) for v in dealers.values())
        if mt and sd and abs(sd - mt) > 2:
            fail(f'metas {k}', f'suma por agencia {sd} ≠ meta_total {mt}')
    if not [f for f in FAIL if f[0].startswith('metas')]:
        ok('metas', f'{len(d.get("ford_months") or {})} meses cuadran por modelo y por agencia')


# ── 5 · Sin fechas futuras ni meses vacíos ───────────────────────────────────
def check_meses(d):
    """Un mes en cero casi siempre es BD faltante, no ausencia de tráfico."""
    vacios = [k for k, m in (d.get('ford_months') or {}).items() if not m.get('total_curr')]
    if vacios:
        fail('meses', f'meses con tráfico en cero (¿falta la BD?): {vacios}')
    else:
        ok('meses', f'{len(d.get("ford_months") or {})} meses con tráfico > 0')
    hoy = pd.Timestamp.today().normalize()
    for k, m in (d.get('ford_months') or {}).items():
        cd = m.get('cut_date')
        if not cd:
            continue
        try:
            f = pd.to_datetime(cd, dayfirst=True)
        except Exception:
            continue
        if f > hoy:
            fail(f'meses {k}', f'corte en el futuro: {cd}')


def check_disp_por_agencia(d):
    """El disponible desglosado por agencia tiene que sumar el total del modelo.
    Si no cuadra, hay unidades con bodega sin mapear que desaparecen del reporte."""
    mc = ((d.get('inventario') or {}).get('monthly_cross') or {}).get('FORD')
    if not mc:
        warn('disp por agencia', 'no hay monthly_cross')
        return
    malos, revisados = [], 0
    for mes, m in mc.items():
        for mod, pm in (m.get('por_modelo') or {}).items():
            pa = pm.get('por_agencia') or {}
            if not pa or 'disp_eom' not in pm:
                continue
            revisados += 1
            suma = sum((v or {}).get('disp_eom', 0) for v in pa.values())
            if suma != pm['disp_eom']:
                malos.append(f'{mes}/{mod}: suma {suma} ≠ total {pm["disp_eom"]}')
    if malos:
        fail('disp por agencia', ' · '.join(malos[:3]) + (f' (+{len(malos)-3})' if len(malos) > 3 else ''))
    else:
        ok('disp por agencia', f'{revisados} combinaciones mes×modelo cuadran')


def check_pauta(d):
    """El presupuesto de pauta tiene que estar completo y cuadrar por sus tres cortes.
    Un mes que falta suele ser un archivo con nombre distinto o una hoja renombrada."""
    p = d.get('pauta')
    if not p:
        fail('pauta', 'falta el nodo pauta en data.json')
        return
    import datetime
    esperados = datetime.date.today().month
    if len(p.get('meses', [])) < esperados:
        faltan = esperados - len(p['meses'])
        warn('pauta', f'{len(p["meses"])} meses cargados, se esperaban {esperados} '
                      f'(faltan {faltan} — revisar nombre de archivo y hoja "Digital Pauta")')
    else:
        ok('pauta', f'{len(p["meses"])} meses · ${p["total"]:,.0f}')
    # los tres cortes deben sumar lo mismo
    tm = sum(p['por_mes'].values())
    tz = sum(sum(v.values()) for v in p['por_zona'].values())
    tmod = sum(sum(v.values()) for v in p['por_modelo'].values())
    if abs(tm - tz) > 1 or abs(tm - tmod) > 1:
        fail('pauta', f'los cortes no cuadran: mes ${tm:,.0f} · zona ${tz:,.0f} · modelo ${tmod:,.0f}')
    else:
        ok('pauta cortes', f'mes = zona = modelo = ${tm:,.0f}')


# ── 6 · Versión del caché ────────────────────────────────────────────────────
def check_pauta_costo(d):
    """La pauta se publica como costo FACTURADO. Si alguien vuelve a emitir el neto
    (o cambia un recargo sin querer), el costo por persona del panel se desploma
    un 24% sin que nada falle."""
    p = (d.get('pauta') or {})
    c = p.get('costo') or {}
    neto, tot, factor = p.get('total_neto'), p.get('total'), c.get('factor')
    if not (neto and tot and factor):
        warn('pauta costo', 'falta total_neto / total / costo.factor en el nodo pauta')
        return
    esperado = round(neto * factor, 2)
    if abs(esperado - tot) > 1.0:
        fail('pauta costo', f'facturado ${tot:,.0f} ≠ neto ${neto:,.0f} × {factor} = ${esperado:,.0f}')
        return
    r = c.get('recargos') or {}
    f_calc = (1 + r.get('rep_medios', 0) + r.get('isd', 0)) * (1 + r.get('ag_xiy', 0) + r.get('ag_bba', 0))
    if abs(f_calc - factor) > 1e-6:
        fail('pauta costo', f'el factor {factor} no sale de los recargos declarados ({f_calc:.6f})')
        return
    ok('pauta costo', f'neto ${neto:,.0f} × {factor} = ${tot:,.0f} facturados')


def check_cruce_ventas(d):
    """El cruce de Análisis General mostraba 542 ventas Ford donde la pestaña Ventas
    decía 635: contaba facturas del snapshot de inventario y las unidades entregadas
    hace meses se caen de esa foto. Ahora se reconcilia contra ventas_mensual; este
    invariante evita que vuelva a divergir."""
    mc = ((d.get('inventario') or {}).get('monthly_cross') or {})
    vm = d.get('ventas_mensual') or {}
    fallos = []
    for marca, meses in mc.items():
        flat = ((vm.get(marca) or {}).get('flat')) or []
        if not flat:
            continue
        oficial = {}
        for r in flat:
            ym = str(r.get('mes') or '')
            if ym:
                oficial[ym] = oficial.get(ym, 0) + (r.get('cantidad') or 0)
        for mk, mv in meses.items():
            ym = str(mv.get('mes_start') or '')[:7]
            if not ym:
                continue
            esp = int(round(oficial.get(ym, 0)))
            if int(mv.get('ventas') or 0) != esp:
                fallos.append(f'{marca}/{mk}: cruce {mv.get("ventas")} vs oficial {esp}')
    if fallos:
        fail('cruce vs ventas', f'{len(fallos)} meses no cuadran: {fallos[:3]}')
    else:
        n = sum(len(m) for m in mc.values())
        ok('cruce vs ventas', f'{n} mes×marca cuadran con ventas_mensual')


def check_cache():
    """Si se cambia un criterio de cálculo sin subir la versión, los meses viejos
    se sirven con el criterio anterior y solo cambia el mes en curso."""
    agg = (BASE / 'aggregate.py').read_text()
    import re
    m = re.search(r"\|(v\d+[a-z0-9\-]*)\"", agg)
    ver = m.group(1) if m else None
    cp = Path.home() / 'dev' / 'panel-datos' / 'cache' / 'months_cache.json'
    if not ver:
        warn('cache', 'no pude leer la versión de la llave en aggregate.py')
        return
    if not cp.exists():
        ok('cache', f'versión {ver} · sin caché en disco')
        return
    c = json.loads(cp.read_text())
    viejas = [k for k, v in c.items() if ver not in str(v.get('_key', ''))]
    if viejas:
        warn('cache', f'versión vigente {ver} · {len(viejas)} meses cacheados con otra versión: '
                      f'{viejas[:4]}{"…" if len(viejas) > 4 else ""}')
    else:
        ok('cache', f'versión {ver} · {len(c)} meses alineados')


def check_sin_modelo(d):
    """'Por definir' se pliega a ESCAPE en Ford (ver inventario.py). Si reaparece
    es que algún camino nuevo escribe el modelo sin pasar por el pliegue.
    Las marcas ORGU SÍ lo conservan: ahí no hay Escape al cual plegarlo."""
    rastro = []

    def walk(o, path, ford):
        if isinstance(o, dict):
            for k, val in o.items():
                if k == 'Por definir' and ford:
                    rastro.append(path + '.' + k)
                walk(val, path + '.' + str(k), ford)
        elif isinstance(o, list):
            for x in o[:500]:
                walk(x, path + '[]', ford)

    for nodo in ('ford', 'ford_months', 'conversion_data', 'embudo'):
        sub = d.get(nodo)
        if sub is None:
            continue
        if nodo == 'conversion_data':
            sub = sub.get('FORD')       # las marcas ORGU conservan su fila
            if sub is None:
                continue
        walk(sub, nodo, True)

    if rastro:
        fail('sin modelo → Escape', f'{len(rastro)} apariciones de "Por definir" en Ford: '
                                    f'{rastro[:3]}{"…" if len(rastro) > 3 else ""}')
    else:
        ok('sin modelo → Escape', 'ningún "Por definir" en los nodos Ford')


def main():
    strict = '--strict' in sys.argv
    d = _data()
    if d is None:
        print('✗ no existe data.json — corré aggregate.py primero')
        sys.exit(1)
    sys.path.insert(0, str(BASE))

    check_ventas_vs_finanzas(d)
    check_bases_atribucion(d)
    check_contrato(d)
    check_metas(d)
    check_meses(d)
    check_disp_por_agencia(d)
    check_pauta(d)
    check_pauta_costo(d)
    check_sin_modelo(d)
    check_cruce_ventas(d)
    check_cache()

    print()
    for n, det in OK:
        print(f'  ✓ {n:34} {det}')
    for n, det in WARN:
        print(f'  ! {n:34} {det}')
    for n, det in FAIL:
        print(f'  ✗ {n:34} {det}')
    print()
    if FAIL:
        print(f'✗ [verificar] {len(FAIL)} invariantes rotos, {len(WARN)} avisos')
        sys.exit(1 if strict else 0)
    print(f'✓ [verificar] {len(OK)} invariantes OK' + (f', {len(WARN)} avisos' if WARN else ''))


if __name__ == '__main__':
    main()
