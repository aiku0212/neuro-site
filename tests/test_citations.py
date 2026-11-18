import io
import json
import re
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
        alerts, errors, _ = self.run_check(refs, {"is-referenced-by-count": 9})
        self.assertEqual((refs[0]["citations"], alerts, errors), (9, [], []))
        self.assertEqual(refs[0]["verification"]["checked"], TODAY)

    def test_failure_keeps_last_good_data(self):
        refs = [ref()]
        alerts, errors, _ = self.run_check(refs, record_error=OSError("down"))
        self.assertEqual(refs[0]["citations"], 5)
        self.assertEqual(refs[0]["verification"]["checked"], "2026-01-01")
        self.assertEqual(len(errors), 1)

    def test_missing_record_is_an_error_not_a_change(self):
        refs = [ref()]
        _, errors, _ = self.run_check(refs, None)
        self.assertEqual(refs[0]["citations"], 5)
        self.assertEqual(len(errors), 1)

    def test_new_retraction_alerts_once(self):
        refs = [ref()]
        notice = {"type": "retraction", "notice_doi": "10.1/n"}
        alerts, _, _ = self.run_check(refs, {"is-referenced-by-count": 5}, [notice])
        self.assertEqual(len(alerts), 1)
        alerts, _, _ = self.run_check(refs, {"is-referenced-by-count": 5}, [notice])
        self.assertEqual(alerts, [])
        self.assertEqual(len(refs[0]["updates"]), 1)

    def test_pubmed_retraction_detected_without_duplicating_crossref(self):
        refs = [ref()]
        summaries = {"1": {"pubtype": ["Journal Article", "Retracted Publication"]}}
        alerts, _, _ = self.run_check(refs, {"is-referenced-by-count": 5}, [], summaries)
        self.assertEqual(alerts[0]["type"], "retraction")
        alerts, _, _ = self.run_check(refs, {"is-referenced-by-count": 5}, [], summaries)
        self.assertEqual(alerts, [])


class FailedLookups(unittest.TestCase):
    run_check = CheckReferences.run_check

    def test_failed_dois_are_reported(self):
        refs = [ref(doi="10.1/a"), ref(doi="10.1/b")]
        _, _, failed = self.run_check(refs, record_error=OSError("down"))
        self.assertEqual(failed, {"10.1/a", "10.1/b"})
        _, _, failed = self.run_check(refs, None)
        self.assertEqual(failed, {"10.1/a", "10.1/b"})
        _, _, failed = self.run_check(refs, {"is-referenced-by-count": 5})
        self.assertEqual(failed, set())

    def test_pubmed_outage_counts_as_failed_for_pmid_references(self):
        refs = [ref(doi="10.1/a", pmid="1"), ref(doi="10.1/b", pmid=None)]
        with mock.patch.object(daily_check, "crossref_record", return_value={"is-referenced-by-count": 5}), \
                mock.patch.object(daily_check, "crossref_notices", return_value=[]), \
                mock.patch.object(daily_check, "pubmed_summaries", side_effect=OSError("down")), \
                mock.patch.object(daily_check.time, "sleep"):
            _, errors, failed = daily_check.check_references(refs, TODAY)
        self.assertEqual(failed, {"10.1/a"})
        self.assertTrue(any("PubMed" in e for e in errors))

    def test_threshold(self):
        self.assertFalse(daily_check.too_many_failures(set(range(5)), 84))
        self.assertTrue(daily_check.too_many_failures(set(range(6)), 84))
        self.assertTrue(daily_check.too_many_failures({1, 2}, 5))   # 40% of a small set
        self.assertFalse(daily_check.too_many_failures({1}, 5))

    def test_status_never_dates_a_failed_lookup_today(self):
        refs = [ref(doi="10.1/a"), ref(doi="10.1/b")]
        checked, failed = daily_check.checked_status(refs, set(), {}, TODAY)
        self.assertEqual((checked, failed), (TODAY, {}))
        previous = {"last_run": "2026-11-05", "checked": "2026-11-05", "lookup_failed": {}}
        checked, failed = daily_check.checked_status(refs, {"10.1/b"}, previous, TODAY)
        self.assertEqual(failed, {"10.1/b": "2026-01-01"})  # older of status and record dates
        self.assertEqual(checked, "2026-01-01")
        # A second failure keeps the date of the last real check, not the previous run.
        checked, failed = daily_check.checked_status(refs, {"10.1/b"}, {"checked": "2026-11-06",
                                                     "lookup_failed": {"10.1/b": "2026-01-01"}}, "2026-11-07")
        self.assertEqual((checked, failed), ("2026-01-01", {"10.1/b": "2026-01-01"}))

    def run_main(self, record_error=None):
        import tempfile
        refs = [ref(doi=f"10.1/{i}", pmid=None) for i in range(10)]
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "references.json").write_text(json.dumps(refs))
            (data / "status.json").write_text(json.dumps({"last_run": "2026-11-05", "checked": "2026-11-05"}))
            rec = mock.Mock(side_effect=record_error) if record_error else mock.Mock(
                return_value={"is-referenced-by-count": 5})
            with mock.patch.object(daily_check, "DATA_DIR", data), \
                    mock.patch.object(daily_check, "crossref_record", rec), \
                    mock.patch.object(daily_check, "crossref_notices", return_value=[]), \
                    mock.patch.object(daily_check, "discover", return_value=([], [])), \
                    mock.patch.object(daily_check.time, "sleep"), \
                    mock.patch("sys.stdout", new_callable=io.StringIO), \
                    mock.patch("sys.stderr", new_callable=io.StringIO):
                code = daily_check.main([])
            return code, json.loads((data / "status.json").read_text())

    def test_run_fails_above_threshold_without_dating_today(self):
        code, status = self.run_main(record_error=OSError("down"))
        self.assertEqual(code, 1)
        self.assertEqual(status["checked"], "2026-01-01")
        self.assertEqual(len(status["lookup_failed"]), 10)
        self.assertNotIn(TODAY, status["lookup_failed"].values())

    def test_run_passes_when_lookups_succeed(self):
        code, status = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(status["lookup_failed"], {})
        self.assertEqual(status["checked"], status["last_run"])

    def test_sources_page_shows_the_oldest_check(self):
        refs = [ref()]
        self.assertEqual(build_refs.checked_date(refs, {"last_run": TODAY, "checked": "2026-11-01"}), "2026-11-01")
        self.assertEqual(build_refs.checked_date(refs, {}), "2026-01-01")


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
        refs = json.loads((Path(__file__).resolve().parent.parent / "data" / "references.json").read_text("utf8"))
        self.assertEqual(build_refs.blocked(refs), [])


