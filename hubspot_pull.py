"""Pull de HubSpot · Ventas Ford (portal 21339231).

Pipeline `default` = Ventas-Ford. Definiciones canónicas del knowledge base:
- Lead recibido: contact con fecha_y_hora_de_ingreso___cc en el período
- Contactado: contact con contactabilidad = 'Contactado'
- Cita agendada: deal con fecha_de_la_cita en el período (pipeline default)
- Cita efectiva: deal con asistio_a_la_cita = 'Si' (pipeline default)
- Venta: deal con dealstage = closedwon, closedate en el período

Exporta:
- monthly_funnel: array por mes con leads/cont/agen/efec/vent
- agency_breakdown: por agencia (cohorte ingreso del último mes completo)
- model_breakdown: por modelo de interés
- kpis: totales y ratios principales del período

Uso: `python3 hubspot_pull.py` → escribe digital.json
"""
from __future__ import annotations
import os, sys, json, time, ssl, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

# Contexto SSL: en algunos entornos el cert.pem del sistema falta y urllib
# revienta con CERTIFICATE_VERIFY_FAILED. Si certifi está disponible lo usamos
# como CA bundle; si no, caemos al contexto por defecto (comportamiento previo).
def _ssl_ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None

_SSL_CTX = _ssl_ctx()

def _urlopen(req, timeout=30):
    if _SSL_CTX is not None:
        return urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX)
    return urllib.request.urlopen(req, timeout=timeout)

# Token: env > .env.local del proyecto Analista-HubSpot-PRO > inline fallback
def _load_token():
    t = os.environ.get('HUBSPOT_TOKEN')
    if t:
        return t
    env_path = Path('/Users/danielyanezalbuja/Documents/Claude/Projects/ORGU — Contact Center (Make vs Buy) (2)/Analista-HubSpot-PRO/panel-orgu/.env.local')
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith('HUBSPOT_TOKEN='):
                return line.split('=', 1)[1].strip()
    return None

TOKEN = _load_token()
BASE = 'https://api.hubapi.com'
PIPELINE_VENTAS_FORD = 'default'

# Ventana de análisis: últimos 7 meses (incluido el mes en curso)
def _months_window(n=7):
    out = []
    now = datetime.now(timezone.utc)
    y, m = now.year, now.month
    months = []
    for _ in range(n):
        months.append((y, m))
        m -= 1
        if m == 0:
            m = 12; y -= 1
    months.reverse()
    es = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic']
    for y, m in months:
        out.append((f"{es[m-1]}-{str(y)[2:]}", y, m-1))  # m-1 porque Python Date.UTC usa 0-idx
    return out

def _month_bounds(y, m_idx):
    """m_idx: 0-11. Devuelve (start_ms, end_ms) en UTC epoch ms."""
    start_dt = datetime(y, m_idx + 1, 1, tzinfo=timezone.utc)
    if m_idx == 11:
        end_dt = datetime(y + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end_dt = datetime(y, m_idx + 2, 1, tzinfo=timezone.utc)
    return int(start_dt.timestamp() * 1000), int(end_dt.timestamp() * 1000) - 1

def _search(obj, filter_groups, properties=None, limit=1):
    """POST /crm/v3/objects/{obj}/search. Devuelve {total, results}."""
    if not TOKEN:
        raise RuntimeError('HUBSPOT_TOKEN no configurado')
    url = f'{BASE}/crm/v3/objects/{obj}/search'
    body = {
        'filterGroups': filter_groups,
        'limit': limit,
    }
    if properties:
        body['properties'] = properties
    req = urllib.request.Request(
        url, method='POST',
        data=json.dumps(body).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {TOKEN}',
            'Content-Type': 'application/json',
        },
    )
    try:
        with _urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        # Rate-limit retry simple
        if e.code == 429:
            time.sleep(2)
            with _urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        raise

def _count(obj, filters):
    res = _search(obj, [{'filters': filters}])
    return int(res.get('total', 0))

def _between(prop, lo, hi):
    return {'propertyName': prop, 'operator': 'BETWEEN', 'value': str(lo), 'highValue': str(hi)}

