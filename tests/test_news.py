"""Offline tests for the News page. They read fixture feeds and never touch the network."""
import datetime
import html
import json
import re
import shutil
import sys
import tempfile
import unittest
import urllib.parse
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures" / "news"
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_news  # noqa: E402

TODAY = datetime.date(2026, 11, 19)
ALLOWED = set().union(*(f["link_hosts"] for f in fetch_news.FEEDS.values()))
CAVEAT = ("These are links to outside reporting and new papers.",
          "Neuroscope has not checked them",
          "a headline can overstate what a study found",
          "educational only and is not medical or veterinary advice")


def no_network(*args, **kwargs):
    raise AssertionError("the news tests must never use the network")


_patches = [mock.patch.object(urllib.request, "urlopen", no_network),
            mock.patch.object(urllib.request.OpenerDirector, "open", no_network)]


def setUpModule():
    for p in _patches:
        p.start()


def tearDownModule():
    for p in _patches:
        p.stop()


def fixture(name):
    return (FIX / name).read_bytes()


class FakeWeb:
    """Answers fetch_news's requests from fixture files; records every URL asked for."""

    def __init__(self, **override):
        self.files = {"esearch": "pubmed_esearch.json", "esummary": "pubmed_esummary.json",
                      "elifesciences.org": "elife.xml", "news.mit.edu": "mit.xml"}
        self.files.update(override)
        self.asked = []

    def __call__(self, url, hosts):
        fetch_news.check_url(url, hosts)
        self.asked.append(url)
        parts = urllib.parse.urlsplit(url)
        key = parts.path.rsplit("/", 1)[-1].split(".")[0] if parts.hostname.startswith("eutils") else parts.hostname
        name = self.files[key]
        if name is None:
            raise OSError("source down")
        return fixture(name)


def page_links(page):
    return re.findall(r'<a\b[^>]*\bhref="([^"]*)"', page)


def head_of(page):
    return page[:page.index("<style")]


