#!/usr/bin/env bash
# Stage 1 of the render pipeline: KiCad board -> binary glTF.
#
# GLB is the only 3D format that survives the trip intact: it carries per-layer meshes
# and material colours, and Blender imports it natively (Blender 5.x dropped VRML/X3D,
# and never read STEP).
#
# Usage:  ./export_glb.sh [board.kicad_pcb] [out.glb]
set -euo pipefail

KICAD_CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
BOARD="${1:-$(dirname "$0")/../thatmicpre-rounded.kicad_pcb}"
OUT="${2:-$(dirname "$0")/board.glb}"

# This board is KiCad 6-era: its footprints reference ${KICAD6_3DMODEL_DIR} and .wrl
# filenames, neither of which resolves under KiCad 10. Point the old variable at the
# current library; --subst-models then picks up the .step files that shipped in its place.
MODELS="${KICAD_3DMODEL_DIR:-/Applications/KiCad/KiCad.app/Contents/SharedSupport/3dmodels}"

"$KICAD_CLI" pcb export glb \
  -o "$OUT" --force \
  -D "KICAD6_3DMODEL_DIR=$MODELS" \
  -D "KISYS3DMOD=$MODELS" \
  --subst-models \
  --include-tracks --include-pads --include-zones \
  --include-silkscreen --include-soldermask \
  --cut-vias-in-body --min-distance 0.005mm \
  "$BOARD"

echo "wrote $OUT"
