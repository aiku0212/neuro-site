#!/usr/bin/env python3
"""Write data/references.json into references.html so the page works as a plain static file."""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "references.html"
DATA = ROOT / "data" / "references.json"


def esc(text):
    return html.escape(text, quote=False)


def page_record(ref):
    rec = {"g": ref["group"], "t": esc(ref["title"]), "a": esc(ref["authors"]),
           "y": ref["year"], "j": esc(ref["journal"])}
    for src, dst in (("citations", "c"), ("tag", "tag"), ("doi", "doi")):
        if ref.get(src) is not None:
            rec[dst] = ref[src]
    if ref.get("meta_analysis"):
        rec["meta"] = 1
    if ref.get("note"):
        rec["note"] = esc(ref["note"])
    if ref.get("updates"):
        rec["upd"] = ref["updates"]
    return rec


def main():
    refs = json.loads(DATA.read_text(encoding="utf8"))
    blocked = [r["title"] for r in refs if r["verification"]["status"] != "confirmed"]
    if blocked:
        raise SystemExit(f"Refusing to build; unconfirmed references: {blocked}")
    payload = json.dumps([page_record(r) for r in refs], indent=1).replace("</", "<\\/")
    src = PAGE.read_text(encoding="utf8")
    src, n = re.subn(r"var REFS=(?:/\*refs:start\*/)?\[.*?\](?:/\*refs:end\*/)?;\n\nvar GROUPS",
                     lambda _: f"var REFS=/*refs:start*/{payload}/*refs:end*/;\n\nvar GROUPS",
                     src, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("Could not find the REFS block in references.html")
    checked = max(r["verification"]["checked"] for r in refs)
    src, n = re.subn(r"<!--checked:start-->.*?<!--checked:end-->",
                     f"<!--checked:start-->{checked}<!--checked:end-->", src, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("Could not find the checked-date marker in references.html")
    PAGE.write_text(src, encoding="utf8")
    print(f"Built references.html from {len(refs)} references, checked {checked}")


if __name__ == "__main__":
    main()
