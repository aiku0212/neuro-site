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

    def test_pages_state_they_are_not_advice(self):
        for name in PUBLIC:
            with self.subTest(page=name):
                self.assertRegex(read(name), r"[Nn]ot (medical|veterinary) advice|Not medical or veterinary advice")


if __name__ == "__main__":
    unittest.main()
