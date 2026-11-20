import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ["index", "app", "spike", "synapse", "pharma", "comparative", "timecells", "references", "about",
          "learn", "conditioning", "news"]
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
        self.assertIn("--directory _site", workflow)

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
                self.assertEqual(nav.count('class="tab"'), 11)
                self.assertIn('href="learn.html"', nav)
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

    def test_workflows_are_least_privilege_and_pinned(self):
        files = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertGreaterEqual(len(files), 2)
        for path in files:
            workflow = path.read_text(encoding="utf8")
            top = workflow.split("jobs:")[0]
            with self.subTest(workflow=path.name):
                self.assertIn("contents: read", top)
                granted = re.search(r"^permissions:\n((?:[ \t]+.*\n)+)", top, re.M).group(1)
                self.assertNotIn("write", granted)
                for use in re.findall(r"uses: (\S+)", workflow):
                    self.assertRegex(use, r"@[0-9a-f]{40}$")
                self.assertIn("if: failure()", workflow)
                # Composite wrappers can call unpinned actions internally; GitHub then blocks the run.
                self.assertNotIn("uses: actions/upload-pages-artifact", workflow)
                # Only the daily workflow may deploy.
                if path.name != "daily-citations.yml":
                    self.assertNotIn("pages: write", workflow)

    def test_every_page_loads_the_tab_helper(self):
        self.assertTrue((ROOT / "assets" / "nav.js").exists())
        for name in PUBLIC:
            with self.subTest(page=name):
                # The news page shows text from outside feeds and carries no script at all.
                want = 0 if name == "news" else 1
                self.assertEqual(read(name).count('<script src="assets/nav.js" defer></script>'), want)
        self.assertNotIn("<script", read("news"))

    def test_learn_hub_links_every_learn_page(self):
        hub = read("learn")
        for name in ["conditioning", "news"]:
            self.assertIn(f'href="{name}.html"', hub)
        for name in ["learn", "conditioning", "news"]:
            nav = re.search(r'<nav class="tabs".*?</nav>', read(name), re.S).group(0)
            self.assertIn('<a class="tab" href="learn.html" aria-current="true">Learn</a>', nav)

    def test_external_scripts_have_integrity(self):
        for name in PUBLIC:
            for tag in re.findall(r"<script[^>]+src=\"https?://[^>]+>", read(name)):
                with self.subTest(page=name):
                    self.assertIn("integrity=", tag)

    def test_workflow_publishes_the_stylesheet(self):
        workflow = (ROOT / ".github" / "workflows" / "daily-citations.yml").read_text(encoding="utf8")
        self.assertIn("cp -R assets _site/", workflow)

    def test_visuals_say_what_they_are(self):
        for name in ["index", "app", "spike", "synapse", "pharma", "comparative", "timecells", "conditioning"]:
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
        self.assertNotIn("Neural Causality", read("timecells"))
        self.assertTrue((ROOT / "docs" / "open-problem-register.md").exists())
        self.assertTrue((ROOT / "docs" / "time-model-research-plan.md").exists())

    def test_time_page_defines_k_and_draws_a_smooth_chart(self):
        page = read("timecells")
        # The slider says what k does, and the text defines k where it first appears.
        self.assertIn("sharpness k <input", page)
        self.assertIn('aria-describedby="k-def"', page)
        self.assertRegex(page, r'id="k-def">[^<]*<span class="mono">sharpness k</span> sets how sharply')
        self.assertIn("k is a whole number that sets how many times F is differentiated", page)
        # The activity chart is computed per pixel, not on the old fixed 240 by 36 grid.
        self.assertNotIn("COLS = 240", page)
        self.assertIn("rowTS[r] = TMIN * Math.exp(", page)

    def test_pharmacology_lists_sourced_harms_for_every_class(self):
        page = read("pharma")
        for cid in ["psy", "dis", "stim", "op", "benzo", "cb"]:
            start = page.index("{id:'%s'," % cid)
            nxt = page.find("\n\n{id:", start + 5)
            block = page[start:nxt if nxt != -1 else page.index("\n];", start)]
            harms = re.search(r'harms:\[(.*?)\],\n hcite:("(?:[^"\\]|\\.)*")}', block, re.S)
            with self.subTest(drug=cid):
                self.assertIsNotNone(harms)
                self.assertIn(len(re.findall(r'^\s*"', harms.group(1), re.M)), (3, 4))
                cite = json.loads(harms.group(2))
                self.assertGreaterEqual(cite.count('<a href="http'), 3)
                # Harm text must never give amounts or routes.
                self.assertNotRegex(harms.group(1), r"\b\d+(\.\d+)?\s?(mg|mcg|µg|ml|g)\b")
        self.assertNotIn("G&#8321;&#8320;", page)
        self.assertNotIn("has a ceiling", page)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_inline_scripts_parse(self):
        for name in PUBLIC:
            scripts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", read(name), re.S)
            for i, code in enumerate(scripts):
                with self.subTest(page=name, script=i), tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
                    f.write(code)
                result = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
                Path(f.name).unlink()
                self.assertEqual(result.returncode, 0, result.stderr[-400:])

    def test_pages_name_the_site_and_have_link_previews(self):
        base = "https://aiku0212.github.io/neuro-site/"
        self.assertTrue((ROOT / "assets" / "favicon.svg").exists())
        self.assertTrue((ROOT / "assets" / "og.png").exists())
        for name in PUBLIC:
            page = read(name)
            head = page[:page.index("<style")] if "<style" in page else page[:3000]
            with self.subTest(page=name):
                self.assertIn("Neuroscope", re.search(r"<title>([^<]*)</title>", head).group(1))
                self.assertIn('<link rel="icon" href="assets/favicon.svg"', head)
                desc = re.search(r'<meta name="description" content="([^"]*)">', head).group(1)
                self.assertIn(f'<meta property="og:description" content="{desc}">', head)
                self.assertIn(f'<meta property="og:image" content="{base}assets/og.png">', head)
                url = base if name == "index" else f"{base}{name}.html"
                self.assertIn(f'<meta property="og:url" content="{url}">', head)
                self.assertIn('<meta name="twitter:card" content="summary_large_image">', head)
                title = re.search(r"<title>([^<]*)</title>", head).group(1)
                self.assertIn(f'<meta property="og:title" content="{title}">', head)
                self.assertIn('<meta property="og:image:width" content="1200">', head)
                self.assertIn('<meta property="og:image:height" content="630">', head)

    def test_visuals_have_text_for_screen_readers(self):
        for name in PUBLIC:
            for tag in re.findall(r"<canvas\b[^>]*>", read(name)):
                with self.subTest(page=name, canvas=tag[:40]):
                    self.assertIn('role="img"', tag)
                    self.assertRegex(tag, r'aria-label="[^"]{20,}"')

    def test_pages_have_one_h1_and_a_main_landmark(self):
        for name in PUBLIC:
            page = read(name)
            with self.subTest(page=name):
                self.assertEqual(len(re.findall(r"<h1\b", page)), 1)
                self.assertTrue("<main" in page or 'role="main"' in page)

    def test_animation_respects_reduced_motion(self):
        checks = {"index": "if(!drag && !reduce) ry+=vy;",
                  "app": "if(!drag&&!reduce) ry+=",
                  "synapse": "autoYaw = !reduceMotion",
                  "pharma": "var vp=reduce?0.5:",
                  "timecells": "var zoom = reduce ? 1 : 0"}
        for name, code in checks.items():
            with self.subTest(page=name):
                page = read(name)
                self.assertRegex(page, r"= *(window\.matchMedia && )?matchMedia\('\(prefers-reduced-motion: ?reduce\)'\)\.matches;")
                self.assertIn(code, page)
        self.assertIn("ry=reduce?1.25:0.5", read("index"))

    def test_app_heading_is_hidden_not_removed(self):
        self.assertIn('<h1 class="sr-only">', read("app"))
        self.assertIn(".sr-only{position:absolute", (ROOT / "assets" / "atlas.css").read_text(encoding="utf8"))

    def test_main_landmark_holds_the_heading_and_the_models(self):
        for name in PUBLIC:
            page = read(name)
            if "<main" not in page:
                continue
            start, end = page.index("<main"), page.index("</main>")
            with self.subTest(page=name):
                for m in re.finditer(r"<h1\b|<canvas\b", page):
                    self.assertTrue(start < m.start() < end, page[m.start():m.start() + 40])

    def test_home_page_names_the_lobes(self):
        page = read("index")
        self.assertIn("var NAMES=[['Frontal'", page)
        self.assertIn("X.fillText(nm[0],lx,ly)", page)
        self.assertIn("y:nm[2]-YC", page)

    def test_pages_state_they_are_not_advice(self):
        for name in PUBLIC:
            with self.subTest(page=name):
                self.assertRegex(read(name), r"[Nn]ot (medical|veterinary) advice|Not medical or veterinary advice")


if __name__ == "__main__":
    unittest.main()
