# Neuroscope

An educational site about neuroplasticity. It reports what the studies measured, including the
null results, and has interactive models of the spike, dendritic spines and time cells. It is not
medical or veterinary advice.

**Live site: <https://aiku0212.github.io/neuro-site/>**

## Pages

The published site is nine static pages: `index` (Evidence), `app` (Explore and Analyze),
`spike`, `synapse` (Spines), `pharma`, `comparative`, `timecells`, `references` (Sources)
and `about`. Shared styles are in `assets/atlas.css`. The favicon (`assets/favicon.svg`) and
the link-preview image (`assets/og.png`) are published with them. `explore.html` and `morphometry.html`
are older versions kept in the repository but not published.

## Sources and checks

- `data/references.json` holds every reference, with DOIs confirmed against Crossref.
- `docs/claim-check.md` records each claim that was checked against its source, and what changed.
- `.github/workflows/daily-citations.yml` refreshes citation counts and correction notices daily,
  queues new papers in an issue for review, and publishes the site. Approving a paper adds it to
  `data/reading_list.json` and asks for a check of the page it relates to. It becomes a source only
  when a page claim cites it. New papers and notices get an issue comment. Notices stay in the
  issue until someone dismisses them, and nothing is published if a step fails or too many lookups fail.
  `data/status.json` records each run and the date by which every reference was last checked.
  An item counts as announced only once its comment is posted, so if a run fails, a later run
  tries to announce the item again instead of dropping it. The workflow cannot detect a schedule
  that never starts. To check that the last run is recent, run `python3 scripts/check_freshness.py`
  (or run the tests with `CHECK_HEARTBEAT=1`), or monitor the schedule from outside the workflow.

## Run it

```bash
python3 -m http.server 8000        # then open http://localhost:8000
python3 -m unittest discover -s tests
python3 scripts/build_refs.py      # rebuild references.html after editing the data file
```

## License

The code is under the [MIT License](LICENSE). The text and original figures are under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Cited papers belong to their
publishers. The three.js library and the fonts keep their own licenses.
