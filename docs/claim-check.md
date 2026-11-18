# Neuroscope claim check

Checked 2026-11-06 against each paper's abstract, and full text where noted. Unchecked items are listed at the end.

## Corrected

| Page | The site said | The source says | Basis |
|---|---|---|---|
| Evidence | "Exercise, high intensity," SMD 0.56 | SMD 0.56 is all exercise training in older adults, measuring resting BDNF | Gholami 2024 abstract |
| Evidence | One intervention "survived"; the rest are null, coin flips or uncontrolled | Yoga and meditation tend upward in limited evidence; two diet reviews report increases with fasting | You 2020, Mohamadinarab 2026, Ashtary-Larky 2026 abstracts |
| Evidence | "Only physical exertion survives pooling"; meditation and fasting fail it | Those reviews were narrative and did not pool results, so they cannot fail pooling | You 2020, Alkurd 2024 abstracts |
| Evidence | "Intensity is everything" | One crossover study of 12 young men, plus subgroup results | Birinci 2026 full text |
| Evidence | Psychedelic null is explained because blood is the wrong compartment | The authors give two explanations, including that animal findings may not translate | Calder 2024 full text |
| Evidence | "Signature of a literature built on noise" | The authors report smaller effects in better-controlled studies, not this conclusion | Calder 2024 abstract |
| Evidence | Exercise timing rules out BDNF because levels are "back to baseline by then" | The inference does not hold: the exercise itself happened at 4 hours. Only two timings were tested, so "optimal" was also unsupported | van Dongen 2016 abstract |
| Evidence | "Ten percent more synapses," no species given | Spine size and density in mice | Shao 2021 abstract |
| Evidence | Val66Met result in "200 patients" | Retrospective study of stroke patients | Lin 2026 abstract |
| Evidence | Fluoxetine binds "the same TrkB site" | "Distinct but partially overlapping sites" | Moliner 2023 abstract |
| Evidence | The "mechanistic reason" for slow SSRI response | "May explain" | Casarotto 2021 abstract |
| Evidence | Psilocybin state combined TrkB and 5-HT2A routes as settled | Moliner reports independence from 5-HT2A; Vargas and Shao 2025 find it necessary | All three abstracts |
| Evidence | "Every figure links to a peer-reviewed source" | The cards had no links | Page inspection |
| Comparative | Human gabapentin pain 16.67% | 5.82% | Live openFDA query, 2026-11-06 |
| Comparative | "Roughly a quarter" of reports are internal states | 21.4% list at least one of the six terms. The old figure added overlapping percentages | Live openFDA query |
| Comparative | Lethargy "is" a compression artifact, "measured, not argued" | The percentages are measured; this reading is a hypothesis | VetSignal README |
| Comparative | 6.17&times; "canine lethargy vs human," human 2.71% | The 2.71% is SOMNOLENCE, relabeled by VetSignal's synonym map. Human LETHARGY is 0.59%; either term is 3.21%, which gives 5.22&times; | Live openFDA query, 2026-11-06 |
| Comparative | "6 / 40 terms map across" | 13 of the top 40 dog terms have a human match once all human terms are searched | VetSignal `crossspecies.py`, 2026-11-07 |
| Comparative | Report and cohort totals | Updated to current openFDA totals | Live openFDA query |
| Sources | Null tags on You, Cahn, Alkurd and Ashtary-Larky | Their results are mixed or weak, not null | Abstracts |
| Sources | Meta-analysis label on five narrative or systematic reviews | No pooled effect is reported in their abstracts | Abstracts |
| Sources | Casarotto, Hodgkin & Huxley, Harris & Stevens, Holtmaat & Svoboda, Zheng missing | Added with DOIs | Crossref |

## Matched the source

Calder (29 studies, SMD 0.024, p = 0.64), Moliner (1,000-fold), Shao 2021 (about 10%, 24 hours, one month), Siegel (threefold, weeks), Woo and Yang (proBDNF), Takesian & Hensch (active brakes), Cornez (species gradient), Birinci (15-minute peak, baseline by 60, low and moderate not different), Alkurd (5/5/6), You (15 studies, 5 uncontrolled), Polyakova (serum recovery in responders), Fluoxetine FDA approval for canine separation anxiety (DailyMed label).

## Still open

- **Ketamine:** the disinhibition, mTOR and "arrives in a day" details cite an opinion article whose abstract does not state them. Reworded as "one leading model," but it still needs a primary source.
- **Depression:** "spine loss in prefrontal cortex" is not in Polyakova 2015 and needs its own source.
- **Exercise:** "most serum BDNF comes from platelets" has no source on the page.
- **Pharmacology page:** stimulant, opioid, benzodiazepine and cannabinoid mechanisms still lack primary citations.
- **Comparative, unverified:** the bridge sections, including "dogs age roughly seven times faster," which is a known oversimplification. Register figures (69k, 63k, 112k, 17 synonyms, 6 of ~40 terms) have not been rechecked.
- **Not checked at all:** Spike and Time Cells page claims, the nine references listed on the Time Cells page, spine dimensions on the Spines page, and the Comparative indications table beyond fluoxetine.
- **Abstract only:** most papers were compared by abstract. Closed-access papers, including van Dongen, Woo and Takesian & Hensch, were not read in full.
- **Corrections not read:** Shao 2025, Schosser 2022 and Holtmaat & Svoboda 2009.