class Alerts(unittest.TestCase):
    ALERT = {"type": "retraction", "doi": "10.1/a", "title": "A paper", "notice_doi": "10.1/n", "pmid": None}

    def test_alert_stays_in_issue_until_dismissed(self):
        state = {"open": []}
        daily_check.record_alerts(state, [dict(self.ALERT)], TODAY)
        queue = {"pending": [], "seen": []}
        for _ in range(2):  # a later run with no new notices still shows it
            out = daily_check.render_issue(queue, state["open"], [], TODAY)
            self.assertIn("Correction and retraction notices (1)", out)
        ids = apply_review.parse_alert_dismissals(out.replace("- [ ] Dismiss", "- [x] Dismiss"))
        self.assertEqual(apply_review.dismiss_alerts(state, ids), 1)
        self.assertNotIn("retraction notices", daily_check.render_issue(queue, state["open"], [], TODAY))

    def test_same_notice_is_recorded_once(self):
        state = {"open": []}
        daily_check.record_alerts(state, [dict(self.ALERT)], TODAY)
        daily_check.record_alerts(state, [dict(self.ALERT)], "2026-11-07")
        self.assertEqual(len(state["open"]), 1)
        self.assertEqual(state["open"][0]["found"], TODAY)

    def test_unknown_alert_id_dismisses_nothing(self):
        state = {"open": []}
        daily_check.record_alerts(state, [dict(self.ALERT)], TODAY)
        self.assertEqual(apply_review.dismiss_alerts(state, {"deadbeef00"}), 0)

    def test_dismissing_a_paper_does_not_dismiss_an_alert(self):
        state = {"open": []}
        daily_check.record_alerts(state, [dict(self.ALERT)], TODAY)
        body = "- [x] Dismiss <!-- review:%s:dismiss -->" % state["open"][0]["id"]
        self.assertEqual(apply_review.parse_alert_dismissals(body), set())


