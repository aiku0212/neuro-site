# Expansion plan: real data and methods

Internal plan. This file lives in `docs/` and is not published with the site.

Five additions, in build order:

1. **Brain scans**: a real MRI you can slice in three directions and turn in 3D.
2. **Recordings**: real EEG and ECG traces you can read.
3. **Sleep and memory**: a real night of sleep, stage by stage.
4. **Methods**: how brain tissue is cut, stained, mounted and imaged.
5. **Receptor callouts**: guided stops on the 3D receptor cards.

Each one ships on its own branch and pull request and goes live only on an explicit yes.

---

## 1. Rules every addition follows

These come from how the site already works. They apply to all five.

**Accuracy before polish.** Every figure says what it is with a `fig-kind` chip:
- *Measured* is a real recording or scan.
- *Simulation* is computed by a model.
- *Drawing* is made by hand.

Real data always says where it came from, how it was processed, and what it cannot show. The tests check for each chip.

**Data licences are checked before any download.** Each dataset's licence and required credit go into the page, the README in `tools/`, and `docs/claim-check.md`. A dataset whose terms are unclear is left out until the owner says yes in writing. BigBrain is one example.

**No outside requests while reading.** All code and data are on the site itself. Any library is vendored at an exact version and checked against the npm integrity hash. Its SHA-384 is pinned in the tests, the same way three.js is now.

**Processing happens before upload.** Raw data (NIfTI scans, EDF recordings, microscope TIFFs) is converted by scripts in `tools/` into small web files. The scripts are committed so anyone can rerun them and get the same files. Each page loads one to three megabytes at most, and only when the reader reaches that figure.

**Motion is calm and purposeful.** The site keeps its current look: smooth, minimal motion with no neon or glow. Every animation:
- pauses when off screen or when the tab is hidden;
- respects reduced-motion settings;
- has Back, Play/Pause and Next controls wherever it tells a story in steps.

GSAP is not used. Easing is written by hand, as on the Pharmacology page.

**It works on phones.** Every figure is checked at 375 px wide. Touch must not trap page scrolling: figures use `touch-action: pan-y`, or start interacting only after a tap.

**Not medical advice.** Scans and recordings are educational. No page explains how to diagnose anything from a scan or trace. Abnormal ECG rhythms are shown as textbook examples with their expert labels, and never as a self-check.

---

## 2. Software choices

| Need | Choice | Why | Rejected |
|---|---|---|---|
| MRI slices and 3D | **NiiVue 0.69.0** (BSD-2-Clause), vendored as its self-contained UMD build (2.3 MB, 0.79 MB compressed), loaded only on the Scans page | Built for brain imaging: reads NIfTI directly, keeps left and right correct, draws three-plane slices and 3D volume rendering, handles touch. Used by research tools, so the orientation handling has been tested by people who care about it. | A custom three.js volume shader: lighter but slower to build, and orientation bugs are easy to make and hard to spot. Pre-cut PNG slices: no 3D and no smooth scrolling. |
| Signal traces (EEG, ECG) | **Canvas 2D drawn by hand**, as on the Time and Conditioning pages | Traces are short (10–60 s), so a custom drawer is small, matches the site exactly, and can animate a sweeping cursor like a real monitor. | uPlot (MIT, 50 KB) is a good fallback if zooming long recordings gets complex. |
| Signal processing | **MNE-Python** (BSD-3) and **SciPy**, run offline in `tools/` | Standard tools for reading EDF files, filtering and power spectra. The results ship as small JSON files. | Processing in the browser: slower, and harder to check. |
| Microscope images | **OpenSeadragon 6.1.1** (BSD-3-Clause) with deep-zoom tiles | Smooth pinch and zoom on very large images, tiles load only where the reader looks. | Plain `<img>`: a full-resolution slide is too heavy for a phone. |
| Method animations | **Blender 5.2** renders (already set up), exported as short AV1/H.264 clips with poster frames, plus step scenes in SVG/Canvas | Blender gives physically lit, realistic tools and tissue. Short clips play smoothly everywhere. SVG steps stay sharp and readable. | Live three.js scenes for every method: heavy on phones for little gain. |
| 3D callouts | **Existing receptor viewer** (three.js r160) with hand-written camera moves | No new code to vendor. | Any animation library. |