def _eq(prop, val):
    return {'propertyName': prop, 'operator': 'EQ', 'value': val}

PIPE_FILTER = _eq('pipeline', PIPELINE_VENTAS_FORD)

# Agencias y modelos del knowledge base
AGENCIES = [
    'Orgu Carlos Julio Arosemena', 'Orgu Orellana', 'Orgu La Y',
    'Orgu Tumbaco', 'Orgu Manta', 'Orgu Machala', 'Orgu Portoviejo',
]
AGENCY_SHORT = {
    'Orgu Carlos Julio Arosemena': 'CJA',
    'Orgu Orellana': 'Orellana',
    'Orgu La Y': 'La Y',
    'Orgu Tumbaco': 'Tumbaco',
    'Orgu Manta': 'Manta',
    'Orgu Machala': 'Machala',
    'Orgu Portoviejo': 'Portoviejo',
}

# Valores del enum cita_confirmada (Etapa 2). Sin gestión = agendadas − suma(estos).
_CONFIRMA_VALS = ['Confirma', 'Desiste', 'No contesta', 'Reagenda']

def fetch_monthly_funnel(months):
    """Para cada mes: leads, contactados, agendadas, confirmadas, efectivas, ventas
    + distribución de confirmación (conf)."""
    out = []
    for label, y, m_idx in months:
        s, e = _month_bounds(y, m_idx)
        leads = _count('contacts', [_between('fecha_y_hora_de_ingreso___cc', s, e)])
        cont  = _count('contacts', [_between('fecha_y_hora_de_ingreso___cc', s, e), _eq('contactabilidad', 'Contactado')])
        agen  = _count('deals',    [PIPE_FILTER, _between('fecha_de_la_cita', s, e)])
        efec  = _count('deals',    [PIPE_FILTER, _between('fecha_de_la_cita', s, e), _eq('asistio_a_la_cita', 'Si')])
        nos  = _count('deals',    [PIPE_FILTER, _between('fecha_de_la_cita', s, e), _eq('asistio_a_la_cita', 'No')])
        tope = _count('contacts', [_between('fecha_y_hora_de_ingreso___cc', s, e), _eq('numero_de_llamada', '12º Llamada')])
        vent  = _count('deals',    [PIPE_FILTER, _eq('dealstage', 'closedwon'), _between('closedate', s, e)])
        # Etapa 2 confirmación: distribución de cita_confirmada sobre las agendadas.
        conf = []
        conf_sum = 0
        for cv in _CONFIRMA_VALS:
            n = _count('deals', [PIPE_FILTER, _between('fecha_de_la_cita', s, e), _eq('cita_confirmada', cv)])
            if n > 0:
                conf.append([cv, n])
            conf_sum += n
        sin_gestion = max(agen - conf_sum, 0)
        if sin_gestion > 0:
            conf.append(['Sin gestión', sin_gestion])
        conf.sort(key=lambda r: r[1], reverse=True)
        confirmadas = next((n for k, n in conf if k == 'Confirma'), 0)
        out.append({
            'label': label, 'year': y, 'month': m_idx + 1,
            'leads': leads, 'cont': cont, 'agen': agen, 'efec': efec, 'vent': vent,
            'tope': tope, 'nos': nos,
            'confirmadas': confirmadas, 'conf': conf,
        })
        print(f'  {label}: leads={leads} cont={cont} agen={agen} confirm={confirmadas} efec={efec}', flush=True)
    return out

