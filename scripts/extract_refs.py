#!/usr/bin/env python3
"""One-time migration: move the REFS array from references.html into data/references.json."""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIELDS = {"g": "group", "t": "title", "a": "authors", "y": "year", "j": "journal",
          "c": "citations", "tag": "tag", "meta": "meta_analysis", "note": "note", "doi": "doi"}
TOKEN = re.compile(r"""(\w+):('(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*"|\d+)""")


def main():
    src = (ROOT / "references.html").read_text(encoding="utf8")
    start = src.index("var REFS=[")
    block = src[start:src.index("];", start)]
    refs = []
    for chunk in re.split(r"(?=\{g:)", block)[1:]:
        ref = {}
        for key, raw in TOKEN.findall(chunk):
            if raw[0] in "'\"":
                value = html.unescape(raw[1:-1].replace("\\'", "'"))
            else:
                value = int(raw)
            ref[FIELDS[key]] = value
        ref["meta_analysis"] = bool(ref.get("meta_analysis"))
        refs.append(ref)
    out = ROOT / "data" / "references.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(refs, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print(f"{len(refs)} references written to {out}")


if __name__ == "__main__":
    main()
