#!/usr/bin/env python3
"""Descarga el último REPORTE DE INVENTARIO desde Outlook usando Microsoft Graph API.

Autenticación: OAuth 2.0 device code flow. La primera vez se abre un código y
URL en consola para que el usuario autorize en el navegador. Después el token se
cachea en ~/.panel_trafico_token.json y se refresca automáticamente.

Exit codes:
  0 = se actualizó el archivo (o no había nada nuevo)
  1 = error de autenticación
  2 = no se encontró archivo en los últimos N días
  3 = error de red / API
"""
import os
import sys
import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import msal
    import requests
except ImportError:
    print('ERROR: faltan dependencias. Ejecuta: pip3 install msal requests', file=sys.stderr)
    sys.exit(1)

# ─── Configuración ──────────────────────────────────────────────────────────
# Client ID público de Azure CLI — uno de los más permitidos en tenants corporativos.
# Si tu tenant lo bloquea, probar con:
#   '1950a258-227b-4e31-a9cf-717495945fc2'   = Microsoft Azure PowerShell
#   '14d82eec-204b-4c2f-b7e8-296a70dab67e'   = Microsoft Graph PowerShell
#   'd3590ed6-52b3-4102-aeff-aad2292ab01c'   = Microsoft Office (bloqueado en Maresa)
# Si todos están bloqueados, requiere App Registration propia en Azure AD (pedir a IT).
CLIENT_ID  = '04b07795-8ddb-461a-bbee-02f9e1bf7b46'
AUTHORITY  = 'https://login.microsoftonline.com/common'
SCOPES     = ['Mail.Read', 'User.Read']
TOKEN_CACHE = Path.home() / '.panel_trafico_token.json'

TARGET_PATH = Path('/Users/danielyanezalbuja/Downloads/REPORTE DE INVENTARIO.xlsm')
DAYS_BACK = 7

# Match en From (case-insensitive). Incluye variantes con y sin tildes.
ALLOWED_SENDERS = [
    'genesis.pincay', 'gpincay', 'génesis', 'genesis',
    'axel.cedeno',   'axel.cedeño', 'acedeno',  'acedeño',
    'diego.quinde',  'dquinde',
]
ATTACHMENT_KEYWORDS  = ['inventario', 'reporte']
ATTACHMENT_EXTENSIONS = ['.xlsm', '.xlsx', '.xls']


def log(msg):
    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {msg}', flush=True)


def get_token():
    """Obtiene access token, usando cache local si existe; si no, device code flow."""
    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE.exists():
        try:
            cache.deserialize(TOKEN_CACHE.read_text())
        except Exception:
            pass

    app = msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY, token_cache=cache)

    # Intento silencioso (token cacheado o refresh)
    result = None
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result:
        log('No hay token válido. Iniciando device code flow...')
        flow = app.initiate_device_flow(scopes=SCOPES)
        if 'user_code' not in flow:
            log(f'ERROR iniciando device flow: {flow.get("error_description", flow)}')
            sys.exit(1)
        log('═══════════════════════════════════════════════════════')
        log(flow['message'])
        log('═══════════════════════════════════════════════════════')
        log('Esperando autenticación en el navegador...')
        result = app.acquire_token_by_device_flow(flow)

    if 'access_token' not in result:
        log(f'ERROR autenticación: {result.get("error_description", result)}')
        sys.exit(1)

    # Persistir cache (incluye refresh token)
    if cache.has_state_changed:
        TOKEN_CACHE.write_text(cache.serialize())
        TOKEN_CACHE.chmod(0o600)

    return result['access_token']


def graph_get(token, url, params=None):
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    if r.status_code == 401:
        log('Token expirado o inválido')
        sys.exit(1)
    r.raise_for_status()
    return r.json()


def main():
    token = get_token()

    # Buscar mensajes recientes con adjuntos relevantes
    since_iso = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).strftime('%Y-%m-%dT%H:%M:%SZ')
    filter_clause = f'receivedDateTime ge {since_iso} and hasAttachments eq true'
    select = 'id,subject,from,receivedDateTime,hasAttachments'
    url = 'https://graph.microsoft.com/v1.0/me/messages'
    params = {
        '$filter': filter_clause,
        '$select': select,
        '$top': '50',
        '$orderby': 'receivedDateTime desc',
    }
    log(f'Buscando correos con adjuntos desde {since_iso}...')
    data = graph_get(token, url, params)
    messages = data.get('value', [])
    log(f'Encontrados {len(messages)} correos con adjuntos en los últimos {DAYS_BACK} días.')

    # Filtrar por remitente
    candidates = []
    for m in messages:
        from_addr = ((m.get('from') or {}).get('emailAddress') or {})
        addr = (from_addr.get('address') or '').lower()
        name = (from_addr.get('name') or '').lower()
        joined = f'{addr} {name}'
        if any(s in joined for s in ALLOWED_SENDERS):
            candidates.append(m)
    log(f'De los remitentes autorizados: {len(candidates)} correos.')
    if not candidates:
        log('No se encontró ningún correo de los remitentes autorizados.')
        sys.exit(2)

    # Para cada candidato (de más reciente a más viejo), revisar adjuntos
    chosen = None
    for m in candidates:
        att_url = f'https://graph.microsoft.com/v1.0/me/messages/{m["id"]}/attachments'
        att_data = graph_get(token, att_url, params={'$select':'id,name,size,contentType'})
        for a in att_data.get('value', []):
            fname = (a.get('name') or '').lower()
            if not any(fname.endswith(ext) for ext in ATTACHMENT_EXTENSIONS):
                continue
            if not any(k in fname for k in ATTACHMENT_KEYWORDS):
                continue
            chosen = {'msg': m, 'att_meta': a}
            break
        if chosen:
            break

    if not chosen:
        log(f'No se encontró adjunto con palabras {ATTACHMENT_KEYWORDS} y extensión válida.')
        sys.exit(2)

    msg = chosen['msg']
    att_meta = chosen['att_meta']
    log(f'Archivo encontrado: "{att_meta["name"]}" ({att_meta.get("size",0)/1024:.1f} KB)')
    log(f'  De: {msg["from"]["emailAddress"]["name"]} <{msg["from"]["emailAddress"]["address"]}>')
    log(f'  Asunto: {msg.get("subject")}')
    log(f'  Recibido: {msg.get("receivedDateTime")}')

    # Descargar contenido completo del adjunto
    content_url = f'https://graph.microsoft.com/v1.0/me/messages/{msg["id"]}/attachments/{att_meta["id"]}/$value'
    headers = {'Authorization': f'Bearer {token}'}
    r = requests.get(content_url, headers=headers, timeout=60)
    r.raise_for_status()
    payload = r.content

    # Comparar hash para evitar re-deploys innecesarios
    new_hash = hashlib.md5(payload).hexdigest()
    if TARGET_PATH.exists():
        with open(TARGET_PATH, 'rb') as f:
            old_hash = hashlib.md5(f.read()).hexdigest()
        if new_hash == old_hash:
            log(f'Archivo idéntico al actual ({new_hash[:8]}...). Sin cambios.')
            sys.exit(2)  # señal de "no hay nada nuevo"

    TARGET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TARGET_PATH, 'wb') as f:
        f.write(payload)
    log(f'OK: guardado en {TARGET_PATH} ({len(payload)/1024:.1f} KB)')
    sys.exit(0)


if __name__ == '__main__':
    main()
