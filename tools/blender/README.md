# Receptor card build

`receptor_card.py` turns a Protein Data Bank entry into the two files a Pharmacology
receptor card uses: a 3D model in `assets/models/` and a still image in `assets/img/`.
`membrane_plane.py` is the helper that works out where the membrane goes.

## The six cards

| Card | Entry | Shown | Left out | View |
|---|---|---|---|---|
| `5ht2a-psilocin-9as8` | 9AS8 | 5-HT2A (chain A), psilocin, G protein (B, C, D) | antibody fragment (E) | 110 |
| `nmda-ketamine-7eu7` | 7EU7 | GluN1 (A, C), GluN2A (B, D), S-ketamine, glycine, glutamate | sugars | 110 |
| `dat-cocaine-9eo4` | 9EO4 | dopamine transporter (B), cocaine | sodium, chloride, cholesterol | 110 |
| `mor-morphine-8ef6` | 8EF6 | mu-opioid receptor (R), morphine, G protein (A, B, C) | second receptor copy (M), helix fragment (F), antibody fragment (E), cholesterol | 20 |
| `gabaa-diazepam-6x3x` | 6X3X | alpha1 (B, D), beta2 (A, C), gamma2 (E), diazepam, GABA | four antibody chains (I, J, K, L), sugars | 290 |
| `cb1-amg315-8ghv` | 8GHV | CB1 (D), AMG315, G protein (A, B, C) | antibody fragment (S) | 110 |

The CB1 entries 5XRA and 5XR8 are not used. The 2017 Nature paper that first reported them was retracted on
27 August 2025 over its cell-signalling data, and a revised, peer-reviewed paper with the same structures was
published the same day (Hua et al. 2025, doi 10.1038/s41586-025-09454-5). Keeping them off the site avoids confusion;
the page test still refuses both IDs.

## What the script does

1. Reads the structure with Molecular Nodes.
2. Keeps the chains and molecules listed above.
3. Turns the model so the membrane normal points up.
   - For 9AS8 the normal is the mean direction of the seven membrane-spanning helices that
     UniProt lists for P28223.
   - For the others it is the direction in which a 30 angstrom slab holds the most
     water-avoiding and fewest charged residues. On 9AS8 the two methods differ by 14 degrees
     in tilt and 0.3 angstroms in height.
   - Which side is outside comes from a part known to be outside (a bound transmitter or an
     outer loop) or inside (the G protein).
4. Draws the proteins as ribbons and the small molecules as spheres, in the site's colours.
5. Reduces the meshes to about 30,000 triangles and writes the GLB in nanometres.
6. Renders the still image with a plain slab for the membrane.

## How to rebuild

Use Blender 5.2.4 LTS with the Molecular Nodes extension, version 520.2.0.

```sh
curl -o 8EF6.cif https://files.rcsb.org/download/8EF6.cif
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
  --addons bl_ext.blender_org.molecularnodes -P tools/blender/receptor_card.py \
  -- mor-morphine-8ef6 8EF6.cif out 20
```

The last argument is the view angle from the table. Use `preview` instead to get four small
images from different sides.

The script writes `out/<card>.glb`, `out/<card>.json` and `out/<card>.png`. Each PNG was
resized to 960 by 1200 and saved as WebP at quality 84, and to 152 by 190 for the thumbnail.
The numbers in the JSON file (size, label points) were copied into the `RC` object in
`pharma.html`.

## Files used

SHA-256 of the coordinate files the committed assets were built from, downloaded 2026-11-20:

- 9AS8 `5353a856fa2c2a7741165a522f2345c5c1d3b2b864b4aac9e7c1237d9daedcf9`
- 7EU7 `7bbee15dff41f25e3f753d85fe9b3b4979d03870e6664f229887dad2ae241aab`
- 9EO4 `71bbf506e9bee53aae0f445ec542a19b865fd55d63f8b066cd68542609d51b82`
- 8EF6 `d2e3021936e1545053153a883174e0d2628979e209ce1eb276edc6f029939d4e`
- 6X3X `8f67b853dd6c49f7836441b3e5cb8aaa16aed5087ae158bd7872728e11dadae2`
- 8GHV `55ea0b8514ee0749cef48ef858cfce033242160c79820f3654d56facde4f59e1`

The 9AS8 model and image on the site were built by the first version of this script. A
rebuild gives the same picture with slightly different triangle counts.
