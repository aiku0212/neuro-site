#!/usr/bin/env python3
"""Daily citation check.

Published automatically: citation counts, and notices of correction or retraction.
Never published automatically: new papers. They wait in data/review_queue.json until
a person approves them, because a new study can change what a page should claim.

A failed lookup keeps the last good data and is reported instead of changing anything.
A reference's record changes only when something about it changed (citations_checked is
the date its count last changed); status.json carries the date of each run, which is the
daily heartbeat that keeps GitHub from pausing the schedule.
If too many lookups fail, the run exits non-zero so nothing is published, and
status.json never dates a reference as checked on a day its lookup failed.
"""
import argparse
import datetime
import hashlib
import json
import os
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
# Fail the run (nothing is published) when more reference lookups fail than either limit.
MAX_FAILED_LOOKUPS = 5
MAX_FAILED_FRACTION = 0.20
# Daily lookups give up quickly, so an outage trips the failure limit, and the run reports
# it, long before the job's 20-minute timeout (each failing lookup costs at most ~22 s).
DAILY_TRIES = 2
DAILY_TIMEOUT = 10
MAX_ANNOUNCED_TITLES = 5  # titles listed in a notification comment; the rest are counted

# GitHub rejects issue bodies over 65,536 characters. The review issue stays under a
# smaller budget, measured in bytes so it is safe however GitHub counts.
ISSUE_BODY_LIMIT = 65536
ISSUE_BODY_BUDGET = 60000
OVERFLOW_NOTE_BYTES = 200
QUEUE_EXPIRY_DAYS = 90
MAX_SHOWN_ERRORS = 30
MAX_SHOWN_ALERTS = 50
MAX_SHOWN_CHECKS = 50
MAX_SHOWN_PAPERS = 100
MAX_TITLE_CHARS = 300


def load(path, default):
    return json.loads(path.read_text(encoding="utf8")) if path.exists() else default


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf8")


def fetch(url):
    return get_json(url, tries=DAILY_TRIES, timeout=DAILY_TIMEOUT)


def crossref_record(doi):
    quoted = urllib.parse.quote(doi, safe="")
    return (fetch(f"https://api.crossref.org/works/{quoted}") or {}).get("message")


def crossref_notices(doi):
    q = urllib.parse.urlencode({"filter": f"updates:{doi}", "select": "DOI,update-to", "rows": 20})
    items = (fetch(f"https://api.crossref.org/works?{q}") or {}).get("message", {}).get("items", [])
    found = []
    for item in items:
        for update in item.get("update-to", []):
            if (update.get("DOI") or "").lower() == doi.lower():
                found.append({"type": update.get("type") or "update", "notice_doi": item.get("DOI")})
    return found


def pubmed_summaries(pmids):
    """PubMed summaries by PMID. Raises when PubMed gives no usable reply (404, or no
    "result"), so an outage is never mistaken for "no retraction". A PMID PubMed skips or
    returns with an error is left out; callers treat it as not checked."""
    if not pmids:
        return {}
    q = urllib.parse.urlencode({"db": "pubmed", "retmode": "json", "id": ",".join(pmids)})
    reply = fetch(f"{EUTILS}/esummary.fcgi?{q}")
    result = reply.get("result") if isinstance(reply, dict) else None
    if not isinstance(result, dict) or not isinstance(result.get("uids"), list):
        raise RuntimeError(f"PubMed esummary gave no result for {len(pmids)} PMIDs")
    return {uid: result[uid] for uid in result["uids"]
            if isinstance(result.get(uid), dict) and "error" not in result[uid]}


def check_references(refs, today):
    """Update refs in place. Returns (alerts, errors, failed), failed being the DOIs
    whose check did not complete (Crossref, or PubMed's retraction check)."""
    alerts, errors, failed = [], [], set()
    pmids = [r["pmid"] for r in refs if r.get("pmid")]
    try:
        summaries = pubmed_summaries(pmids)
    except Exception as err:  # keep checking Crossref if PubMed is down
        summaries = None
        errors.append(f"PubMed retraction check failed: {err}")
    for ref in refs:
        if summaries is None and ref.get("pmid"):
            failed.add(ref.get("doi"))
        elif ref.get("pmid") and ref["pmid"] not in summaries:
            errors.append(f"PubMed gave no record for PMID {ref['pmid']} ({ref.get('doi')}); "
                          "retraction check incomplete")
            failed.add(ref.get("doi"))
    for i, ref in enumerate(refs):
        if too_many_failures(failed, len(refs)):
            # The run fails anyway; stop now so it says why instead of hitting the job timeout.
            rest = {r.get("doi") for r in refs[i:]} - failed
            failed |= rest
            errors.append(f"Stopped after {len(failed) - len(rest)} failed lookups; "
                          f"{len(rest)} references not checked")
            break
        doi = ref.get("doi")
        try:
            record = crossref_record(doi)
            if not record:
                errors.append(f"No Crossref record for {doi}")
                failed.add(doi)
                continue
            time.sleep(PAUSE)
            notices = crossref_notices(doi)
        except Exception as err:
            errors.append(f"Lookup failed for {doi}: {err}")
            failed.add(doi)
            continue
        count = record.get("is-referenced-by-count")
        # Only real changes are written; the day's check date lives in status.json.
        if isinstance(count, int) and count != ref.get("citations"):
            ref["citations"] = count
            ref["citations_checked"] = today

        summary = (summaries or {}).get(ref.get("pmid"), {})
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
    return alerts, errors, failed


