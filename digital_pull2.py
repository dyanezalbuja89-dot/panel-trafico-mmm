#!/usr/bin/env python3
"""Pull EFICIENTE del dato digital (Ford + Dong Feng) via fetch-and-aggregate:
trae los registros paginados UNA vez y agrupa en Python — ~200 queries en vez de
~3.700 (contar 1x1). Emite la estructura completa que consume el panel en vivo:
funnel + confirmación + desperdicio (cards + cruce) por mes y por agencia.

Lo usa hubspot_pull.py (main) para llenar digital.json con dato vivo de TODO.
"""
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

import hubspot_pull as H  # reusa TOKEN, BASE, _urlopen, label maps

_NUM_INTERNAL_TO_IDX = {}
for _i, (_val, _lbl) in enumerate(H._NUM_LLAMADA):
    _NUM_INTERNAL_TO_IDX[_val] = _i           # '1º Llamada'->0 ... '69º Llamada'->8 ... '12º Llamada'->11
_NUM_INTERNAL_TO_LBL = {v: l for v, l in H._NUM_LLAMADA}
_RES_TO_LBL = dict(H._RES_LLAMADA)            # resultado_de_llamada interno -> etiqueta panel
_REACT_INTERNAL_TO_IDX = {'1º Llamada': 0, '2º Llamada': 1, '3º Llamada': 2}  # idx3 = Sin react.

# Clasificación del detalle granular (detalle_resultado_de_llamada___ultima_llamada, 24
# valores) en 4+1 categorías de eficiencia/desperdicio. Verificado con datos-hubspot
# (jun-2026) + criterio del usuario. 'Aceptaciones auditadas' = Citó (100% tiene deal con
# fecha_de_la_cita; es agendamiento, no asistencia → no es "Convirtió"). Salida legítima =
# cierre sano (compró/no volver). Desperdicio = no contesta/sin interés/error/no califica.
# Gestión activa = seguimiento genuino en curso. Sin mapear/null → 'Sin tipificar'.
# Variantes de capitalización del campo _1 incluidas (Sin Interés / Solicita Cotización).
_CAT_ORDER = ['Citó', 'En gestión activa', 'Salida legítima', 'Desperdicio', 'Sin tipificar']
_CATEGORIA = {
    'Aceptaciones auditadas': 'Citó',
    'Seguimiento por Whatsapp': 'En gestión activa',
    'Llamar después': 'En gestión activa',
    'Interesado a futuro': 'En gestión activa',
    'Solicita cotización': 'En gestión activa',
    'Solicita Cotización': 'En gestión activa',
    # gestión en curso (aún se intenta contactar; pedido del usuario 22-jun) — antes Desperdicio
    'No contesta': 'En gestión activa',
    'Buzón de voz': 'En gestión activa',
    'Se cortó llamada': 'En gestión activa',
    'Cliente compró un vehículo de otra marca': 'Salida legítima',
    'Cliente ya compró un vehículo FORD en otro concesionario': 'Salida legítima',
    'Ya compró un vehículo usado': 'Salida legítima',
    'No desea que lo contacten se acercará directamente': 'Salida legítima',
    'NO Volver a Contactar': 'Salida legítima',
    'Ocupado': 'Desperdicio',
    'Línea no existe/Suspendida/Fuera de servicio': 'Desperdicio',
    'Sin interés': 'Desperdicio',
    'Sin Interés': 'Desperdicio',
    'Curiosos': 'Desperdicio',
    'Equivocado': 'Desperdicio',
    'Repetido': 'Desperdicio',
    'Información cruzada': 'Desperdicio',
    'Fuera del país': 'Desperdicio',
    'Fuera de presupuesto': 'Desperdicio',
    'Buro Bajo': 'Desperdicio',
    'Fuera de Ciudad o Región': 'Desperdicio',
}

MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']