def fetch_agency_breakdown(months):
    """Cohorte de ingreso del último mes completo, por agencia."""
    last = months[-2] if len(months) >= 2 else months[-1]
    _, y, m_idx = last
    s, e = _month_bounds(y, m_idx)
    rows = []
    for ag in AGENCIES:
        leads = _count('contacts', [_between('fecha_y_hora_de_ingreso___cc', s, e), _eq('agencia', ag)])
        if leads == 0:
            continue
        agen = _count('deals',    [PIPE_FILTER, _between('fecha_de_la_cita', s, e), _eq('agencia', ag)])
        efec = _count('deals',    [PIPE_FILTER, _between('fecha_de_la_cita', s, e), _eq('agencia', ag), _eq('asistio_a_la_cita', 'Si')])
        vent = _count('deals',    [PIPE_FILTER, _eq('dealstage', 'closedwon'), _between('closedate', s, e), _eq('agencia', ag)])
        rows.append({
            'agency': AGENCY_SHORT.get(ag, ag),
            'agency_full': ag,
            'leads': leads, 'agen': agen, 'efec': efec, 'vent': vent,
            'show_rate': round(100 * efec / agen, 1) if agen else 0,
        })
        print(f'  [agency] {ag}: leads={leads} efec={efec} show={round(100*efec/agen,1) if agen else 0}%', flush=True)
    rows.sort(key=lambda r: r['leads'], reverse=True)
    return { 'period': last[0], 'rows': rows }

def fetch_model_breakdown(months):
    """Cohorte ingreso último mes completo, por modelo de interés."""
    last = months[-2] if len(months) >= 2 else months[-1]
    _, y, m_idx = last
    s, e = _month_bounds(y, m_idx)
    # Obtener modelos top via search con properties=modelo_de_interes y agruparlos
    # Más simple: pedir todos los contacts del período y agrupar en cliente.
    # Pero la API de search limita a 100 results por página; usamos paginación.
    cursor = None
    page = 0
    counts = {}
    while True:
        body_filter = [{'filters': [_between('fecha_y_hora_de_ingreso___cc', s, e)]}]
        body = {
            'filterGroups': body_filter,
            'properties': ['modelo_de_interes'],
            'limit': 100,
        }
        if cursor:
            body['after'] = cursor
        req = urllib.request.Request(
            f'{BASE}/crm/v3/objects/contacts/search', method='POST',
            data=json.dumps(body).encode('utf-8'),
            headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
        )
        with _urlopen(req, timeout=30) as r:
            j = json.loads(r.read())
        for res in j.get('results', []):
            m = (res.get('properties', {}) or {}).get('modelo_de_interes') or '(sin modelo)'
            counts[m] = counts.get(m, 0) + 1
        nxt = j.get('paging', {}).get('next', {}).get('after') if j.get('paging') else None
        page += 1
        if not nxt or page > 50:
            break
        cursor = nxt
    rows = sorted(
        [{'model': m, 'leads': c} for m, c in counts.items()],
        key=lambda r: r['leads'], reverse=True
    )[:12]
    print(f'  [model] top: {[r["model"]+":"+str(r["leads"]) for r in rows[:5]]}', flush=True)
    return { 'period': last[0], 'rows': rows }

def compute_kpis(funnel):
    """Totales y ratios del período."""
    s = lambda k: sum(m[k] for m in funnel)
    leads, cont, agen, efec, vent = s('leads'), s('cont'), s('agen'), s('efec'), s('vent')
    return {
        'period_leads': leads,
        'period_cont': cont,
        'period_agen': agen,
        'period_efec': efec,
        'period_vent': vent,
        'rate_cont':       round(100 * cont / leads, 1) if leads else 0,
        'rate_agen':       round(100 * agen / leads, 1) if leads else 0,
        'rate_show':       round(100 * efec / agen, 1)  if agen  else 0,
        'rate_no_show':    round(100 * (agen - efec) / agen, 1) if agen else 0,
        'rate_close':      round(100 * vent / efec, 1)  if efec  else 0,
        'rate_lead_to_sale': round(100 * vent / leads, 1) if leads else 0,
    }

# ─── Desperdicio por fase · cohorte 2026 ───
# Tres distribuciones del "sangrado" del CC:
#   - no_contactados: contactos cohorte 2026 (lead_enviado_cct=Si) con
#     contactabilidad='No contactado', repartidos por nº de llamada.
#   - contactados: contactos contactabilidad='Contactado', por estatus
#     (resultado_de_llamada, etiquetas legibles) y por nº de llamada.
#   - no_show: deals pipeline default con cita 2026 y asistio='No', por etapa.
# Cohorte fija ene–jul 2026 (BETWEEN '2026-01-01' AND '2026-07-01').

