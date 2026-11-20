# Open problem register

This register was moved from the Comparative page on 2026-11-07 because it reads as an internal research plan.
Nothing here is closed. The status column describes how far the groundwork has gone.

The report counts (69k, 63k, 112k) have not been rechecked against current openFDA data. The vocabulary match was updated to 13 of the top 40 dog terms on 2026-11-07, and to 12 of 40 on 2026-11-18, when the dog figures moved to safety reports only.

| # | Problem | Notes | Status |
|---|---|---|---|
| 01 | VeDDRA ↔ MedDRA crosswalk | No public mapping exists between the veterinary and human adverse-event vocabularies. Lexical normalization plus 17 hand-written synonyms currently matches 12 of the top 40 dog terms (safety reports). This is an ontology alignment problem, and embeddings are suited to it. The vet-only-drug negative control already exists in code. | Wedge |
| 02 | Non-verbal ground truth | The problem is inferring internal states in a patient that cannot self-report. It underlies pain scales, welfare scoring, and every behavioural label in pet psychiatry. It is the hardest problem on this list and the one with the widest reach. | Thesis |
| 03 | Anthelmintic resistance as a reporting signal | There are 69k lack-of-efficacy reports for heartworm larvae and 63k for flea preventives. The testable claim is that failure reports cluster geographically and show a trend over time. This needs a reporting-effort control analogous to the German Shepherd comparison. | Open |
| 04 | Bayesian shrinkage for small cells | Use the empirical Bayes geometric mean (EBGM) from the multi-item gamma Poisson shrinker (MGPS) in place of the raw proportional reporting ratio (PRR). This is a prerequisite for any analysis broken down by region × year × breed, where cell counts fall to double digits. It also retroactively strengthens the MDR1 result. | Open |
| 05 | Breed entity resolution | Breed is owner-typed free text in an inverted taxonomy. The 112k mixed-breed reports are currently left out of any breed-stratified analysis. | Open |
| 06 | Dose- and weight-adjusted exposure | The database contains dose numerator, unit, and animal weight. Using them breaks the count-only query model, so this needs new tooling before it needs new statistics. | Deferred |
| 07 | Veterinary clinical NLP | Vet records are unstructured, with no consistently applied coding standard. The field is far behind natural language processing (NLP) for human clinical text. This is the largest gap on this list and also the one most dependent on data access. | Scope |
| 08 | Comparative neuropsychiatry | This is the subject of the Comparative page. It treats critical-period closure, compulsive disorder, and cognitive decline as three phenotypes where canine and human neuroscience measure the same mechanism with different instruments. | New |
