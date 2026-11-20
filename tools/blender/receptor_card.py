"""Build the 5-HT2A and psilocin receptor card assets from PDB 9AS8.

Run with Blender 5.2.4 LTS and Molecular Nodes 520.2.0:
  Blender -b --factory-startup --addons bl_ext.blender_org.molecularnodes \
      -P receptor_card.py -- 9AS8.cif out_dir

Outputs a GLB (receptor, G protein and psilocin as three meshes, membrane normal along +Y,
units of nanometres, origin at the middle of the membrane), a JSON file of the points
the page labels, and a still image of the same scene with a plain slab for the membrane.
"""
import bpy, bmesh, sys, json, importlib, os
import numpy as np
from mathutils import Matrix, Vector

mn = importlib.import_module("bl_ext.blender_org.molecularnodes")
CIF, OUT = sys.argv[sys.argv.index("--") + 1: sys.argv.index("--") + 3]
os.makedirs(OUT, exist_ok=True)

# Membrane-spanning segments of human 5-HT2A (UniProt P28223, read 2026-11-20).
TM = [(81, 97), (112, 137), (147, 171), (192, 215), (233, 258), (323, 348), (357, 382)]
# Atlas colours from the site's stylesheet, converted from sRGB to the linear values Blender and glTF store.
def lin(h): return tuple((((int(h[i:i + 2], 16) / 255) + 0.055) / 1.055) ** 2.4 for i in (1, 3, 5))
COLORS = {"receptor": lin("#6a54a6"), "gprotein": lin("#8fa0b3"), "ligand": lin("#c0573a")}
BUDGET = {"receptor": 16000, "gprotein": 9000}

for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)

# ---- orientation from the atoms ----
ref = mn.Molecule.load(CIF, style=None, name="ref")
u = ref.universe
S = float(ref.named_attribute("position")[0][0] / u.atoms.positions[0][0])   # world units per angstrom
sel_tm = " or ".join("resid %d:%d" % r for r in TM)
ca = u.select_atoms("chainID A and name CA and (%s)" % sel_tm).positions * S
lig = u.select_atoms("resname 91Q")
gp = u.select_atoms("(chainID B or chainID C or chainID D) and name CA").positions * S
centre = ca.mean(0)
# The membrane normal is taken as the mean direction of the seven helices,
# each pointed from the cell side to the outside.
axis = np.zeros(3)
for i, (a, b) in enumerate(TM):
    h = u.select_atoms("chainID A and name CA and resid %d:%d" % (a, b)).positions * S
    c = h.mean(0); d = np.linalg.svd(h - c)[2][0]
    if np.dot(d, h[-1] - h[0]) < 0: d = -d          # along the sequence
    if i % 2 == 0: d = -d                           # odd-numbered helices run outside to inside
    axis += d
axis /= np.linalg.norm(axis)
if np.dot(axis, lig.positions.mean(0) * S - centre) < 0: axis = -axis   # psilocin sits toward the outside
z = Vector(axis)
rot = z.rotation_difference(Vector((0, 0, 1))).to_matrix().to_4x4()
M = rot @ Matrix.Translation(-Vector(centre))
def place(p): return np.array([(M @ Vector(q))[:] for q in p])
ca_p = place(ca); lig_p = place(lig.positions * S); gp_p = place(gp)
print("SCALE units per angstrom", S, "| TM half-height (nm)", float(np.abs(ca_p[:, 2]).max() / (S * 10)),
      "| ligand z (nm)", float(lig_p[:, 2].mean() / (S * 10)), "| G protein z (nm)", float(gp_p[:, 2].mean() / (S * 10)))
bpy.data.objects.remove(ref.object, do_unlink=True)

# ---- meshes ----
def material(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*COLORS[name], 1); b.inputs["Roughness"].default_value = 0.8
    b.inputs["Metallic"].default_value = 0.0
    return m

def cartoon(name, selection):
    mol = mn.Molecule.load(CIF, style="cartoon", selection=selection, name=name)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(mol.object.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(mol.object, do_unlink=True)
    ob = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(ob)
    me.transform(M)
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.triangulate(bm, faces=bm.faces)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5); bm.to_mesh(me); bm.free()
    n0 = len(me.polygons)
    if n0 > BUDGET[name]:
        mod = ob.modifiers.new("dec", "DECIMATE"); mod.ratio = BUDGET[name] / n0
        dg = bpy.context.evaluated_depsgraph_get()
        me2 = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
        ob.modifiers.clear(); ob.data = me2; bpy.data.meshes.remove(me); me = me2
    for a in list(me.attributes):
        if a.name not in ("position",) and not a.is_internal and not a.is_required:
            try: me.attributes.remove(a)
            except Exception: pass
    for p in me.polygons: p.use_smooth = True
    me.materials.clear(); me.materials.append(material(name))
    print("MESH", name, "tris before", n0, "after", len(me.polygons), "verts", len(me.vertices))
    return ob

