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
  queues new papers in an issue for review, and publishes the site. Papers are added only when a
  maintainer ticks them, and nothing is published if any check fails.

## Run it

```bash
python3 -m http.server 8000        # then open http://localhost:8000
python3 -m unittest discover -s tests
python3 scripts/build_refs.py      # rebuild references.html after editing the data file
```

## License

Code: [MIT](LICENSE). Text and original figures: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Cited papers belong to their publishers; three.js and the fonts keep their own licenses.
