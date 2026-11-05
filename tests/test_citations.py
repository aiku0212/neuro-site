import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import apply_review  # noqa: E402
import build_refs  # noqa: E402
import daily_check  # noqa: E402

TODAY = "2026-11-06"


def ref(**extra):
    base = {"group": "bdnf", "title": "A paper", "authors": "Smith et al.", "year": 2020, "journal": "J",
            "doi": "10.1/a", "pmid": "1", "citations": 5, "updates": [],
            "verification": {"status": "confirmed", "reasons": [], "checked": "2026-01-01"}}
    base.update(extra)
    return base


class CheckReferences(unittest.TestCase):
    def run_check(self, refs, record=None, notices=(), summaries=None, record_error=None):
        rec = mock.Mock(side_effect=record_error) if record_error else mock.Mock(return_value=record)
        with mock.patch.object(daily_check, "crossref_record", rec), \
                mock.patch.object(daily_check, "crossref_notices", return_value=list(notices)), \
                mock.patch.object(daily_check, "pubmed_summaries", return_value=summaries or {}), \
                mock.patch.object(daily_check.time, "sleep"):
            return daily_check.check_references(refs, TODAY)

    def test_updates_count(self):
        refs = [ref()]
        alerts, errors = self.run_check(refs, {"is-referenced-by-count": 9})
        self.assertEqual((refs[0]["citations"], alerts, errors), (9, [], []))
        self.assertEqual(refs[0]["verification"]["checked"], TODAY)

    def test_failure_keeps_last_good_data(self):
        refs = [ref()]
        alerts, errors = self.run_check(refs, record_error=OSError("down"))
        self.assertEqual(refs[0]["citations"], 5)
        self.assertEqual(refs[0]["verification"]["checked"], "2026-01-01")
        self.assertEqual(len(errors), 1)

    def test_missing_record_is_an_error_not_a_change(self):
        refs = [ref()]
        _, errors = self.run_check(refs, None)
        self.assertEqual(refs[0]["citations"], 5)
        self.assertEqual(len(errors), 1)

    def test_new_retraction_alerts_once(self):
        refs = [ref()]
        notice = {"type": "retraction", "notice_doi": "10.1/n"}
        alerts, _ = self.run_check(refs, {"is-referenced-by-count": 5}, [notice])
        self.assertEqual(len(alerts), 1)
        alerts, _ = self.run_check(refs, {"is-referenced-by-count": 5}, [notice])
        self.assertEqual(alerts, [])
        self.assertEqual(len(refs[0]["updates"]), 1)

    def test_pubmed_retraction_detected_without_duplicating_crossref(self):
        refs = [ref()]
        summaries = {"1": {"pubtype": ["Journal Article", "Retracted Publication"]}}
        alerts, _ = self.run_check(refs, {"is-referenced-by-count": 5}, [], summaries)
        self.assertEqual(alerts[0]["type"], "retraction")
        alerts, _ = self.run_check(refs, {"is-referenced-by-count": 5}, [], summaries)
        self.assertEqual(alerts, [])


class Discover(unittest.TestCase):
    def run_discover(self, refs, queue, summaries):
        search = {"esearchresult": {"idlist": list(summaries)}}
        with mock.patch.object(daily_check, "get_json", return_value=search), \
                mock.patch.object(daily_check, "pubmed_summaries",
                                  side_effect=lambda ids: {i: summaries[i] for i in ids}), \
                mock.patch.object(daily_check.time, "sleep"):
            return daily_check.discover(refs, queue, {"bdnf": "term"})

    @staticmethod
    def summary(doi="10.1/new"):
        ids = [{"idtype": "doi", "value": doi}] if doi else []
        return {"title": "New", "authors": [{"name": "Lee AB"}, {"name": "Kim C"}],
                "fulljournalname": "J", "pubdate": "2026 Nov", "articleids": ids}

    def test_queues_once_and_never_publishes(self):
        refs, queue = [ref()], {"pending": [], "seen": []}
        items, _ = self.run_discover(refs, queue, {"2": self.summary()})
        self.assertEqual(items[0]["authors"], "Lee et al.")
        self.assertEqual(len(refs), 1)
        items, _ = self.run_discover(refs, queue, {"2": self.summary()})
        self.assertEqual(items, [])
        self.assertEqual(len(queue["pending"]), 1)

    def test_skips_cited_paper(self):
        queue = {"pending": [], "seen": []}
        self.run_discover([ref()], queue, {"2": self.summary("10.1/A")})
        self.assertEqual(queue["pending"], [])

    def test_no_doi_retried_later(self):
        queue = {"pending": [], "seen": []}
        self.run_discover([ref()], queue, {"2": self.summary("")})
        self.assertEqual(queue["seen"], [])