## For the author to decide

- The headline "The brain pays to stop learning": sources support active closure, but not an energy cost.
- "Every supervised model of an animal internal state" has "no held-out ground truth" (Comparative): this is an uncited generalization.
- Brain-region placement on the Evidence page: for example, a serum BDNF study sits on the cerebellum.
- Whether to publish the open problem register on the Comparative page. It reads as an internal research plan.

## Second pass, 2026-11-07

Primary sources were added for every claim listed as open above, each confirmed against Crossref.

| Claim | Change | Source |
|---|---|---|
| Ketamine disinhibition, mTOR, "arrives in a day" | Now labeled a leading model from rat studies, with a competing mechanism; onset about two hours in a small trial | Homayoun & Moghaddam 2007; Li et al. 2010; Zanos et al. 2016; Zarate et al. 2006 |
| "Measurable spine loss" in depression | Human postmortem evidence is synapse loss; spine loss is from rats | Kang et al. 2012 |
| "Most serum BDNF comes from platelets" | Reworded: platelets store and release BDNF, so serum is not a direct brain measure | Fujimura et al. 2002 |
| "Dogs age roughly seven times faster" | Removed; the relationship is non-linear | Wang et al. 2020 |
| Stimulant, opioid, benzodiazepine, cannabinoid mechanisms | Primary citations replace "textbook consensus" | Ritz 1987; Sulzer 2005; Johnson & North 1992; Study & Barker 1981; Wilson & Nicoll 2001 |
| Spike page: 13.5 µA/cm² "buys 38 mV" | The model gives about 36 mV; threshold about 13.3 | Rerun of the page's own equations |
| "The signature of a literature built on noise" | Removed from the blood BDNF card (not the authors' conclusion) | Calder et al. 2024 |
| Findings placed on unrelated brain regions | Only five findings are now placed on the brain; blood, receptor, molecule and cell-type findings are not | Page redesign |
| Headline "pays to stop learning" | Now "works to stop learning": closure is active, but no source supports an energy cost | Takesian & Hensch 2013 |

Still open: spine dimensions need Harris & Stevens 1989 in full text (the journal page was not accessible); the nine Time page references are listed but not checked against the model text; the Pharmacology page describes mechanisms but not adverse effects; most papers were compared by abstract only.

## Pharmacology pass, 2026-11-17

Each drug class now lists three or four harms and limits. Every bullet was drafted from a source the drafter opened (FDA labels and safety communications, CDC, NIDA, DEA, or a peer-reviewed paper), checked a second time by an independent reviewer, and read by a final reviewer for doses, use tips and US-only advice. Harm sources are linked under each list; the 13 that have DOIs are also on the Sources page.

| Class | Corrected | Source |
|---|---|---|
| Opioids, cannabinoids | Receptor type "G₁₀-coupled" is Gi/o-coupled | UniProt P35372; Lovinger 2008 |
| Psychedelics | Steps merged two competing models into one chain; now presented as two models, both from cell and animal work | Vargas et al. 2023; Moliner et al. 2023 |
| Psychedelics | "Persists for weeks" is "still present a month later, in mouse frontal cortex" | Shao et al. 2021 |
| Dissociatives | The disinhibition study used MK-801, not ketamine; the trial sentence now gives n = 18 and the one-week response rate | Homayoun & Moghaddam 2007; Zarate et al. 2006 |
| Dissociatives | Schedule label now covers PCP (II) and DXM (not controlled) | eCFR 21 CFR 1308 |
| Stimulants | Noradrenaline rises as well as dopamine | Faraone 2018 |
| Opioids | "Rather than exciting them" contradicted the cited paper; opioids excite dopamine neurons by disinhibition. Breathing suppression added | Johnson & North 1992; Jalabert et al. 2011; Baldo & Rose 2022 |
| Benzodiazepines | "Has a ceiling" read as a safety assurance; replaced with the combination risk. "Alone it does nothing" overstated | FDA boxed warning; Campo-Soria et al. 2006; Löscher & Rogawski 2012 |
| Cannabinoids | Schedule label: DEA rule of Apr 28, 2026 moved FDA-approved and state-licensed medical marijuana to Schedule III | Federal Register 2026-08176 |
| Cannabinoids | "Partial agonist" applies to THC only; synthetics are full agonists. THC skips the retrograde step | Tai & Fantegrossi 2017 |

Still open on this page: psilocybin may be rescheduled if FDA approves a psilocybin product in 2027; recheck the label then.
