# Photoreal render pipeline

Two stages: KiCad exports the board as binary glTF, Blender rebuilds the materials and
renders it with Cycles.

```bash
./export_glb.sh                      # thatmicpre-rounded.kicad_pcb -> board.glb
./render.sh                          # board.glb -> ../thatmicpre_3D_render.png
```

`render.sh` is a thin wrapper; anything can be overridden as `key=value`:

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
  -P render_board.py -- board.glb out.png samples=640 res=2600 rotz=-45 key=1.6
```

| knob | default | what it does |
|---|---|---|
| `samples` | 640 | Cycles samples; 128 is fine for previews |
| `res` | 2600 | square render, cropped to content afterwards |
| `rotx` / `rotz` | -32 / -60 | view angle, same convention as `kicad-cli pcb render --rotate` |
| `margin` | 1.30 | framing headroom; must leave room for the shadow |
| `key` | 1.35 | key light in watts — the board is 45 mm, so this is single digits |
| `hdri` / `hdri_strength` | studio / 0.12 | environment, from Blender's bundled studio lights |
| `bevel` | 0.00006 | shading-normal bevel radius in metres |
| `expo` | 0.0 | exposure compensation in stops |
| `solder` | 1 | set `0` to skip the generated solder fillets |
| `blend` | – | path to also save the assembled scene as a `.blend` |
| `norender` | 0 | set `1` to build and save the `.blend` without rendering |

## Why it looks like a photo and the KiCad view doesn't

KiCad's raytracer is Whitted-style: no indirect bounces, no image-based lighting, no
microfacet roughness, no denoiser. Cycles is a path tracer, so the gains come from
lighting and materials rather than from the geometry, which is identical.

What `render_board.py` adds on top of the glTF import:

- **Real PBR materials.** Soldermask as a semi-gloss dielectric with a clearcoat and
  90% alpha, so the copper pours read through it the way they do on a real board.
  ENIG pads, tinned leads and the aluminium can are proper metals with distinct
  roughness rather than flat colours.
- **Solder fillets** (optional, `solder=1`). KiCad exports bare leads through flat pads.
  The script finds every hole a component lead actually passes through, then builds a
  concave meniscus sized from that hole's own pad copper. Unpopulated pads — the 7-pin
  header — are deliberately left bare. Off by default in `render.sh`, which renders the
  board as fabricated rather than as assembled.
- **Resistor colour bands.** Both 1K resistors get brown-black-red-gold painted along
  the body via a constant-interpolation ramp on object-space X.
- **Bevelled edges.** A Bevel node rounds shading normals so edges catch a highlight.
  Perfectly sharp edges are the reason CAD renders look like CAD.
- **Micro-surface noise.** Soldermask gets a faint orange-peel bump; most materials get
  a little roughness jitter so highlights are not uniform.

## Notes

- Component identification keys off the glTF material names (`mat_0` … `mat_15`), which
  KiCad assigns in export order. If the BOM changes, re-check the mapping table near the
  top of `render_board.py` — the script prints every object and material with `-P
  inspect.py` style probing.
- Output is RGBA with a transparent background; the contact shadow is carried in the
  alpha channel by a Cycles shadow catcher, so it composites onto light or dark pages.
- **The board file still has the wrong 3D model on RV1** — a round Bourns 3339P on what
  is a square 3362P footprint. Until that is fixed, this pipeline renders the round part.
  The correct model is already staged at `../3dmodels/3362p-1-103.stp`; see the note in
  the top-level README.

- Running `export_glb.sh` against a board in the repo makes KiCad 10 rewrite that board's
  `.kicad_prl` into its newer format (v3 → v5). That file is editor state, not design
  data, but it will show up in `git status` — `git checkout --` it if you don't want the
  format bump.

## Opening the scene by hand

`thatmicpre.blend` is the assembled scene: geometry, rebuilt materials, the light rig,
the orthographic camera and the shadow catcher, with the HDRI packed into the file so it
opens on any machine. Regenerate it any time with:

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
  -P render_board.py -- board.glb /dev/null blend=thatmicpre.blend norender=1
```

Mesh objects are named by role — `Fr4`, `Mask`, `Silk`, `Pads`, `Tracks`, `DIP8`,
`Resistor`, `CeramicCap`, `Electrolytic`, `Trimmer` — so materials are easy to find in
the shader editor. Note that edits made in the .blend are not fed back into the scripts;
treat the .blend as an output, and change `render_board.py` if you want a change to stick.
