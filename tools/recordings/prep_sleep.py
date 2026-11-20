"""Make the data for the Sleep page from one Sleep-EDF Expanded night (PhysioNet, ODC-By 1.0).

    python3 tools/recordings/prep_sleep.py <folder with SC4001E0-PSG.edf and SC4001EC-Hypnogram.edf> assets/recordings

Writes sleep.json (hypnogram, one 30 s example per stage, spectrogram scale) and sleep-spectrogram.png.
"""
import json, os, struct, sys, zlib
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from readers import read_edf, read_edf_annotations, bandpass, welch

src, out = sys.argv[1], sys.argv[2]
psg = read_edf(os.path.join(src, "SC4001E0-PSG.edf"))
hyp = read_edf_annotations(os.path.join(src, "SC4001EC-Hypnogram.edf"))
head = open(os.path.join(src, "SC4001E0-PSG.edf"), "rb").read(256)
h0, m0, s0 = (int(v) for v in head[176:184].decode().split("."))
FS = 100; EP = 30

# one stage per 30 s epoch, Rechtschaffen & Kales labels as scored
CODE = {"Sleep stage W": "W", "Sleep stage 1": "1", "Sleep stage 2": "2", "Sleep stage 3": "3",
        "Sleep stage 4": "4", "Sleep stage R": "R", "Sleep stage ?": "?", "Movement time": "M"}
n_ep = int(len(psg["EEG Fpz-Cz"][0]) / FS / EP)
stage = ["?"] * n_ep
for onset, dur, text in hyp:
    for k in range(int(onset // EP), min(n_ep, int((onset + dur) // EP))):
        stage[k] = CODE.get(text, "?")
asleep = [k for k, s in enumerate(stage) if s in "1234R"]
first, last = asleep[0], asleep[-1]
a, b = first - 60, last + 61                     # 30 minutes either side of sleep
stages = "".join(stage[a:b])

eeg = {c: bandpass(psg[c][0], FS, 0.3, 35, 0.3, 6) for c in ("EEG Fpz-Cz", "EEG Pz-Oz", "EOG horizontal")}

def runs_middle(code, minlen=3):
    """Epoch indices in the middle of runs of at least minlen epochs of this stage."""
    out, k = [], a
    while k < b:
        if stage[k] == code:
            j = k
            while j < b and stage[j] == code: j += 1
            if j - k >= minlen: out += list(range(k + 1, j - 1))
            k = j
        else: k += 1
    return out

def band(x, lo, hi):
    f, p = welch(x, FS, 400); m = (f >= lo) & (f <= hi); return float(p[m].sum() * (f[1] - f[0]))

def seg(c, k): return eeg[c][k * EP * FS:(k + 1) * EP * FS]

# A clear example of each stage, chosen by the feature that defines it, from inside a stable run.
pick = {
    "W": max([k for k in runs_middle("W", 5) if k < first], key=lambda k: band(seg("EEG Pz-Oz", k), 8, 12) / (band(seg("EEG Pz-Oz", k), 1, 30) + 1e-9)),
    "1": max(runs_middle("1", 2) or [k for k in range(a, b) if stage[k] == "1"], key=lambda k: band(seg("EEG Fpz-Cz", k), 4, 8) / (band(seg("EEG Fpz-Cz", k), 1, 30) + 1e-9)),
    "2": max(runs_middle("2", 5), key=lambda k: band(seg("EEG Fpz-Cz", k), 11, 16) / (band(seg("EEG Fpz-Cz", k), 1, 30) + 1e-9)),
    "4": max(runs_middle("4", 4), key=lambda k: band(seg("EEG Fpz-Cz", k), 0.5, 2)),
    "R": max(runs_middle("R", 5), key=lambda k: float(np.std(seg("EOG horizontal", k)))),
}
examples = {}
for code, k in pick.items():
    examples[code] = {"epoch": k - a, "clock": "%02d:%02d" % divmod((h0 * 3600 + m0 * 60 + s0 + k * EP) // 60 % 1440, 60),
                      "traces": {c.replace("EEG ", "").replace("EOG horizontal", "EOG"): [int(round(v)) for v in seg(c, k)]
                                 for c in ("EEG Fpz-Cz", "EEG Pz-Oz", "EOG horizontal")}}

# Spectrogram of Fpz-Cz: one column per epoch, 0.5-25 Hz, log power, as an image.
F_LO, F_HI = 0.5, 25
cols = []
for k in range(a, b):
    f, p = welch(eeg["EEG Fpz-Cz"][k * EP * FS:(k + 1) * EP * FS], FS, 400)
    m = (f >= F_LO) & (f <= F_HI); cols.append(np.log10(p[m] + 1e-6))
S = np.array(cols).T[::-1]                      # rows: high frequency at the top
lo, hi = np.percentile(S, 2), np.percentile(S, 99.5)
v = np.clip((S - lo) / (hi - lo), 0, 1)
stops = np.array([[15, 26, 23], [38, 58, 92], [106, 84, 166], [214, 128, 92], [246, 226, 160]], float)
pos = v * (len(stops) - 1); i = np.minimum(pos.astype(int), len(stops) - 2); t = (pos - i)[..., None]
rgb = (stops[i] * (1 - t) + stops[i + 1] * t).round().astype(np.uint8)
def png(arr, path):
    hgt, w = arr.shape[:2]; raw = b"".join(b"\0" + arr[y].tobytes() for y in range(hgt))
    c = lambda tag, d: struct.pack(">I", len(d)) + tag + d + struct.pack(">I", zlib.crc32(tag + d))
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + c(b"IHDR", struct.pack(">IIBBBBB", w, hgt, 8, 2, 0, 0, 0)) + c(b"IDAT", zlib.compress(raw, 9)) + c(b"IEND", b""))
os.makedirs(out, exist_ok=True)
png(rgb, os.path.join(out, "sleep-spectrogram.png"))

start_clock = (h0 * 3600 + m0 * 60 + s0 + a * EP)
counts = {s: stages.count(s) for s in "W1234R?M"}
data = {"record": "SC4001", "epoch_s": EP, "fs": FS, "start_clock_s": start_clock % 86400,
        "stages": stages, "counts": counts,
        "spectrogram": {"f_lo": F_LO, "f_hi": F_HI, "channel": "Fpz-Cz", "rows": int(S.shape[0]), "cols": int(S.shape[1]),
                        "method": "Welch, 4 s Hann windows, half overlap, per 30 s epoch; log power, 2nd-99.5th percentile"},
        "filter": "0.3-35 Hz band-pass, zero phase", "examples": examples}
open(os.path.join(out, "sleep.json"), "w").write(json.dumps(data, separators=(",", ":")) + "\n")
print("epochs", len(stages), "from", "%02d:%02d" % divmod(start_clock // 60 % 1440, 60), counts)
print({k: (v["clock"], v["epoch"]) for k, v in examples.items()})
for n in ("sleep.json", "sleep-spectrogram.png"): print(n, os.path.getsize(os.path.join(out, n)))
