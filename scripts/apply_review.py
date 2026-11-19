#!/usr/bin/env python3
"""Apply ticked boxes from the review issue to the queue.

Usage: apply_review.py path/to/issue_body.md

Approving a paper does not make it a source. It moves to data/reading_list.json, which
the Sources page never reads, and the issue then asks for a check of the page it bears
on. A paper joins data/references.json only when a page claim cites it, by the usual
route that confirms it against Crossref (scripts/finalize_refs.py). Preprints are marked
on the reading list so they are never mistaken for confirmed sources.

Correction and retraction notices stay in the issue until their Dismiss box is ticked.

Only papers already in data/review_queue.json can be approved, so editing the issue
can't add arbitrary content. A paper with both boxes ticked stays pending.
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_dois import is_preprint  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "data" / "review_queue.json"
READING_LIST = ROOT / "data" / "reading_list.json"
ALERTS = ROOT / "data" / "alerts.json"
TICKED = re.compile(r"^\s*-\s*\[[xX]\].*<!--\s*(review|check|alert):([0-9a-f]+):(approve|dismiss|done)\s*-->", re.M)
VALID = {("review", "approve"), ("review", "dismiss"), ("check", "done"), ("alert", "dismiss")}

# Pages that draw on each watch group, so an approval says where to look.
GROUP_PAGES = {
    "bdnf": ["index.html"],
    "psy": ["index.html", "pharma.html"],
    "cp": ["index.html"],
    "bird": ["index.html", "comparative.html"],
    "int": ["index.html"],
    "gen": ["index.html"],
}


def load(path, default):
    return json.loads(path.read_text(encoding="utf8")) if path.exists() else default


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf8")


def ticked(body, kind):
    marks = {}
    for k, ident, action in TICKED.findall(body):
        if k == kind and (k, action) in VALID:
            marks.setdefault(ident, set()).add(action)
    return marks


def parse_decisions(body):
    return {pmid: actions.pop() for pmid, actions in ticked(body, "review").items() if len(actions) == 1}


def parse_page_checks(body):
    return set(ticked(body, "check"))


def parse_alert_dismissals(body):
    return set(ticked(body, "alert"))


def dismiss_alerts(alert_state, ids):
    """Drop ticked notices from the issue. The notice itself stays on the Sources page."""
    before = len(alert_state["open"])
    alert_state["open"] = [a for a in alert_state["open"] if a["id"] not in ids]
    return before - len(alert_state["open"])


def to_reading_entry(item, today):
    return {"pmid": item["pmid"], "doi": item["doi"], "group": item["group"], "title": item["title"],
            "authors": item["authors"], "journal": item["journal"], "year": item["year"],
            "preprint": is_preprint(doi=item["doi"], journal=item["journal"]),
            "approved": today, "pages": GROUP_PAGES.get(item["group"], ["index.html"]),
            "page_check": "open"}


def apply_decisions(reading_list, queue, decisions, today):
    approved, dismissed, still_pending = 0, 0, []
    listed = {e["pmid"] for e in reading_list}
    for item in queue["pending"]:
        action = decisions.get(item["pmid"])
        if action == "approve":
            if item["pmid"] not in listed:
                reading_list.append(to_reading_entry(item, today))
            approved += 1
        elif action == "dismiss":
            dismissed += 1
        else:
            still_pending.append(item)
    queue["pending"] = still_pending
    return approved, dismissed


def apply_page_checks(reading_list, done, today):
    closed = 0
    for entry in reading_list:
        if entry.get("page_check") == "open" and entry["pmid"] in done:
            entry["page_check"] = today
            closed += 1
    return closed


def main():
    body = Path(sys.argv[1]).read_text(encoding="utf8")
    today = time.strftime("%Y-%m-%d")
    queue = load(QUEUE, {"pending": [], "seen": []})
    reading_list = load(READING_LIST, [])
    approved, dismissed = apply_decisions(reading_list, queue, parse_decisions(body), today)
    checked = apply_page_checks(reading_list, parse_page_checks(body), today)
    alert_state = load(ALERTS, {"open": []})
    cleared = dismiss_alerts(alert_state, parse_alert_dismissals(body))
    save(QUEUE, queue)
    save(READING_LIST, reading_list)
    save(ALERTS, alert_state)
    print(f"Applied review: {approved} approved to the reading list, {dismissed} dismissed, "
          f"{checked} page checks done, {cleared} notices dismissed")


if __name__ == "__main__":
    main()