def checked_status(refs, failed, previous, today):
    """Return (checked, lookup_failed) for status.json.

    lookup_failed maps each DOI whose check failed today to the last date it is known
    to have been checked; checked is the date by which every reference had been checked
    (today only when none failed). Neither ever claims a check that did not happen.

    Only a run that passed is committed, so in a status.json of this format (it has
    "checked") a DOI missing from lookup_failed was checked on that run's last_run.
    verification.checked is the date the reference was confirmed; it is no longer
    updated daily, so it only counts when it is later (a reference added since then).
    An older status.json's last_run proves nothing, so then only verification.checked counts."""
    prior = previous.get("lookup_failed", {})
    last_good = previous.get("last_run") if "checked" in previous else None
    lookup_failed = {}
    for ref in refs:
        doi = ref.get("doi")
        if doi not in failed:
            continue
        known = [d for d in (last_good, ref.get("verification", {}).get("checked")) if d]
        lookup_failed[doi] = prior.get(doi) if doi in prior else (max(known) if known else None)
    dates = list(lookup_failed.values())
    checked = today if not dates else (None if None in dates else min(dates))
    return checked, lookup_failed


def too_many_failures(failed, total):
    return len(failed) > MAX_FAILED_LOOKUPS or len(failed) > MAX_FAILED_FRACTION * max(total, 1)


def report_failure(message):
    print(f"::error::{message}", file=sys.stderr)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf8") as f:
            f.write(f"## Citation check failed\n\n{message}\n")


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
            ids = (fetch(f"{EUTILS}/esearch.fcgi?{q}") or {}).get("esearchresult", {}).get("idlist", [])
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
                    "year": int(year.group()) if year else None, "queued": time.strftime("%Y-%m-%d")}
            queue["pending"].append(item)
            queue["seen"].append(pmid)
            seen.add(pmid)
            new_items.append(item)
        time.sleep(PAUSE)
    return new_items, errors


def safe_md(text):
    """Stop paper titles from pinging GitHub users or breaking the checklist."""
    return re.sub(r"\s+", " ", str(text)).replace("@", "@​").replace("<", "&lt;").replace("[", "\\[").replace("]", "\\]")


def size(text):
    return len(text.encode("utf8"))


def clip(text, limit=MAX_TITLE_CHARS):
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text if len(text) <= limit else text[:limit - 1] + "…"


def section(title, intro, blocks, cap, what):
    return {"head": f"## {title}\n{intro}\n\n" if intro else f"## {title}\n\n",
            "blocks": blocks, "cap": cap, "what": what}


