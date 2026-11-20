# Neuroscope claim check

Claims were checked on 2026-11-06 against each paper's abstract, and against the full text where noted. Unchecked items are listed at the end.

## Corrected

| Page | The site said | The source says | Basis |
|---|---|---|---|
| Evidence | "Exercise, high intensity," SMD 0.56 | SMD 0.56 is all exercise training in older adults, measuring resting BDNF | Gholami 2024 abstract |
| Evidence | One intervention "survived", and the rest are null, coin flips or uncontrolled | Yoga and meditation tend upward in limited evidence, and two diet reviews report increases with fasting | You 2020, Mohamadinarab 2026, Ashtary-Larky 2026 abstracts |
| Evidence | "Only physical exertion survives pooling", while meditation and fasting fail it | Those reviews were narrative and did not pool results, so they cannot fail pooling | You 2020, Alkurd 2024 abstracts |
| Evidence | "Intensity is everything" | One crossover study of 12 young men, plus subgroup results | Birinci 2026 full text |
| Evidence | Psychedelic null is explained because blood is the wrong compartment | The authors give two explanations, including that animal findings may not translate | Calder 2024 full text |
| Evidence | "Signature of a literature built on noise" | The authors report smaller effects in better-controlled studies, not this conclusion | Calder 2024 abstract |
| Evidence | Exercise timing rules out BDNF because levels are "back to baseline by then" | The inference does not hold, because the exercise itself happened at 4 hours. Only two timings were tested, so "optimal" was also unsupported | van Dongen 2016 abstract |
| Evidence | "Ten percent more synapses," no species given | Spine size and density in mice | Shao 2021 abstract |
| Evidence | Val66Met result in "200 patients" | Retrospective study of stroke patients | Lin 2026 abstract |
| Evidence | Fluoxetine binds "the same TrkB site" | "Distinct but partially overlapping sites" | Moliner 2023 abstract |
| Evidence | The "mechanistic reason" for slow SSRI response | "May explain" | Casarotto 2021 abstract |
| Evidence | Psilocybin state combined TrkB and 5-HT2A routes as settled | Moliner reports independence from 5-HT2A, but Vargas and Shao 2025 find it necessary | All three abstracts |
| Evidence | "Every figure links to a peer-reviewed source" | The cards had no links | Page inspection |
| Comparative | Human gabapentin pain 16.67% | 5.82% | Live openFDA query, 2026-11-06 |
| Comparative | "Roughly a quarter" of reports are internal states | 21.4% list at least one of the six terms. The old figure added overlapping percentages | Live openFDA query |
| Comparative | Lethargy "is" a compression artifact, "measured, not argued" | The percentages are measured, but this reading is a hypothesis | VetSignal README |
| Comparative | 6.17&times; "canine lethargy vs human," human 2.71% | The 2.71% is SOMNOLENCE, relabeled by VetSignal's synonym map. Human LETHARGY is 0.59%. Either term is 3.21%, which gives 5.22&times; | Live openFDA query, 2026-11-06 |
| Comparative | "6 / 40 terms map across" | 13 of the top 40 dog terms have a human match once all human terms are searched | VetSignal `crossspecies.py`, 2026-11-07 |
| Comparative | Report and cohort totals | Updated to current openFDA totals | Live openFDA query |
| Sources | Null tags on You, Cahn, Alkurd and Ashtary-Larky | Their results are mixed or weak, not null | Abstracts |
| Sources | Meta-analysis label on five narrative or systematic reviews | No pooled effect is reported in their abstracts | Abstracts |
| Sources | Casarotto, Hodgkin & Huxley, Harris & Stevens, Holtmaat & Svoboda, Zheng missing | Added with DOIs | Crossref |

## Matched the source

Calder (29 studies, SMD 0.024, p = 0.64), Moliner (1,000-fold), Shao 2021 (about 10%, 24 hours, one month), Siegel (threefold, weeks), Woo and Yang (proBDNF), Takesian & Hensch (active brakes), Cornez (species gradient), Birinci (15-minute peak, baseline by 60, low and moderate not different), Alkurd (5/5/6), You (15 studies, 5 uncontrolled), Polyakova (serum recovery in responders), Fluoxetine FDA approval for canine separation anxiety (DailyMed label).

## Still open

