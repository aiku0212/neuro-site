#!/usr/bin/env python3
"""Daily citation check.

Published automatically: citation counts, and notices of correction or retraction.
Never published automatically: new papers. They wait in data/review_queue.json until
a person approves them, because a new study can change what a page should claim.

A failed lookup keeps the last good data and is reported instead of changing anything.
"""
import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_dois import get_json, is_preprint  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
LOOKBACK_DAYS = 7
MAX_PER_QUERY = 20
PAUSE = 0.4
MAX_ANNOUNCED_TITLES = 5  # titles listed in a notification comment; the rest are counted


def load(path, default):
    return json.loads(path.read_text(encoding="utf8")) if path.exists() else default


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf8")


def crossref_record(doi):
    quoted = urllib.parse.quote(doi, safe="")
    return (get_json(f"https://api.crossref.org/works/{quoted}") or {}).get("message")


def crossref_notices(doi):
    q = urllib.parse.urlencode({"filter": f"updates:{doi}", "select": "DOI,update-to", "rows": 20})
    items = (get_json(f"https://api.crossref.org/works?{q}") or {}).get("message", {}).get("items", [])
    found = []
    for item in items:
        for update in item.get("update-to", []):
            if (update.get("DOI") or "").lower() == doi.lower():
                found.append({"type": update.get("type") or "update", "notice_doi": item.get("DOI")})
    return found


def pubmed_summaries(pmids):
    if not pmids:
        return {}
    q = urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "id": ",".join(pmids)})
    result = (get_json(f"{EUTILS}/esummary.fcgi?{q}") or {}).get("result", {})
    return {uid: result[uid] for uid in result.get("uids", [])}


def check_references(refs, today):
    """Update refs in place. Returns (alerts, errors)."""
    alerts, errors = [], []
    pmids = [r["pmid"] for r in refs if r.get("pmid")]
    try:
        summaries = pubmed_summaries(pmids)
    except Exception as err:  # keep checking Crossref if PubMed is down
        summaries = {}
        errors.append(f"PubMed retraction check failed: {err}")
    for ref in refs:
        doi = ref.get("doi")
        try:
            record = crossref_record(doi)
            if not record:
                errors.append(f"No Crossref record for {doi}")
                continue
            time.sleep(PAUSE)
            notices = crossref_notices(doi)
        except Exception as err:
            errors.append(f"Lookup failed for {doi}: {err}")
            continue
        count = record.get("is-referenced-by-count")
        if isinstance(count, int):
            ref["citations"] = count
            ref["citations_checked"] = today
        ref["verification"]["checked"] = today

        summary = summaries.get(ref.get("pmid"), {})
        if any("retracted publication" in str(p).lower() for p in summary.get("pubtype", [])):
            notices.append({"type": "retraction", "pmid": ref["pmid"]})

        existing = ref.setdefault("updates", [])
        known = {(u.get("type", "").lower(), u.get("notice_doi")) for u in existing}
        retraction_known = any(re.search("retract|withdraw", u.get("type", ""), re.I) for u in existing)
        for notice in notices:
            is_retraction = bool(re.search("retract|withdraw", notice["type"], re.I))
            if is_retraction and "notice_doi" not in notice and retraction_known:
                continue
            if (notice["type"].lower(), notice.get("notice_doi")) in known:
                continue
            existing.append(notice)
            known.add((notice["type"].lower(), notice.get("notice_doi")))
            retraction_known = retraction_known or is_retraction
            alerts.append({"type": notice["type"], "doi": doi, "title": ref["title"],
                           "notice_doi": notice.get("notice_doi"), "pmid": notice.get("pmid")})
        time.sleep(PAUSE)
    return alerts, errors


def alert_id(alert):
    key = "|".join(str(alert.get(k) or "") for k in ("doi", "type", "notice_doi", "pmid")).lower()
    return hashlib.sha1(key.encode("utf8")).hexdigest()[:10]