class Sandbox(unittest.TestCase):
    """A copy of news.html and data/ in a temporary folder."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        (self.tmp / "data").mkdir()
        shutil.copy(ROOT / "news.html", self.tmp / "news.html")
        sleep = mock.patch.object(fetch_news.time, "sleep")
        sleep.start()
        self.addCleanup(sleep.stop)
        self.log = []

    def run_fetch(self, web=None, previous=None):
        if previous is not None:
            (self.tmp / "data" / "news.json").write_text(json.dumps(previous), encoding="utf8")
        self.web = web or FakeWeb()
        return fetch_news.run(root=self.tmp, get=self.web, today=TODAY, log=self.log.append)

    def data(self):
        return json.loads((self.tmp / "data" / "news.json").read_text(encoding="utf8"))

    def page(self):
        return (self.tmp / "news.html").read_text(encoding="utf8")


class Adapters(Sandbox):
    def test_rss2_parses(self):
        entries = fetch_news.parse_feed(fixture("elife.xml"))
        self.assertEqual(len(entries), 12)
        self.assertEqual(entries[0]["when"], datetime.datetime(2026, 11, 18, tzinfo=datetime.timezone.utc))
        self.assertIn("<i>Mus musculus</i>", entries[0]["title"])
        self.assertEqual(entries[8]["when"].date(), datetime.date(2026, 11, 10))  # dc:date

    def test_rdf_parses(self):
        entries = fetch_news.parse_feed(fixture("rdf.xml"))
        self.assertEqual([e["url"] for e in entries], ["https://elifesciences.org/articles/910001",
                                                       "https://elifesciences.org/articles/910002"])
        self.assertEqual([e["when"].date().isoformat() for e in entries], ["2026-11-17", "2026-11-12"])

    def test_atom_parses(self):
        entries = fetch_news.parse_feed(fixture("atom.xml"))
        self.assertEqual(entries[0]["url"], "https://news.mit.edu/2026/atom-entry-1118")  # alternate, not self
        self.assertEqual(entries[0]["when"].date().isoformat(), "2026-11-18")  # published before updated
        self.assertEqual(entries[1]["url"], "https://news.mit.edu/2026/atom-entry-1110")
        self.assertEqual(fetch_news.clean_title(entries[0]["title"]), "An Atom entry about astrocytes")

    def test_pubmed_parses(self):
        web = FakeWeb()
        entries = fetch_news.fetch_pubmed(fetch_news.FEEDS["pubmed"], web)
        items = fetch_news.normalize(entries, "pubmed", TODAY)
        self.assertEqual([(i["source"], i["url"], i["date"]) for i in items], [
            ("neuron", "https://pubmed.ncbi.nlm.nih.gov/90000001/", "2026-11-17"),
            ("nat-rev-neurosci", "https://pubmed.ncbi.nlm.nih.gov/90000002/", "2026-11-09"),
            ("annu-rev-neurosci", "https://pubmed.ncbi.nlm.nih.gov/90000006/", "2026-10-28")])
        self.assertEqual(items[0]["title"], "A made-up review of place cells")
        # Trends Cogn Sci, preprints and undated records are left out.
        self.assertNotIn("Trends Cogn Sci", fetch_news.pubmed_term())
        for url in web.asked:
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            self.assertEqual(query["tool"], ["neuroscope-news"])
            self.assertNotIn("email", query)
        search = urllib.parse.parse_qs(urllib.parse.urlsplit(web.asked[0]).query)
        self.assertIn("review[pt] NOT preprint[pt]", search["term"][0])
        self.assertEqual((search["datetype"], search["reldate"]), (["edat"], ["28"]))

    def test_entity_declarations_are_refused(self):
        with self.assertRaises(ValueError):
            fetch_news.parse_feed(fixture("entities.xml"))

    def test_malformed_xml_raises(self):
        with self.assertRaises(Exception):
            fetch_news.parse_feed(fixture("malformed.xml"))


class Cleaning(unittest.TestCase):
    def items(self):
        entries = fetch_news.parse_feed(fixture("elife.xml"))
        return fetch_news.normalize(entries, "elife", TODAY)

    def test_javascript_and_off_host_links_are_dropped(self):
        urls = [i["url"] for i in self.items()]
        self.assertTrue(urls)
        for url in urls:
            self.assertTrue(url.startswith("https://elifesciences.org/"), url)
        hosts = {"elifesciences.org"}
        for bad in ["javascript:alert(1)", "https://example.com/a", "http://elifesciences.org/a",
                    "https://elifesciences.org.evil.test/a", "https://user@elifesciences.org/a",
                    "https://elifesciences.org:8443/a", "data:text/html,hi", "//elifesciences.org/a", ""]:
            with self.subTest(url=bad):
                self.assertIsNone(fetch_news.clean_url(bad, hosts))

    def test_tracking_parameters_are_removed(self):
        self.assertEqual(self.items()[0]["url"], "https://elifesciences.org/articles/900001")
        self.assertEqual(fetch_news.clean_url("https://news.mit.edu/a?rss=yes&id=2#top", {"news.mit.edu"}),
                         "https://news.mit.edu/a?id=2")

    def test_html_in_titles_is_stripped(self):
        titles = [i["title"] for i in self.items()]
        self.assertIn("Sleep spindles in Mus musculus track a test variable", titles)
        self.assertIn("Tricky alert(1) title & more", titles)
        for title in titles:
            self.assertNotRegex(title, r"<[a-z/]")
        self.assertEqual(len(fetch_news.clean_title("x" * 500)), 200)

    def test_undated_future_old_corrections_and_duplicates_are_dropped(self):
        items = fetch_news.select(self.items(), TODAY)
        titles = [i["title"] for i in items]
        self.assertEqual(titles, ["Sleep spindles in Mus musculus track a test variable",
                                  "Tricky alert(1) title & more", "Grid cells in a test arena"])

    def test_items_keep_only_four_fields(self):
        for item in self.items():
            self.assertEqual(set(item), {"source", "title", "url", "date"})

    def test_caps_per_source_per_week_and_in_total(self):
        def item(source, n, day):
            host = "elifesciences.org" if source == "elife" else "pubmed.ncbi.nlm.nih.gov"
            return {"source": source, "title": f"T{source}{n}", "url": f"https://{host}/{source}/{n}/",
                    "date": day.isoformat()}
        many = [item("elife", n, TODAY - datetime.timedelta(days=n % 3)) for n in range(9)]
        chosen = fetch_news.select(many, TODAY)
        self.assertEqual(len(chosen), 5)  # 16-19 Nov share one ISO week
        lots = [item(sid, n, TODAY - datetime.timedelta(days=d))
                for sid in ["elife", "neuron", "nat-rev-neurosci"] for d in range(28) for n in (d * 10, d * 10 + 1)]
        chosen = fetch_news.select(lots, TODAY)
        self.assertEqual(len(chosen), 40)
        per = {}
        for i in chosen:
            key = (i["source"], datetime.date.fromisoformat(i["date"]).isocalendar()[:2])
            per[key] = per.get(key, 0) + 1
        self.assertLessEqual(max(per.values()), 5)
        self.assertEqual(chosen, sorted(chosen, key=lambda i: (i["date"], i["title"]), reverse=True))

    def test_output_is_escaped(self):
        data = {"updated": TODAY.isoformat(), "sources": [], "items": [
            {"source": "elife", "title": 'p < 0.05 & "x" > y', "url": "https://elifesciences.org/articles/1?a=1&b=2",
             "date": "2026-11-18"}]}
        data["sources"] = [{"id": s, "name": v["name"], "kind": v["kind"], "last_ok": "2026-11-19", "status": "ok"}
                           for s, v in fetch_news.SOURCES.items()]
        out = fetch_news.render_news(data, TODAY)
        self.assertIn("p &lt; 0.05 &amp; &quot;x&quot; &gt; y", out)
        self.assertIn('href="https://elifesciences.org/articles/1?a=1&amp;b=2"', out)
        self.assertNotIn("p < 0.05", out)

    def test_fetching_refuses_other_hosts_and_plain_http(self):
        for url in ["http://news.mit.edu/feed", "https://example.com/feed", "file:///etc/passwd"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                fetch_news.fetch_url(url, {"news.mit.edu"})


class Runs(Sandbox):
    def test_run_writes_the_list_and_page(self):
        self.assertEqual(self.run_fetch(), 0)
        data, page = self.data(), self.page()
        self.assertEqual(len(data["items"]), 8)
        for item in data["items"]:
            self.assertEqual(set(item), {"source", "title", "url", "date"})
        for source in data["sources"]:
            self.assertEqual(set(source), {"id", "name", "kind", "last_ok", "status"})
            self.assertEqual((source["status"], source["last_ok"]), ("ok", "2026-11-19"))
        for href in page_links(page):
            parts = urllib.parse.urlsplit(html.unescape(href))
            if parts.scheme:
                self.assertEqual(parts.scheme, "https")
                self.assertIn(parts.hostname, ALLOWED)
        for tag in re.findall(r'<a\b[^>]*href="https://[^>]*>', page):
            self.assertIn('rel="noopener noreferrer"', tag)
        self.assertIn("Tricky alert(1) title &amp; more", page)
        self.assertNotIn("must never be stored", page + json.dumps(data))
        self.assertIn("<!--news:start-->", page)
        self.assertIn("<span>Updated Thursday 19 November 2026</span>", page)
        self.assertEqual(len(self.web.asked), 4)

    def test_a_failed_source_keeps_its_previous_items(self):
        previous = {"updated": "2026-11-12", "sources": [
            {"id": "elife", "name": "eLife", "kind": fetch_news.RESEARCH, "last_ok": "2026-11-12", "status": "ok"}],
            "items": [{"source": "elife", "title": "Kept from last week", "url": "https://elifesciences.org/articles/5",
                       "date": "2026-11-11"},
                      {"source": "elife", "title": "Too old now", "url": "https://elifesciences.org/articles/6",
                       "date": "2026-10-01"}]}
        self.assertEqual(self.run_fetch(FakeWeb(**{"elifesciences.org": "malformed.xml"}), previous), 0)
        data = self.data()
        elife = [i["title"] for i in data["items"] if i["source"] == "elife"]
        self.assertEqual(elife, ["Kept from last week"])
        status = {s["id"]: s for s in data["sources"]}
        self.assertEqual((status["elife"]["status"], status["elife"]["last_ok"]), ("failed", "2026-11-12"))
        self.assertEqual(status["neuron"]["status"], "ok")
        self.assertIn("Could not be reached on this update", self.page())
        self.assertTrue(any("eLife failed" in line for line in self.log))

    def test_every_source_failing_exits_non_zero_and_writes_nothing(self):
        previous = {"updated": "2026-11-12", "sources": [], "items": []}
        before_page = self.page()
        down = FakeWeb(esearch=None, esummary=None, **{"elifesciences.org": None, "news.mit.edu": None})
        self.assertNotEqual(self.run_fetch(down, previous), 0)
        self.assertEqual(self.page(), before_page)
        self.assertEqual(self.data(), previous)

    def test_failed_validation_exits_non_zero_and_writes_nothing(self):
        (self.tmp / "news.html").write_text("<!doctype html><p>no markers</p>", encoding="utf8")
        self.assertNotEqual(self.run_fetch(), 0)
        self.assertFalse((self.tmp / "data" / "news.json").exists())
        bad = {"updated": "2026-11-19", "sources": [], "items": [
            {"source": "elife", "title": "x", "url": "https://elifesciences.org/1", "date": "2026-11-18", "summary": "no"}]}
        with self.assertRaises(ValueError):
            fetch_news.validate(bad, TODAY)

    def test_a_poisoned_previous_item_is_dropped(self):
        previous = {"updated": "2026-11-12", "sources": [], "items": [
            {"source": "elife", "title": "Evil", "url": "javascript:alert(1)", "date": "2026-11-11"},
            {"source": "mit-news", "title": "Wrong host", "url": "https://elifesciences.org/articles/7", "date": "2026-11-11"}]}
        self.assertEqual(self.run_fetch(previous=previous), 0)
        self.assertNotIn("javascript:", self.page())
        self.assertNotIn("Wrong host", self.page())


def valid_data(**changes):
    """A small news.json that passes validation, with top-level changes applied."""
    data = {"updated": TODAY.isoformat(),
            "sources": [{"id": sid, "name": v["name"], "kind": v["kind"], "last_ok": TODAY.isoformat(), "status": "ok"}
                        for sid, v in fetch_news.SOURCES.items()],
            "items": [{"source": "elife", "title": "A fine title", "url": "https://elifesciences.org/articles/1",
                       "date": "2026-11-18"}]}
    data.update(changes)
    return data


class FakeResponse:
    def __init__(self, body, url):
        self.body, self.url, self.asked = body, url, 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def geturl(self):
        return self.url

    def read(self, n=-1):
        n = len(self.body) if n is None or n < 0 else n
        out, self.body = self.body[:n], self.body[n:]
        self.asked += len(out)
        return out


class FakeOpener:
    def __init__(self, body=b"<rss/>", final_url=None):
        self.body, self.final_url, self.calls = body, final_url, []

    def open(self, req, timeout=None):
        self.calls.append((req.full_url, timeout, dict(req.header_items())))
        self.response = FakeResponse(self.body, self.final_url or req.full_url)
        return self.response


class Fetching(unittest.TestCase):
    """fetch_url's limits, with a fake opener in place of the network."""

    def fetch(self, opener, url="https://news.mit.edu/feed.xml"):
        with mock.patch.object(fetch_news.urllib.request, "build_opener", return_value=opener) as build, \
                mock.patch.object(fetch_news.time, "sleep"):
            try:
                return fetch_news.fetch_url(url, {"news.mit.edu"})
            finally:
                self.handlers = build.call_args.args if build.called else ()

    def test_timeout_user_agent_and_redirect_guard_are_used(self):
        opener = FakeOpener(b"<rss/>")
        self.assertEqual(self.fetch(opener), b"<rss/>")
        url, timeout, headers = opener.calls[0]
        self.assertEqual(timeout, fetch_news.TIMEOUT)
        self.assertEqual(headers.get("User-agent"), "neuroscope-news/1.0")
        guards = [h for h in self.handlers if isinstance(h, fetch_news._Redirects)]
        self.assertEqual([g.hosts for g in guards], [{"news.mit.edu"}])

    def test_large_responses_are_refused_without_reading_them_all(self):
        opener = FakeOpener(b"x" * (fetch_news.MAX_BYTES * 3))
        with self.assertRaises(ValueError):
            self.fetch(opener)
        self.assertLessEqual(opener.response.asked, fetch_news.MAX_BYTES + 1)

    def test_a_final_url_off_the_allowlist_is_refused(self):
        with self.assertRaises(ValueError):
            self.fetch(FakeOpener(final_url="https://example.com/feed.xml"))

    def test_redirects_must_stay_on_allowed_https_hosts(self):
        guard = fetch_news._Redirects({"news.mit.edu"})
        req = urllib.request.Request("https://news.mit.edu/feed.xml")
        for target in ["https://example.com/feed.xml", "http://news.mit.edu/feed.xml", "file:///etc/passwd"]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                guard.redirect_request(req, None, 302, "Found", {}, target)
        self.assertIsNotNone(guard.redirect_request(req, None, 302, "Found", {}, "https://news.mit.edu/new.xml"))

    def test_a_slow_response_hits_the_deadline(self):
        clock = iter(range(0, 10_000, 40))
        opener = FakeOpener(b"x" * (fetch_news.CHUNK * 4))
        with mock.patch.object(fetch_news.time, "monotonic", lambda: next(clock)):
            with self.assertRaises(TimeoutError):
                self.fetch(opener)


