"""Find the membrane plane of a membrane protein from its own atoms (no residue numbering needed).
A 30 angstrom slab is placed so that it holds as many water-avoiding residues, and as few charged
ones, as possible. Used by the receptor card build, and runnable alone as a check."""
import numpy as np
HYD = {"LEU": 1, "ILE": 1, "VAL": 1, "PHE": 1, "MET": 1, "ALA": 0.5, "TRP": 1, "CYS": 0.5, "TYR": 0.3}
POL = {"ASP": -1.5, "GLU": -1.5, "LYS": -1.5, "ARG": -1.5, "ASN": -0.7, "GLN": -0.7, "HIS": -0.5, "PRO": -0.2, "SER": -0.2, "THR": -0.1}
def weights(names): return np.array([HYD.get(n, POL.get(n, 0.0)) for n in names])
def sphere(n):
    i = np.arange(n) + 0.5; phi = np.arccos(1 - i / n); th = np.pi * (1 + 5 ** 0.5) * i   # upper hemisphere
    return np.c_[np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)]
def best_offset(t, w, half):
    lo, hi = t.min(), t.max(); edges = np.arange(lo - 1, hi + 2, 1.0)
    h = np.histogram(t, bins=edges, weights=w)[0]; c = np.concatenate([[0], np.cumsum(h)])
    k = int(round(2 * half)); 
    if len(h) <= k: return h.sum(), (lo + hi) / 2
    s = c[k:] - c[:-k]; j = int(np.argmax(s)); return s[j], edges[j] + half
def membrane(ca, names, half=15.0, prior=None, cone=None, n=6000):
    """ca in angstroms. Returns (unit normal, centre point on the normal, score)."""
    w = weights(names); c0 = ca.mean(0); X = ca - c0; best = (-1e9, None, 0)
    dirs = sphere(n)
    if prior is not None and cone is not None:
        keep = np.abs(dirs @ prior) > np.cos(np.radians(cone)); dirs = dirs[keep]
    for d in dirs:
        s, off = best_offset(X @ d, w, half)
        if s > best[0]: best = (s, d, off)
    s, d, off = best
    for scale in (0.05, 0.02, 0.008):                      # refine around the best direction
        rng = np.random.default_rng(0)
        for _ in range(400):
            e = d + rng.normal(0, scale, 3); e /= np.linalg.norm(e)
            s2, off2 = best_offset(X @ e, w, half)
            if s2 > s: s, d, off = s2, e, off2
    return d, c0 + d * off, s