def record_alerts(state, alerts, today):
    """Keep each notice open in the issue until someone ticks Dismiss."""
    open_ids = {a["id"] for a in state["open"]}
    for alert in alerts:
        entry = dict(alert, id=alert_id(alert), found=today)
        if entry["id"] not in open_ids:
            state["open"].append(entry)
            open_ids.add(entry["id"])


def announcement(queue, alert_state, today):
    """Comment text for anything not announced before, or "" if nothing is new.

    Marks what it announces, so a paper or notice triggers one notification, however
    long it then waits in the issue body."""
    papers = [i for i in queue["pending"] if not i.get("announced")]
    notices = [a for a in alert_state["open"] if not a.get("announced")]
    if not papers and not notices:
        return ""
    for entry in papers + notices:
        entry["announced"] = today
    counts = []
    if notices:
        counts.append(f"{len(notices)} correction or retraction notice{'s' * (len(notices) != 1)}")
    if papers:
        counts.append(f"{len(papers)} paper{'s' * (len(papers) != 1)} to review")
    lines = [f"New since the last check: {' and '.join(counts)}. Details and checkboxes are in the issue body."]
    titles = [f"- **{safe_md(a['type'])}**: {safe_md(a['title'])}" for a in notices]
    titles += [f"- {safe_md(i['title'])}" for i in papers]
    lines += [""] + titles[:MAX_ANNOUNCED_TITLES]
    if len(titles) > MAX_ANNOUNCED_TITLES:
        lines.append(f"- and {len(titles) - MAX_ANNOUNCED_TITLES} more")
    return "\n".join(lines) + "\n"


def short_authors(summary):
    names = [a.get("name", "") for a in summary.get("authors", []) if a.get("name")]
    if not names:
        return "Unknown"
    parts = names[0].split()
    surname = " ".join(parts[:-1]) if len(parts) > 1 else parts[0]
    return f"{surname} et al." if len(names) > 1 else surname


def discover(refs, queue, queries):
    """Add new PubMed papers to the queue. Returns (new_items, errors)."""
    cited_dois = {(r.get("doi") or "").lower() for r in refs}
    cited_pmids = {r.get("pmid") for r in refs}
    seen = set(queue["seen"])
    new_items, errors = [], []
    for group, term in queries.items():
        q = urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "datetype": "edat",
                                    "reldate": LOOKBACK_DAYS, "retmax": MAX_PER_QUERY, "term": term})
        try:
            ids = (get_json(f"{EUTILS}/esearch.fcgi?{q}") or {}).get("esearchresult", {}).get("idlist", [])
            time.sleep(PAUSE)
            fresh = [i for i in ids if i not in seen and i not in cited_pmids]
            summaries = pubmed_summaries(fresh)
        except Exception as err:
            errors.append(f"Search failed for group {group}: {err}")
            continue
        for pmid, summary in summaries.items():
            doi = next((a["value"].lower() for a in summary.get("articleids", [])
                        if a.get("idtype") == "doi"), "")
            # Without a DOI the paper can't be monitored; a later run retries once PubMed has one.
            if not doi or doi in cited_dois:
                continue
            year = re.match(r"\d{4}", summary.get("pubdate", "") or "")
            item = {"pmid": pmid, "doi": doi, "group": group, "title": summary.get("title", "").strip(),
                    "authors": short_authors(summary), "journal": summary.get("fulljournalname", ""),
                    "year": int(year.group()) if year else None}
            queue["pending"].append(item)
            queue["seen"].append(pmid)
            seen.add(pmid)
            new_items.append(item)
        time.sleep(PAUSE)
    return new_items, errors


def safe_md(text):
    """Stop paper titles from pinging GitHub users or breaking the checklist."""
    return re.sub(r"\s+", " ", str(text)).replace("@", "@​").replace("<", "&lt;").replace("[", "\\[").replace("]", "\\]")


