# Receptor card build

`receptor_card.py` turns Protein Data Bank entry 9AS8 into the two files the Pharmacology
receptor card uses.

- `assets/models/5ht2a-psilocin-9as8.glb` is the 3D model.
- `assets/img/5ht2a-psilocin-9as8.webp` is the still image.

## What it does

1. Reads the structure with Molecular Nodes.
2. Keeps the receptor (chain A), psilocin (ligand 91Q) and the G protein (chains B, C and D).
   It leaves out the antibody fragment (chain E).
3. Turns the model so the membrane normal points up. The normal is the mean direction of
   the seven membrane-spanning helices listed by UniProt for P28223.
4. Draws the proteins as ribbons and psilocin as spheres, in the site's colours.
5. Reduces the meshes to about 28,000 triangles and writes the GLB in nanometres.
6. Renders the still image with a plain slab for the membrane.

## How to rebuild

Use Blender 5.2.4 LTS with the Molecular Nodes extension, version 520.2.0.

```sh
curl -o 9AS8.cif https://files.rcsb.org/download/9AS8.cif
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
  --addons bl_ext.blender_org.molecularnodes -P tools/blender/receptor_card.py -- 9AS8.cif out
```

The file used for the committed assets had this SHA-256:
`5353a856fa2c2a7741165a522f2345c5c1d3b2b864b4aac9e7c1237d9daedcf9`.

The script writes `out/5ht2a-psilocin-9as8.glb` and a PNG. The PNG was resized to
960 by 1200 and saved as WebP at quality 84.
