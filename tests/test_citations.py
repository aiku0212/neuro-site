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

    def test_approve_goes_to_reading_list_not_sources(self):
        body = self.render().replace("- [ ] Approve", "- [x] Approve")
        reading, queue = [], {"pending": [dict(self.ITEM)], "seen": ["2"]}
        counts = apply_review.apply_decisions(reading, queue, apply_review.parse_decisions(body), TODAY)
        self.assertEqual(counts, (1, 0))
        self.assertEqual(reading[0]["doi"], "10.1/new")
        self.assertEqual(reading[0]["page_check"], "open")
        self.assertNotIn("verification", reading[0])
        self.assertFalse(reading[0]["preprint"])
        self.assertEqual(queue["pending"], [])

    def test_approving_twice_lists_once(self):
        reading = []
        for _ in range(2):
            queue = {"pending": [dict(self.ITEM)], "seen": ["2"]}
            apply_review.apply_decisions(reading, queue, {"2": "approve"}, TODAY)
        self.assertEqual(len(reading), 1)

    def test_approved_preprint_is_marked_and_never_confirmed(self):
        item = dict(self.ITEM, doi="10.64898/2026.10.21.760719", journal="bioRxiv : the preprint server for biology")
        reading, queue = [], {"pending": [item], "seen": ["2"]}
        apply_review.apply_decisions(reading, queue, {"2": "approve"}, TODAY)
        self.assertTrue(reading[0]["preprint"])
        out = daily_check.render_issue({"pending": [], "seen": []}, [], [], TODAY, reading)
        self.assertIn("preprint, not peer reviewed", out)

    def test_approval_does_not_change_the_sources_page(self):
        refs = [ref()]
        before = [build_refs.page_record(r) for r in refs]
        reading, queue = [], {"pending": [dict(self.ITEM)], "seen": ["2"]}
        apply_review.apply_decisions(reading, queue, {"2": "approve"}, TODAY)
        self.assertEqual([build_refs.page_record(r) for r in refs], before)
        self.assertEqual(len(refs), 1)

    def test_approval_asks_for_a_page_check_until_ticked(self):
        reading, queue = [], {"pending": [dict(self.ITEM, group="psy")], "seen": ["2"]}
        apply_review.apply_decisions(reading, queue, {"2": "approve"}, TODAY)
        out = daily_check.render_issue(queue, [], [], TODAY, reading)
        self.assertIn("pages to check (1)", out)
        self.assertIn("index.html, pharma.html", out)
        ticked = out.replace("- [ ] Page checked", "- [x] Page checked")
        done = apply_review.parse_page_checks(ticked)
        self.assertEqual(apply_review.apply_page_checks(reading, done, TODAY), 1)
        self.assertEqual(reading[0]["page_check"], TODAY)
        self.assertNotIn("pages to check", daily_check.render_issue(queue, [], [], TODAY, reading))

    def test_page_check_for_unknown_paper_does_nothing(self):
        reading = [apply_review.to_reading_entry(self.ITEM, TODAY)]
        self.assertEqual(apply_review.apply_page_checks(reading, {"999"}, TODAY), 0)
        self.assertEqual(reading[0]["page_check"], "open")

    def test_both_ticked_stays_pending(self):
        body = self.render().replace("- [ ] Approve", "- [x] Approve").replace("- [ ] Dismiss", "- [x] Dismiss")
        self.assertEqual(apply_review.parse_decisions(body), {})

    def test_unknown_id_cannot_add_a_reference(self):
        body = "- [x] Approve <!-- review:999:approve -->"
        reading, queue = [], {"pending": [dict(self.ITEM)], "seen": ["2"]}
        apply_review.apply_decisions(reading, queue, apply_review.parse_decisions(body), TODAY)
        self.assertEqual(reading, [])

    def test_title_cannot_ping_or_inject(self):
        item = dict(self.ITEM, title="Hi @someone <img src=x> [link](y)")
        out = daily_check.render_issue({"pending": [item], "seen": []}, [], [], TODAY)
        self.assertNotIn("@someone", out)
        self.assertNotIn("<img", out)


class Preprints(unittest.TestCase):
    def test_detects_preprints_by_type_name_and_doi(self):
        from resolve_dois import is_preprint
        self.assertTrue(is_preprint(crossref_type="posted-content"))
        self.assertTrue(is_preprint(journal="medRxiv : the preprint server for health sciences"))
        self.assertTrue(is_preprint(doi="10.1101/2024.01.02.573000"))
        self.assertTrue(is_preprint(doi="10.64898/2026.10.18.759937"))
        # Cold Spring Harbor journals share the 10.1101 prefix.
        self.assertFalse(is_preprint(doi="10.1101/lm.041012.115", journal="Learning & Memory"))
        self.assertFalse(is_preprint(doi="10.1016/j.neuron.2021.06.008", journal="Neuron",
                                     crossref_type="journal-article"))

    def test_no_current_source_is_a_preprint(self):
        import json
        refs = json.loads((Path(__file__).resolve().parent.parent / "data" / "references.json").read_text("utf8"))
        self.assertEqual(build_refs.blocked(refs), [])


class Build(unittest.TestCase):
    def test_refuses_preprint_sources(self):
        self.assertEqual(build_refs.blocked([ref(doi="10.1101/2024.01.02.573000", journal="bioRxiv")]), ["A paper"])
        self.assertEqual(build_refs.blocked([ref()]), [])

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
