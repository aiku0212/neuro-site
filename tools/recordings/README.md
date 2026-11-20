# Recording data

`prep_recordings.py` makes `assets/recordings/recordings.json` for the Recordings page.
`readers.py` holds small numpy readers for EDF and for MIT-BIH format 212 signals and annotations.

Inputs, from PhysioNet (Open Data Commons Attribution License v1.0), checked against PhysioNet's SHA256SUMS:

| File | SHA-256 |
|---|---|
| eegmmidb/1.0.0/S001/S001R01.edf | 4743b736131a7e147c150e8b37711029b6cda5e356c4b3e8261a03cdcaaf8b0c |
| eegmmidb/1.0.0/S001/S001R02.edf | 31a95e0a880e6c3d89960d9d62c144f24cc4e9f5d7e93c7f864ef61cd49e847e |
| mitdb/1.0.0/100.hea, .dat, .atr | 60ebc904…, b2ea3c25…, 8d8a5349… |
| mitdb/1.0.0/119.hea, .dat, .atr | 658f0138…, 02a286a2…, fd919c8e… |

Run with any Python that has numpy:

    python3 tools/recordings/prep_recordings.py <folder with the files> assets/recordings

The annotation reader's beat counts match the database's published totals, which is the check that it reads
the format correctly.

## Sleep page

`prep_sleep.py` makes `assets/recordings/sleep.json` and `sleep-spectrogram.png` from one night of the
Sleep-EDF Database Expanded (PhysioNet, Open Data Commons Attribution License v1.0, doi 10.13026/C2X676),
recording SC4001, scored by experts with the Rechtschaffen & Kales rules.

| File | SHA-256 |
|---|---|
| sleep-edfx/1.0.0/sleep-cassette/SC4001E0-PSG.edf | 2b40a18adf76af69a42d6db1f30f31d26b369f6d27ca0050ef30147ef892b131 |
| sleep-edfx/1.0.0/sleep-cassette/SC4001EC-Hypnogram.edf | a4cf67694ade1b52a0ddd06d5817fd45d2d3e8bac5302f640f3e9cfbbf12a996 |

It keeps 30 minutes either side of sleep, and picks one clear 30 s example per stage from inside a run of
that stage, by the feature that defines it: alpha at the back of the head (awake, before sleep), theta (stage 1),
spindle-band power (stage 2), slow-wave power (stage 4) and eye-movement size (REM).

    python3 tools/recordings/prep_sleep.py <folder with the two files> assets/recordings