# Etiquetas legibles del enum numero_de_llamada. OJO: el valor interno del 9º
# es '69º Llamada' (quirk de HubSpot), no '9º Llamada'.
_NUM_LLAMADA = [(f'{i}º Llamada', f'{i}ª') for i in range(1, 13)]
_NUM_LLAMADA[8] = ('69º Llamada', '9ª')  # índice 8 = 9ª llamada

# resultado_de_llamada (valor interno) → etiqueta legible del panel
_RES_LLAMADA = [
    ('Contactado',                    'Contactado'),
    ('Barreras técnicas/No contesta', 'Barreras técnicas/No contesta'),
    ('No interesado',                 'No interesado'),
    ('Sin recursos económicos',       'Sin recursos económicos'),
    ('Posponer contacto',             'Posponer contacto'),
    ('Errores operativos',            'Errores operativos'),
]

# dealstage (GUID/interno) → etiqueta legible. Pipeline default = Ventas-Ford.
_DEALSTAGE = [
    ('23721767',     'Negocio Asignado'),
    ('qualifiedtobuy','En gestión'),
    ('23726667',     'Cita agendada (atascado)'),
    ('958509219',    'Reagendar'),
    ('23721774',     'Cita Efectiva (error)'),
    ('77008301',     'Solicitud de crédito'),
    ('23817118',     'Vehiculo Reservado'),
    ('closedwon',    'Vendido'),
    ('closedlost',   'Perdido'),
]

_MES_ABBR = ['ene', 'feb', 'mar', 'abr', 'may', 'jun',
             'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
# Meses 2026 con dato del CC para el desglose mensual del desperdicio (H1).
# Extender al avanzar el año (jul=7, ...).
_DESP_MONTHS_2026 = [1, 2, 3, 4, 5, 6]


def _desp_window(s, e, incl_c_by=True):
    """3 distribuciones del desperdicio para la ventana [s, e] (ms epoch).

    incl_c_by: si False, omite contactados.by_llamada (no se muestra por-mes
    en el panel) para ahorrar ~12 counts por ventana.
    """
    ING = _between('fecha_y_hora_de_ingreso___cc', s, e)
    ENV = _eq('lead_enviado_cct', 'Si')
    CITA = _between('fecha_de_la_cita', s, e)

    # --- No contactados ---
    nc_base = [ING, ENV, _eq('contactabilidad', 'No contactado')]
    nc_total = _count('contacts', nc_base)
    nc_by = []
    for val, lbl in _NUM_LLAMADA:
        n = _count('contacts', nc_base + [_eq('numero_de_llamada', val)])
        if n > 0:
            nc_by.append([lbl, n])
    nc_by.sort(key=lambda r: r[1], reverse=True)

    # --- Contactados ---
    c_base = [ING, ENV, _eq('contactabilidad', 'Contactado')]
    c_total = _count('contacts', c_base)
    c_est = []
    for val, lbl in _RES_LLAMADA:
        n = _count('contacts', c_base + [_eq('resultado_de_llamada', val)])
        if n > 0:
            c_est.append([lbl, n])
    c_est.sort(key=lambda r: r[1], reverse=True)
    c_by = []
    if incl_c_by:
        for val, lbl in _NUM_LLAMADA:
            n = _count('contacts', c_base + [_eq('numero_de_llamada', val)])
            if n > 0:
                c_by.append([lbl, n])
        c_by.sort(key=lambda r: r[1], reverse=True)

    # --- No-show (deals) ---
    ns_base = [PIPE_FILTER, CITA, _eq('asistio_a_la_cita', 'No')]
    ns_total = _count('deals', ns_base)
    ns_est = []
    for sid, lbl in _DEALSTAGE:
        n = _count('deals', ns_base + [_eq('dealstage', sid)])
        if n > 0:
            ns_est.append([lbl, n])
    ns_est.sort(key=lambda r: r[1], reverse=True)

    cont = {'total': c_total, 'by_estatus': c_est}
    if incl_c_by:
        cont['by_llamada'] = c_by
    return {
        'no_contactados': {'total': nc_total, 'by_llamada': nc_by},
        'contactados':    cont,
        'no_show':        {'total': ns_total, 'by_estatus': ns_est},
    }


def fetch_cc_desperdicio(months):
    """Desperdicio (cohorte 2026): agregado H1 + desglose por mes.

    Devuelve dict con no_contactados/contactados/no_show (agregado, idéntico al
    histórico) MÁS 'by_month' { 'ene·26': {...}, ... } para el filtro de mes del
    panel. Si algo falla, devuelve {'available': False} sin romper el pull.
    """
    try:
        full_s = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        full_e = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp() * 1000) - 1
        agg = _desp_window(full_s, full_e, incl_c_by=True)

        by_month = {}
        for m in _DESP_MONTHS_2026:
            ms = int(datetime(2026, m, 1, tzinfo=timezone.utc).timestamp() * 1000)
            ny, nm = (2026, m + 1) if m < 12 else (2027, 1)
            me = int(datetime(ny, nm, 1, tzinfo=timezone.utc).timestamp() * 1000) - 1
            label = _MES_ABBR[m - 1] + '·26'
            by_month[label] = _desp_window(ms, me, incl_c_by=False)

        print(f'  [desperdicio] no_cont={agg["no_contactados"]["total"]} '
              f'cont={agg["contactados"]["total"]} '
              f'no_show={agg["no_show"]["total"]} (+by_month {len(by_month)})',
              flush=True)
        return {
            'available': True,
            'no_contactados': agg['no_contactados'],
            'contactados':    agg['contactados'],
            'no_show':        agg['no_show'],
            'by_month':       by_month,
        }
    except Exception as ex:
        print(f'  [desperdicio] FALLO: {type(ex).__name__}: {ex}', file=sys.stderr, flush=True)
        return {'available': False}

