#!/usr/bin/env python3
"""Weekly news list for news.html.

Lists new review articles from five neuroscience review journals (through PubMed), new
eLife neuroscience papers and MIT News neuroscience stories. Each item is a headline, its
source, a kind label, a date and a link to the original. Nothing is summarized, and no
abstract or article text is stored.

A source that fails keeps its previous items and is marked "failed". If every source
fails, or the result does not pass validation, the run exits non-zero and changes nothing,
so the last good page stays up. Feed text is data: it is stripped of tags, capped and
escaped before it reaches the page.
"""
import argparse
import datetime
import html
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from xml.parsers import expat
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "neuroscope-news/1.0"}
TOOL = "neuroscope-news"          # NCBI asks clients to name themselves; no email is sent
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT = 30                      # seconds per socket operation
DEADLINE = 60                     # seconds for one whole response, so a slow drip cannot stall the run
CHUNK = 64 * 1024
PAUSE = 1.0                       # seconds between requests
TRIES = 2
WINDOW_DAYS = 28
PER_SOURCE_WEEK = 5
MAX_ITEMS = 40
MAX_TITLE = 200
UTC = datetime.timezone.utc

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
REVIEW = "Review article"
RESEARCH = "Research paper (eLife reviewed preprint)"
UNIVERSITY = "University news office"
# Section heads on the page, in order.
DESKS = [(REVIEW, "Reviews"), (RESEARCH, "Research"), (UNIVERSITY, "University news")]

# One request (or pair, for PubMed) per feed. "fetch_hosts" may be contacted, and items
# may only link to "link_hosts". Both are https only.
FEEDS = {
    "pubmed": {"name": "PubMed", "adapter": "pubmed",
               "fetch_hosts": {"eutils.ncbi.nlm.nih.gov"},
               "link_hosts": {"pubmed.ncbi.nlm.nih.gov"},
               "about": "new review articles in five neuroscience review journals"},
    "elife": {"name": "eLife", "adapter": "feed",
              "url": "https://elifesciences.org/rss/subject/neuroscience.xml",
              "fetch_hosts": {"elifesciences.org"}, "link_hosts": {"elifesciences.org"},
              "about": "new neuroscience papers, published as reviewed preprints"},
    "mit-news": {"name": "MIT News", "adapter": "feed",
                 "url": "https://news.mit.edu/topic/mitneuroscience-rss.xml",
                 "fetch_hosts": {"news.mit.edu"}, "link_hosts": {"news.mit.edu"},
                 "about": "neuroscience stories from MIT's news office"},
}

# PubMed journal abbreviation ([ta]) -> source id and display name.
JOURNALS = {
    "Nat Rev Neurosci": ("nat-rev-neurosci", "Nature Reviews Neuroscience"),
    "Annu Rev Neurosci": ("annu-rev-neurosci", "Annual Review of Neuroscience"),
    "Trends Neurosci": ("trends-neurosci", "Trends in Neurosciences"),
    "Neuron": ("neuron", "Neuron"),
    "Curr Opin Neurobiol": ("curr-opin-neurobiol", "Current Opinion in Neurobiology"),
}

# Each source the page shows: its feed, display name and kind label.
SOURCES = {sid: {"feed": "pubmed", "name": name, "kind": REVIEW} for sid, name in JOURNALS.values()}
SOURCES["elife"] = {"feed": "elife", "name": "eLife", "kind": RESEARCH}
SOURCES["mit-news"] = {"feed": "mit-news", "name": "MIT News", "kind": UNIVERSITY}

