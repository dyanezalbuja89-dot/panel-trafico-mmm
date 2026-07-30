#!/bin/bash
# Deploy con verificación end-to-end. Uso: ./deploy.sh [--skip-aggregate]
# 1. (opcional) aggregate  2. build  3. cache-buster  4. deploy  5. VERIFICA que
# el data.json LIVE coincide con el local; si no, reintenta con --force.
set -e
cd "$(dirname "$0")"

if [ "$1" != "--skip-aggregate" ]; then
  echo "→ aggregate..."
  /usr/bin/python3 aggregate.py | tail -2
fi

echo "→ build..."
/usr/bin/python3 build.py | tail -1

echo "→ cache-buster..."
H=$(date +%s)
sed -i.bak "s/BUILD_HASH_PLACEHOLDER/$H/g" index.html && rm -f index.html.bak

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
