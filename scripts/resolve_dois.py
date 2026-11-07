#!/usr/bin/env python3
"""Look up each reference in Crossref and PubMed and record how well it matches.

A DOI is accepted only when the title, year and first author all agree. Anything
else is marked for human review; nothing is guessed. Existing metadata written by
hand (title, note, tag, etc.) is never overwritten.
"""
import difflib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "references.json"
UA = {"User-Agent": "neuroscope-citation-check/1.0"}
TITLE_MIN = 0.90


def get_json(url, tries=5):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return None
            if err.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == tries - 1:
                raise
            time.sleep(2 ** (attempt + 1))


def norm(text):
    text = unicodedata.normalize("NFKD", re.sub(r"<[^>]+>", " ", text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def title_score(a, b):
    return round(difflib.SequenceMatcher(None, norm(a), norm(b)).ratio(), 3)


def first_author(authors):
    head = re.split(r"\s+et al|,|&", authors)[0].strip()
    return norm(head)


def author_ok(ref, names):
    wanted = first_author(ref["authors"])
    wanted_tokens = set(wanted.split())
    return any(wanted_tokens & set(norm(n).split()) for n in names[:1]) if names else False


def crossref(ref):
    query = urllib.parse.urlencode({
        "query.bibliographic": ref["title"],
        "rows": 5,
        "select": "DOI,title,author,issued,container-title,type,is-referenced-by-count",
    })
    data = get_json(f"https://api.crossref.org/works?{query}")
    best = None
    for item in (data or {}).get("message", {}).get("items", []):
        title = (item.get("title") or [""])[0]
        parts = (item.get("issued", {}).get("date-parts") or [[None]])[0]
        cand = {
            "doi": (item.get("DOI") or "").lower(),
            "title": title,
            "year": parts[0] if parts else None,
            "journal": (item.get("container-title") or [""])[0],
            "first_author": [a.get("family", "") for a in item.get("author", [])],
            "type": item.get("type"),
            "citations": item.get("is-referenced-by-count"),
            "score": title_score(ref["title"], title),
        }
        if best is None or cand["score"] > best["score"]:
            best = cand
    return best


def pubmed(ref):
    term = urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "retmax": 5,
                                   "term": f'{ref["title"]}[Title]'})
    ids = (get_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{term}") or {})
    idlist = ids.get("esearchresult", {}).get("idlist", [])
    if not idlist:
        term = urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "retmax": 5,
                                       "term": ref["title"]})
        ids = get_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{term}") or {}
        idlist = ids.get("esearchresult", {}).get("idlist", [])
    if not idlist:
        return None
    time.sleep(0.4)
    q = urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "id": ",".join(idlist)})
    summ = (get_json(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?{q}") or {}).get("result", {})
    best = None
    for pmid in summ.get("uids", []):
        rec = summ[pmid]
        doi = next((x["value"].lower() for x in rec.get("articleids", []) if x.get("idtype") == "doi"), "")
        year = re.match(r"\d{4}", rec.get("pubdate", "") or "")
        cand = {
            "pmid": pmid,
            "doi": doi,
            "title": rec.get("title", ""),
            "year": int(year.group()) if year else None,
            "journal": rec.get("fulljournalname", ""),
            "first_author": [a.get("name", "") for a in rec.get("authors", [])],
            "pubtypes": rec.get("pubtype", []),
            "score": title_score(ref["title"], rec.get("title", "")),
        }
        if best is None or cand["score"] > best["score"]:
            best = cand
    return best


def strong(ref, cand):
    return bool(cand and cand["score"] >= TITLE_MIN and cand.get("doi")
                and cand["year"] is not None and abs(cand["year"] - ref["year"]) <= 1
                and author_ok(ref, cand["first_author"]))


def classify(ref, cr, pm):
    """Return (status, doi, reasons)."""
    cr_ok, pm_ok = strong(ref, cr), strong(ref, pm)
    if cr_ok and pm_ok:
        if cr["doi"] == pm["doi"]:
            return "verified_two_sources", cr["doi"], []
        return "conflict", None, [f'Crossref {cr["doi"]} vs PubMed {pm["doi"]}']
    if pm_ok:
        return "verified_one_source", pm["doi"], ["PubMed only"]
    if cr_ok:
        return "verified_one_source", cr["doi"], ["Crossref only"]
    reasons = []
    for name, cand in (("Crossref", cr), ("PubMed", pm)):
        if not cand:
            reasons.append(f"{name}: no candidate")
            continue
        reasons.append(f'{name}: score {cand["score"]}, year {cand["year"]}, '
                       f'author {(cand["first_author"] or ["?"])[0]}, doi {cand.get("doi") or "none"}, '
                       f'title "{cand["title"][:100]}"')
    return "needs_review", None, reasons


def main():
    refs = json.loads(DATA.read_text(encoding="utf8"))
    for i, ref in enumerate(refs, 1):
        prior = (ref.get("doi") or "").lower() or None
        cr, pm = crossref(ref), pubmed(ref)
        status, doi, reasons = classify(ref, cr, pm)
        if prior and doi and prior != doi:
            status, doi = "conflict", None
            reasons.append(f"Site listed {prior}")
        elif prior and not doi and status == "needs_review":
            reasons.append(f"Site listed {prior}, not confirmed")
        ref["verification"] = {"status": status, "reasons": reasons, "checked": time.strftime("%Y-%m-%d")}
        if doi:
            ref["doi"] = doi
        if pm and strong(ref, pm):
            ref["pmid"] = pm["pmid"]
            ref["verification"]["pubtypes"] = pm["pubtypes"]
            ref["verification"]["matched_journal"] = pm["journal"]
        elif cr and strong(ref, cr):
            ref["verification"]["matched_journal"] = cr["journal"]
        if cr and strong(ref, cr):
            ref["verification"]["crossref_citations"] = cr["citations"]
        print(f'{i:2d}/{len(refs)} {status:22s} {doi or "-":38s} {ref["title"][:60]}', flush=True)
        DATA.write_text(json.dumps(refs, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
        time.sleep(0.5)


if __name__ == "__main__":
    main()
