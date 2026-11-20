"""Build the receptor card assets (a 3D model and a still image) from Protein Data Bank entries.

Run with Blender 5.2.4 LTS and Molecular Nodes 520.2.0:
  Blender -b --factory-startup --addons bl_ext.blender_org.molecularnodes \
      -P receptor_card.py -- <card> <file.cif> <out_dir> [preview | <azimuth in degrees>]

Each run writes <card>.glb (membrane normal along +Y, nanometres, origin mid-membrane),
<card>.json (numbers the page needs for the camera and labels) and still images.
"preview" renders four small stills from different sides, to choose a view from.
"""
import bpy, bmesh, sys, json, importlib, os, math
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from membrane_plane import membrane

mn = importlib.import_module("bl_ext.blender_org.molecularnodes")
CARD, CIF, OUT = sys.argv[sys.argv.index("--") + 1: sys.argv.index("--") + 4]
MODE = (sys.argv[sys.argv.index("--") + 4:] or ["preview"])[0]
os.makedirs(OUT, exist_ok=True)

# Atlas colours from the site's stylesheet.
VIOLET, SKY, ROSE, GREY, AMBER, GREEN = "#6a54a6", "#2f6fa8", "#a2477e", "#8fa0b3", "#c0573a", "#3d8a4a"
GPROT = "(chainID A or chainID B or chainID C) and protein"
CARDS = {
    # Human 5-HT2A, psilocin, engineered mini-Gq with G-beta and G-gamma. The antibody fragment (chain E) is left out.
    # Membrane-spanning segments are UniProt P28223's, read 2026-11-20.
    "5ht2a-psilocin-9as8": dict(
        parts=[("receptor", "chainID A and protein", VIOLET), ("gprotein", "(chainID B or chainID C or chainID D) and protein", GREY)],
        ligands=[("ligand", "resname 91Q", AMBER, 0.7)], budget={"receptor": 16000, "gprotein": 9000},
        tm=("chainID A", [(81, 97), (112, 137), (147, 171), (192, 215), (233, 258), (323, 348), (357, 382)]),
        outside="resname 91Q"),
    # Human GluN1 (A, C) and GluN2A (B, D) with S-ketamine in the pore, and glycine and glutamate on the outer domains.
    "nmda-ketamine-7eu7": dict(
        parts=[("receptor", "(chainID A or chainID C) and protein and resid 1:860", VIOLET),
               ("receptor2", "(chainID B or chainID D) and protein and resid 1:860", SKY)],
        ligands=[("ligand", "resname JC9", AMBER, 1.0),
                 ("ligand2", "(resname GLY and resid 910) or (resname GLU and resid 904)", GREEN, 1.0)],
        budget={"receptor": 13000, "receptor2": 13000}, sphere=(8, 5),
        outside="(resname GLY and resid 910) or (resname GLU and resid 904)"),
    # Human dopamine transporter with cocaine. Residues 172 to 236 are an outer loop (UniProt Q01959).
    "dat-cocaine-9eo4": dict(
        parts=[("receptor", "chainID B and protein", VIOLET)],
        ligands=[("ligand", "resname COC", AMBER, 0.8)], budget={"receptor": 26000},
        outside="chainID B and protein and resid 172:236"),
    # Human mu-opioid receptor with morphine and Gi. The entry holds two receptor copies. Chain R is the one
    # modelled with the whole G protein. Chain M, the helix fragment F and the antibody fragment E are left out.
    "mor-morphine-8ef6": dict(
        parts=[("receptor", "chainID R and protein", VIOLET), ("gprotein", GPROT, GREY)],
        ligands=[("ligand", "chainID R and resname MOI", AMBER, 0.7)], budget={"receptor": 16000, "gprotein": 9000},
        inside=GPROT),
    # Human alpha1 (B, D), beta2 (A, C) and gamma2 (E) GABA-A receptor with GABA and diazepam. The four Fab chains are left out.
    "gabaa-diazepam-6x3x": dict(
        parts=[("receptor", "(chainID B or chainID D) and protein", VIOLET), ("receptor2", "(chainID A or chainID C) and protein", SKY),
               ("receptor3", "chainID E and protein", ROSE)],
        ligands=[("ligand", "resname DZP", AMBER, 1.0), ("ligand2", "resname ABU", GREEN, 1.0)],
        budget={"receptor": 10000, "receptor2": 10000, "receptor3": 5000}, sphere=(8, 5),
        outside="resname ABU"),
    # Human CB1 with AMG315 and Gi. The antibody fragment (chain S) is left out.
    "cb1-amg315-8ghv": dict(
        parts=[("receptor", "chainID D and protein", VIOLET), ("gprotein", GPROT, GREY)],
        ligands=[("ligand", "resname ZI5", AMBER, 0.7)], budget={"receptor": 16000, "gprotein": 9000},
        inside=GPROT),
}
cfg = CARDS[CARD]