- The ketamine details on disinhibition, mTOR and "arrives in a day" cite an opinion article whose abstract does not state them. They were reworded as "one leading model," but they still need a primary source.
- The depression claim of "spine loss in prefrontal cortex" is not in Polyakova 2015 and needs its own source.
- The exercise claim that "most serum BDNF comes from platelets" has no source on the page.
- On the Pharmacology page, the stimulant, opioid, benzodiazepine and cannabinoid mechanisms still lack primary citations.
- On the Comparative page, the bridge sections are unverified. They include "dogs age roughly seven times faster," which is a known oversimplification. The register figures (69k, 63k, 112k, 17 synonyms, 6 of ~40 terms) have not been rechecked.
- The following have not been checked at all: the Spike page claims outside the passages listed under the 2026-11-18 pass, the Time Cells page's sentences, the spine dimensions on the Spines page, and the Comparative indications table beyond fluoxetine. The Time Cells page's nine references now have DOIs and are on the Sources page, but its sentences have not been compared with them.
- Most papers were compared by abstract only. Closed-access papers, including van Dongen, Woo and Takesian & Hensch, were not read in full.
- The corrections to Shao 2025, Schosser 2022 and Holtmaat & Svoboda 2009 have not been read.
- Cahn 2017 has two correction notices, read on 2026-11-18. A 2022 corrigendum (doi 10.3389/fnhum.2022.868021) corrects the funding statement, which now says a co-author paid the experimental costs by private donation. It also adds a conflict-of-interest statement not disclosed before. That statement says the same co-author organized data collection and analyzed results, and that the senior author is Scientific Director of the Chopra Foundation. In the corrigendum, the authors say this does not change the scientific conclusions. A 2023 erratum (doi 10.3389/fnhum.2023.1278043) amends that statement again on the editorial office's advice and corrects two authors' affiliations, adding the Chopra Foundation for the senior author. Both notices were read in full on PubMed Central.

## For the author to decide

- Whether to keep the headline "The brain pays to stop learning". Sources support active closure, but not an energy cost.
- Whether the findings on the Evidence page are placed on the right brain regions. For example, a serum BDNF study is placed on the cerebellum.
- Whether to publish the open problem register on the Comparative page. It reads as an internal research plan.

## Second pass, 2026-11-07

Primary sources were added for every claim listed as open above, each confirmed against Crossref.