TAG = re.compile(r"</?[A-Za-z][^<>]*>")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
CORRECTION = re.compile(r"^\s*(author\s+)?(correction|erratum|corrigendum)\b", re.I)
NS = {"atom": "http://www.w3.org/2005/Atom", "dc": "http://purl.org/dc/elements/1.1/",
      "rss1": "http://purl.org/rss/1.0/", "prism": "http://prismstandard.org/namespaces/basic/2.0/"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


# ---------------------------------------------------------------- fetching

def check_url(url, hosts):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or (parts.hostname or "").lower() not in hosts:
        raise ValueError(f"refusing to fetch {url}: not https on an allowed host")


class _Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl, self.hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_url(url, hosts):
    """GET url and return at most MAX_BYTES of body. Only https on hosts, redirects included."""
    check_url(url, hosts)
    opener = urllib.request.build_opener(_Redirects(hosts))
    for attempt in range(TRIES):
        try:
            started = time.monotonic()
            with opener.open(urllib.request.Request(url, headers=UA), timeout=TIMEOUT) as resp:
                check_url(resp.geturl(), hosts)
                data = b""
                while len(data) <= MAX_BYTES:
                    chunk = resp.read(min(CHUNK, MAX_BYTES + 1 - len(data)))
                    if not chunk:
                        break
                    data += chunk
                    if time.monotonic() - started > DEADLINE:
                        raise TimeoutError(f"{url} took longer than {DEADLINE} s")
            if len(data) > MAX_BYTES:
                raise ValueError(f"{url} is larger than {MAX_BYTES} bytes")
            return data
        except urllib.error.HTTPError as err:
            if err.code in (429, 500, 502, 503, 504) and attempt < TRIES - 1:
                time.sleep(5)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == TRIES - 1:
                raise
            time.sleep(5)


# ---------------------------------------------------------------- parsing

def local(tag):
    return tag.rsplit("}", 1)[-1]


def text_of(el):
    return "".join(el.itertext()) if el is not None else ""


def first(el, *paths):
    for path in paths:
        found = el.find(path, NS)
        if found is not None and text_of(found).strip():
            return text_of(found).strip()
    return ""


def parse_when(value):
    """An aware datetime from an RFC 822 or ISO 8601 date, or None."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        try:
            when = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                when = datetime.datetime.strptime(value, "%Y/%m/%d %H:%M")
            except ValueError:
                return None
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def refuse_entities(data):
    """Raise ValueError if the document declares any entity. The byte check alone misses
    UTF-16 and other encodings, so expat itself is asked before ElementTree expands anything."""
    if re.search(rb"<!ENTITY", data.replace(b"\x00", b""), re.I):
        raise ValueError("feed declares entities")

    def declared(*_):
        raise ValueError("feed declares entities")

    parser = expat.ParserCreate()
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    parser.EntityDeclHandler = declared
    parser.UnparsedEntityDeclHandler = declared
    parser.Parse(data, True)


def parse_feed(data):
    """Entries of an RSS 2.0, RSS 1.0 (RDF) or Atom feed as {title, url, when}."""
    refuse_entities(data)
    root = ET.fromstring(data)
    kind = local(root.tag)
    entries = []
    if kind == "rss":
        for item in root.findall("./channel/item"):
            entries.append({"title": first(item, "title"), "url": first(item, "link"),
                            "when": parse_when(first(item, "pubDate", "dc:date"))})
    elif kind == "RDF":
        for item in root.findall("rss1:item", NS):
            entries.append({"title": first(item, "rss1:title"), "url": first(item, "rss1:link"),
                            "when": parse_when(first(item, "dc:date", "prism:publicationDate"))})
    elif kind == "feed":
        for entry in root.findall("atom:entry", NS):
            link = ""
            for el in entry.findall("atom:link", NS):
                if el.get("rel", "alternate") == "alternate" and el.get("href"):
                    link = el.get("href")
                    break
            entries.append({"title": first(entry, "atom:title"), "url": link,
                            "when": parse_when(first(entry, "atom:published", "atom:updated"))})
    else:
        raise ValueError(f"not a known feed format: <{kind}>")
    if not entries:
        raise ValueError("feed has no items")
    return entries


def fetch_feed(feed, get):
    return parse_feed(get(feed["url"], feed["fetch_hosts"]))


def pubmed_term():
    journals = " OR ".join(f'"{abbr}"[ta]' for abbr in JOURNALS)
    return f"({journals}) AND review[pt] NOT preprint[pt]"


def entry_date(record):
    for event in record.get("history") or []:
        if isinstance(event, dict) and event.get("pubstatus") == "entrez":
            return parse_when(event.get("date"))
    return None


def fetch_pubmed(feed, get):
    """Reviews that entered PubMed in the last WINDOW_DAYS days, as {source, title, url, when}."""
    query = urllib.parse.urlencode({"db": "pubmed", "term": pubmed_term(), "datetype": "edat",
                                    "reldate": WINDOW_DAYS, "retmax": 100, "retmode": "json",
                                    "tool": TOOL})
    found = json.loads(get(f"{EUTILS}/esearch.fcgi?{query}", feed["fetch_hosts"]))
    ids = found["esearchresult"]["idlist"]
    if not all(isinstance(i, str) and i.isdigit() for i in ids):
        raise ValueError("PubMed returned an id that is not a number")
    if not ids:
        return []
    time.sleep(PAUSE)
    query = urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json",
                                    "tool": TOOL})
    result = json.loads(get(f"{EUTILS}/esummary.fcgi?{query}", feed["fetch_hosts"]))["result"]
    entries = []
    for uid in result["uids"]:
        record = result.get(uid)
        if not isinstance(record, dict) or "error" in record or not str(uid).isdigit():
            continue
        types = {str(t).lower() for t in record.get("pubtype") or []}
        if "preprint" in types or "published erratum" in types or "review" not in types:
            continue
        source = JOURNALS.get(record.get("source"))
        if not source:
            continue
        entries.append({"source": source[0], "title": record.get("title", ""),
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/", "when": entry_date(record)})
    return entries


ADAPTERS = {"feed": fetch_feed, "pubmed": fetch_pubmed}


# ---------------------------------------------------------------- cleaning

def clean_title(raw):
    """Plain text: tags stripped (also ones escaped in the feed), entities decoded, capped."""
    title = TAG.sub("", html.unescape(TAG.sub("", raw or "")))
    title = " ".join(CONTROL.sub(" ", title).split())
    if title.endswith(".") and not title.endswith(".."):
        title = title[:-1]
    if len(title) > MAX_TITLE:
        title = title[:MAX_TITLE - 1].rstrip() + "…"
    return title


def clean_url(url, hosts):
    """The https URL on one of hosts, without tracking parameters or fragment, else None."""
    try:
        parts = urllib.parse.urlsplit((url or "").strip())
        port = parts.port
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if parts.scheme.lower() != "https" or host not in hosts or parts.username or parts.password \
            or port not in (None, 443) or CONTROL.search(url or ""):
        return None
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() != "rss"]
    path = urllib.parse.quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~")
    return urllib.parse.urlunsplit(("https", host, path, urllib.parse.urlencode(query), ""))


def normalize(entries, feed_id, today):
    """Cleaned items for one feed: {source, title, url, date}, dated, in the window, not
    in the future, with corrections dropped."""
    feed = FEEDS[feed_id]
    now = datetime.datetime.combine(today, datetime.time(23, 59, 59), UTC)
    items = []
    for entry in entries:
        source = entry.get("source") or feed_id
        if SOURCES.get(source, {}).get("feed") != feed_id:
            continue
        title = clean_title(entry.get("title"))
        url = clean_url(entry.get("url"), feed["link_hosts"])
        when = entry.get("when")
        if not title or not url or when is None or when > now or CORRECTION.search(title):
            continue
        day = when.astimezone(UTC).date()
        if day > today or (today - day).days >= WINDOW_DAYS:
            continue
        items.append({"source": source, "title": title, "url": url, "date": day.isoformat()})
    return items


# ---------------------------------------------------------------- building

def week_of(day):
    year, week, _ = day.isocalendar()
    return year, week


def select(items, today):
    """Newest first, one copy of each, at most PER_SOURCE_WEEK per source per ISO week and
    MAX_ITEMS in all."""
    seen_urls, seen_titles, per_week, chosen = set(), set(), {}, []
    for item in sorted(items, key=lambda i: (i["date"], i["title"]), reverse=True):
        day = datetime.date.fromisoformat(item["date"])
        if day > today or (today - day).days >= WINDOW_DAYS:
            continue
        key_title = (item["source"], item["title"].casefold())
        if item["url"] in seen_urls or key_title in seen_titles:
            continue
        slot = (item["source"], week_of(day))
        if per_week.get(slot, 0) >= PER_SOURCE_WEEK:
            continue
        seen_urls.add(item["url"])
        seen_titles.add(key_title)
        per_week[slot] = per_week.get(slot, 0) + 1
        chosen.append(item)
        if len(chosen) == MAX_ITEMS:
            break
    return chosen


def iso_day(value):
    """The date for a YYYY-MM-DD string, else None."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def build(previous, fresh, failed, today):
    """The new news.json from last week's data, this run's items by feed, and failed feeds."""
    prev_items = [i for i in previous.get("items") or [] if isinstance(i, dict)]
    prev_sources = {s.get("id"): s for s in previous.get("sources") or [] if isinstance(s, dict)}
    pool = []
    for feed_id in FEEDS:
        pool += fresh.get(feed_id, [])
    # Previous items stay until they leave the window (feeds drop older entries), and are
    # all that is left of a feed that failed. They pass the same checks as new items.
    # An item that would fail validation is dropped here, so one bad record cannot block
    # every later update.
    for item in prev_items:
        source = SOURCES.get(item.get("source"))
        title = item.get("title")
        if not source or not isinstance(title, str) or not 0 < len(title) <= MAX_TITLE \
                or TAG.search(title) or CONTROL.search(title) or CORRECTION.search(title) \
                or not iso_day(item.get("date")):
            continue
        if clean_url(item.get("url"), FEEDS[source["feed"]]["link_hosts"]) != item.get("url"):
            continue
        pool.append({"source": item["source"], "title": title, "url": item["url"], "date": item["date"]})
    sources = []
    for sid, source in SOURCES.items():
        ok = source["feed"] not in failed
        last_ok = prev_sources.get(sid, {}).get("last_ok")
        last_ok = today.isoformat() if ok else (last_ok if iso_day(last_ok) else None)
        sources.append({"id": sid, "name": source["name"], "kind": source["kind"],
                        "last_ok": last_ok, "status": "ok" if ok else "failed"})
    return {"updated": today.isoformat(), "sources": sources, "items": select(pool, today)}


def validate(data, today):
    """Raise ValueError unless data is exactly what the page may show."""
    if set(data) != {"updated", "sources", "items"}:
        raise ValueError("news.json has unexpected top-level keys")
    if iso_day(data["updated"]) != today:
        raise ValueError("news.json is not dated today")
    if len(data["items"]) > MAX_ITEMS:
        raise ValueError("too many items")
    ids = [s.get("id") for s in data["sources"]]
    if ids != list(SOURCES):
        raise ValueError("sources do not match the source list")
    for source in data["sources"]:
        expected, last_ok = SOURCES[source["id"]], source.get("last_ok")
        if set(source) != {"id", "name", "kind", "last_ok", "status"} or source["status"] not in ("ok", "failed") \
                or (source["name"], source["kind"]) != (expected["name"], expected["kind"]) \
                or (last_ok is not None and not (iso_day(last_ok) and iso_day(last_ok) <= today)):
            raise ValueError(f"bad source record {source.get('id')}")
    for item in data["items"]:
        if set(item) != {"source", "title", "url", "date"}:
            raise ValueError("an item has keys other than source, title, url and date")
        source = SOURCES.get(item["source"])
        if not source:
            raise ValueError(f"unknown source {item['source']!r}")
        if clean_url(item["url"], FEEDS[source["feed"]]["link_hosts"]) != item["url"]:
            raise ValueError(f"link not allowed: {item['url']!r}")
        if not isinstance(item["title"], str) or not 0 < len(item["title"]) <= MAX_TITLE \
                or TAG.search(item["title"]) or CONTROL.search(item["title"]):
            raise ValueError(f"bad title {item['title']!r}")
        day = iso_day(item["date"])
        if day is None or day > today or (today - day).days >= WINDOW_DAYS:
            raise ValueError(f"date out of range: {item['date']}")


# ---------------------------------------------------------------- rendering

def esc(text):
    return html.escape(str(text), quote=True)


def long_date(day):
    return f"{day.strftime('%A')} {day.day} {MONTHS[day.month - 1]} {day.year}"


def mid_date(day):
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def short_date(day):
    return f"{day.day} {MONTHS[day.month - 1][:3]} {day.year}"


def item_html(item, lead=False):
    source = SOURCES[item["source"]]
    day = datetime.date.fromisoformat(item["date"])
    link = (f'<a href="{esc(item["url"])}" rel="noopener noreferrer">{esc(item["title"])}</a>')
    via = " via PubMed" if source["feed"] == "pubmed" else ""
    byline = (f'<p class="byline"><span class="src">{esc(source["name"])}{via}</span>'
              f'<span class="sep" aria-hidden="true"> · </span>'
              f'<time datetime="{day.isoformat()}">{short_date(day)}</time></p>')
    kind = f'<p class="kind">{esc(source["kind"])}</p>'
    if lead:
        return (f'<article class="lead" aria-labelledby="lead-hl">\n'
                f'  <p class="kind">Newest review article</p>\n'
                f'  <h2 class="lead-hl" id="lead-hl">{link}</h2>\n  {byline}\n</article>')
    return f'<li>{kind}<h4 class="hl">{link}</h4>{byline}</li>'


def pick_lead(items, today):
    recent = [i for i in items if (today - datetime.date.fromisoformat(i["date"])).days < 7]
    reviews = [i for i in recent if SOURCES[i["source"]]["kind"] == REVIEW]
    return (reviews or recent or items or [None])[0]


def render_news(data, today):
    items = data["items"]
    out = []
    lead = pick_lead(items, today)
    counts = {kind: sum(SOURCES[i["source"]]["kind"] == kind for i in items) for kind, _ in DESKS}
    weeks = []
    for item in items:
        if item is lead:
            continue
        key = week_of(datetime.date.fromisoformat(item["date"]))
        if not weeks or weeks[-1][0] != key:
            weeks.append((key, []))
        weeks[-1][1].append(item)

    if lead:
        index = "\n".join(f'    <li><span>{esc(label)}</span> <b>{counts[kind]}</b></li>'
                          for kind, label in DESKS)
        out.append('<div class="front">\n' + item_html(lead, lead=True) + '\n'
                   '<aside class="index" aria-labelledby="index-head">\n'
                   '  <h2 id="index-head">In this edition</h2>\n'
                   f'  <ul>\n{index}\n  </ul>\n'
                   f'  <p>{len(items)} headlines from the last four weeks, newest first.</p>\n'
                   '</aside>\n</div>')
    else:
        out.append('<p class="empty">Nothing new from these sources in the last four weeks.</p>')

    for (year, week), group in weeks:
        monday = datetime.date.fromisocalendar(year, week, 1)
        wid = f"w{year}-{week:02d}"
        label = (f"This week, from {mid_date(monday)}" if week_of(today) == (year, week)
                 else f"Week of {mid_date(monday)}")
        desks = []
        for kind, title in DESKS:
            these = [i for i in group if SOURCES[i["source"]]["kind"] == kind]
            if not these:
                continue
            did = f"{wid}-{title.split()[0].lower()}"
            rows = "\n".join("      " + item_html(i) for i in these)
            desks.append(f'  <section class="desk" aria-labelledby="{did}">\n'
                         f'    <h3 id="{did}">{esc(title)}</h3>\n'
                         f'    <ul class="items">\n{rows}\n    </ul>\n  </section>')
        # cols-N caps the week at N columns, so a week with one or two items
        # does not leave an empty column beside them on wide screens.
        out.append(f'<section class="week" aria-labelledby="{wid}">\n'
                   f'<h2 class="week-head" id="{wid}"><span>{label}</span></h2>\n'
                   f'<div class="cols cols-{min(3, len(group))}">\n' + "\n".join(desks) + '\n</div>\n</section>')

    rows = []
    by_feed = {}
    for source in data["sources"]:
        by_feed.setdefault(SOURCES[source["id"]]["feed"], []).append(source)
    for feed_id, feed in FEEDS.items():
        records = by_feed.get(feed_id, [])
        failed = any(s["status"] == "failed" for s in records)
        last_ok = max((s["last_ok"] for s in records if s["last_ok"]), default=None)
        if not failed:
            state = f"Checked {mid_date(datetime.date.fromisoformat(last_ok))}."
        elif last_ok:
            state = (f"Could not be reached on this update. Items shown are from the last good "
                     f"check on {mid_date(datetime.date.fromisoformat(last_ok))}.")
        else:
            state = "Could not be reached on this update."
        names = ""
        if feed_id == "pubmed":
            names = (" These are " + ", ".join(n for _, n in list(JOURNALS.values())[:-1])
                     + " and " + list(JOURNALS.values())[-1][1] + ".")
        cls = ' class="failed"' if failed else ""
        rows.append(f'    <li{cls}><b>{esc(feed["name"])}</b> lists '
                    f'{esc(feed["about"])}.{esc(names)} {esc(state)}</li>')
    out.append('<section class="wire" aria-labelledby="wire-head">\n'
               '  <h2 id="wire-head">Where these come from</h2>\n'
               '  <ul>\n' + "\n".join(rows) + '\n  </ul>\n</section>')
    return "\n".join(out)


def render_edition(data, today):
    year, week = week_of(today)
    count = len(data["items"])
    shown = len({i["source"] for i in data["items"]})
    return (f'<span>Week {week}, {year}</span>'
            f'<span>Updated {long_date(today)}</span>'
            f'<span>{count} headline{"" if count == 1 else "s"} from {shown} source{"" if shown == 1 else "s"}</span>')


def fill(page, name, body):
    pattern = re.compile(rf"<!--{name}:start-->.*?<!--{name}:end-->", re.S)
    if len(pattern.findall(page)) != 1:
        raise ValueError(f"news.html needs exactly one <!--{name}:start--> ... <!--{name}:end--> block")
    return pattern.sub(lambda _: f"<!--{name}:start-->{body}<!--{name}:end-->", page)


def check_page(page):
    """Every link the generated page carries is internal or https on an allowed host."""
    allowed = set().union(*(f["link_hosts"] for f in FEEDS.values()))
    body = page[page.index("<body") if "<body" in page else 0:]
    for tag in ("<script", "<img", "<iframe", "<embed", "<object"):
        if tag in body.lower():
            raise ValueError(f"news.html must not contain {tag}>")
    for href in re.findall(r'<a\b[^>]*\bhref="([^"]*)"', body):
        if href.startswith("#") or re.fullmatch(r"[a-z_-]+\.html(#[\w-]*)?", href):
            continue
        parts = urllib.parse.urlsplit(html.unescape(href))
        if parts.scheme != "https" or parts.hostname not in allowed:
            raise ValueError(f"news.html links off the allowlist: {href}")


def write_atomic(path, text):
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf8") as f:
        f.write(text)
    os.replace(tmp, path)


def run(root=ROOT, get=fetch_url, today=None, log=print):
    """Fetch, merge, validate and write. Returns the exit code."""
    today = today or datetime.datetime.now(UTC).date()
    data_path, page_path = root / "data" / "news.json", root / "news.html"
    try:
        previous = json.loads(data_path.read_text(encoding="utf8")) if data_path.exists() else {}
        if not isinstance(previous, dict):
            raise ValueError("data/news.json is not an object")
    except ValueError as err:
        log(f"::error::Could not read data/news.json; nothing was changed: {err}")
        return 2
    fresh, failed = {}, set()
    for n, (feed_id, feed) in enumerate(FEEDS.items()):
        if n:
            time.sleep(PAUSE)
        try:
            fresh[feed_id] = normalize(ADAPTERS[feed["adapter"]](feed, get), feed_id, today)
            log(f"{feed['name']}: {len(fresh[feed_id])} usable items")
        except Exception as err:  # one bad source must not take down the others
            failed.add(feed_id)
            log(f"::warning::{feed['name']} failed, keeping its previous items: {err}")
    if len(failed) == len(FEEDS):
        log("::error::Every news source failed; nothing was changed")
        return 1
    try:
        data = build(previous, fresh, failed, today)
        validate(data, today)
        page = page_path.read_text(encoding="utf8")
        page = fill(page, "edition", render_edition(data, today))
        page = fill(page, "news", "\n" + render_news(data, today) + "\n")
        check_page(page)
    except (ValueError, KeyError, TypeError, AttributeError) as err:
        log(f"::error::News did not pass validation; nothing was changed: {err}")
        return 2
    write_atomic(data_path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    write_atomic(page_path, page)
    per_source = {}
    for item in data["items"]:
        per_source[item["source"]] = per_source.get(item["source"], 0) + 1
    log(f"Wrote {len(data['items'])} items: " + ", ".join(f"{k} {v}" for k, v in per_source.items()))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    return run()


if __name__ == "__main__":
    sys.exit(main())
