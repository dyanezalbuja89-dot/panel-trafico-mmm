#!/bin/bash
# Sincroniza data de OneDrive → cache local (~/dev/panel-datos/).
# Copia solo archivos nuevos o modificados (rsync incremental).
#
# Uso:
#   ./sync_data.sh          # sync ligero (BDs julio actual + inventario más reciente)
#   ./sync_data.sh --full   # sync completo (todos los históricos)
#
# Corre esto ANTES de aggregate.py cuando llegue un BD/inventario nuevo.
# La primera vez toma varios minutos; luego solo copia lo que cambió.

set -e
FULL=${1:-}

OD_BASE="/Users/danielyanezalbuja/Library/CloudStorage/OneDrive-Maresa/Marketing/2026"
LOCAL="$HOME/dev/panel-datos"
mkdir -p "$LOCAL/bd" "$LOCAL/inv" "$LOCAL/metas" "$LOCAL/embudo"

echo "→ Sync inventarios..."
rsync -av --update --include="*.xlsm" --include="*.xlsx" --exclude="*" \
  "$OD_BASE/Inventrario/" "$LOCAL/inv/" 2>&1 | tail -5

echo "→ Sync metas Julio (mes actual)..."
rsync -av --update --include="*.xlsx" --exclude="*" \
  "$OD_BASE/Análisis de tráfico/2026/Julio/TRAFICO_DY/" "$LOCAL/metas/" 2>&1 | tail -3

echo "→ Sync BDs julio (curr+prev)..."
# Snapshot los BDs más recientes del mes en curso
find "$OD_BASE/Análisis de tráfico/2026/Julio/BD_JULIO" -maxdepth 1 -name "BD_JUL_*.xlsx" -mtime -7 2>/dev/null | while read f; do
  base=$(basename "$f")
  if [ ! -f "$LOCAL/bd/$base" ] || [ "$f" -nt "$LOCAL/bd/$base" ]; then
    cp "$f" "$LOCAL/bd/$base" && echo "  updated $base"
  fi
done

if [ "$FULL" = "--full" ]; then
  echo "→ Sync FULL: BDs históricos + metas de todos los meses + embudo..."
  # BDs históricos
  for f in "$OD_BASE/Análisis de tráfico/2026/Julio/BD_JULIO/"BD_*.xlsx; do
    base=$(basename "$f")
    if [ ! -f "$LOCAL/bd/$base" ]; then
      ( cp "$f" "$LOCAL/bd/$base" && echo "  new $base" ) &
    fi
  done
  wait
  # Metas históricas
  for m in Junio Mayo Abril Marzo Febrero Enero; do
    D="$OD_BASE/Análisis de tráfico/2026/$m/TRAFICO_DY"
    [ -d "$D" ] && find "$D" -name "*.xlsx" 2>/dev/null | while read f; do
      base=$(basename "$f")
      [ ! -f "$LOCAL/metas/$base" ] && cp "$f" "$LOCAL/metas/$base" && echo "  meta $base"
    done
  done
  # Embudo (opcional, tarda mucho por número de archivos)
  echo "  (skip embudo — usar 'rsync -a $OD_BASE/Análisis\\ de\\ embudo/ $LOCAL/embudo/' manual si necesitas)"
fi

echo "→ Estado cache:"
echo "  BDs:     $(ls "$LOCAL/bd"     2>/dev/null | wc -l) archivos"
echo "  Invs:    $(ls "$LOCAL/inv"    2>/dev/null | wc -l) archivos"
echo "  Metas:   $(ls "$LOCAL/metas"  2>/dev/null | wc -l) archivos"
echo "  Total:   $(du -sh "$LOCAL"    2>/dev/null | awk '{print $1}')"
echo "✓ Sync completo"
