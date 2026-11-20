# Neuroscope

An educational site about neuroplasticity. It reports what the studies measured, including the
null results, and has interactive models of the spike, dendritic spines and time cells. It is not
medical or veterinary advice.

**Live site: <https://aiku0212.github.io/neuro-site/>**

## Pages

The published site is twelve static pages: `index` (Evidence), `app` (Explore and Analyze),
`spike`, `synapse` (Spines), `pharma`, `comparative`, `timecells`, `references` (Sources),
`about`, and the Learn section: `learn` (the hub), `conditioning` and `news`. Shared styles
are in `assets/atlas.css`, and `assets/nav.js` keeps the current tab in view on narrow screens. The favicon (`assets/favicon.svg`) and
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

## News page

`news.html` lists new neuroscience items from the last four weeks as headlines only: each
entry is a headline, its source, a kind label, a date and a link to the original. Nothing is
summarized. The sources are:

- PubMed: new review articles in Nature Reviews Neuroscience, Annual Review of Neuroscience,
  Trends in Neurosciences, Neuron and Current Opinion in Neurobiology, linked to their PubMed
  records ("Review article").
- eLife neuroscience RSS ("Research paper (eLife reviewed preprint)").
- MIT News neuroscience RSS ("University news office").

`.github/workflows/weekly-news.yml` runs every Monday at 08:43 UTC (and by hand). It runs the
offline tests, then `scripts/fetch_news.py`, which writes `data/news.json` and the list between
the `<!--news:start-->` and `<!--news:end-->` markers in `news.html`, and commits only those two
files. It does not deploy: the daily workflow publishes them on its next run. The list keeps
at most 5 items per source per week and 40 in all. A source that fails keeps its previous items
and is marked as failed on the page. If every source fails, or the result does not pass
validation, the script exits non-zero and changes nothing, and the workflow opens or comments
on a "News update failed" issue. The tests in `tests/test_news.py` use fixture feeds in
`tests/fixtures/news/` and never touch the network.

## Run it

```bash
python3 -m http.server 8000        # then open http://localhost:8000
python3 -m unittest discover -s tests
python3 scripts/build_refs.py      # rebuild references.html after editing the data file
python3 scripts/fetch_news.py      # refresh the News page (about four requests)
```

## License

The code is under the [MIT License](LICENSE). The text and original figures are under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Cited papers belong to their
publishers. The three.js library and the fonts keep their own licenses.

### Third-party material

- **three.js r160** (MIT). The Pharmacology receptor card uses four files copied from the
  npm package `three@0.160.0` into `assets/vendor/three-r160/`, with its license. The tests
  pin their hashes. The Spines page still loads three.js r160 from cdnjs.
- **Protein structure 9AS8** from the Protein Data Bank, which releases its data to the
  public domain (CC0). The structure is from Gumpper et al., *Nature Communications* 2025.
- **Blender 5.2.4 and Molecular Nodes 520.2.0** were used to turn the structure into the
  image and 3D model. `tools/blender/` holds the script and the steps to rebuild them.