def lin(h):   # sRGB hex to the linear values Blender and glTF store
    return tuple((((int(h[i:i + 2], 16) / 255) + 0.055) / 1.055) ** 2.4 for i in (1, 3, 5))

for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)

# ---- orientation ----
ref = mn.Molecule.load(CIF, style=None, name="ref")
u = ref.universe
S = float(ref.named_attribute("position")[0][0] / u.atoms.positions[0][0])   # world units per angstrom
rec_sel = " or ".join("(%s)" % p[1] for p in cfg["parts"] if p[0].startswith("receptor"))
rec_ca = u.select_atoms("(%s) and name CA" % rec_sel)
if "tm" in cfg:
    # mean direction of the listed helices, each pointed from the cell side to the outside
    chain, segs = cfg["tm"]
    pts = u.select_atoms("%s and name CA and (%s)" % (chain, " or ".join("resid %d:%d" % r for r in segs))).positions
    centre = pts.mean(0); axis = np.zeros(3)
    for i, (a, b) in enumerate(segs):
        h = u.select_atoms("%s and name CA and resid %d:%d" % (chain, a, b)).positions
        d = np.linalg.svd(h - h.mean(0))[2][0]
        if np.dot(d, h[-1] - h[0]) < 0: d = -d
        axis += -d if i % 2 == 0 else d
    axis /= np.linalg.norm(axis)
    # report how far the general method below would differ, as a check on it
    a2, c2, _ = membrane(rec_ca.positions.astype(float), list(rec_ca.resnames))
    print("CHECK slab method vs helix method: angle %.1f deg, centre shift along normal %.1f A"
          % (math.degrees(math.acos(min(1, abs(float(a2 @ axis))))), abs(float((c2 - centre) @ axis))))
else:
    # the 30 angstrom slab that holds the most water-avoiding and fewest charged residues
    axis, centre, score = membrane(rec_ca.positions.astype(float), list(rec_ca.resnames))
    print("PLANE score %.0f" % score, "CA in slab", int((np.abs((rec_ca.positions - centre) @ axis) < 15).sum()), "of", len(rec_ca))
if "outside" in cfg and np.dot(axis, u.select_atoms(cfg["outside"]).positions.mean(0) - centre) < 0: axis = -axis
if "inside" in cfg and np.dot(axis, u.select_atoms(cfg["inside"]).positions.mean(0) - centre) > 0: axis = -axis
rot = Vector(axis).rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4()
M = rot @ Matrix.Translation(-Vector(centre * S))
K = 1.0 / (S * 10)                                   # world units to nanometres
def place(p):                                        # angstroms to oriented nanometres (Blender axes, z up)
    return np.array([(M @ Vector(q * S))[:] for q in p]) * K
def gl(p):                                           # Blender axes to glTF axes (x, height, depth)
    return [round(float(v), 2) for v in (p[0], p[2], -p[1])]

# ---- meshes ----
def material(name, colour):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*lin(colour), 1); b.inputs["Roughness"].default_value = 0.8
    b.inputs["Metallic"].default_value = 0.0
    return m

def cartoon(name, selection, colour):
    mol = mn.Molecule.load(CIF, style="cartoon", selection=selection, name="mn_" + name)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(mol.object.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(mol.object, do_unlink=True)
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    me.transform(M); me.transform(Matrix.Scale(K, 4))
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6); bm.to_mesh(me); bm.free()
    n0 = len(me.polygons); want = cfg["budget"][name]
    if n0 > want:
        mod = ob.modifiers.new("dec", "DECIMATE"); mod.ratio = want / n0
        dg = bpy.context.evaluated_depsgraph_get()
        me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
        ob.modifiers.clear(); ob.data = me2; bpy.data.meshes.remove(me); me = me2
    for a in list(me.attributes):
        if a.name != "position" and not a.is_internal and not a.is_required:
            try: me.attributes.remove(a)
            except Exception: pass
    for p in me.polygons: p.use_smooth = True
    me.materials.clear(); me.materials.append(material(name, colour))
    print("MESH", name, "tris before", n0, "after", len(me.polygons))
    return ob

objs = [cartoon(*p) for p in cfg["parts"]]