class Hardening(Sandbox):
    def test_entities_in_utf16_are_refused(self):
        with self.assertRaises(ValueError):
            fetch_news.parse_feed(fixture("entities.xml").decode().replace('<?xml version="1.0"?>', '<?xml version="1.0" encoding="UTF-16"?>').encode("utf-16"))

    def test_each_entity_guard_works_on_its_own(self):
        data = fixture("entities.xml")
        with mock.patch.object(fetch_news.re, "search", return_value=None), self.assertRaises(ValueError):
            fetch_news.refuse_entities(data)  # expat's declaration handler alone
        with mock.patch.object(fetch_news.expat, "ParserCreate", return_value=mock.Mock()), \
                self.assertRaises(ValueError):
            fetch_news.refuse_entities(data.decode().encode("utf-16"))  # the byte check alone

    def test_normalize_keeps_each_feed_on_its_own_hosts_and_dates(self):
        when = datetime.datetime(2026, 11, 18, tzinfo=datetime.timezone.utc)
        entries = [{"title": "Wrong host", "url": "https://elifesciences.org/articles/1", "when": when},
                   {"title": "Future", "url": "https://news.mit.edu/a", "when": when + datetime.timedelta(days=3)},
                   {"title": "Old", "url": "https://news.mit.edu/b", "when": when - datetime.timedelta(days=40)},
                   {"title": "Fine", "url": "https://news.mit.edu/c", "when": when}]
        self.assertEqual([i["title"] for i in fetch_news.normalize(entries, "mit-news", TODAY)], ["Fine"])

    def pubmed_web(self, esearch, esummary=None):
        def get(url, hosts):
            fetch_news.check_url(url, hosts)
            return json.dumps(esearch if "esearch" in url else esummary).encode()
        return get

    def test_pubmed_drops_non_reviews_and_errata_and_refuses_odd_ids(self):
        hist = [{"pubstatus": "entrez", "date": "2026/11/17 06:00"}]
        summary = {"result": {"uids": ["1", "2", "3"],
                              "1": {"source": "Neuron", "title": "An article", "pubtype": ["Journal Article"], "history": hist},
                              "2": {"source": "Neuron", "title": "Erratum", "pubtype": ["Published Erratum", "Review"], "history": hist},
                              "3": {"source": "Neuron", "title": "A review", "pubtype": ["Review"], "history": hist}}}
        entries = fetch_news.fetch_pubmed(fetch_news.FEEDS["pubmed"],
                                          self.pubmed_web({"esearchresult": {"idlist": ["1", "2", "3"]}}, summary))
        self.assertEqual([e["title"] for e in entries], ["A review"])
        with self.assertRaises(ValueError):
            fetch_news.fetch_pubmed(fetch_news.FEEDS["pubmed"],
                                    self.pubmed_web({"esearchresult": {"idlist": ["1", "2&db=x"]}}))

    def test_an_empty_week_still_publishes_a_page(self):
        def get(url, hosts):
            fetch_news.check_url(url, hosts)
            if "esearch" in url:
                return b'{"esearchresult": {"idlist": []}}'
            return fixture("rdf.xml").replace(b"2026-11-1", b"2025-11-1")
        self.assertEqual(self.run_fetch(get), 0)
        self.assertEqual(self.data()["items"], [])
        self.assertIn("Nothing new from these sources", self.page())
        self.assertIn("<span>0 headlines from 0 sources</span>", self.page())

    def test_bad_previous_titles_dates_and_last_ok_are_dropped(self):
        previous = {"updated": "2026-11-12", "sources": [
            {"id": "elife", "name": "eLife", "kind": fetch_news.RESEARCH, "last_ok": "<b>soon</b>", "status": "ok"}],
            "items": [{"source": "elife", "title": "<script>x</script>", "url": "https://elifesciences.org/articles/8", "date": "2026-11-11"},
                      {"source": "elife", "title": ["not", "text"], "url": "https://elifesciences.org/articles/9", "date": "2026-11-11"},
                      {"source": "elife", "title": "Odd date", "url": "https://elifesciences.org/articles/10", "date": "20261111"},
                      {"source": "elife", "title": "Kept", "url": "https://elifesciences.org/articles/11", "date": "2026-11-11"}]}
        self.assertEqual(self.run_fetch(FakeWeb(**{"elifesciences.org": None}), previous), 0)
        data = self.data()
        self.assertEqual([i["title"] for i in data["items"] if i["source"] == "elife"], ["Kept"])
        self.assertIsNone({s["id"]: s for s in data["sources"]}["elife"]["last_ok"])

    def test_unreadable_previous_data_exits_non_zero_and_writes_nothing(self):
        (self.tmp / "data" / "news.json").write_text("{not json", encoding="utf8")
        before = self.page()
        self.assertNotEqual(self.run_fetch(), 0)
        self.assertEqual(self.page(), before)
        self.assertEqual((self.tmp / "data" / "news.json").read_text(encoding="utf8"), "{not json")

    def test_invalid_data_is_never_written(self):
        bad = valid_data()
        bad["items"][0]["summary"] = "An abstract"
        with mock.patch.object(fetch_news, "build", return_value=bad):
            self.assertEqual(self.run_fetch(), 2)
        self.assertFalse((self.tmp / "data" / "news.json").exists())

    def test_a_page_that_fails_the_link_check_is_never_written(self):
        before = self.page()
        with mock.patch.object(fetch_news, "render_news", return_value='<a href="https://example.com/">x</a>'):
            self.assertEqual(self.run_fetch(), 2)
        self.assertEqual(self.page(), before)
        self.assertFalse((self.tmp / "data" / "news.json").exists())

    def test_check_page_refuses_scripts_and_off_list_links(self):
        fetch_news.check_page('<a href="about.html">ok</a><a href="https://news.mit.edu/a">ok</a>')
        for bad in ['<script>alert(1)</script>', '<a href="javascript:alert(1)">x</a>', '<img src="x">',
                    '<a href="https://example.com/">x</a>', '<a href="http://news.mit.edu/a">x</a>',
                    '<iframe src="https://news.mit.edu/"></iframe>']:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                fetch_news.check_page(bad)

    def test_validate_refuses_each_kind_of_bad_record(self):
        fetch_news.validate(valid_data(), TODAY)

        def item(**kw):
            return valid_data(items=[dict(valid_data()["items"][0], **kw)])
        cases = {"extra item key": item(summary="x"),
                 "off-host link": item(url="https://example.com/a"),
                 "wrong host for source": item(url="https://news.mit.edu/a"),
                 "javascript link": item(url="javascript:alert(1)"),
                 "tag in title": item(title="<b>x</b>"),
                 "empty title": item(title=""),
                 "long title": item(title="x" * 201),
                 "future date": item(date="2026-11-20"),
                 "old date": item(date="2026-10-01"),
                 "odd date": item(date="20261118"),
                 "unknown source": item(source="transmitter"),
                 "too many": valid_data(items=valid_data()["items"] * 41),
                 "extra top key": dict(valid_data(), note="x"),
                 "stale updated": valid_data(updated="2026-11-12"),
                 "missing source": valid_data(sources=valid_data()["sources"][1:])}
        renamed = valid_data()
        renamed["sources"][0]["name"] = "<b>Someone else</b>"
        cases["renamed source"] = renamed
        bad_ok = valid_data()
        bad_ok["sources"][0]["last_ok"] = "tomorrow"
        cases["bad last_ok"] = bad_ok
        for name, data in cases.items():
            with self.subTest(name), self.assertRaises((ValueError, KeyError, TypeError)):
                fetch_news.validate(data, TODAY)


