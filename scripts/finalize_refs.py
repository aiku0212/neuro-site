#!/usr/bin/env python3
"""Fetch each DOI's official Crossref record and confirm it against the site's citation.

DOI_OVERRIDES are matches identified by reading the lookup output, where the only
mismatch was a shortened title on the site (or a preprint outranking the journal
version). Each is still rechecked here against journal and first author; a failed
check marks the reference needs_review rather than accepting it.
"""
import html
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_dois import first_author, get_json, norm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "references.json"

# (first author token, title prefix) -> DOI
DOI_OVERRIDES = {
    ("calder", "Effects of psychoplastogens"): "10.1038/s41380-024-02830-z",
    ("fernandes", "Peripheral"): "10.1186/s12916-015-0529-7",
    ("thakkar", "BDNF as a biomarker"): "10.1002/brb3.2903",
    ("shao", "Psilocybin induces"): "10.1016/j.neuron.2021.06.008",
    ("zhang", "Psychedelics and the extracellular"): "10.1016/j.biopsych.2026.02.011",
    ("cisneros-franco", "Critical periods"): "10.1016/b978-0-444-64150-2.00009-5",
    ("cornez", "Perineuronal"): "10.1002/dneu.22485",
    ("london", "Developmental song"): "10.1016/j.beproc.2017.11.008",
    ("hayase", "Seasonal"): "10.1186/s13041-021-00869-5",
    ("gholami", "Exercise training"): "10.1016/j.exger.2024.112658",
    ("ruiz-gonzález", "Effects of physical"): "10.1016/j.neubiorev.2021.05.025",
    ("shobeiri", "Exercise-induced"): "10.1371/journal.pone.0264557",
    ("birinci", "Time-dependent"): "10.1038/s41598-026-37728-z",
    ("mackay", "Aerobic"): "10.1080/10749357.2026.2628540",
    ("van dongen", "Physical exercise"): "10.1016/j.cub.2016.04.071",
    ("makepeace", "Higher intensity"): "10.1371/journal.pone.0308373",
    ("you", "Effects of meditation"): "10.1016/j.smhs.2020.03.001",
    ("cahn", "Increased BDNF"): "10.3389/fnhum.2017.00315",
    ("alkurd", "Effect of calorie"): "10.3390/medicina60010191",
    ("mohamadinarab", "The effect of dietary"): "10.1186/s40795-025-01174-3",
    ("ashtary-larky", "Effects of dietary"): "10.1093/nutrit/nuaf308",
    ("lin", "BDNF Val66Met"): "10.1007/s10072-026-08948-y",
    ("parchure", "BDNF gene polymorphism predicts"): "10.1111/ner.13495",
}


def override_for(ref):
    author = re.split(r"\s+et al|,|&", ref["authors"])[0].strip().lower()
    for (who, prefix), doi in DOI_OVERRIDES.items():
        if author == who and ref.get("site_title", ref["title"]).startswith(prefix):
            return doi
    return None


def journal_ok(site, official):
    a, b = norm(site).replace(" and ", " "), norm(official).replace(" and ", " ")
    return bool(a and b and (a in b or b in a))


def clean(text):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or ""))).strip()


def pubmed_first_author(doi):
    """Crossref omits authors on some book chapters, so fall back to PubMed by DOI."""
    q = urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "term": f"{doi}[AID]"})
    ids = (get_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{q}") or {}).get("esearchresult", {}).get("idlist", [])
    if not ids:
        return None
    time.sleep(0.4)
    q = urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "id": ids[0]})
    rec = (get_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?{q}") or {}).get("result", {}).get(ids[0], {})
    authors = rec.get("authors") or []
    return authors[0].get("name") if authors else None


def main():
    refs = json.loads(DATA.read_text(encoding="utf8"))
    today = time.strftime("%Y-%m-%d")
    for i, ref in enumerate(refs, 1):
        ref.setdefault("site_title", ref["title"])
        ref.setdefault("site_year", ref["year"])
        if "citations" in ref and "citations_at_compile" not in ref:
            ref["citations_at_compile"] = ref["citations"]
        doi = override_for(ref) or ref.get("doi")
        problems = []
        msg = (get_json("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")) or {}).get("message") if doi else None
        if not msg:
            problems.append(f"no Crossref record for {doi}")
        else:
            journal = clean((msg.get("container-title") or [""])[0])
            family = [clean(a.get("family") or a.get("name") or "") for a in msg.get("author", [])]
            parts = (msg.get("issued", {}).get("date-parts") or [[None]])[0]
            year = parts[0] if parts else None
            if not journal_ok(ref["journal"], journal):
                problems.append(f'journal "{ref["journal"]}" vs "{journal}"')
            wanted = set(norm(first_author(ref["authors"])).split())
            if family and not wanted & set(norm(family[0]).split()):
                problems.append(f'first author "{ref["authors"]}" vs "{family[0]}"')
            if not family:
                pm_author = pubmed_first_author(doi)
                if not pm_author or not wanted & set(norm(pm_author).split()):
                    problems.append(f"Crossref lists no author; PubMed gave {pm_author}")
            if year is None or abs(year - ref["site_year"]) > 2:
                problems.append(f'year {ref["site_year"]} vs {year}')
            if msg.get("type") == "posted-content":
                problems.append("DOI is a preprint")
            if not problems:
                ref["doi"] = doi
                ref["title"] = clean((msg.get("title") or [ref["title"]])[0])
                # Crossref's year can be online-first or print, so the cited year stays as written.
                ref["year"] = ref["site_year"]
                ref["crossref_year"] = year
                ref["citations"] = msg.get("is-referenced-by-count")
                ref["citations_checked"] = today

            time.sleep(0.4)
            q = urllib.parse.urlencode({"filter": f"updates:{doi}", "select": "DOI,type,update-to,title", "rows": 10})
            notices = (get_json(f"https://api.crossref.org/works?{q}") or {}).get("message", {}).get("items", [])
            updates = []
            for n in notices:
                for u in n.get("update-to", []):
                    if (u.get("DOI") or "").lower() == doi.lower():
                        updates.append({"type": u.get("type"), "notice_doi": n.get("DOI")})
            ref["updates"] = updates

        ref["verification"]["status"] = "confirmed" if not problems else "needs_review"
        ref["verification"]["reasons"] = problems
        ref["verification"]["checked"] = today
        flag = " UPDATES:" + json.dumps(ref.get("updates")) if ref.get("updates") else ""
        print(f'{i:2d} {ref["verification"]["status"]:12s} {ref.get("doi","-"):38s} {ref["site_year"]}->{ref["year"]} c={ref.get("citations_at_compile")}->{ref.get("citations")} {"; ".join(problems)}{flag}', flush=True)
        DATA.write_text(json.dumps(refs, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
        time.sleep(0.4)


if __name__ == "__main__":
    main()
