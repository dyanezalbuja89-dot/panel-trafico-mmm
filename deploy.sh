#!/bin/bash
# Deploy con verificación end-to-end. Uso: ./deploy.sh [--skip-aggregate]
# 1. (opcional) aggregate  2. build  3. cache-buster  4. deploy  5. VERIFICA que
# el data.json LIVE coincide con el local; si no, reintenta con --force.
set -e
cd "$(dirname "$0")"

if [ "$1" != "--skip-aggregate" ]; then
  echo "→ aggregate..."
  /usr/bin/python3 aggregate.py | tail -2
  # Cuadre asesores vs fuente cruda (caso Daniela 4-ago). Si no cuadra, NO se despliega.
  /usr/bin/python3 checks_asesores.py
  # Invariantes del panel: ventas contra finanzas, bases de atribución, contrato de
  # campos, metas y caché. Con --strict corta el deploy si algo se rompió.
  if ! /usr/bin/python3 verificar.py --strict; then
    echo "✗ ABORTA: hay invariantes rotos. Revisar antes de publicar."
    exit 1
  fi
fi

echo "→ build..."
/usr/bin/python3 build.py | tail -1

echo "→ cache-buster..."
H=$(date +%s)
sed -i.bak "s/BUILD_HASH_PLACEHOLDER/$H/g" index.html && rm -f index.html.bak

# Integridad post-build: este script llama a build.py directo, así que repite el
# check de safe_build.sh. Sin esto se puede publicar (y pushear) un index.html
# al que se le cayó una pestaña entera.
for marker in tab-digital tab-inv tab-ford tab-embudo "TAB DIGITAL · HubSpot"; do
  if ! grep -q "$marker" index.html; then
    echo "✗ FALLO: '$marker' no está en index.html post-build. No se despliega." >&2
    exit 1
  fi
done
echo "✓ index.html íntegro (5 markers)"

# ── Push ANTES de publicar ────────────────────────────────────────────────────
# El cron de digital corre cada hora y hace `git reset --hard origin/main`: todo
# commit que se quede local dura menos de 60 minutos y el siguiente rebuild
# revierte el panel. Publicar algo que no está en el remoto es publicarlo a
# plazo fijo, así que si el push no entra, no se despliega.
echo "→ sincronizando con el remoto antes de publicar..."
git fetch -q origin

if [ -n "$(git status --porcelain)" ]; then
  git add -A
  # Si el hook aborta porque el remoto se adelantó (otra sesión o el cron),
  # rebasamos y reintentamos una vez.
  git commit -q -m "deploy: $(date '+%Y-%m-%d %H:%M')" \
    || { git pull -q --rebase origin main && git commit -q -m "deploy: $(date '+%Y-%m-%d %H:%M')"; }
fi

git pull -q --rebase origin main

if ! git push -q origin HEAD:main; then
  echo "✗ FALLO: no se pudo pushear. No se despliega — el cron revertiría el panel." >&2
  exit 1
fi

if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "✗ FALLO: local y origin/main no coinciden tras el push. No se despliega." >&2
  exit 1
fi
echo "✓ remoto al día ($(git rev-parse --short HEAD)) — el cron ya no puede revertirlo"

LOCAL_MD5=$(md5 -q data.json)
echo "→ data.json local md5: $LOCAL_MD5"

deploy_and_verify () {
  local extra=$1
  echo "→ vercel deploy $extra..."
  npx vercel --prod --yes $extra 2>&1 | grep -E "Aliased|Production" | head -2
  sleep 8
  LIVE_MD5=$(curl -s "https://panel-trafico.vercel.app/data.json?_=$(date +%s%N)" | md5 -q)
  echo "→ data.json LIVE md5: $LIVE_MD5"
  [ "$LIVE_MD5" = "$LOCAL_MD5" ]
}

if deploy_and_verify ""; then
  echo "✓ DEPLOY VERIFICADO — LIVE coincide con local"
else
  echo "⚠ LIVE difiere de local — reintentando con --force..."
  if deploy_and_verify "--force"; then
    echo "✓ DEPLOY VERIFICADO (tras --force)"
  else
    echo "✗ FALLO: LIVE sigue difiriendo tras --force. Revisar manualmente." >&2
    exit 1
  fi
fi
