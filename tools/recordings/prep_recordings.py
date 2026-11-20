"""Make the data file for the Recordings page from PhysioNet downloads.

    python3 tools/recordings/prep_recordings.py <folder with S001R01.edf, S001R02.edf, 100.*, 119.*> assets/recordings

EEG: EEG Motor Movement/Imagery Dataset, subject 1, run 1 (eyes open) and run 2 (eyes closed).
ECG: MIT-BIH Arrhythmia Database, records 100 and 119, lead MLII.
Both are under the Open Data Commons Attribution License v1.0.
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from readers import read_edf, read_wfdb_212, read_atr, bandpass, welch

src, out = sys.argv[1], sys.argv[2]
P = lambda n: os.path.join(src, n)
data = {}

# ---- EEG: 20 s of channel Oz from each run, and the spectrum of O1, Oz and O2 over the whole run
T0, T1 = 10, 30
eeg = {}
for key, run in (("open", "S001R01"), ("closed", "S001R02")):
    e = read_edf(P(run + ".edf")); fs = e["Oz"][1]
    trace = bandpass(e["Oz"][0], fs, 1, 40)[int(T0 * fs):int(T1 * fs)]
    occ = np.mean([bandpass(e[c][0], fs, 1, 40) for c in ("O1", "Oz", "O2")], 0)
    f, p = welch(occ, fs, int(2 * fs))
    keep = (f >= 1) & (f <= 30)
    alpha = p[(f >= 8) & (f <= 12)].sum() * (f[1] - f[0])
    eeg[key] = {"trace": [round(float(v), 1) for v in trace], "psd": [round(float(v), 3) for v in p[keep]],
                "alpha_power": round(float(alpha), 1),
                "peak_hz": float(f[(f >= 6) & (f <= 14)][np.argmax(p[(f >= 6) & (f <= 14)])])}
    eeg["fs"] = fs; eeg["freqs"] = [float(v) for v in f[keep]]
eeg["ratio"] = round(eeg["closed"]["alpha_power"] / eeg["open"]["alpha_power"], 1)
eeg.update(unit="µV", channel="Oz", start_s=T0, filter="1-40 Hz band-pass, zero phase, upper edge tapered over 35-45 Hz",
           spectrum="Welch, 2 s Hann windows, half overlap, mean of O1, Oz and O2, whole 61 s run")
data["eeg"] = eeg

# ---- ECG
def clip(record, start_s, secs=10):
    s, fs, names = read_wfdb_212(P(record)); a = read_atr(P(record))
    x = bandpass(s[:, names.index("MLII")], fs, 0.5, 40)
    i0, i1 = int(start_s * fs), int((start_s + secs) * fs)
    beats = [[int(t - i0), sym] for t, sym, _ in a if i0 <= t < i1 and sym in "NVALRAaJSEFj/Q"]
    return {"fs": fs, "start_s": start_s, "trace": [round(float(v), 3) for v in x[i0:i1]], "beats": beats}, x, a, fs

def first_window(a, fs, ok, secs=10):
    """Start time (s) of the first 10 s window, after 60 s, whose beats all pass ok(symbols)."""
    beats = [(t, sym) for t, sym, _ in a if sym not in "+~|\"x![]"]
    for t, _ in beats:
        if t < 60 * fs: continue
        syms = [b for u, b in beats if t - 0.2 * fs <= u < t - 0.2 * fs + secs * fs]
        if ok(syms): return round((t - 0.2 * fs) / fs, 2)

s100, fs = read_wfdb_212(P("100"))[0:2]
a100 = read_atr(P("100"))
start = first_window(a100, fs, lambda b: len(b) >= 10 and set(b) == {"N"})
normal, x100, _, fs = clip("100", start)
s119 = read_atr(P("119"))
start119 = first_window(s119, fs, lambda b: b.count("V") >= 4 and set(b) <= {"N", "V"} and "VV" not in "".join(b))
pvc, _, _, _ = clip("119", start119)

# average normal beat from record 100, aligned on each labelled beat's largest point within 50 ms
pre, post = int(0.30 * fs), int(0.50 * fs)
syms = [(t, sym) for t, sym, _ in a100 if sym in "NVA"]
segs = []
for k in range(1, len(syms) - 1):
    t, sym = syms[k]
    if sym != "N" or syms[k - 1][1] != "N" or syms[k + 1][1] != "N": continue
    w = int(0.05 * fs); r = t - w + int(np.argmax(x100[t - w:t + w]))
    if r - pre < 0 or r + post > len(x100): continue
    segs.append(x100[r - pre:r + post])
avg = np.mean(segs, 0); ms = (np.arange(len(avg)) - pre) / fs * 1000
def peak(lo, hi, sign):
    m = (ms >= lo) & (ms <= hi); i = np.where(m)[0][np.argmax(sign * avg[m])]
    return round(float(ms[i]), 1)
waves = {"P": peak(-250, -90, 1), "Q": peak(-60, -5, -1), "R": peak(-10, 10, 1), "S": peak(5, 70, -1), "T": peak(150, 420, 1)}
data["ecg"] = {"unit": "mV", "lead": "MLII", "filter": "0.5-40 Hz band-pass, zero phase, upper edge tapered over 35-45 Hz",
               "normal": dict(normal, record="100"), "pvc": dict(pvc, record="119"),
               "average": {"fs": fs, "pre_ms": 300, "beats": len(segs), "trace": [round(float(v), 4) for v in avg],
                           "waves_ms": waves}}

os.makedirs(out, exist_ok=True)
path = os.path.join(out, "recordings.json")
open(path, "w").write(json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n")
print(path, os.path.getsize(path), "bytes")
print("EEG alpha power open/closed:", eeg["open"]["alpha_power"], eeg["closed"]["alpha_power"], "ratio", eeg["ratio"],
      "peaks", eeg["open"]["peak_hz"], eeg["closed"]["peak_hz"])
print("ECG normal window", start, "s,", len(normal["beats"]), "beats; PVC window", start119, "s,",
      "".join(b[1] for b in pvc["beats"]), "; average of", len(segs), "beats, waves", waves)