def render_issue(queue, alerts, errors, today, reading_list=()):
    lines = [f"Last run: {today}", ""]
    if errors:
        lines += [f"## Lookup problems ({len(errors)})", "The last good data stayed in place.", ""]
        lines += [f"- {safe_md(e)}" for e in errors] + [""]
    if alerts:
        lines += [f"## Correction and retraction notices ({len(alerts)})",
                  "Review any claims that rely on these papers. Each notice stays here until you tick Dismiss.", ""]
        for a in alerts:
            link = f" · [notice](https://doi.org/{a['notice_doi']})" if a.get("notice_doi") else ""
            lines.append(f"**{safe_md(a['type'])}**: {safe_md(a['title'])}  ")
            lines.append(f"found {a.get('found', '?')} · https://doi.org/{a['doi']}{link}")
            lines.append(f"- [ ] Dismiss <!-- alert:{a['id']}:dismiss -->")
            lines.append("")
    checks = [e for e in reading_list if e.get("page_check") == "open"]
    if checks:
        lines += [f"## Approved papers: pages to check ({len(checks)})",
                  "Approved papers go on the reading list (data/reading_list.json), not the Sources page. "
                  "Check whether the page should change, then tick the box. A paper becomes a source "
                  "only when a page claim cites it.", ""]
        for entry in checks:
            label = " · **preprint, not peer reviewed**" if entry.get("preprint") else ""
            lines.append(f"**{safe_md(entry['title'])}**  ")
            lines.append(f"approved {entry['approved']} · check {', '.join(entry['pages'])} · "
                         f"https://doi.org/{entry['doi']}{label}")
            lines.append(f"- [ ] Page checked <!-- check:{entry['pmid']}:done -->")
            lines.append("")
    lines += [f"## New papers to review ({len(queue['pending'])})",
              "Tick one box per paper. The next daily run applies it. "
              "Approving puts a paper on the reading list and asks for a page check; it does not add it to Sources.", ""]
    for item in queue["pending"]:
        pid = item["pmid"]
        label = " · **preprint, not peer reviewed**" if is_preprint(item.get("doi"), item.get("journal")) else ""
        lines.append(f"**{safe_md(item['title'])}**  ")
        lines.append(f"{safe_md(item['authors'])}, {safe_md(item['journal'])}, {item['year']} · "
                     f"group `{item['group']}` · https://doi.org/{item['doi']}{label}")
        lines.append(f"- [ ] Approve <!-- review:{pid}:approve -->")
        lines.append(f"- [ ] Dismiss <!-- review:{pid}:dismiss -->")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--announce", type=Path,
                        help="write a notification comment here when there are new papers or notices")
    args = parser.parse_args(argv)
    today = time.strftime("%Y-%m-%d")
    refs = load(DATA_DIR / "references.json", [])
    queue = load(DATA_DIR / "review_queue.json", {"pending": [], "seen": []})
    queries = load(DATA_DIR / "watch_queries.json", {})
    reading_list = load(DATA_DIR / "reading_list.json", [])
    alert_state = load(DATA_DIR / "alerts.json", {"open": []})

    alerts, errors = check_references(refs, today)
    new_items, search_errors = discover(refs, queue, queries)
    errors += search_errors
    record_alerts(alert_state, alerts, today)
    if args.announce:
        args.announce.write_text(announcement(queue, alert_state, today), encoding="utf8")

    save(DATA_DIR / "references.json", refs)
    save(DATA_DIR / "review_queue.json", queue)
    save(DATA_DIR / "alerts.json", alert_state)
    # A dated commit each day also keeps GitHub from pausing the schedule on a quiet repo.
    save(DATA_DIR / "status.json", {"last_run": today, "references": len(refs), "alerts": len(alerts),
                                    "open_alerts": len(alert_state["open"]),
                                    "new_papers": len(new_items), "pending_review": len(queue["pending"]),
                                    "errors": len(errors)})
    (DATA_DIR / "review_issue.md").write_text(render_issue(queue, alert_state["open"], errors, today, reading_list), encoding="utf8")
    print(f"{len(refs)} references checked; {len(alerts)} new notices; {len(new_items)} new papers; "
          f"{len(queue['pending'])} pending; {len(errors)} errors")
    for err in errors:
        print("  !", err)


if __name__ == "__main__":
    main()