def render_issue(queue, alerts, errors, today, reading_list=(), expired=0):
    """Markdown for the review issue, always within ISSUE_BODY_BUDGET bytes.

    Sections are written in order of urgency. Each shows at most its cap, and stops early
    when the budget runs out; the rest are counted, not dropped from the data."""
    sections = []
    if errors:
        sections.append(section(f"Lookup problems ({len(errors)})", "The last good data stayed in place.",
                                [f"- {safe_md(clip(e))}\n" for e in errors], MAX_SHOWN_ERRORS, "problems"))
    if alerts:
        blocks = []
        for a in alerts:
            link = f" · [notice](https://doi.org/{a['notice_doi']})" if a.get("notice_doi") else ""
            blocks.append(f"**{safe_md(a['type'])}**: {safe_md(clip(a['title']))}  \n"
                          f"found {a.get('found', '?')} · https://doi.org/{a['doi']}{link}\n"
                          f"- [ ] Dismiss <!-- alert:{a['id']}:dismiss -->\n\n")
        sections.append(section(f"Correction and retraction notices ({len(alerts)})",
                                "Review any claims that rely on these papers. "
                                "Each notice stays here until you tick Dismiss.", blocks, MAX_SHOWN_ALERTS, "notices"))
    checks = [e for e in reading_list if e.get("page_check") == "open"]
    if checks:
        blocks = []
        for entry in checks:
            label = " · **preprint, not peer reviewed**" if entry.get("preprint") else ""
            blocks.append(f"**{safe_md(clip(entry['title']))}**  \n"
                          f"approved {entry['approved']} · check {', '.join(entry['pages'])} · "
                          f"https://doi.org/{entry['doi']}{label}\n"
                          f"- [ ] Page checked <!-- check:{entry['pmid']}:done -->\n\n")
        sections.append(section(f"Approved papers: pages to check ({len(checks)})",
                                "Approved papers go on the reading list (data/reading_list.json), not the Sources "
                                "page. Check whether the page should change, then tick the box. A paper becomes a "
                                "source only when a page claim cites it.", blocks, MAX_SHOWN_CHECKS, "page checks"))
    blocks = []
    for item in queue["pending"]:
        pid = item["pmid"]
        label = " · **preprint, not peer reviewed**" if is_preprint(item.get("doi"), item.get("journal")) else ""
        blocks.append(f"**{safe_md(clip(item['title']))}**  \n"
                      f"{safe_md(clip(item['authors'], 100))}, {safe_md(clip(item['journal'], 150))}, {item['year']} · "
                      f"group `{safe_md(item['group'])}` · https://doi.org/{item['doi']}{label}\n"
                      f"- [ ] Approve <!-- review:{pid}:approve -->\n"
                      f"- [ ] Dismiss <!-- review:{pid}:dismiss -->\n\n")
    intro = ("Tick one box per paper. The next daily run applies it. Approving puts a paper on the reading "
             "list and asks for a page check; it does not add it to Sources. "
             f"Papers not reviewed within {QUEUE_EXPIRY_DAYS} days expire.")
    if expired:
        intro += f" {expired} expired on this run."
    sections.append(section(f"New papers to review ({len(queue['pending'])})", intro, blocks,
                            MAX_SHOWN_PAPERS, "papers"))

    out = f"Last run: {today}\n\n"
    reserve = OVERFLOW_NOTE_BYTES * len(sections)  # room for every section's "N more" line
    for sec in sections:
        reserve -= OVERFLOW_NOTE_BYTES
        if size(out + sec["head"]) + reserve > ISSUE_BODY_BUDGET:
            out += f"_{len(sec['blocks'])} {sec['what']} not shown: the issue is at its size limit._\n\n"
            continue
        out += sec["head"]
        shown = 0
        for block in sec["blocks"][:sec["cap"]]:
            if size(out + block) + reserve + OVERFLOW_NOTE_BYTES > ISSUE_BODY_BUDGET:
                break
            out += block
            shown += 1
        if shown < len(sec["blocks"]):
            out += (f"_{len(sec['blocks']) - shown} more {sec['what']} not shown here. "
                    "They appear as the ones above are cleared._\n\n")
    if size(out) > ISSUE_BODY_BUDGET:  # cannot happen with the reserve above; never exceed the limit
        out = out.encode("utf8")[:ISSUE_BODY_BUDGET - 100].decode("utf8", "ignore") + "\n\n_Truncated._\n"
    return out


def expire_queue(queue, today):
    """Drop papers waiting longer than QUEUE_EXPIRY_DAYS. They stay in "seen", so they
    are never queued again. Returns how many expired."""
    now = datetime.date.fromisoformat(today)
    kept = []
    for item in queue["pending"]:
        queued = item.setdefault("queued", today)
        if (now - datetime.date.fromisoformat(queued)).days <= QUEUE_EXPIRY_DAYS:
            kept.append(item)
    expired = len(queue["pending"]) - len(kept)
    queue["pending"] = kept
    return expired


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

    previous = load(DATA_DIR / "status.json", {})
    alerts, errors, failed = check_references(refs, today)
    new_items, search_errors = discover(refs, queue, queries)
    expired = expire_queue(queue, today)
    errors += search_errors
    record_alerts(alert_state, alerts, today)
    if args.announce:
        args.announce.write_text(announcement(queue, alert_state, today), encoding="utf8")

    save(DATA_DIR / "references.json", refs)
    save(DATA_DIR / "review_queue.json", queue)
    save(DATA_DIR / "alerts.json", alert_state)
    # The one record that changes every day: a dated commit keeps GitHub from pausing the schedule.
    checked, lookup_failed = checked_status(refs, failed, previous, today)
    save(DATA_DIR / "status.json", {"last_run": today, "checked": checked, "lookup_failed": lookup_failed,
                                    "references": len(refs), "alerts": len(alerts),
                                    "open_alerts": len(alert_state["open"]),
                                    "new_papers": len(new_items), "pending_review": len(queue["pending"]),
                                    "expired": expired,
                                    "errors": len(errors)})
    (DATA_DIR / "review_issue.md").write_text(render_issue(queue, alert_state["open"], errors, today, reading_list, expired), encoding="utf8")
    print(f"{len(refs) - len(failed)} of {len(refs)} references checked; {len(alerts)} new notices; {len(new_items)} new papers; "
          f"{len(queue['pending'])} pending; {len(errors)} errors")
    for err in errors:
        print("  !", err)
    if too_many_failures(failed, len(refs)):
        report_failure(f"{len(failed)} of {len(refs)} reference lookups failed (limit: more than "
                       f"{MAX_FAILED_LOOKUPS}, or more than {MAX_FAILED_FRACTION:.0%}). Citation counts and "
                       f"correction checks are incomplete, so this run publishes nothing. "
                       f"Sources stay dated {checked or 'unchecked'}.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
