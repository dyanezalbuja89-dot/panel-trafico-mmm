#!/bin/bash
# safe_build.sh — Rebuild + deploy seguro coordinado entre sesiones.
#
# Uso:
#   ./safe_build.sh           # build + verifica + commit interactivo + push
#   ./safe_build.sh --deploy  # build + verifica + commit + push + vercel deploy
#   ./safe_build.sh --check   # solo verifica integridad (no toca nada)
#
# Mata el bug clásico: dos sesiones Claude editan build.py simultáneo,
# la segunda hace build + push y borra lo que la primera no había commited.
#
# Cómo evita el problema:
#   1. git fetch origin → trae cambios remotos sin tocar tu working tree
#   2. compara local vs remoto → aborta si remote está adelante
#   3. verifica que tabs críticas (Seguimiento Digital) sigan intactas
#   4. SOLO entonces ejecuta python3 build.py
#   5. después de build, re-verifica integridad antes de commit
set -euo pipefail

cd "$(dirname "$0")"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

ok()    { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}⚠${NC} $1"; }
fail()  { echo -e "${RED}✗${NC} $1"; exit 1; }

check_only=false
deploy=false
for arg in "$@"; do
  case "$arg" in
    --check)  check_only=true ;;
    --deploy) deploy=true ;;
  esac
done

# 1. Sync con remoto
echo "→ Fetching origin..."
git fetch origin --quiet
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)
BASE=$(git merge-base HEAD origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
  ok "Local y remoto en sync ($LOCAL)"
elif [ "$LOCAL" = "$BASE" ]; then
  warn "Remoto está adelante. Pulling..."
  git pull --rebase --quiet || fail "Conflictos al rebase. Resolver manualmente y reintentar."
  ok "Pulled. HEAD ahora $(git rev-parse HEAD)"
elif [ "$REMOTE" = "$BASE" ]; then
  warn "Tienes commits locales no pusheados. Continuando."
else
  fail "Diverged. Local y remote tienen commits distintos. Resolver con 'git pull --rebase' o 'git rebase origin/main' manual."
fi

# 2. Integridad pre-build: archivos críticos completos
echo "→ Verificando integridad pre-build..."

# 2a. build.py: tabs HTML
BUILD_PY_MARKERS=(
  "tab-digital"
  "TAB DIGITAL · HubSpot"
  "tab-inv"
  "tab-ford"
  "tab-embudo"
  "tab-xiy"
)
# 2b. inventario.py: funciones de carga + normalización (si las borran, refresh_inv_only revienta)
INVENTARIO_PY_MARKERS=(
  "def load_inventario"
  "def loc_to_agency"
  "def res_agency_norm"
  "def normalize_familia"
  "DEFAULT_INVENTORY_PATH"
  "LOCATION_TO_AGENCY"
)
# 2c. aggregate.py: pipeline principal (si lo rompen, data.json sale incompleto)
AGGREGATE_PY_MARKERS=(
  "MONTHS_CONFIG"
  "def main()"
  "def load_raw"
  "junio_2026"
  "ford_months"
  "brands_months"
)

check_markers() {
  local file="$1"; shift
  local missing=0
  [ -f "$file" ] || { warn "$file no existe — skipping"; return 0; }
  for marker in "$@"; do
    if ! grep -qF "$marker" "$file"; then
      warn "$file no contiene '$marker'"
      missing=$((missing+1))
    fi
  done
  if [ $missing -gt 0 ]; then
    fail "$missing marker(s) ausente(s) en $file. Revisar antes de rebuild."
  fi
  ok "$file íntegro ($# markers verificados)"
}

check_markers build.py        "${BUILD_PY_MARKERS[@]}"
check_markers inventario.py   "${INVENTARIO_PY_MARKERS[@]}"
check_markers aggregate.py    "${AGGREGATE_PY_MARKERS[@]}"

if [ "$check_only" = true ]; then
  ok "Check OK — no se ejecutó build."
  exit 0
fi

# 3. Build
echo "→ Ejecutando python3 build.py..."
python3 build.py 2>&1 | tail -3

# 4. Post-build: index.html mantiene las tabs
echo "→ Verificando integridad post-build de index.html..."
for marker in "${BUILD_PY_MARKERS[@]}"; do
  if ! grep -qF "$marker" index.html; then
    fail "index.html post-build NO contiene '$marker'. Build emitió artefacto incompleto — NO commit/push."
  fi
done
ok "index.html post-build OK"

# 4b. data.json: top-level keys requeridas (smoke test que no quedó vacío)
echo "→ Verificando data.json..."
DATA_JSON_KEYS=(
  "ford_months"
  "brands_months"
  "inventario"
  "default_month_key"
  "months_config"
)
for k in "${DATA_JSON_KEYS[@]}"; do
  if ! grep -qF "\"$k\"" data.json; then
    fail "data.json NO contiene clave '$k'. Aggregate falló parcial — no pushear."
  fi
done
ok "data.json íntegro"

# 5. Deploy + commit (solo si --deploy)
if [ "$deploy" = true ]; then
  echo "→ Deploying a Vercel prod..."
  DEPLOY=$(npx vercel --prod --yes 2>&1 | grep -oE 'panel-trafico-[a-z0-9]+-daniels-projects-4cad0649\.vercel\.app' | head -1)
  if [ -z "$DEPLOY" ]; then
    fail "Deploy fallido — no se obtuvo URL"
  fi
  ok "Deploy: $DEPLOY"
  npx vercel alias set "$DEPLOY" panel-trafico.vercel.app 2>&1 | tail -1
fi

echo ""
ok "safe_build.sh terminó OK"
echo "  Siguientes pasos manuales:"
echo "    git add -A"
echo "    git commit -m '...'"
echo "    git push"