# Ventana 2026-H1 (ene 1 .. jul 1 - 1ms)
_S = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
_E = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp() * 1000) - 1
# "Ahora" para evaluar tareas futuras (notes_next_activity_date >= _NOW = tiene tarea futura).
_NOW = int(datetime.now(timezone.utc).timestamp() * 1000)


def _act_ms(v):
    """Fecha HubSpot (ISO o ms) -> ms epoch, o None si vacío/no parseable."""
    if not v:
        return None
    s = str(v).strip()
    try:
        if s.isdigit():
            return int(s)
        return int(datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp() * 1000)
    except (ValueError, OverflowError):
        try:
            return int(datetime.fromisoformat(s[:10]).replace(tzinfo=timezone.utc).timestamp() * 1000)
        except ValueError:
            return None


def _label_from_ms(v):
    """Fecha HubSpot (ISO 'YYYY-MM-DDT..Z' o ms epoch) -> 'ene·26'..'jun·26' o None."""
    if v is None:
        return None
    s = str(v).strip()
    dt = None
    if s.isdigit():
        try:
            dt = datetime.fromtimestamp(int(s) / 1000, tz=timezone.utc)
        except (ValueError, OverflowError):
            return None
    else:
        try:
            dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        except ValueError:
            # millis raros / formato → recorta a 'YYYY-MM-DD'
            try:
                dt = datetime.fromisoformat(s[:10])
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    if dt.year != 2026 or dt.month > 6:
        return None
    return MESES[dt.month - 1] + '·26'


def _search_page(obj, filters, properties, after, limit=100):
    url = f'{H.BASE}/crm/v3/objects/{obj}/search'
    body = {'filterGroups': [{'filters': filters}], 'properties': properties, 'limit': limit}
    if after:
        body['after'] = after
    req = urllib.request.Request(
        url, method='POST', data=json.dumps(body).encode('utf-8'),
        headers={'Authorization': f'Bearer {H.TOKEN}', 'Content-Type': 'application/json'})
    for attempt in range(4):
        try:
            with H._urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 + attempt)
                continue
            raise
    raise RuntimeError(f'search {obj} falló tras reintentos')


def _fetch_all(obj, filters, properties):
    """Pagina /search y devuelve [props_dict, ...] de TODOS los registros (<10k)."""
    out, after, pages = [], None, 0
    while True:
        res = _search_page(obj, filters, properties, after)
        for r in res.get('results', []):
            p = dict(r.get('properties', {}))
            p['_id'] = r.get('id')
            out.append(p)
        after = (res.get('paging') or {}).get('next', {}).get('after')
        pages += 1
        if not after or pages > 200:
            break
    return out


def _assoc_react(deal_ids):
    """Para los deals no-show: trae numero_de_llamada_reactivacion del CONTACT asociado.
    Devuelve {deal_id: react_internal|None}. Batched (cross-object)."""
    out = {}
    deal_to_contact = {}
    for i in range(0, len(deal_ids), 100):
        chunk = deal_ids[i:i + 100]
        url = f'{H.BASE}/crm/v4/associations/deals/contacts/batch/read'
        body = {'inputs': [{'id': d} for d in chunk]}
        req = urllib.request.Request(url, method='POST', data=json.dumps(body).encode('utf-8'),
                                     headers={'Authorization': f'Bearer {H.TOKEN}', 'Content-Type': 'application/json'})
        try:
            with H._urlopen(req, timeout=40) as r:
                res = json.loads(r.read())
            for row in res.get('results', []):
                frm = str(row.get('from', {}).get('id'))
                tos = row.get('to', [])
                if tos:
                    deal_to_contact[frm] = str(tos[0].get('toObjectId'))
        except Exception:
            pass
    contact_ids = list(set(deal_to_contact.values()))
    react = {}
    for i in range(0, len(contact_ids), 100):
        chunk = contact_ids[i:i + 100]
        url = f'{H.BASE}/crm/v3/objects/contacts/batch/read'
        body = {'inputs': [{'id': c} for c in chunk], 'properties': ['numero_de_llamada_reactivacion']}
        req = urllib.request.Request(url, method='POST', data=json.dumps(body).encode('utf-8'),
                                     headers={'Authorization': f'Bearer {H.TOKEN}', 'Content-Type': 'application/json'})
        try:
            with H._urlopen(req, timeout=40) as r:
                res = json.loads(r.read())
            for row in res.get('results', []):
                react[str(row.get('id'))] = (row.get('properties') or {}).get('numero_de_llamada_reactivacion')
        except Exception:
            pass
    for d in deal_ids:
        c = deal_to_contact.get(str(d))
        out[str(d)] = react.get(c) if c else None
    return out


