"""
KiCad GLB -> Blender/Cycles photoreal render.

Usage:
  Blender -b --factory-startup -P render_board.py -- <board.glb> <out.png> [key=value ...]

Overrides: samples, res, rotx, rotz, ortho, margin, key, hdri, hdri_rot,
           hdri_strength, bevel, expo, shadow, denoise, solder, blend, norender
"""
import bpy, sys, os, math
from mathutils import Vector

# ---------------------------------------------------------------- args
argv = sys.argv[sys.argv.index("--") + 1:]
GLB, OUT = argv[0], argv[1]
CFG = dict(samples=256, res=2000, rotx=-32.0, rotz=-60.0, ortho=0.062,
           hdri="studio", hdri_rot=0.0, hdri_strength=0.07, shadow=1, denoise=1, key=1.2,
           expo=0.0, margin=1.10, bevel=0.00006, solder=1, blend="", norender=0, look="AgX - Medium Contrast")
for kv in argv[2:]:
    k, v = kv.split("=", 1)
    CFG[k] = type(CFG[k])(v) if k in CFG and not isinstance(CFG[k], str) else v

HDRI_DIR = "/Applications/Blender.app/Contents/Resources/5.1/datafiles/studiolights/world"

# ---------------------------------------------------------------- scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=GLB)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']

# ---------------------------------------------------------------- identify parts by material signature
def sig(o):
    return frozenset(m.name for m in o.data.materials if m)

ROLE_BY_MAT = {
    'mat_9': 'pads', 'mat_10': 'tracks', 'mat_11': 'silk', 'mat_12': 'silk',
    'mat_13': 'mask', 'mat_14': 'mask', 'mat_15': 'fr4',
}
for o in meshes:
    s = sig(o)
    if 'mat_7' in s:            o.name = 'Trimmer'
    elif 'mat_4' in s:          o.name = 'Electrolytic'
    elif 'mat_3' in s:          o.name = 'Resistor'
    elif 'mat_2' in s and len(s) == 2: o.name = 'DIP8'
    elif 'mat_1' in s:          o.name = 'CeramicCap'
    else:
        for m in s:
            if m in ROLE_BY_MAT:
                o.name = ROLE_BY_MAT[m].capitalize(); break

# ---------------------------------------------------------------- materials
BEVEL_R = float(CFG['bevel'])