SEG = cfg.get("sphere", (12, 7))        # coarser spheres where the molecules are small on screen
VDW = {"C": 1.7, "N": 1.55, "O": 1.52, "CL": 1.75, "S": 1.8, "F": 1.47}
copies = {}
for name, sel, colour, scale in cfg["ligands"]:
    ag = u.select_atoms(sel); ag = ag[np.array([str(e).upper() != "H" for e in ag.elements])]
    pts = place(ag.positions); bm = bmesh.new()
    for p, el in zip(pts, ag.elements):
        bmesh.ops.create_uvsphere(bm, u_segments=SEG[0], v_segments=SEG[1], radius=VDW.get(str(el).upper(), 1.7) * scale / 10,
                                  matrix=Matrix.Translation(Vector(p)))
    bmesh.ops.triangulate(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    me.materials.append(material(name, colour))
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob); objs.append(ob)
    groups = {}                                      # where each copy of the molecule sits, for labels
    for p, a in zip(pts, ag): groups.setdefault((a.chainID, int(a.resid), a.resname), []).append(p)
    copies[name] = [{"chain": k[0], "res": k[2], "atoms": len(v), "at": gl(np.mean(v, 0))} for k, v in sorted(groups.items())]
    print("MESH", name, "tris", len(me.polygons), "copies", [(c["chain"], c["res"], c["atoms"], c["at"]) for c in copies[name]])

# ---- numbers for the page ----
allv = np.concatenate([np.array([v.co[:] for v in o.data.vertices]) for o in objs])
zlo, zhi = float(allv[:, 2].min()), float(allv[:, 2].max()); rmax = float(np.hypot(allv[:, 0], allv[:, 1]).max())
rc = place(rec_ca.positions); inslab = rc[np.abs(rc[:, 2]) < 1.5]
slab_r = float(np.hypot(inslab[:, 0], inslab[:, 1]).max()) + 1.6
top = rc[np.argmax(rc[:, 2])]
meta = {"card": CARD, "units": "nm", "up": "+Y is the outside of the cell", "membrane_half_thickness_nm": 1.5,
        "height_range_nm": [round(zlo, 2), round(zhi, 2)], "radius_nm": round(rmax, 2), "slab_half_width_nm": round(slab_r, 2),
        "receptor_height_range_nm": [round(float(rc[:, 2].min()), 2), round(float(rc[:, 2].max()), 2)],
        "receptor_top": gl(top), "parts": {}, "ligands": copies, "triangles": {o.name: len(o.data.polygons) for o in objs}}
for name, sel, colour in cfg["parts"]:
    meta["parts"][name] = gl(place(u.select_atoms("(%s) and name CA" % sel).positions).mean(0))
bpy.data.objects.remove(ref.object, do_unlink=True)
json.dump(meta, open(os.path.join(OUT, CARD + ".json"), "w"), indent=1)

bpy.ops.object.select_all(action="DESELECT")
for ob in objs: ob.select_set(True)
glb = os.path.join(OUT, CARD + ".glb")
bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True, export_yup=True,
                          export_apply=True, export_normals=True, export_texcoords=False,
                          export_materials="EXPORT", export_cameras=False, export_lights=False,
                          export_animations=False, export_extras=False)
print("GLB bytes", os.path.getsize(glb), "META", json.dumps(meta))

# ---- still images: the same scene with a plain slab for the membrane ----
scn = bpy.context.scene
scn.render.engine = "CYCLES"; scn.cycles.device = "CPU"
scn.render.film_transparent = True; scn.view_settings.view_transform = "Standard"
scn.render.image_settings.file_format = "PNG"; scn.render.image_settings.color_mode = "RGBA"
w = bpy.data.worlds.new("w"); scn.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 0.75
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 2.0; sun.data.angle = 0.6
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); scn.collection.objects.link(sun)
slab = bpy.data.meshes.new("slab"); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1); bm.to_mesh(slab); bm.free()
so = bpy.data.objects.new("membrane", slab); so.scale = (2 * slab_r, 2 * slab_r, 3.0); scn.collection.objects.link(so)
sm = bpy.data.materials.new("membrane"); sm.use_nodes = True
b = sm.node_tree.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (*lin("#93a6ba"), 1)
b.inputs["Alpha"].default_value = 0.16; b.inputs["Roughness"].default_value = 1.0
slab.materials.append(sm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); scn.collection.objects.link(cam); scn.camera = cam
cam.data.type = "ORTHO"; mid = (zlo + zhi) / 2
cam.data.ortho_scale = max(zhi - zlo, 2 * max(rmax, slab_r) / 0.8) * 1.12
preview = MODE == "preview"
scn.cycles.samples = 24 if preview else 96
scn.render.resolution_x, scn.render.resolution_y = (480, 600) if preview else (1200, 1500)
for az in ((20, 110, 200, 290) if preview else (float(MODE),)):
    a = math.radians(az); d = 80
    cam.location = (d * math.sin(a), -d * math.cos(a), mid + d * 0.15)
    cam.rotation_euler = (Vector((0, 0, mid)) - Vector(cam.location)).to_track_quat("-Z", "Y").to_euler()
    scn.render.filepath = os.path.join(OUT, CARD + ("-az%03d" % az if preview else "") + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDER", scn.render.filepath)