class Review(unittest.TestCase):
    ITEM = {"pmid": "2", "doi": "10.1/new", "group": "bdnf", "title": "New", "authors": "Lee et al.",
            "journal": "J", "year": 2026}

    def render(self):
        queue = {"pending": [dict(self.ITEM)], "seen": ["2"]}
        return daily_check.render_issue(queue, [], [], TODAY)

    def test_unticked_stays_pending(self):
        self.assertEqual(apply_review.parse_decisions(self.render()), {})

    def test_approve_round_trip(self):
        body = self.render().replace("- [ ] Approve", "- [x] Approve")
        refs, queue = [], {"pending": [dict(self.ITEM)], "seen": ["2"]}
        counts = apply_review.apply_decisions(refs, queue, apply_review.parse_decisions(body), TODAY)
        self.assertEqual(counts, (1, 0))
        self.assertEqual(refs[0]["doi"], "10.1/new")
        self.assertEqual(queue["pending"], [])

    def test_dismiss_round_trip(self):
        body = self.render().replace("- [ ] Dismiss", "- [x] Dismiss")
        refs, queue = [], {"pending": [dict(self.ITEM)], "seen": ["2"]}
        self.assertEqual(apply_review.apply_decisions(refs, queue, apply_review.parse_decisions(body), TODAY), (0, 1))
        self.assertEqual(refs, [])

    def test_both_ticked_stays_pending(self):
        body = self.render().replace("- [ ] Approve", "- [x] Approve").replace("- [ ] Dismiss", "- [x] Dismiss")
        self.assertEqual(apply_review.parse_decisions(body), {})

    def test_unknown_id_cannot_add_a_reference(self):
        body = "- [x] Approve <!-- review:999:approve -->"
        refs, queue = [], {"pending": [dict(self.ITEM)], "seen": ["2"]}
        apply_review.apply_decisions(refs, queue, apply_review.parse_decisions(body), TODAY)
        self.assertEqual(refs, [])

    def test_title_cannot_ping_or_inject(self):
        item = dict(self.ITEM, title="Hi @someone <img src=x> [link](y)")
        out = daily_check.render_issue({"pending": [item], "seen": []}, [], [], TODAY)
        self.assertNotIn("@someone", out)
        self.assertNotIn("<img", out)


class Build(unittest.TestCase):
    def test_escapes_html(self):
        rec = build_refs.page_record(ref(title="A <b> & C"))
        self.assertEqual(rec["t"], "A &lt;b&gt; &amp; C")

    def test_notice_urls(self):
        rec = build_refs.page_record(ref(updates=[{"type": "retraction", "pmid": "1"},
                                                  {"type": "erratum", "notice_doi": "10.1/n"}]))
        self.assertEqual(rec["upd"][0]["url"], "https://pubmed.ncbi.nlm.nih.gov/1/")
        self.assertEqual(rec["upd"][1]["url"], "https://doi.org/10.1/n")

    def test_index_counts_follow_data(self):
        html = "cite:'Shao et al., <em>Neuron</em> 2021 \\u00B7 458 citations'},"
        data = [ref(authors="Shao et al.", year=2021, citations=628)]
        self.assertIn("\\u00B7 628 citations", build_refs.update_index_counts(html, data))

    def test_index_count_needs_matching_year(self):
        html = "cite:'Shao et al., <em>Neuron</em> 2021 \\u00B7 458 citations'},"
        data = [ref(authors="Shao et al.", year=2025, citations=121)]
        self.assertIn("\\u00B7 458 citations", build_refs.update_index_counts(html, data))


if __name__ == "__main__":
    unittest.main()