class PublishedPage(unittest.TestCase):
    """The committed news.html and data/news.json."""

    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / "news.html").read_text(encoding="utf8")
        cls.data = json.loads((ROOT / "data" / "news.json").read_text(encoding="utf8"))

    def test_news_json_items_have_exactly_four_keys(self):
        self.assertTrue(self.data["items"])
        for item in self.data["items"]:
            self.assertEqual(set(item), {"source", "title", "url", "date"})
        for source in self.data["sources"]:
            self.assertEqual(set(source), {"id", "name", "kind", "last_ok", "status"})

    def test_every_link_is_https_on_an_allowed_host_or_internal(self):
        for href in page_links(self.page):
            with self.subTest(href=href):
                if href.startswith("#") or re.fullmatch(r"[a-z_-]+\.html(#[\w-]*)?", href):
                    continue
                parts = urllib.parse.urlsplit(html.unescape(href))
                self.assertEqual(parts.scheme, "https")
                self.assertIn(parts.hostname, ALLOWED)
        for tag in re.findall(r'<a\b[^>]*href="https://[^>]*>', self.page):
            self.assertIn('rel="noopener noreferrer"', tag)

    def test_caveat_is_near_the_top(self):
        box = re.search(r'<div class="caveat"[^>]*>(.*?)</div>', self.page, re.S)
        self.assertIsNotNone(box)
        text = " ".join(box.group(1).split())
        for part in CAVEAT:
            self.assertIn(part, text)
        self.assertLess(self.page.index('class="caveat"'), self.page.index("<!--news:start-->"))

    def test_head(self):
        head, base = head_of(self.page), "https://aiku0212.github.io/neuro-site/"
        self.assertTrue(self.page.startswith('<!doctype html>\n<html lang="en">\n<meta charset="utf-8">'))
        self.assertIn('<meta name="viewport" content="width=device-width,initial-scale=1">', head)
        self.assertIn("<title>Neuroscience News · Neuroscope</title>", head)
        self.assertIn('<meta property="og:title" content="Neuroscience News · Neuroscope">', head)
        desc = re.search(r'<meta name="description" content="([^"]+)">', head).group(1)
        self.assertIn(f'<meta property="og:description" content="{desc}">', head)
        for line in ['<meta property="og:type" content="website">',
                     '<meta property="og:site_name" content="Neuroscope">',
                     f'<meta property="og:url" content="{base}news.html">',
                     f'<meta property="og:image" content="{base}assets/og.png">',
                     '<meta property="og:image:width" content="1200">',
                     '<meta property="og:image:height" content="630">',
                     '<meta name="twitter:card" content="summary_large_image">',
                     '<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">']:
            self.assertIn(line, head)
        self.assertRegex(head, r'<meta property="og:image:alt" content="[^"]{20,}">')
        self.assertLess(self.page.index("</style>"), self.page.index('href="assets/atlas.css"'))

    def test_nav_has_eleven_tabs_with_learn_current(self):
        nav = re.search(r'<nav class="tabs".*?</nav>', self.page, re.S).group(0)
        tabs = re.findall(r'<a class="tab" href="([^"]+)"', nav)
        self.assertEqual(tabs, ["app.html", "app.html#analyze", "spike.html", "synapse.html", "pharma.html",
                                "index.html", "comparative.html", "timecells.html", "learn.html",
                                "references.html", "about.html"])
        self.assertIn('<a class="tab" href="learn.html" aria-current="true">Learn</a>', nav)
        self.assertEqual(nav.count("aria-current"), 1)

    def test_one_h1_inside_main(self):
        self.assertEqual(len(re.findall(r"<h1\b", self.page)), 1)
        start, end = self.page.index("<main"), self.page.index("</main>")
        self.assertTrue(start < self.page.index("<h1") < end)
        self.assertEqual(self.page.count("<main"), 1)

    def test_footer(self):
        footer = re.search(r"<footer>.*?</footer>", self.page, re.S).group(0)
        self.assertIn("Educational only. Not medical or veterinary advice.", footer)
        self.assertIn('href="about.html"', footer)
        self.assertIn('href="references.html"', footer)

    def test_no_scripts_images_embeds_or_summaries(self):
        lower = self.page.lower()
        for tag in ("<script", "<img", "<iframe", "<embed", "<object", "<video", "<audio"):
            self.assertNotIn(tag, lower)
        self.assertEqual(self.page.count("<!--news:start-->"), 1)
        self.assertEqual(self.page.count("<!--news:end-->"), 1)
        self.assertEqual(self.page.count("<!--edition:start-->"), 1)

    def test_fixed_text_follows_the_writing_standard(self):
        fixed = re.sub(r"<!--news:start-->.*?<!--news:end-->", "", self.page, flags=re.S)
        fixed = re.sub(r"<style>.*?</style>", "", fixed, flags=re.S)
        text = html.unescape(re.sub(r"<[^>]+>", " ", fixed))
        self.assertNotIn("—", text)
        self.assertNotIn(";", text)
        self.assertNotIn("—", self.page)

    def test_the_committed_list_passes_validation(self):
        fetch_news.validate(self.data, datetime.date.fromisoformat(self.data["updated"]))
        fetch_news.check_page(self.page)


class Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wf = (ROOT / ".github" / "workflows" / "weekly-news.yml").read_text(encoding="utf8")
        cls.daily = (ROOT / ".github" / "workflows" / "daily-citations.yml").read_text(encoding="utf8")

    def test_least_privilege_and_pinned(self):
        top, jobs = self.wf.split("\njobs:", 1)
        self.assertIn("permissions:\n  contents: read", top)
        self.assertNotIn("write", top)
        self.assertNotIn("pages: write", self.wf)
        self.assertNotIn("id-token", self.wf)
        self.assertEqual(re.findall(r"^\s+(\w[\w-]*): write", jobs, re.M), ["contents", "issues"])
        uses = re.findall(r"uses: (\S+)", self.wf)
        self.assertTrue(uses)
        for use in uses:
            self.assertRegex(use, r"@[0-9a-f]{40}$")
        for action in ("actions/checkout", "actions/setup-python"):
            line = re.search(rf"- uses: {action}@\S+  # v\d", self.daily).group(0)
            self.assertIn(line, self.wf)

    def test_schedule_concurrency_and_steps(self):
        self.assertIn('cron: "43 8 * * 1"', self.wf)
        self.assertIn("workflow_dispatch:", self.wf)
        self.assertIn("group: daily-citations\n  cancel-in-progress: false", self.wf)
        self.assertIn("timeout-minutes: 10", self.wf)
        steps = [self.wf.index("python -m unittest"), self.wf.index("python scripts/fetch_news.py"),
                 self.wf.index("git push")]
        self.assertEqual(steps, sorted(steps))
        self.assertEqual(re.findall(r"git add (.+)", self.wf), ["data/news.json news.html"])
        self.assertIn('git config user.name "github-actions[bot]"', self.wf)
        self.assertNotIn("deploy", self.wf.split("\njobs:", 1)[1].lower().replace("does not deploy", ""))

    def test_failure_is_reported(self):
        job = self.wf[self.wf.index("  report-failure:"):]
        self.assertIn("needs: [update]", job)
        self.assertIn("if: failure() || cancelled() || needs.update.result != 'success'", job)
        self.assertIn("issues: write", job)
        self.assertIn("--label news-failed", job)
        self.assertIn('--title "News update failed"', job)


if __name__ == "__main__":
    unittest.main()