| Claim | Change | Source |
|---|---|---|
| Ketamine disinhibition, mTOR, "arrives in a day" | Now labeled a leading model from rat studies, with a competing mechanism. Onset is about two hours in a small trial | Homayoun & Moghaddam 2007; Li et al. 2010; Zanos et al. 2016; Zarate et al. 2006 |
| "Measurable spine loss" in depression | Human postmortem evidence shows synapse loss. The spine loss evidence is from rats | Kang et al. 2012 |
| "Most serum BDNF comes from platelets" | Reworded to say that platelets store and release BDNF, so serum is not a direct brain measure | Fujimura et al. 2002 |
| "Dogs age roughly seven times faster" | Removed, because the relationship is non-linear | Wang et al. 2020 |
| Stimulant, opioid, benzodiazepine, cannabinoid mechanisms | Primary citations replace "textbook consensus" | Ritz 1987; Sulzer 2005; Johnson & North 1992; Study & Barker 1981; Wilson & Nicoll 2001 |
| Spike page: 13.5 µA/cm² "buys 38 mV" | The model gives about 36 mV, and the threshold is about 13.3 | Rerun of the page's own equations |
| "The signature of a literature built on noise" | Removed from the blood BDNF card (not the authors' conclusion) | Calder et al. 2024 |
| Findings placed on unrelated brain regions | Only five findings are now placed on the brain. Blood, receptor, molecule and cell-type findings are not | Page redesign |
| Headline "pays to stop learning" | Now "works to stop learning". Closure is active, but no source supports an energy cost | Takesian & Hensch 2013 |

Several items are still open. The spine dimensions need Harris & Stevens 1989 in full text (the journal page was not accessible). The nine Time page references are listed but not checked against the model text. The Pharmacology page describes mechanisms but not adverse effects. Most papers were compared by abstract only.

## Pharmacology pass, 2026-11-17

Each drug class now lists three or four harms and limits. Every bullet was drafted from a source the drafter opened (FDA labels and safety communications, CDC, NIDA, DEA, or a peer-reviewed paper), checked a second time in a separate AI-assisted pass, and read in a final AI-assisted pass for doses, use tips and US-only advice. No pharmacist or physician has reviewed them. Harm sources are linked under each list, and the 13 that have DOIs are also on the Sources page.

| Class | Corrected | Source |
|---|---|---|
| Opioids, cannabinoids | Receptor type "G₁₀-coupled" is Gi/o-coupled | UniProt P35372; Lovinger 2008 |
| Psychedelics | Steps merged two competing models into one chain. They are now presented as two models, both from cell and animal work | Vargas et al. 2023; Moliner et al. 2023 |
| Psychedelics | "Persists for weeks" is "still present a month later, in mouse frontal cortex" | Shao et al. 2021 |
| Dissociatives | The disinhibition study used MK-801, not ketamine. The trial sentence now gives n = 18 and the one-week response rate | Homayoun & Moghaddam 2007; Zarate et al. 2006 |
| Dissociatives | Schedule label now covers PCP (II) and DXM (not controlled) | eCFR 21 CFR 1308 |
| Stimulants | Noradrenaline rises as well as dopamine | Faraone 2018 |
| Opioids | "Rather than exciting them" contradicted the cited paper. Opioids excite dopamine neurons by disinhibition. Breathing suppression added | Johnson & North 1992; Jalabert et al. 2011; Baldo & Rose 2022 |
| Benzodiazepines | "Has a ceiling" read as a safety assurance and was replaced with the combination risk. "Alone it does nothing" was an overstatement | FDA boxed warning; Campo-Soria et al. 2006; Löscher & Rogawski 2012 |
| Cannabinoids | The schedule label now reflects the DEA rule of Apr 28, 2026, which moved FDA-approved and state-licensed medical marijuana to Schedule III | Federal Register 2026-08176 |
| Cannabinoids | "Partial agonist" applies to THC only. Synthetic cannabinoids are full agonists. THC skips the retrograde step | Tai & Fantegrossi 2017 |

One item is still open on this page. Psilocybin may be rescheduled if FDA approves a psilocybin product in 2027, so recheck the label then.

## Claim pass, 2026-11-18

Each change below was drafted in one AI-assisted pass from the source or the page's own model, then checked in a second, separate AI-assisted pass that tried to refute it. Two further AI-assisted passes then reread the whole change. No outside expert has reviewed these changes. Model figures come from running the page's own code. Citation counts and correction notices were checked on Crossref. Sixteen sources were added to the Sources page.

| Page | Corrected | Source |
|---|---|---|
| Spike | The second identical pulse fires from a 15 ms gap, not about 17 ms. The block is relative, since an 80 uA/cm² pulse fires at an 11 ms gap. Potassium activation, not only the h gate, delays recovery | The page's model; Hodgkin & Huxley 1952 |
| Spike | The undershoot is not the refractory period, which starts during the spike | The page's model; Hodgkin & Huxley 1952 |
| Spike | The model has no pump. The resting potential is where the currents balance | Hodgkin & Huxley 1952 |
| Spike | At 17 C the threshold rises (about 13.3 to 15.3 uA/cm²). This is not heat block, and the uncited history claim was removed. Real squid axons show reversible heat block at 35 to 40 C | The page's model; Hodgkin & Katz 1949 |
| Spike | The threshold is given as about 13.3 everywhere. The voltage chart's label no longer mentions an afterhyperpolarization mark that the chart does not draw | The page's model |
| Explore | The figures of 86 billion neurons and 16 billion in the cerebral cortex are now cited. The uncited "thousands of synapses" clause was removed | Azevedo et al. 2009 |
| Explore | Single-neuron caption cited Yang 2014, a proBDNF paper. It now cites rat CA1 input counts | Megías et al. 2001 |
| Explore | TrkB binding now says "in cell and mouse studies" | Moliner et al. 2023 |
| Explore | The membrane level showed four drug-related receptors (TrkB, p75NTR, 5-HT2A, NMDA). It now shows the three glutamate receptors of a spine synapse (AMPA, NMDA, mGluR), which replaces the TrkB line above. Checked from the two reviews' abstracts and standard textbook facts, not by an expert | Traynelis et al. 2010; Niswender & Conn 2010 |
| Explore | Perineuronal-net line toned down to what the source shows | Lensjø et al. 2017 |
| Pharmacology | New receptor card for psilocin and 5-HT2A. Method, resolution, chains, the ligand and the modelled residues (79 to 393, with 264 to 312 and 350 to 353 missing) were read from the PDB entry and its coordinate file. The membrane position is an estimate from UniProt's membrane-spanning segments. The caption has not been checked by a structural biologist | PDB 9AS8; Gumpper et al. 2025; UniProt P28223 |
| Pharmacology | Receptor cards added for the other five classes. For each one, the method, resolution, chains, bound molecules and modelled residues were read from the PDB entry and its coordinate file, and the binding-site statements were checked against the paper's abstract. Which subunits each diazepam, GABA and ketamine molecule touches was computed from the coordinates. Full-length protein sizes are UniProt's. The membrane position is an estimate from the protein's own water-avoiding residues. No structural biologist has checked the captions | PDB 7EU7, 9EO4, 8EF6, 6X3X, 8GHV; Zhang 2021; Nielsen 2024; Zhuang 2022; Kim 2020; Krishna Kumar 2023 |
| Pharmacology | The cannabinoid card shows AMG315, a relative of anandamide, and says it is not THC. The claim that no peer-reviewed THC-bound CB1 structure exists rests on one search in November 2026 and should be rechecked | PDB 8GHV; Krishna Kumar 2023 |
| Spines | Species named (rat). "~10,000 spines per cortical cell" is 8,000 to 15,000 by cell type in rat visual cortex | Larkman 1991 |
| Spines | The "almost linear" AMPA claim was softened, "thin spines grow into mushroom spines" is "can grow toward", and "the learning spine" is described as a proposal | Matsuzaki et al. 2001, 2004; Bourne & Harris 2007 |
| Evidence | Schematic bars no longer print "100%". They say high, medium or low | The page's own values are hand-set |
| Evidence | The exercise finding now names "12 young men", and "back to baseline within the hour" is "no longer clearly above baseline by sixty minutes", in the card titles too | Birinci et al. |
| Comparative | Unsourced bridge cards are labelled "Unsourced hypothesis" | None listed |
| Comparative | "No held-out ground truth" rewritten and cited | Chiavaccini et al. 2024 |
| Comparative | "Synapse Bench" (an internal name) replaced with the visible section name | None listed |
| Comparative | Gabapentin figures recomputed on safety reports: 8,444 reports, lethargy 17.82%, 5.55× (supersedes the 5.22× and 13 of 40 above), 12 of 40 terms, pain 5.64%. Added that gabapentin is rarely the main product in these dog reports | Live openFDA queries, 2026-11-18 |
| About | Ketamine line and the Pharmacology pass brought up to date | None listed |
| Time | Internal project name removed from the footer | None listed |

Also in this pass, after a second read of the whole branch:

| Page | Corrected | Source |
|---|---|---|
| Spike | "Every spike is the same height" is "nearly the same height". The simulator note says spike size depends on the stimulus once the axon is warm | The page's model |
| Explore | The membrane card no longer chains Moliner and Vargas into one mechanism. It says the two groups disagree | Moliner et al. 2023; Vargas et al. 2023 |
| Evidence | The bench list no longer prints level words for hand-set values. Under ketamine, the blocked NMDA receptor is drawn dimmed, not brighter | The page's own values are hand-set |
| Evidence | The exercise title now says BDNF was already up right after exercise and peaked at fifteen minutes | Birinci et al. 2026 |

Several items are still open from this pass. On the Comparative page, gabapentin is listed alongside another drug in almost every dog report, so the comparison may need a different cohort (for example reports where gabapentin is the first drug listed). On the Spike page, the TTX and TEA notes were not checked. On the Spines page, "that neck is a resistor" overstates Harris & Stevens 1989. On the Evidence page, the directions the hand-set bench values imply (for example perineuronal nets under psilocybin and ketamine) have not been checked against sources. Hodgkin & Katz 1949 was read from the scanned pages on PubMed Central. Its summary states the 35 to 40 C heat block.

## Brain scans page (2026-11-20)

| Claim | Basis |
|---|---|
| The template averages the T1 scans of 152 adults, fitted in repeated rounds to the previous round's average | McGill BIC page for ICBM 2009 nonlinear atlases; Fonov et al. 2011 |
| Licence: use, copy, modify and distribute for any purpose, with the notice in all copies | `COPYING` inside `mni_icbm152_nlin_asym_09c_nifti.zip` (SHA-256 804382e5d68a42ff8096ee845a7600b6658434da762fa67840a149eb25d48bd4), copied to `assets/scans/COPYING-ICBM152` |
| White matter bright, grey matter mid-grey, fluid dark on T1 | Plewes & Kucharczyk 2012; measured on this file: median 234, 181 and 88 on the page's 0-255 scale |
| MRI magnet tens of thousands of times Earth's field; hydrogen nuclei align; radio pulse; relaxation differs by tissue; gradients encode position; no X-rays | Plewes & Kucharczyk 2012. A 1.5 to 3 tesla scanner against Earth's field of about 50 microtesla is a ratio of 30,000 to 60,000 |
| MNI zero is near the anterior commissure | Standard description of MNI space. Not checked on this file |
| Seven landmark coordinates | Each checked visually on three-plane crops of the processed file and by the tissue under it. A unit test checks the tissue |
| The cerebellum holds about four in five of the brain's neurons | Azevedo et al. 2009: about 69 of 86 billion |
| Template's age range | Not stated on the page because the McGill page read for this does not give it |

## Recordings page (2026-11-20)

| Claim | Basis |
|---|---|
| Both datasets are under the Open Data Commons Attribution License v1.0, with the citations shown | PhysioNet dataset pages for eegmmidb 1.0.0 and mitdb 1.0.0, read 2026-11-20 |
| Run 1 is eyes open and run 2 eyes closed | eegmmidb dataset description |
| Alpha power 14.3 times higher with eyes closed, peak 10.0 Hz | Computed by `tools/recordings/prep_recordings.py` for this one subject |
| Berger reported a rhythm of about ten per second in 1929 | Berger 1929 |
| Eyes-closed alpha is largest over the back of the head | Barry et al. 2007 abstract |
| EEG reflects summed synaptic currents of aligned pyramidal cells, not single spikes; poor at locating sources | Buzsáki et al. 2012 |
| Beat labels (N, V) | Cardiologist annotations in the MIT-BIH `.atr` files. The reader's counts match the database's published totals (record 100: 2239 N, 33 A, 1 V; record 119: 1543 N, 444 V) |
| P = atria depolarise, QRS = ventricles depolarise with atrial repolarisation hidden, T = ventricular repolarisation; AV node delay | Kligfield et al. 2007 |
| Premature ventricular complexes come early, lack a preceding P wave, are wide, are often followed by a pause, and are common and often benign | Marcus 2020 |
| Lead II lies roughly along the heart's main axis | Standard: lead II is at +60°, near the normal mean axis. MIT-BIH uses a modified lead II |
| Wave positions on the average beat (P −175, Q −25, R 0, S 22, T 356 ms) | Peak search in fixed windows on the average of 2,169 normal beats. Checked by eye on the plot |

## Sleep page (2026-11-20)

Every sentence in the stage notes and the evidence section came from a two-pass check. One researcher per topic drafted claims from abstracts they opened. An independent skeptic then re-fetched each source on Crossref and PubMed and kept, reworded or dropped each claim. The run's full output is not in the repository. Points worth knowing:

| Claim | Basis and caveat |
|---|---|
| N3 rule: slow waves of 0.5-2 Hz, >75 µV, over frontal leads, taking up 20% or more of an epoch | Corrected after the final review: the first wording ("more than 20%", no frequency band) was slightly off, and it cited the inter-scorer study, which does not define the rule. Now cited to Silber 2007 (the task force) and Berry 2017 (manual v2.4). Rests on the AASM manual, which is not open access. Moderate support |
| Spindles about 11-16 Hz, >0.5 s | Durka 2015, a methods paper quoting standard definitions, not the AASM manual. The page says "commonly defined" |
| "Deep sleep is concentrated early in the night" | Dropped as a general claim, because no opened abstract states it. The page gives this night's own numbers instead: 173 of 220 deep-sleep epochs in the first half, and REM 67 of 125 in the second half |
| Sleep benefit g = 0.44, bias-corrected 0.28 | Berres & Erdfelder 2021 abstract. The page says moderate, shrinking to small |
| Spindle-memory link, and its reanalysis | Kumral 2023 vs Ujma 2024. The Ujma commentary has no abstract and was checked from its OSF preprint abstract. Labelled contested |
| Closed-loop sound stimulation | Ngo 2013; Henin 2019 (failed double-blind repeat, n = 19); Wunderlin 2021 (g = 0.25, p = 0.07); Harlow 2023 (benefit falls with publication year). Labelled "did not hold up reliably" |
| TMR g = 0.29; NREM yes, REM and wake no | Hu 2020 abstract. Null studies are cited alongside |
| REM-memory debate | Siegel 2001, Rasch 2009, Goerke 2014 (mixed), Boyce 2016 (mice, pro-REM). Labelled contested |
| Sleep loss before learning: medium effect, after learning smaller, publication bias | Newbury 2021; Crowley 2024 for restriction |
| Sleep-EDF volunteers: home recordings 1987-1991, healthy, no sleep medication, all described as white | PhysioNet sleep-edfx page |
| Age of this volunteer | Not stated, because the subject table could not be downloaded |
| Final review fixes | Merger criticism dated to Grigg-Damberger 2012, not "still". Fpz-Cz described as forehead-to-crown, compared with the standard C4-A1 lead. Staresina 2015 hippocampal recordings described as coming from people with epilepsy |