---

## 3. Brain scans (building now)

**Data: MNI ICBM152 2009c nonlinear asymmetric template**, from McGill.
- It is the average of 152 adult T1 MRI scans, aligned to one another. It is the standard reference brain in brain imaging.
- **Licence:** use, copy, change and distribute for any purpose, provided the copyright notice appears in all copies. The notice ships as `assets/scans/COPYING-ICBM152` and is quoted on the page.
- **Download:** `mni_icbm152_nlin_asym_09c_nifti.zip`, 57.6 MB, SHA-256 `804382e5…48bd4`.

**Processing** (`tools/scans/prep_icbm.py`):
- removes the skull with the template's own brain mask;
- crops to the brain;
- rescales to 0–255;
- makes a tissue map (grey matter, white matter, fluid) from the template's probability maps, wherever one tissue's probability is at least 0.5.

The output is 1.7 MB plus 0.2 MB.

**Page: `scans.html`**, a Learn topic.
- **Viewer.** Three planes (side, front, top) plus a 3D view. Buttons switch between all planes, a single large plane, and 3D. Clicking or dragging moves a crosshair, and the readout shows the position in millimetres and the tissue under it.
- **Tissue colours toggle.** Paints grey matter, white matter and fluid, so the reader learns to read T1 contrast.
- **Guided landmarks.** Step buttons move the crosshair to structures that are easy to recognise: corpus callosum, lateral ventricles, thalamus, hippocampus, cerebellum, brainstem. Each has a one-line caption. Every coordinate was checked against the image before it was written.
- **Text sections.**
  - What a T1 scan shows.
  - How MRI makes the picture: magnetic field, radio pulse, relaxation, gradients for position.
  - Why an average brain looks smoother than any one person's.
  - Limits: an average blurs fine folds, the mask is approximate, and this is not a diagnostic image.
- **References:** Fonov et al. 2011 (*NeuroImage*) and Fonov et al. 2009 (*NeuroImage* abstract) for the template, and Mazziotta et al. 2001 for the ICBM project.

**Later on this page:**
- a "Real people differ" panel with two or three individual scans from OpenNeuro (CC0, faces already removed);
- a 3D cortical surface mesh made in Blender from the tissue map, for a cleaner 3D view than volume rendering.

---

## 4. Recordings: EEG and ECG

**Data (PhysioNet, Open Data Commons Attribution 1.0, credit required):**
- *EEG Motor Movement/Imagery Dataset* (Schalk 2009, doi 10.13026/C28G6P). Runs 1 and 2 are one minute with eyes open and one minute with eyes closed, from the same person.
- *MIT-BIH Arrhythmia Database* (Moody and Mark 2005, doi 10.13026/C2F305). ECG with about 110,000 beats labelled by cardiologists.

**Processing:**
- MNE-Python reads the EDF files.
- A 1–40 Hz band-pass filter, with the filter written on the page.
- One subject's O1/O2 channels (over the visual cortex), cut to 20 s clips.
- A power spectrum for each eye condition.
- For ECG: lead MLII, 10 s windows, with the expert beat labels kept.

The JSON files are about 100 KB each.

**Page: `recordings.html`**, a Learn topic with two sections.
- **EEG: the alpha rhythm.**
  - A sweeping trace like a monitor.
  - An eyes open / eyes closed switch on the same person.
  - A spectrum that grows a peak near 10 Hz when the eyes close.
  - Steps: what an electrode picks up (summed activity of many cortical neurons, not single spikes), why closing the eyes changes it, and what EEG cannot locate well.
- **ECG: reading a heartbeat.**
  - Click a beat to label the P wave, QRS complex and T wave, and what each one means electrically.
  - A comparison strip of a few expert-labelled abnormal beats, labelled as examples and not as a self-check.
  - Links to the Spike page: the same ion currents, in heart muscle.