def pbr(name, base, rough, metal=0.0, alpha=1.0, coat=0.0, coat_rough=0.05,
        ior=1.45, sheen=0.0, bevel=True, orange_peel=0.0, rough_var=0.0,
        bands=None, band_range=None):
    """Rebuild a glTF material as a Cycles PBR shader.

    bevel        -- round shading normals on sharp edges (catches highlights like a real part)
    orange_peel  -- micro-bump strength, e.g. soldermask texture
    rough_var    -- +/- roughness jitter driven by the same noise
    bands        -- [(pos, rgb), ...] constant-interpolated colour bands along local X
    band_range   -- (x0, x1) in metres that `bands` positions 0..1 map onto
    """
    m = bpy.data.materials.get(name)
    if m is None:
        return None
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    L = nt.links
    out = nt.nodes.new('ShaderNodeOutputMaterial'); out.location = (600, 0)
    b = nt.nodes.new('ShaderNodeBsdfPrincipled');   b.location = (300, 0)
    i = b.inputs
    i['Base Color'].default_value = (*base, 1.0)
    i['Roughness'].default_value = rough
    i['Metallic'].default_value = metal
    i['IOR'].default_value = ior
    if 'Alpha' in i: i['Alpha'].default_value = alpha
    for cn, cv in (('Coat Weight', coat), ('Coat Roughness', coat_rough)):
        if cn in i: i[cn].default_value = cv
    if 'Sheen Weight' in i: i['Sheen Weight'].default_value = sheen
    L.new(b.outputs['BSDF'], out.inputs['Surface'])
    if alpha < 1.0:
        m.surface_render_method = 'BLENDED'

    # ---- colour bands (resistor value code) --------------------------------
    if bands and band_range:
        texc = nt.nodes.new('ShaderNodeTexCoord');  texc.location = (-800, 200)
        sep  = nt.nodes.new('ShaderNodeSeparateXYZ'); sep.location = (-620, 200)
        mr   = nt.nodes.new('ShaderNodeMapRange');  mr.location = (-450, 200)
        ramp = nt.nodes.new('ShaderNodeValToRGB');  ramp.location = (-250, 200)
        mr.inputs['From Min'].default_value = band_range[0]
        mr.inputs['From Max'].default_value = band_range[1]
        L.new(texc.outputs['Object'], sep.inputs['Vector'])
        L.new(sep.outputs['X'], mr.inputs['Value'])
        L.new(mr.outputs['Result'], ramp.inputs['Fac'])
        el = ramp.color_ramp
        el.interpolation = 'CONSTANT'
        while len(el.elements) > 1:
            el.elements.remove(el.elements[-1])
        el.elements[0].position = 0.0
        el.elements[0].color = (*bands[0][1], 1.0)
        for pos, rgb in bands[1:]:
            e = el.elements.new(pos)
            e.color = (*rgb, 1.0)
        L.new(ramp.outputs['Color'], i['Base Color'])

    # ---- surface micro-detail ---------------------------------------------
    normal_src = None
    if bevel and BEVEL_R > 0:
        bv = nt.nodes.new('ShaderNodeBevel'); bv.location = (0, -300)
        bv.samples = 4
        bv.inputs['Radius'].default_value = BEVEL_R
        normal_src = bv.outputs['Normal']

    if orange_peel > 0 or rough_var > 0:
        tc2 = nt.nodes.new('ShaderNodeTexCoord'); tc2.location = (-800, -420)
        noi = nt.nodes.new('ShaderNodeTexNoise'); noi.location = (-600, -420)
        noi.inputs['Scale'].default_value = 900.0
        noi.inputs['Detail'].default_value = 4.0
        noi.inputs['Roughness'].default_value = 0.55
        L.new(tc2.outputs['Object'], noi.inputs['Vector'])
        if orange_peel > 0:
            bump = nt.nodes.new('ShaderNodeBump'); bump.location = (100, -420)
            bump.inputs['Strength'].default_value = orange_peel
            bump.inputs['Distance'].default_value = 0.00002
            L.new(noi.outputs['Fac'], bump.inputs['Height'])
            if normal_src:
                L.new(normal_src, bump.inputs['Normal'])
            normal_src = bump.outputs['Normal']
        if rough_var > 0:
            rr = nt.nodes.new('ShaderNodeMapRange'); rr.location = (100, -600)
            rr.inputs['To Min'].default_value = max(0.0, rough - rough_var)
            rr.inputs['To Max'].default_value = min(1.0, rough + rough_var)
            L.new(noi.outputs['Fac'], rr.inputs['Value'])
            L.new(rr.outputs['Result'], i['Roughness'])

    if normal_src:
        L.new(normal_src, i['Normal'])
    return m, nt, b

# --- 1K 4-band code (brown black red gold), positions normalised over the 6.3 mm body
BEIGE = (0.790, 0.640, 0.400)
BANDS_1K = [
    (0.000,  BEIGE),
    (0.098, (0.150, 0.070, 0.028)),   # brown  1
    (0.194,  BEIGE),
    (0.241, (0.018, 0.018, 0.020)),   # black  0
    (0.337,  BEIGE),
    (0.384, (0.430, 0.030, 0.020)),   # red    x100
    (0.479,  BEIGE),
    (0.765, (0.620, 0.450, 0.130)),   # gold   +/-5%
    (0.860,  BEIGE),
]
RES_BODY_X = (0.00193, 0.00823)   # measured resistor body span, object space, metres

# board stack
pbr('mat_15', (0.260, 0.215, 0.115), 0.66, rough_var=0.08)                  # FR4 edge
for mm in ('mat_13', 'mat_14'):                                             # soldermask
    pbr(mm, (0.012, 0.048, 0.250), 0.24, alpha=0.90,
        coat=0.22, coat_rough=0.12, orange_peel=0.12, rough_var=0.05)
for mm in ('mat_11', 'mat_12'):                                             # silkscreen
    pbr(mm, (0.870, 0.870, 0.855), 0.72, rough_var=0.06)