def main(output_path='digital.json'):
    if not TOKEN:
        print('[ERROR] HUBSPOT_TOKEN no configurado. Generando snapshot vacío.', file=sys.stderr)
        snapshot = {
            'available': False,
            'note': 'HUBSPOT_TOKEN no disponible. Configurar variable de entorno o .env.local en Analista-HubSpot-PRO.',
        }
    else:
        print('[hubspot_pull] Iniciando fetch live · portal 21339231 · Ventas-Ford', flush=True)
        months = _months_window(7)
        print(f'[hubspot_pull] Meses: {[m[0] for m in months]}', flush=True)
        print('[hubspot_pull] Fetch monthly funnel...', flush=True)
        funnel = fetch_monthly_funnel(months)
        print('[hubspot_pull] Fetch agency breakdown...', flush=True)
        agency = fetch_agency_breakdown(months)
        print('[hubspot_pull] Fetch model breakdown...', flush=True)
        model = fetch_model_breakdown(months)
        kpis = compute_kpis(funnel)
        print('[hubspot_pull] Fetch desperdicio por fase...', flush=True)
        desperdicio = fetch_cc_desperdicio(months)
        # ── Pull EFICIENTE (fetch-aggregate) Ford + Dong Feng → todo el panel en vivo ──
        live = None
        try:
            import digital_pull2 as _D2
            print('[hubspot_pull] Fetch eficiente Ford + Dong Feng (live)...', flush=True)
            live = _D2.fetch_all_brands()
        except Exception as _ex:
            print(f'[hubspot_pull] live fetch FALLO: {type(_ex).__name__}: {_ex}', file=sys.stderr, flush=True)
        snapshot = {
            'available': True,
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'portal': '21339231',
            'pipeline': 'Ventas-Ford',
            'months': funnel,
            'agencies': agency,
            'models': model,
            'kpis': kpis,
            'cc_desperdicio': desperdicio,
            'live': live,
        }
    out = Path(output_path)
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    print(f'[hubspot_pull] Wrote {out} ({out.stat().st_size:,} bytes)', flush=True)
    return snapshot

if __name__ == '__main__':
    main()