class Announce(unittest.TestCase):
    def test_announces_new_items_once(self):
        queue = {"pending": [dict(Review.ITEM)], "seen": ["2"]}
        state = {"open": []}
        daily_check.record_alerts(state, [dict(Alerts.ALERT)], TODAY)
        text = daily_check.announcement(queue, state, TODAY)
        self.assertIn("1 correction or retraction notice and 1 paper to review", text)
        self.assertEqual(daily_check.announcement(queue, state, TODAY), "")

    def test_quiet_when_nothing_is_new(self):
        self.assertEqual(daily_check.announcement({"pending": [], "seen": []}, {"open": []}, TODAY), "")

    def test_comment_is_short_and_cannot_ping(self):
        items = [dict(Review.ITEM, pmid=str(i), title=f"@user{i} paper") for i in range(40)]
        text = daily_check.announcement({"pending": items, "seen": []}, {"open": []}, TODAY)
        self.assertLessEqual(len(text.splitlines()), daily_check.MAX_ANNOUNCED_TITLES + 3)
        self.assertIn("and 35 more", text)
        self.assertNotIn("@user", text)

    def test_main_writes_comment_only_when_new(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / "references.json").write_text("[]")
            (data / "review_queue.json").write_text(json.dumps({"pending": [dict(Review.ITEM)], "seen": ["2"]}))
            out = data / "announce.md"
            with mock.patch.object(daily_check, "DATA_DIR", data), \
                    mock.patch.object(daily_check, "discover", return_value=([], [])), \
                    mock.patch.object(daily_check, "pubmed_summaries", return_value={}), \
                    mock.patch("sys.stdout", new_callable=io.StringIO):
                daily_check.main(["--announce", str(out)])
                self.assertIn("1 paper to review", out.read_text())
                daily_check.main(["--announce", str(out)])
                self.assertEqual(out.read_text(), "")


class QueueSize(unittest.TestCase):
    @staticmethod
    def queue(n, title="A fairly long paper title about plasticity in the adult cortex " * 3):
        items = [dict(Review.ITEM, pmid=str(10000000 + i), title=f"{title} {i}", queued=TODAY,
                      journal="bioRxiv : the preprint server for biology") for i in range(n)]
        return {"pending": items, "seen": [i["pmid"] for i in items]}

    def test_300_item_queue_stays_under_github_limit(self):
        queue = self.queue(300)
        out = daily_check.render_issue(queue, [], [], TODAY)
        self.assertLessEqual(len(out.encode("utf8")), daily_check.ISSUE_BODY_BUDGET)
        self.assertLess(len(out), daily_check.ISSUE_BODY_LIMIT)
        self.assertIn("New papers to review (300)", out)
        self.assertIn("more papers not shown here", out)
        self.assertEqual(out.count("<!-- review:"), 2 * daily_check.MAX_SHOWN_PAPERS)

    def test_everything_at_once_stays_under_limit(self):
        long = "Ünïcode tïtle with many characters " * 40
        alerts = [{"id": f"{i:010x}", "type": "retraction", "doi": f"10.1/{i}", "title": long, "found": TODAY}
                  for i in range(300)]
        reading = [dict(apply_review.to_reading_entry(dict(Review.ITEM, pmid=str(i), title=long), TODAY))
                   for i in range(300)]
        errors = [f"Lookup failed for 10.1/{i}: " + "x" * 2000 for i in range(300)]
        out = daily_check.render_issue(self.queue(300, long), alerts, errors, TODAY, reading)
        self.assertLessEqual(len(out.encode("utf8")), daily_check.ISSUE_BODY_BUDGET)
        # Shown boxes still parse, so whatever is visible can be acted on.
        self.assertTrue(apply_review.parse_alert_dismissals(out.replace("- [ ] Dismiss", "- [x] Dismiss")))

    def test_small_queue_is_shown_in_full(self):
        out = daily_check.render_issue(self.queue(3), [], [], TODAY)
        self.assertEqual(out.count("<!-- review:"), 6)
        self.assertNotIn("not shown", out)

    def test_old_items_expire_but_are_not_requeued(self):
        queue = self.queue(2)
        queue["pending"][0]["queued"] = "2026-07-01"
        expired = daily_check.expire_queue(queue, TODAY)
        self.assertEqual(expired, 1)
        self.assertEqual([i["pmid"] for i in queue["pending"]], ["10000001"])
        self.assertIn("10000000", queue["seen"])

    def test_items_without_a_date_start_their_clock_now(self):
        queue = {"pending": [dict(Review.ITEM)], "seen": ["2"]}
        self.assertEqual(daily_check.expire_queue(queue, TODAY), 0)
        self.assertEqual(queue["pending"][0]["queued"], TODAY)


class WatchQueries(unittest.TestCase):
    QUERIES = json.loads((Path(__file__).resolve().parent.parent / "data" / "watch_queries.json").read_text("utf8"))

    def test_every_query_excludes_preprints(self):
        for group, term in self.QUERIES.items():
            with self.subTest(group=group):
                self.assertTrue(term.endswith(" NOT preprint[pt]"))
                self.assertEqual(term.count("(") , term.count(")"))

    def test_bare_plasticity_needs_a_neural_term(self):
        # "plasticity" alone matched phenotypic, psychological and materials plasticity.
        for group in ("psy", "cp"):
            term = self.QUERIES[group]
            with self.subTest(group=group):
                for m in re.finditer(r'(?<!")\bplasticity\[tiab\]', term):
                    self.assertTrue(term[m.end():].startswith(" AND ("), term[m.start() - 20:m.end() + 20])


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