pbr('mat_9',  (0.780, 0.650, 0.385), 0.26, metal=1.0, rough_var=0.05)       # ENIG pads
pbr('mat_10', (0.720, 0.430, 0.200), 0.44, metal=1.0)                       # copper tracks
# components
pbr('mat_0', (0.760, 0.755, 0.730), 0.28, metal=1.0, rough_var=0.06)        # tinned leads
pbr('mat_1', (0.610, 0.170, 0.035), 0.50, coat=0.18, rough_var=0.07)        # ceramic cap dip
pbr('mat_2', (0.021, 0.021, 0.023), 0.38, rough_var=0.06)                   # DIP epoxy
pbr('mat_3', BEIGE, 0.48, rough_var=0.06,                                   # resistor + bands
    bands=BANDS_1K, band_range=RES_BODY_X)
pbr('mat_4', (0.022, 0.085, 0.330), 0.34, coat=0.10, rough_var=0.05)                        # elco sleeve
pbr('mat_5', (0.640, 0.625, 0.590), 0.32, metal=1.0, rough_var=0.06)        # elco alu top
pbr('mat_6', (0.630, 0.655, 0.720), 0.32, metal=1.0)                        # trimmer pins
pbr('mat_7', (0.020, 0.120, 0.520), 0.36, coat=0.25)                        # trimmer body
pbr('mat_8', (0.900, 0.895, 0.880), 0.44, rough_var=0.06)                   # trimmer screw

# ---------------------------------------------------------------- solder fillets
# Bare leads poking through flat pads is the strongest "this is CAD" tell. KiCad's pad
# mesh is unwelded shards, so instead locate holes from the component leads that pass
# through them -- which also skips the unpopulated header automatically.
BOARD_ROLE_MATS = {'mat_9', 'mat_10', 'mat_11', 'mat_12', 'mat_13', 'mat_14', 'mat_15'}

