#!/bin/bash
# Refresco HORARIO del dato digital (HubSpot · Ventas-Ford + Dongfeng).
# Lanzado por launchd cada hora. Flujo:
#   sync a origin → pull HubSpot → merge solo 'digital' en data.json → build → deploy.
# NO commitea data.json (lo maneja el flujo diario de inventario) — solo deploya
# el index.html con el dato digital fresco. Así no hay conflictos de git.
set -e
REPO="/Users/danielyanezalbuja/dev/panel-trafico-mmm"
LOG="$HOME/panel_digital_hourly.log"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

log(){ echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"; }

cd "$REPO" || exit 1
log "═══ refresco digital horario ═══"

# 1. Sync al canónico (descarta el merge de la hora previa; trae data.json de otras pestañas)
git fetch origin main >> "$LOG" 2>&1 || log "WARN git fetch"
git reset --hard origin/main >> "$LOG" 2>&1 || log "WARN git reset"

# 2. Pull HubSpot → digital.json
log "pull HubSpot..."
python3 hubspot_pull.py >> "$LOG" 2>&1 || { log "ERROR hubspot_pull; abort"; exit 1; }

# 3. Merge solo 'digital' en data.json (preserva otras pestañas)
python3 _merge_digital.py >> "$LOG" 2>&1 || { log "ERROR merge; abort"; exit 1; }

# 4. Build index.html con el dato fresco
python3 build.py >> "$LOG" 2>&1 || { log "ERROR build; abort"; exit 1; }

# 5. Deploy a Vercel prod
log "deploy..."
npx --yes vercel@latest --prod --yes >> "$LOG" 2>&1 && log "✓ deploy OK" || log "⚠ deploy falló"

log "✓ refresco completado"