def _sorted_pairs(counter):
    return sorted([[k, v] for k, v in counter.items() if v > 0], key=lambda r: r[1], reverse=True)


def fetch_brand_full(cfg):
    """Estructura completa de una marca: funnel/conf/desperdicio por mes y agencia."""
    pipe = cfg['pipeline']
    cohort = cfg['cohort']
    lead_filter = cfg.get('lead_filter', [])
    agencies = cfg['agencies']          # [(interno, corto), ...]
    stage_map = cfg['stage_map']        # dealstage interno -> etiqueta panel
    ag_internal = {a for a, _ in agencies}
    ag_short = dict(agencies)

    # ── CONTACTS (cohorte) ──
    c_filters = [H._between(cohort, _S, _E)] + lead_filter
    contacts = _fetch_all('contacts', c_filters,
                          [cohort, 'contactabilidad', 'resultado_de_llamada', 'numero_de_llamada',
                           'agencia', 'lead_enviado_cct',
                           'detalle_resultado_de_llamada___ultima_llamada',
                           'notes_next_activity_date'])
    # ── DEALS (actividad por fecha_de_la_cita) ──
    d_filters = [H._eq('pipeline', pipe), H._between('fecha_de_la_cita', _S, _E)]
    deals = _fetch_all('deals', d_filters,
                       ['fecha_de_la_cita', 'asistio_a_la_cita', 'cita_confirmada', 'dealstage', 'agencia'])

    def newcell():
        return {'leads': 0, 'cont': 0, 'tope': 0, 'agen': 0, 'confirmadas': 0, 'efec': 0, 'nos': 0,
                'nc_by': {}, 'c_est': {}, 'c_cross': {}, 'ns_est': {}, 'conf_d': {}, 'ns_react': {},
                'c_cat': {}, 'c_cat_det': {}, 'c_cat_llam': {}, 'c_cat_notask': {}}
    # cells[(scope, label)] donde scope = 'T' o agencia-corta
    cells = {}

    def cell(scope, label):
        k = (scope, label)
        if k not in cells:
            cells[k] = newcell()
        return cells[k]

    # Agrega contacts
    for p in contacts:
        lbl = _label_from_ms(p.get(cohort))
        if not lbl:
            continue
        ag = p.get('agencia')
        scopes = ['T'] + ([ag_short[ag]] if ag in ag_internal else [])
        contab = p.get('contactabilidad')
        env = p.get('lead_enviado_cct')
        num = p.get('numero_de_llamada')
        res = p.get('resultado_de_llamada')
        det = p.get('detalle_resultado_de_llamada___ultima_llamada')
        nact = _act_ms(p.get('notes_next_activity_date'))
        no_task = (nact is None) or (nact < _NOW)   # sin próxima actividad/tarea en HubSpot
        for sc in scopes:
            c = cell(sc, lbl)
            c['leads'] += 1
            if contab == 'Contactado':
                c['cont'] += 1
            if num == '12º Llamada':
                c['tope'] += 1
            # desperdicio (cohorte lead_enviado_cct=Si para Ford; DF no lo tiene → trata None como ok)
            cohort_ok = (env == 'Si') if cfg.get('require_env') else True
            if cohort_ok and contab == 'No contactado':
                lbln = _NUM_INTERNAL_TO_LBL.get(num)
                if lbln:
                    c['nc_by'][lbln] = c['nc_by'].get(lbln, 0) + 1
            if cohort_ok and contab == 'Contactado':
                # null/sin mapear → 'Sin tipificar' (setter no tipificó la llamada);
                # antes se botaba en silencio (el panel ocultaba ~1,2% de los contactados).
                est = _RES_TO_LBL.get(res) or 'Sin tipificar'
                c['c_est'][est] = c['c_est'].get(est, 0) + 1
                idx = _NUM_INTERNAL_TO_IDX.get(num)
                if idx is not None:
                    arr = c['c_cross'].setdefault(est, [0] * 12)
                    arr[idx] += 1
                # categoría real (Citó / gestión / salida / desperdicio) desde el detalle granular
                cat = _CATEGORIA.get(det, 'Sin tipificar')
                c['c_cat'][cat] = c['c_cat'].get(cat, 0) + 1
                # drill categoría → sub-estatus granular (etiqueta legible = el detalle, o 'Sin tipificar')
                detlbl = det if (det in _CATEGORIA) else 'Sin tipificar'
                d = c['c_cat_det'].setdefault(cat, {})
                d[detlbl] = d.get(detlbl, 0) + 1
                # distribución por nº de llamada por categoría (ej. "gestión activa en qué llamada está")
                if idx is not None:
                    cl = c['c_cat_llam'].setdefault(cat, [0] * 12)
                    cl[idx] += 1
                # sin tarea futura en HubSpot (huérfano CRM; el CC agenda en Genesys, ver nota panel)
                if no_task:
                    c['c_cat_notask'][cat] = c['c_cat_notask'].get(cat, 0) + 1

    # Agrega deals
    noshow_ids = []
    for p in deals:
        lbl = _label_from_ms(p.get('fecha_de_la_cita'))
        if not lbl:
            continue
        ag = p.get('agencia')
        scopes = ['T'] + ([ag_short[ag]] if ag in ag_internal else [])
        asis = p.get('asistio_a_la_cita')
        confv = p.get('cita_confirmada')
        stage = p.get('dealstage')
        if asis == 'No':
            noshow_ids.append(p.get('_id'))
        for sc in scopes:
            c = cell(sc, lbl)
            c['agen'] += 1
            if confv == 'Confirma':
                c['confirmadas'] += 1
            if asis == 'Si':
                c['efec'] += 1
            elif asis == 'No':
                c['nos'] += 1
                stlbl = stage_map.get(stage, stage)
                c['ns_est'][stlbl] = c['ns_est'].get(stlbl, 0) + 1
            # distribución de confirmación
            ck = confv if confv in ('Confirma', 'Desiste', 'No contesta', 'Reagenda') else 'Sin gestión'
            c['conf_d'][ck] = c['conf_d'].get(ck, 0) + 1

    # Cruce no-show (reactivación) vía asociaciones — solo nivel T (Todas).
    react_by_deal = _assoc_react([d for d in noshow_ids if d]) if noshow_ids else {}
    for p in deals:
        if p.get('asistio_a_la_cita') != 'No':
            continue
        lbl = _label_from_ms(p.get('fecha_de_la_cita'))
        if not lbl:
            continue
        stage = p.get('dealstage')
        stlbl = stage_map.get(stage, stage)
        rv = react_by_deal.get(str(p.get('_id')))
        idx = _REACT_INTERNAL_TO_IDX.get(rv, 3)  # default Sin react.
        c = cell('T', lbl)
        arr = c['ns_react'].setdefault(stlbl, [0, 0, 0, 0])
        arr[idx] += 1

    # ── Empaqueta a la forma que consume el panel ──
    months_order = [m + '·26' for m in MESES[:6]]
    def funnel_obj(c):
        conf = _sorted_pairs(c['conf_d'])
        return {'leads': c['leads'], 'cont': c['cont'], 'tope': c['tope'],
                'agen': c['agen'], 'agendadas': c['agen'],  # ambos nombres (panel usa 'agendadas')
                'confirmadas': c['confirmadas'], 'efec': c['efec'], 'nos': c['nos'], 'conf': conf}
    def desp_obj(c):
        by_cat = [[k, c['c_cat'][k]] for k in _CAT_ORDER if c['c_cat'].get(k)]
        cat_det = {k: _sorted_pairs(v) for k, v in c['c_cat_det'].items()}
        return {
            'no_contactados': {'total': sum(c['nc_by'].values()), 'by_llamada': _sorted_pairs(c['nc_by'])},
            'contactados': {'total': sum(c['c_est'].values()), 'by_estatus': _sorted_pairs(c['c_est']),
                            'by_categoria': by_cat, 'cat_detalle': cat_det, 'cat_llamada': dict(c['c_cat_llam']),
                            'cat_notask': dict(c['c_cat_notask'])},
            'no_show': {'total': sum(c['ns_est'].values()), 'by_estatus': _sorted_pairs(c['ns_est'])},
        }

    months = []
    by_month, cruce = {}, {}
    for lbl in months_order:
        c = cells.get(('T', lbl))
        if not c:
            continue
        fo = funnel_obj(c)
        idx = MESES.index(lbl.split('·')[0])
        months.append({'label': lbl, 'year': 2026, 'month': idx + 1, **fo})
        by_month[lbl] = desp_obj(c)
        cruce[lbl] = {'contactados': c['c_cross'], 'no_show': c['ns_react']}

    ag_funnel, by_agency = {}, {}
    for ag_int, ag_s in agencies:
        af, ad = {}, {}
        for lbl in months_order:
            c = cells.get((ag_s, lbl))
            if not c:
                continue
            af[lbl] = funnel_obj(c)
            ad[lbl] = desp_obj(c)
        if af:
            ag_funnel[ag_s] = af
            by_agency[ag_s] = ad

    return {
        'months': months,
        'ag': ag_funnel,
        'desperdicio': {'by_month': by_month, 'by_agency': by_agency, 'cruce': cruce},
    }


