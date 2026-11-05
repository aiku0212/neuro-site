#!/usr/bin/env python3
"""Apply ticked boxes from the review issue to the queue.

Usage: apply_review.py path/to/issue_body.md

Only papers already in data/review_queue.json can be approved, so editing the issue
can't add arbitrary content. A paper with both boxes ticked stays pending.
"""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFS = ROOT / "data" / "references.json"
QUEUE = ROOT / "data" / "review_queue.json"
TICKED = re.compile(r"^\s*-\s*\[[xX]\].*<!--\s*review:(\d+):(approve|dismiss)\s*-->", re.M)


def parse_decisions(body):
    decisions = {}
    for pmid, action in TICKED.findall(body):
        decisions.setdefault(pmid, set()).add(action)
    return {pmid: actions.pop() for pmid, actions in decisions.items() if len(actions) == 1}


def to_reference(item, today):
    return {"group": item["group"], "title": item["title"], "authors": item["authors"],
            "year": item["year"], "journal": item["journal"], "doi": item["doi"], "pmid": item["pmid"],
            "meta_analysis": False, "site_title": item["title"], "site_year": item["year"], "updates": [],
            "verification": {"status": "confirmed", "reasons": ["Approved from review queue"], "checked": today}}


def apply_decisions(refs, queue, decisions, today):
    approved, dismissed, still_pending = 0, 0, []
    for item in queue["pending"]:
        action = decisions.get(item["pmid"])
        if action == "approve":
            refs.append(to_reference(item, today))
            approved += 1
        elif action == "dismiss":
            dismissed += 1
        else:
            still_pending.append(item)
    queue["pending"] = still_pending
    return approved, dismissed


def main():
    body = Path(sys.argv[1]).read_text(encoding="utf8")
    refs = json.loads(REFS.read_text(encoding="utf8"))
    queue = json.loads(QUEUE.read_text(encoding="utf8")) if QUEUE.exists() else {"pending": [], "seen": []}
    approved, dismissed = apply_decisions(refs, queue, parse_decisions(body), time.strftime("%Y-%m-%d"))
    REFS.write_text(json.dumps(refs, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    QUEUE.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print(f"Applied review: {approved} approved, {dismissed} dismissed")


if __name__ == "__main__":
    main()
