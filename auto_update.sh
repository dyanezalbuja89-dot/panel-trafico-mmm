#!/bin/bash
# Pipeline automático: descargar inventario → regenerar data → build → deploy.
# Se ejecuta diariamente desde launchd a las 10 AM.

set -e

# Paths
PANEL_DIR="/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026/Análisis de tráfico/2026/Abril/panel-trafico"
LOG_FILE="$HOME/panel_trafico_auto.log"
ENV_FILE="$HOME/.panel_trafico_env"

# Log con timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "═══ Inicio auto-update ═══"

# 1. Cargar credenciales
if [ ! -f "$ENV_FILE" ]; then
    log "ERROR: $ENV_FILE no existe. Crea el archivo con OUTLOOK_EMAIL y OUTLOOK_APP_PASSWORD."
    exit 1
fi
set -a
source "$ENV_FILE"
set +a

# Asegurar que PATH tiene node/npm/python3
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

cd "$PANEL_DIR"

# 2. Descargar último archivo de inventario desde Outlook
log "Descargando inventario desde Outlook..."
FETCH_OUTPUT=$(python3 fetch_inventario.py 2>&1 || true)
FETCH_EXIT=$?
echo "$FETCH_OUTPUT" | tee -a "$LOG_FILE"

if [ "$FETCH_EXIT" -eq 2 ]; then
    log "No hay archivo nuevo. Skip pipeline."
    exit 0
elif [ "$FETCH_EXIT" -ne 0 ]; then
    log "ERROR descarga (exit $FETCH_EXIT). Abort."
    exit "$FETCH_EXIT"
fi

# 3. Regenerar data.json
log "Generando data.json..."
python3 aggregate.py >> "$LOG_FILE" 2>&1

# 4. Build index.html
log "Construyendo index.html..."
python3 build.py >> "$LOG_FILE" 2>&1

# 5. Deploy a Vercel producción
log "Deployando a Vercel..."
DEPLOY_OUTPUT=$(npx --yes vercel@latest --prod --yes 2>&1)
echo "$DEPLOY_OUTPUT" | tail -5 | tee -a "$LOG_FILE"

# 6. Push a GitHub (para que el analista del Claude Project tenga data fresca)
log "Sincronizando con GitHub..."
if git diff --quiet && git diff --staged --quiet ; then
    log "No hay cambios para pushear."
else
    git add -A >> "$LOG_FILE" 2>&1
    TODAY=$(date '+%Y-%m-%d %H:%M')
    git commit -m "Auto-update: data refrescada $TODAY" >> "$LOG_FILE" 2>&1
    git push origin main >> "$LOG_FILE" 2>&1 && log "✓ Push a GitHub OK" || log "⚠ git push falló (ver log)"
fi

log "✓ Update completado"
log ""