# Configs de marca
_FORD_STAGES = {'23726667': 'Cita agendada (atascado)', 'closedlost': 'Perdido',
                '958509219': 'Reagendar', '23721774': 'Cita Efectiva (error)'}
_DF_STAGES = {'1129598793': 'Cita agendada (atascado)', '1129598794': 'Reagendar',
              '1129598795': 'Cita Efectiva (error)', '1129697154': 'Perdido',
              '1129598792': 'En gestión'}

BRANDS = {
    'ford': {'pipeline': 'default', 'cohort': 'fecha_y_hora_de_ingreso___cc', 'lead_filter': [],
             'require_env': True, 'stage_map': _FORD_STAGES,
             'agencies': [(k, v) for k, v in H.AGENCY_SHORT.items()]},
    'dongfeng': {'pipeline': '773555758', 'cohort': 'createdate',
                 'lead_filter': [{'propertyName': 'dongfeng___modelo_de_interes', 'operator': 'HAS_PROPERTY'}],
                 'require_env': False, 'stage_map': _DF_STAGES,
                 'agencies': [('Orgu La Y', 'La Y'), ('Orgu Machala', 'Machala')]},
}


def fetch_all_brands():
    out = {}
    for name, cfg in BRANDS.items():
        print(f'[digital2] fetch {name}...', flush=True)
        out[name] = fetch_brand_full(cfg)
        m = out[name]['months']
        tot = sum(x['leads'] for x in m)
        print(f'[digital2]   {name}: {len(m)} meses, leads {tot}', flush=True)
    return out


if __name__ == '__main__':
    import sys
    data = fetch_all_brands()
    Path = __import__('pathlib').Path
    Path('digital2.json').write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print('Wrote digital2.json')
