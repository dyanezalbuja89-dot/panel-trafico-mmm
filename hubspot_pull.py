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
import os, sys, json, time, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

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
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        # Rate-limit retry simple
        if e.code == 429:
            time.sleep(2)
            with urllib.request.urlopen(req, timeout=30) as r:
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

def fetch_monthly_funnel(months):
    """Para cada mes: leads, contactados, agendadas, efectivas, ventas."""
    out = []
    for label, y, m_idx in months:
        s, e = _month_bounds(y, m_idx)
        leads = _count('contacts', [_between('fecha_y_hora_de_ingreso___cc', s, e)])
        cont  = _count('contacts', [_between('fecha_y_hora_de_ingreso___cc', s, e), _eq('contactabilidad', 'Contactado')])
        agen  = _count('deals',    [PIPE_FILTER, _between('fecha_de_la_cita', s, e)])
        efec  = _count('deals',    [PIPE_FILTER, _between('fecha_de_la_cita', s, e), _eq('asistio_a_la_cita', 'Si')])
        vent  = _count('deals',    [PIPE_FILTER, _eq('dealstage', 'closedwon'), _between('closedate', s, e)])
        out.append({
            'label': label, 'year': y, 'month': m_idx + 1,
            'leads': leads, 'cont': cont, 'agen': agen, 'efec': efec, 'vent': vent,
        })
        print(f'  {label}: leads={leads} cont={cont} agen={agen} efec={efec} vent={vent}', flush=True)
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
        with urllib.request.urlopen(req, timeout=30) as r:
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
        snapshot = {
            'available': True,
            'updated_at': datetime.now(timezone.utc).isoformat(),
            'portal': '21339231',
            'pipeline': 'Ventas-Ford',
            'months': funnel,
            'agencies': agency,
            'models': model,
            'kpis': kpis,
        }
    out = Path(output_path)
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    print(f'[hubspot_pull] Wrote {out} ({out.stat().st_size:,} bytes)', flush=True)
    return snapshot

if __name__ == '__main__':
    main()
