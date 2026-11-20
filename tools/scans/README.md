# Brain scan data

`prep_icbm.py` makes the two files the Scans page loads, from the MNI ICBM152 2009c
nonlinear asymmetric template (McConnell Brain Imaging Centre, McGill).

- Download: https://www.bic.mni.mcgill.ca/~vfonov/icbm/2009/mni_icbm152_nlin_asym_09c_nifti.zip
  (57,583,823 bytes, SHA-256 `804382e5d68a42ff8096ee845a7600b6658434da762fa67840a149eb25d48bd4`)
- Licence: the `COPYING` notice in the zip, kept as `assets/scans/COPYING-ICBM152`. It must go
  with every copy, so the page quotes it in full.

Run with any Python that has numpy (Blender's Python works):

    python3 tools/scans/prep_icbm.py <unzipped folder>/mni_icbm152_nlin_asym_09c assets/scans

The template stores int16 values with a scale factor in the header. The script applies it, so
fluid keeps its dark values instead of reading as negative numbers.

The viewer is NiiVue 0.69.0 (BSD 2-Clause), the self-contained `dist/niivue.umd.js` from the npm
package, whose tarball matched npm's published sha512 integrity. Its SHA-384 is pinned in the tests.
