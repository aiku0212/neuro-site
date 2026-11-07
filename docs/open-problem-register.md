# Open problem register

Moved from the Comparative page on 2026-11-07, because it reads as an internal research plan.
Nothing here is closed; status describes how far the groundwork has gone.

The report counts (69k, 63k, 112k) have not been rechecked against current openFDA data. The vocabulary match was updated to 13 of the top 40 dog terms on 2026-11-07.

| # | Problem | Notes | Status |
|---|---|---|---|
| 01 | VeDDRA ↔ MedDRA crosswalk | No public mapping exists between the veterinary and human adverse-event vocabularies. Lexical normalization plus 17 hand-written synonyms currently matches 13 of the top 40 dog terms. Ontology alignment; embeddings are suited to it; the vet-only-drug negative control already exists in code. | Wedge |
| 02 | Non-verbal ground truth | Inferring internal states in a patient that cannot self-report. Underlies pain scales, welfare scoring, and every behavioural label in pet psychiatry. The hardest of these and the one with the widest reach. | Thesis |
| 03 | Anthelmintic resistance as a reporting signal | 69k lack-of-efficacy reports for heartworm larvae, 63k for flea preventives. Testable claim: failure reports cluster geographically and trend in time. Needs a reporting-effort control analogous to the German Shepherd comparison. | Open |
| 04 | Bayesian shrinkage for small cells | EBGM/MGPS in place of raw PRR. Prerequisite for anything sliced by region × year × breed, where cells fall to double digits. Retroactively strengthens the MDR1 result. | Open |
| 05 | Breed entity resolution | Owner-typed free text in an inverted taxonomy. 112k mixed-breed reports are currently invisible to any breed-stratified analysis. | Open |
| 06 | Dose- and weight-adjusted exposure | The database carries dose numerator, unit, and animal weight. Breaks the count-only query model, so it needs new machinery before it needs new statistics. | Deferred |
| 07 | Veterinary clinical NLP | Vet records are unstructured with no consistently applied coding standard. Far behind human clinical NLP. Largest gap on this list; also the one most dependent on data access. | Scope |
| 08 | Comparative neuropsychiatry | The Comparative page. Critical-period closure, compulsive disorder, and cognitive decline as three phenotypes where canine and human neuroscience are measuring the same mechanism through different instruments. | New |
