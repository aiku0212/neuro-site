# Neuroscope

An educational site about neuroplasticity: what the studies measured, including the null
results, with interactive models of the spike, dendritic spines and time cells. It is not
medical or veterinary advice.

## Pages

The published site is nine static pages: `index` (Evidence), `app` (Explore and Analyze),
`spike`, `synapse` (Spines), `pharma`, `comparative`, `timecells`, `references` (Sources)
and `about`. Shared styles are in `assets/atlas.css`. `explore.html` and `morphometry.html`
are older versions kept in the repository but not published.

## Sources and checks

- `data/references.json` holds every reference, with DOIs confirmed against Crossref.
- `docs/claim-check.md` records each claim that was checked against its source, and what changed.
- `.github/workflows/daily-citations.yml` refreshes citation counts and correction notices daily,
  queues new papers in an issue for review, and publishes the site. Approving a paper puts it on
  `data/reading_list.json` and asks for a check of the page it bears on; it becomes a source only
  when a page claim cites it. New papers and notices get an issue comment, notices stay in the
  issue until dismissed, and nothing is published if a step fails or too many lookups fail.
  `data/status.json` records each run and the date by which every reference was last checked.
  An item counts as announced only once its comment is posted, so a failed run announces it
  again rather than never. The workflow cannot notice a schedule that never starts: run
  `python3 scripts/check_freshness.py` (or `CHECK_HEARTBEAT=1` with the tests) to check that
  the last run is recent, or watch it from outside.

## Run it

```bash
python3 -m http.server 8000        # then open http://localhost:8000
python3 -m unittest discover -s tests
python3 scripts/build_refs.py      # rebuild references.html after editing the data file
```

## License

Code: [MIT](LICENSE). Text and original figures: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Cited papers belong to their publishers; three.js and the fonts keep their own licenses.
