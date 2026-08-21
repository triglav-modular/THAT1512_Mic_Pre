#!/usr/bin/env bash
# Stage 2: board.glb -> photoreal PNG, cropped to content, transparent background.
set -euo pipefail
BLENDER="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
HERE="$(cd "$(dirname "$0")" && pwd)"
GLB="${1:-$HERE/board.glb}"
OUT="${2:-$HERE/../thatmicpre_3D_render.png}"
[ $# -ge 1 ] && shift; [ $# -ge 1 ] && shift

TMP="$(mktemp -t boardrender).png"
trap 'rm -f "$TMP"' EXIT

"$BLENDER" -b --factory-startup -P "$HERE/render_board.py" -- \
  "$GLB" "$TMP" samples=512 res=2800 ortho=0 margin=1.45 key=1.35 solder=0 "$@"

# Cycles renders a fixed square; tighten it to the board plus its shadow.
python3 "$HERE/crop_alpha.py" "$TMP" "$OUT" 12 50
echo "wrote $OUT"
