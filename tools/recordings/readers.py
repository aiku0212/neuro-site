"""Small readers for the two PhysioNet formats the Recordings page uses. numpy only."""
import numpy as np

def read_edf(path):
    """European Data Format. Returns {label: (samples in physical units, rate, unit)}."""
    b = open(path, 'rb').read()
    n_rec = int(b[236:244]); dur = float(b[244:252]); ns = int(b[252:256])
    h = b[256:256 + ns * 256]
    def field(off, width):
        start = off * ns
        return [h[start + i * width:start + (i + 1) * width].decode('ascii').strip() for i in range(ns)]
    labels = field(0, 16); units = field(16 + 80, 8)
    pmin = [float(x) for x in field(16 + 80 + 8, 8)]; pmax = [float(x) for x in field(16 + 80 + 16, 8)]
    dmin = [float(x) for x in field(16 + 80 + 24, 8)]; dmax = [float(x) for x in field(16 + 80 + 32, 8)]
    nsamp = [int(x) for x in field(16 + 80 + 40 + 80, 8)]
    raw = np.frombuffer(b, '<i2', offset=256 + ns * 256)
    per_rec = sum(nsamp)
    raw = raw[:n_rec * per_rec].reshape(n_rec, per_rec)
    out, pos = {}, 0
    for i, lab in enumerate(labels):
        d = raw[:, pos:pos + nsamp[i]].reshape(-1).astype(float); pos += nsamp[i]
        gain = (pmax[i] - pmin[i]) / (dmax[i] - dmin[i])
        out[lab.strip('.')] = ((d - dmin[i]) * gain + pmin[i], nsamp[i] / dur, units[i])
    return out

def read_wfdb_212(record):
    """MIT-BIH signal file in format 212 (two 12-bit samples in three bytes).
    Returns (signals in mV with shape (n, channels), rate, channel names)."""
    hea = [l for l in open(record + '.hea').read().splitlines() if l and not l.startswith('#')]
    name, nch, fs, n = hea[0].split()[:4]; nch, fs, n = int(nch), float(fs), int(n)
    gains, zeros, names = [], [], []
    for line in hea[1:1 + nch]:
        p = line.split(); gains.append(float(p[2])); zeros.append(int(p[4])); names.append(p[8])
    b = np.frombuffer(open(record + '.dat', 'rb').read(), np.uint8).astype(np.int32)
    b = b[:len(b) // 3 * 3].reshape(-1, 3)
    s0 = b[:, 0] | ((b[:, 1] & 0x0F) << 8)
    s1 = b[:, 2] | ((b[:, 1] & 0xF0) << 4)
    s = np.stack([s0, s1], 1)
    s[s > 2047] -= 4096
    s = s[:n, :nch].astype(float)
    return (s - np.array(zeros)) / np.array(gains), fs, names

CODES = {1: 'N', 2: 'L', 3: 'R', 4: 'a', 5: 'V', 6: 'F', 7: 'J', 8: 'A', 9: 'S', 10: 'E', 11: 'j',
         12: '/', 13: 'Q', 14: '~', 16: '|', 18: 's', 19: 'T', 22: '"', 25: 'B', 27: '!', 28: '+',
         31: 'e', 32: 'n', 34: 'f', 38: 'x', 41: '[', 42: ']'}

def read_atr(record):
    """MIT-format annotation file. Returns a list of (sample, symbol, aux text)."""
    w = np.frombuffer(open(record + '.atr', 'rb').read(), '<u2')
    out, t, i = [], 0, 0
    while i < len(w):
        code, val = w[i] >> 10, w[i] & 0x3FF
        if code == 0 and val == 0: break
        if code == 59:                      # SKIP: a 32-bit interval follows, high word first
            t += (int(w[i + 1]) << 16) | int(w[i + 2]); i += 3; continue
        if code == 63:                      # AUX: text for the previous annotation
            n = int(val); text = w[i + 1:i + 1 + (n + 1) // 2].tobytes()[:n].decode('ascii', 'replace')
            if out: out[-1] = (out[-1][0], out[-1][1], text.strip('\x00'))
            i += 1 + (n + 1) // 2; continue
        if code in (60, 61, 62): i += 1; continue   # NUM, SUB, CHN: not used here
        t += int(val); out.append((t, CODES.get(int(code), '?%d' % code), '')); i += 1
    return out

def bandpass(x, fs, lo, hi, lo_w=0.5, hi_w=10.0):
    """Zero-phase band-pass: FFT mask with raised-cosine edges centred on lo and hi.
    The wide upper edge (hi_w Hz) avoids the ringing a sharp cutoff adds after fast waves. Mean removed first."""
    x = np.asarray(x, float) - np.mean(x); n = len(x)
    f = np.fft.rfftfreq(n, 1 / fs); X = np.fft.rfft(x)
    up = np.clip((f - (lo - lo_w / 2)) / lo_w, 0, 1); down = np.clip(((hi + hi_w / 2) - f) / hi_w, 0, 1)
    m = (0.5 - 0.5 * np.cos(np.pi * up)) * (0.5 - 0.5 * np.cos(np.pi * down))
    return np.fft.irfft(X * m, n)

def welch(x, fs, seg):
    """Power spectrum by Welch's method: Hann windows of seg samples, half overlap."""
    x = np.asarray(x, float) - np.mean(x); w = np.hanning(seg); step = seg // 2
    parts = [x[i:i + seg] * w for i in range(0, len(x) - seg + 1, step)]
    p = np.mean([np.abs(np.fft.rfft(s)) ** 2 for s in parts], 0) / (fs * (w ** 2).sum())
    p[1:-1] *= 2
    return np.fft.rfftfreq(seg, 1 / fs), p