def add_solder_fillets(scene):
    pads = next((o for o in meshes if 'mat_9' in sig(o)), None)
    fr4  = next((o for o in meshes if 'mat_15' in sig(o)), None)
    if pads is None or fr4 is None:
        return None
    comps = [o for o in meshes if not (sig(o) & BOARD_ROLE_MATS)]

    pad_w = [pads.matrix_world @ v.co for v in pads.data.vertices]
    top_z = max(p.z for p in pad_w)
    fr4_top = max((fr4.matrix_world @ v.co).z for v in fr4.data.vertices)

    # lead vertices that sit below the board's top face are inside a hole
    pts = []
    for c in comps:
        mw = c.matrix_world
        for v in c.data.vertices:
            w = mw @ v.co
            if w.z < fr4_top - 0.0002:
                pts.append(w)

    # centroid clustering; 1.2 mm is well inside the 2.54 mm minimum pad pitch
    R = 0.0012
    clusters = []
    for p in pts:
        for c in clusters:
            if (c['x'] - p.x) ** 2 + (c['y'] - p.y) ** 2 < R * R:
                c['n'] += 1
                c['x'] += (p.x - c['x']) / c['n']
                c['y'] += (p.y - c['y']) / c['n']
                break
        else:
            clusters.append({'x': p.x, 'y': p.y, 'n': 1})

    # pad copper near the top face, bucketed for a quick radius lookup
    CELL = 0.002
    grid = {}
    for w in pad_w:
        if w.z > top_z - 0.00008:
            grid.setdefault((int(w.x // CELL), int(w.y // CELL)), []).append(w)

    def pad_radius(cx, cy):
        best = 0.0
        gx, gy = int(cx // CELL), int(cy // CELL)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for w in grid.get((gx + dx, gy + dy), ()):
                    d2 = (w.x - cx) ** 2 + (w.y - cy) ** 2
                    if d2 < 0.0016 ** 2:
                        best = max(best, math.sqrt(d2))
        return min(max(best, 0.00055), 0.0011)

    verts, faces = [], []
    for c in clusters:
        cx, cy = c['x'], c['y']
        rad = pad_radius(cx, cy)
        h = min(rad * 0.46, 0.00058)
        # concave meniscus: wide at the pad, tucking in to the lead
        prof = [(rad * 1.04, 0.0), (rad * 0.74, h * 0.38),
                (rad * 0.48, h * 0.74), (0.00040, h)]
        SEG = 24
        base = len(verts)
        for (r, z) in prof:
            for si in range(SEG):
                a = 2 * math.pi * si / SEG
                verts.append((cx + r * math.cos(a), cy + r * math.sin(a),
                              top_z + z - 0.00003))
        for ring in range(len(prof) - 1):
            for si in range(SEG):
                s2 = (si + 1) % SEG
                a0 = base + ring * SEG + si; a1 = base + ring * SEG + s2
                faces.append((a0, a1, a1 + SEG, a0 + SEG))

    print(f"### solder joints: {len(clusters)}")
    if not clusters:
        return None
    sm = bpy.data.meshes.new("SolderMesh")
    sm.from_pydata(verts, [], faces)
    sm.update(); sm.shade_smooth()
    so = bpy.data.objects.new("Solder", sm)
    scene.collection.objects.link(so)     # verts already in world space
    so.data.materials.append(bpy.data.materials.new("mat_solder"))
    meshes.append(so)
    return so

_solder = add_solder_fillets(scene) if int(CFG['solder']) else None
if _solder:
    pbr('mat_solder', (0.680, 0.675, 0.655), 0.24, metal=1.0, rough_var=0.10)

# ---------------------------------------------------------------- group + orient
root = bpy.data.objects.new("BoardRoot", None)
scene.collection.objects.link(root)
# glTF import builds its own empty hierarchy: re-parent every scene root under ours,
# keeping each object's existing world transform.
for o in list(bpy.data.objects):
    if o is not root and o.parent is None:
        mw = o.matrix_world.copy()
        o.parent = root
        o.matrix_parent_inverse = root.matrix_world.inverted()
        o.matrix_world = mw
bpy.context.view_layer.update()

# world-space bounds of everything
def world_bounds():
    lo = Vector((1e9,) * 3); hi = Vector((-1e9,) * 3)
    for o in meshes:
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            for k in range(3):
                lo[k] = min(lo[k], w[k]); hi[k] = max(hi[k], w[k])
    return lo, hi

lo, hi = world_bounds()
print(f"### imported bounds {tuple(round(v,4) for v in lo)} .. {tuple(round(v,4) for v in hi)}")
print(f"### size {tuple(round(hi[k]-lo[k],4) for k in range(3))}")

# Bake the centring into each child's parent-inverse so the root's origin sits at the
# board centre -- otherwise the view rotation pivots around the wrong point.
from mathutils import Matrix
off = Matrix.Translation(-(lo + hi) / 2)
for o in root.children:
    o.matrix_parent_inverse = off @ o.matrix_parent_inverse
bpy.context.view_layer.update()

root.rotation_euler = (math.radians(CFG['rotx']), 0.0, math.radians(CFG['rotz']))
bpy.context.view_layer.update()

lo, hi = world_bounds()
root.location = Vector((-(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, 0.0))
bpy.context.view_layer.update()
lo, hi = world_bounds()
print(f"### after orient {tuple(round(v,4) for v in lo)} .. {tuple(round(v,4) for v in hi)}")
print(f"### projected {round(hi.x-lo.x,4)} x {round(hi.y-lo.y,4)}")

# ---------------------------------------------------------------- shadow catcher
if CFG['shadow']:
    bpy.ops.mesh.primitive_plane_add(size=0.4, location=(0, 0, lo.z - 0.00012))
    floor = bpy.context.active_object
    floor.name = "ShadowCatcher"
    floor.is_shadow_catcher = True
    floor.visible_diffuse = floor.visible_glossy = False

# ---------------------------------------------------------------- camera (orthographic, straight down)
cam_data = bpy.data.cameras.new("Cam")
cam_data.type = 'ORTHO'
# ortho<=0 -> auto-fit the oriented board with a margin
cam_data.ortho_scale = (max(hi.x - lo.x, hi.y - lo.y) * float(CFG['margin'])
                        if float(CFG['ortho']) <= 0 else float(CFG['ortho']))
print(f"### ortho_scale {cam_data.ortho_scale:.5f}")
cam = bpy.data.objects.new("Cam", cam_data)
cam.location = (0, 0, 0.5)
cam.rotation_euler = (0, 0, 0)
scene.collection.objects.link(cam)
scene.camera = cam

# ---------------------------------------------------------------- world / HDRI
world = bpy.data.worlds.new("W"); scene.world = world
world.use_nodes = True
nt = world.node_tree; nt.nodes.clear()
wout = nt.nodes.new('ShaderNodeOutputWorld');  wout.location = (600, 0)
bg   = nt.nodes.new('ShaderNodeBackground');   bg.location = (400, 0)
env  = nt.nodes.new('ShaderNodeTexEnvironment'); env.location = (100, 0)
mapn = nt.nodes.new('ShaderNodeMapping');      mapn.location = (-120, 0)
texc = nt.nodes.new('ShaderNodeTexCoord');     texc.location = (-320, 0)
env.image = bpy.data.images.load(os.path.join(HDRI_DIR, CFG['hdri'] + ".exr"))
mapn.inputs['Rotation'].default_value[2] = math.radians(float(CFG['hdri_rot']))
bg.inputs['Strength'].default_value = float(CFG['hdri_strength'])
nt.links.new(texc.outputs['Generated'], mapn.inputs['Vector'])
nt.links.new(mapn.outputs['Vector'], env.inputs['Vector'])
nt.links.new(env.outputs['Color'], bg.inputs['Color'])
nt.links.new(bg.outputs['Background'], wout.inputs['Surface'])

# ---------------------------------------------------------------- studio light rig
# The HDRI alone gives dome-wide soft light, which smears the shadow catcher into a
# grey haze. A dominant key light restores a defined contact shadow.
def area_light(name, loc, size, power, rot=(0, 0, 0), color=(1, 1, 1), shadow=True):
    d = bpy.data.lights.new(name, type='AREA')
    d.shape = 'SQUARE'; d.size = size; d.energy = power; d.color = color
    # Only the key casts. Fill and rim throwing their own shadows onto the catcher is
    # what turns a contact shadow into a grey smear across the frame.
    d.use_shadow = shadow
    try: d.cycles.cast_shadow = shadow
    except Exception: pass
    o = bpy.data.objects.new(name, d)
    o.location = loc; o.rotation_euler = rot
    scene.collection.objects.link(o)
    return o

KEY = float(CFG['key'])
if KEY > 0:
    # key: high and to the upper-left, aimed down at the board
    area_light("Key",  (-0.070, 0.066, 0.145), 0.070, KEY,
               rot=(math.radians(28), math.radians(-18), math.radians(-42)))
    # fill: broad, opposite side, low power to lift the shadow side
    area_light("Fill", (0.110, -0.055, 0.075), 0.22, KEY * 0.16,
               rot=(math.radians(62), 0.0, math.radians(118)),
               color=(0.93, 0.96, 1.0), shadow=False)
    # rim: behind and low, picks out the board edge and component silhouettes
    area_light("Rim",  (0.055, 0.115, 0.045), 0.10, KEY * 0.35,
               rot=(math.radians(76), 0.0, math.radians(200)), shadow=False)

# ---------------------------------------------------------------- render settings
scene.render.engine = 'CYCLES'
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'METAL'
prefs.get_devices()
for d in prefs.devices:
    d.use = True
scene.cycles.device = 'GPU'
scene.cycles.samples = int(CFG['samples'])
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.005
scene.cycles.use_denoising = bool(int(CFG['denoise']))
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.cycles.max_bounces = 16
scene.cycles.transmission_bounces = 12
scene.cycles.transparent_max_bounces = 16
scene.cycles.caustics_reflective = True
scene.cycles.blur_glossy = 0.5

scene.render.film_transparent = True
scene.render.resolution_x = int(CFG['res'])
scene.render.resolution_y = int(CFG['res'])
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.compression = 20
scene.render.filepath = OUT

scene.view_settings.view_transform = 'AgX'
try:
    scene.view_settings.look = CFG['look']
except Exception:
    pass
scene.view_settings.exposure = float(CFG['expo'])

if CFG['blend']:
    bp = os.path.abspath(CFG['blend'])
    try:
        bpy.ops.file.pack_all()          # embed the HDRI so the file is self-contained
    except Exception as e:
        print("### pack warning:", e)
    bpy.ops.wm.save_as_mainfile(filepath=bp, compress=True)
    print("### wrote", bp)

if not int(CFG['norender']):
    bpy.ops.render.render(write_still=True)
    print("### wrote", OUT)
