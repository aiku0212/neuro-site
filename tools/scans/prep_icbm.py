"""Turn the MNI ICBM152 2009c asymmetric template into small files for the Scans page.

Run with any Python that has numpy:
    python3 tools/scans/prep_icbm.py <unzipped mni_icbm152_nlin_asym_09c folder> assets/scans

Writes, all 1 mm and cropped to the brain:
    icbm152-t1-brain.nii.gz    T1 image, skull removed with the template's own brain mask, 1-255 inside the brain
    icbm152-tissue.nii.gz      1 grey matter, 2 white matter, 3 fluid: the most likely tissue
                               in each voxel, where that tissue's probability is at least 0.5
Values are rescaled for display, so they are not the template's original intensities.
"""
import gzip, os, struct, sys
import numpy as np

src, out = sys.argv[1], sys.argv[2]
P = lambda n: os.path.join(src, 'mni_icbm152_%s_tal_nlin_asym_09c%s.nii' % n)

def read(path):
    b = open(path, 'rb').read()
    dim = struct.unpack('<8h', b[40:56]); dt = struct.unpack('<h', b[70:72])[0]
    off = int(struct.unpack('<f', b[108:112])[0])
    nx, ny, nz = dim[1:4]
    dtype = {2: np.uint8, 4: np.int16, 16: np.float32, 64: np.float64}[dt]
    a = np.frombuffer(b, dtype=dtype, count=nx*ny*nz, offset=off).reshape((nz, ny, nx))
    # The template stores int16 values with a scale factor; apply it, or dark fluid reads as negative.
    slope, inter = struct.unpack('<ff', b[112:120])
    if slope == 0: slope, inter = 1.0, 0.0
    return b[:348], a.astype(np.float32) * slope + inter

def write(path, hdr, arr, origin):
    h = bytearray(hdr)
    nz, ny, nx = arr.shape
    h[40:56] = struct.pack('<8h', 3, nx, ny, nz, 1, 1, 1, 1)
    h[70:74] = struct.pack('<hh', 2, 8)                 # uint8
    h[108:112] = struct.pack('<f', 352.0)
    h[112:120] = struct.pack('<ff', 1.0, 0.0)           # no scaling
    h[252:256] = struct.pack('<hh', 0, 4)               # sform only, MNI space
    for i, row in enumerate(((1, 0, 0, origin[0]), (0, 1, 0, origin[1]), (0, 0, 1, origin[2]))):
        h[280+16*i:296+16*i] = struct.pack('<4f', *row)
    with gzip.GzipFile(path, 'wb', compresslevel=9, mtime=0) as f:
        f.write(bytes(h) + b'\0\0\0\0' + np.ascontiguousarray(arr, dtype=np.uint8).tobytes())

hdr, t1 = read(P(('t1', '')))
_, mask = read(P(('t1', '_mask')))
_, gm = read(P(('gm', ''))); _, wm = read(P(('wm', ''))); _, csf = read(P(('csf', '')))
x0 = struct.unpack('<f', hdr[292:296])[0]; y0 = struct.unpack('<f', hdr[308:312])[0]; z0 = struct.unpack('<f', hdr[324:328])[0]

brain = mask > 0.5
zs, ys, xs = np.where(brain)
pad = 3
lo = [max(0, a.min() - pad) for a in (zs, ys, xs)]
hi = [min(n, a.max() + pad + 1) for a, n in zip((zs, ys, xs), t1.shape)]
crop = tuple(slice(l, h) for l, h in zip(lo, hi))
origin = (x0 + lo[2], y0 + lo[1], z0 + lo[0])

v = t1[crop]
top = np.percentile(v[brain[crop]], 99.5)
bottom = v[brain[crop]].min()
img = np.where(brain[crop], np.clip((v - bottom) / (top - bottom) * 254 + 1, 1, 255).round(), 0)

probs = np.stack([gm, wm, csf])[(slice(None),) + crop]
lab = probs.argmax(0) + 1
lab[(probs.max(0) < 0.5) | ~brain[crop]] = 0

os.makedirs(out, exist_ok=True)
write(os.path.join(out, 'icbm152-t1-brain.nii.gz'), hdr, img, origin)
write(os.path.join(out, 'icbm152-tissue.nii.gz'), hdr, lab, origin)
print('cropped to', img.shape[::-1], 'origin', origin)
for n in ('icbm152-t1-brain.nii.gz', 'icbm152-tissue.nii.gz'):
    print(n, os.path.getsize(os.path.join(out, n)))
print('tissue voxels', {k: int((lab == k).sum()) for k in (1, 2, 3)})
