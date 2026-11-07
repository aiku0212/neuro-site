import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ["index", "app", "spike", "synapse", "pharma", "comparative", "timecells", "references", "about"]
NOT_PUBLISHED = ["explore", "morphometry"]


def read(name):
    return (ROOT / f"{name}.html").read_text(encoding="utf8")


class PublicPages(unittest.TestCase):
    def test_every_html_file_is_classified(self):
        found = {path.stem for path in ROOT.glob("*.html")}
        self.assertEqual(found, set(PUBLIC) | set(NOT_PUBLISHED))

    def test_workflow_publishes_exactly_the_public_pages(self):
        workflow = (ROOT / ".github" / "workflows" / "daily-citations.yml").read_text(encoding="utf8")
        listed = re.search(r"for page in ([^;]+);", workflow).group(1).split()
        self.assertEqual(sorted(listed), sorted(PUBLIC))
        self.assertIn("path: _site", workflow)

    def test_pages_declare_encoding_language_and_viewport(self):
        for name in PUBLIC + NOT_PUBLISHED:
            start = read(name)[:300].lower()
            with self.subTest(page=name):
                self.assertTrue(start.startswith("<!doctype html>"))
                self.assertIn('<html lang="en">', start)
                self.assertIn('<meta charset="utf-8">', start)
                self.assertIn('name="viewport"', start)

    def test_every_page_reaches_every_tab_and_the_limits(self):
        for name in PUBLIC:
            nav = re.search(r'<nav class="tabs".*?</nav>', read(name), re.S).group(0)
            with self.subTest(page=name):
                self.assertEqual(nav.count('class="tab"'), 10)
                self.assertIn('href="about.html"', nav)

    def test_links_stay_on_published_pages(self):
        for name in PUBLIC:
            links = re.findall(r'href="([a-z_-]+)\.html', read(name))
            with self.subTest(page=name):
                self.assertEqual(sorted(set(links) - set(PUBLIC)), [])

    def test_pages_use_the_atlas_design_system(self):
        self.assertTrue((ROOT / "assets" / "atlas.css").exists())
        for name in PUBLIC:
            page = read(name)
            with self.subTest(page=name):
                self.assertIn('href="assets/atlas.css"', page)
                # Only the Atlas palette: no leftover dark or cream page backgrounds.
                self.assertNotRegex(page, r"--(bg|ground):#(0|F2EDE3|F4F0E8)")
                self.assertNotIn("prefers-color-scheme: light", page)

    def test_workflow_is_least_privilege_and_pinned(self):
        workflow = (ROOT / ".github" / "workflows" / "daily-citations.yml").read_text(encoding="utf8")
        top = workflow.split("jobs:")[0]
        self.assertIn("contents: read", top)
        self.assertNotIn("pages: write", top)
        for use in re.findall(r"uses: (\S+)", workflow):
            with self.subTest(action=use):
                self.assertRegex(use, r"@[0-9a-f]{40}$")
        self.assertIn("if: failure()", workflow)

    def test_external_scripts_have_integrity(self):
        for name in PUBLIC:
            for tag in re.findall(r"<script[^>]+src=\"https?://[^>]+>", read(name)):
                with self.subTest(page=name):
                    self.assertIn("integrity=", tag)

    def test_workflow_publishes_the_stylesheet(self):
        workflow = (ROOT / ".github" / "workflows" / "daily-citations.yml").read_text(encoding="utf8")
        self.assertIn("cp -R assets _site/", workflow)

    def test_visuals_say_what_they_are(self):
        for name in ["index", "app", "spike", "synapse", "pharma", "comparative", "timecells"]:
            with self.subTest(page=name):
                self.assertRegex(read(name), r'class="fig-kind" data-kind="(schematic|simulation|illustrative|measured)"')

    def test_about_names_author_corrections_and_license(self):
        about = read("about")
        self.assertIn("written and maintained by", about)
        self.assertIn("neuro-site/issues/new", about)
        self.assertIn("CC BY 4.0", about)
        self.assertIn("MIT License", about)
        self.assertTrue((ROOT / "LICENSE").read_text(encoding="utf8").startswith("MIT License"))

    def test_internal_plans_are_not_published(self):
        self.assertNotIn("Open problem register", read("comparative"))
        self.assertNotRegex(read("timecells"), r"Project [123]")
        self.assertTrue((ROOT / "docs" / "open-problem-register.md").exists())
        self.assertTrue((ROOT / "docs" / "time-model-research-plan.md").exists())

    def test_pages_state_they_are_not_advice(self):
        for name in PUBLIC:
            with self.subTest(page=name):
                self.assertRegex(read(name), r"[Nn]ot (medical|veterinary) advice|Not medical or veterinary advice")


if __name__ == "__main__":
    unittest.main()