rec = cartoon("receptor", "chainID A and protein")
gpo = cartoon("gprotein", "(chainID B or chainID C or chainID D) and protein")

# psilocin: one sphere per heavy atom at 0.7 of its van der Waals radius
VDW = {"C": 1.7, "N": 1.55, "O": 1.52}
bm = bmesh.new()
for p, el in zip(lig_p, lig.elements):
    r = VDW.get(el, 1.7) * 0.7 * S
    bmesh.ops.create_uvsphere(bm, u_segments=14, v_segments=8, radius=r, matrix=Matrix.Translation(Vector(p)))
bmesh.ops.triangulate(bm, faces=bm.faces)
me = bpy.data.meshes.new("ligand"); bm.to_mesh(me); bm.free()
for p in me.polygons: p.use_smooth = True
me.materials.append(material("ligand"))
ligo = bpy.data.objects.new("ligand", me); bpy.context.collection.objects.link(ligo)
print("MESH ligand tris", len(me.polygons), "atoms", len(lig_p), "elements", sorted(set(lig.elements)))

# nanometres in the file, whatever unit Molecular Nodes used
k = 1.0 / (S * 10)
for ob in (rec, gpo, ligo):
    ob.data.transform(Matrix.Scale(k, 4)); ob.data.update()

bpy.ops.object.select_all(action="DESELECT")
for ob in (rec, gpo, ligo): ob.select_set(True)
glb = os.path.join(OUT, "5ht2a-psilocin-9as8.glb")
bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB", use_selection=True, export_yup=True,
                          export_apply=True, export_normals=True, export_texcoords=False,
                          export_materials="EXPORT", export_cameras=False, export_lights=False,
                          export_animations=False, export_extras=False)
tm_half = float(np.abs(ca_p[:, 2]).max() * k)
meta = {
    "source": "PDB 9AS8", "units": "nm", "up": "+Y is the outside of the cell",
    "membrane_half_thickness_nm": 1.5,
    "tm_extent_nm": round(tm_half, 2),
    "ligand_centre_nm": [round(float(v), 3) for v in (lig_p.mean(0) * k)[[0, 2, 1]] * np.array([1, 1, -1])],
    "gprotein_centre_nm": [round(float(v), 3) for v in (gp_p.mean(0) * k)[[0, 2, 1]] * np.array([1, 1, -1])],
    "triangles": {o.name: len(o.data.polygons) for o in (rec, gpo, ligo)},
}
json.dump(meta, open(os.path.join(OUT, "5ht2a-psilocin-9as8.json"), "w"), indent=1)
print("GLB bytes", os.path.getsize(glb), "META", json.dumps(meta))

# ---- still images: the same scene with a schematic membrane slab ----
import math
scn = bpy.context.scene
scn.render.engine = "CYCLES"; scn.cycles.samples = 96; scn.cycles.device = "CPU"
scn.render.film_transparent = True; scn.view_settings.view_transform = "Standard"
scn.render.resolution_x, scn.render.resolution_y = 1200, 1500
scn.render.image_settings.file_format = "PNG"; scn.render.image_settings.color_mode = "RGBA"
w = bpy.data.worlds.new("w"); scn.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1); w.node_tree.nodes["Background"].inputs[1].default_value = 0.75
sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN")); sun.data.energy = 2.0; sun.data.angle = 0.6
sun.rotation_euler = (math.radians(50), 0, math.radians(35)); scn.collection.objects.link(sun)
slab = bpy.data.meshes.new("slab"); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1); bm.to_mesh(slab); bm.free()
so = bpy.data.objects.new("membrane", slab); so.scale = (11, 11, 3.0); scn.collection.objects.link(so)
sm = bpy.data.materials.new("membrane"); sm.use_nodes = True
b = sm.node_tree.nodes["Principled BSDF"]; b.inputs["Base Color"].default_value = (*lin("#93a6ba"), 1)
b.inputs["Alpha"].default_value = 0.16; b.inputs["Roughness"].default_value = 1.0
slab.materials.append(sm)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); scn.collection.objects.link(cam); scn.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 14.5
for az in (110,):
    a = math.radians(az); d = 40
    cam.location = (d * math.sin(a), -d * math.cos(a), -2.6 + 6)
    look = Vector((0, 0, -2.6)); dirv = look - Vector(cam.location)
    cam.rotation_euler = dirv.to_track_quat("-Z", "Y").to_euler()
    scn.render.filepath = os.path.join(OUT, "5ht2a-psilocin-9as8.png")
    bpy.ops.render.render(write_still=True)
    print("RENDER", scn.render.filepath)