- **Motion:** the sweep cursor runs at real speed (25 mm/s style) with a pause button. Reduced motion shows a still trace.

---

## 5. Sleep and memory

**Data:** *Sleep-EDF Database Expanded* (PhysioNet, ODC-By 1.0, doi 10.13026/C2X676). Whole-night recordings with sleep stages scored by experts.

**Processing:** for one night:
- the hypnogram (stage every 30 s);
- example 30 s EEG windows for wake, N1, N2 (with spindles and K-complexes marked), N3 (slow waves) and REM;
- a spectrogram of the whole night, made in SciPy and saved as one image.

**Page: `sleep.html`**, a Learn topic.
- A night-long hypnogram you can scrub, with the matching EEG window shown live.
- A spectrogram strip under the hypnogram.
- Text on how the stages are defined.
- What the evidence says about sleep and memory consolidation: reviews only, with mixed results marked as on the Evidence page.
- Links to Recordings (EEG basics) and Time (memory).

**Evidence work first:** a literature pass for the memory claims (spindle–memory links, targeted memory reactivation), with null results logged in `docs/claim-check.md`.

---

## 6. Methods: tissue to image

**Scope.** Concepts and reasoning only:
- what each method shows;
- how it works in principle;
- what it cannot show;
- what goes wrong.

No step-by-step protocols, chemical amounts or safety procedures, which belong in a lab manual under supervision. Circuit-control methods (optogenetics, chemogenetics) are out of scope.

**Pages:** one hub, `methods.html`, with one short page per method:

| Tutorial | Shows | Visual |
|---|---|---|
| Fixing and slicing | Why tissue is fixed; vibratome vs cryostat vs microtome; section thickness and what it allows | Blender clip of a blade cutting a block into sections that float off; Back/Play/Next steps |
| Nissl stain | Cell bodies; cortical layers | Real image, deep zoom (Cell Image Library or similar, licence per image) |
| Golgi stain | Whole single neurons, chosen at random | Real image (CIL:40260, CC BY, Ellisman and Larson) plus a 3D trace that rotates |
| Immunohistochemistry and immunofluorescence | Finding one protein with antibodies | Step scene: antibody binds, second antibody carries the label; then a real multi-channel image |
| Mounting and imaging | Floating sections onto slides; light vs confocal microscopy | Blender clip; a confocal z-stack you can step through |

Links to the section-mounter project only if the user wants that public.

**Image sourcing:** every image's licence is checked one by one and recorded with its ID. Allen Institute images are used only after their full Terms of Use have been read. If a commercial-use limit or an unclear term remains, it is asked about first.

---

## 7. Receptor callouts

On each of the six cards:
- a "Tour" button moves the camera to three or four stops (receptor in the membrane, binding pocket, bound drug, signalling partner);
- a caption at each stop, with labels that fade in at each step;
- camera moves eased by hand over 900 ms (instant with reduced motion);
- the reader can still drag at any time, which ends the tour.

Stops are chosen from the coordinate files, and every residue named is checked in the deposited structure.

---

## 8. Quality gates for each pull request

1. Unit tests pass, with new tests for each page: data files exist and are small enough, licences are present, pinned hashes match, fig-kind chips are present, no outside scripts.
2. Headless Chrome screenshots at 1280 px and 375 px, plus a real-browser click-through of every control with no console errors.
3. `docs/claim-check.md` has a row for every factual claim, with its source.
4. Every reference is added to `data/references.json`, so the Sources page lists it.
5. The deploy workflow's page list and `PUBLIC` in the tests both include the new page.
6. The live site matches main after deploy, checked file by file with SHA-256 checksums.

## 9. Open decisions for the owner

- BigBrain needs written permission for an educational site. Should we ask?
- Should the Methods section link to the section-mounter project?
- Should there be a top-menu tab for these pages, or should they stay under Learn? The current plan is Learn, to keep the menu short.
