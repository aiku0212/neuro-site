import base64
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ["index", "app", "spike", "synapse", "pharma", "comparative", "timecells", "references", "about",
          "learn", "conditioning", "news", "scans"]
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
        for name in ["conditioning", "news", "scans"]:
            self.assertIn(f'href="{name}.html"', hub)
        for name in ["learn", "conditioning", "news", "scans"]:
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
        for name in ["index", "app", "spike", "synapse", "pharma", "comparative", "timecells", "conditioning", "scans"]:
            with self.subTest(page=name):
                self.assertRegex(read(name), r'class="fig-kind" data-kind="(schematic|simulation|drawing|measured)"')

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

    def test_scans_page_uses_local_data_and_checked_landmarks(self):
        import gzip, struct
        page = read("scans")
        # The viewer is vendored at a fixed version and matches the published npm build.
        viewer = (ROOT / "assets" / "vendor" / "niivue-0.69.0" / "niivue.umd.js").read_bytes()
        self.assertEqual(base64.b64encode(hashlib.sha384(viewer).digest()).decode(), "Oyof6MyzZMH1tvMLLYFRQLWZtk9Y/WbiL3wkdXzwaCS82xRXXy9U+kRrkDDAVq6E")
        self.assertIn("BSD 2-Clause License", (ROOT / "assets" / "vendor" / "niivue-0.69.0" / "LICENSE").read_text(encoding="utf8"))
        self.assertIn('s.src = "assets/vendor/niivue-0.69.0/niivue.umd.js";', page)
        self.assertNotRegex(page, r'src="https?://')
        # The template's copyright notice ships with the data and appears on the page.
        notice = (ROOT / "assets" / "scans" / "COPYING-ICBM152").read_text(encoding="utf8")
        self.assertIn("Louis Collins", notice)
        self.assertIn("provided that the above copyright notice appear in all copies", " ".join(notice.split()))
        self.assertIn("provided that the above copyright notice appear in all copies", page)
        self.assertTrue((ROOT / "tools" / "scans" / "prep_icbm.py").is_file())
        vols = {}
        for name in ("icbm152-t1-brain", "icbm152-tissue"):
            path = ROOT / "assets" / "scans" / (name + ".nii.gz")
            self.assertLess(path.stat().st_size, 2_500_000)
            raw = gzip.decompress(path.read_bytes())
            dims = struct.unpack("<8h", raw[40:56])[1:4]
            origin = [struct.unpack("<f", raw[292 + 16 * i:296 + 16 * i])[0] for i in range(3)]
            self.assertEqual(struct.unpack("<h", raw[70:72])[0], 2)   # uint8
            vols[name] = (raw[352:], dims, origin)
        self.assertEqual(vols["icbm152-t1-brain"][1:], vols["icbm152-tissue"][1:])
        # Every landmark sits in the tissue its caption describes.
        want = {"Corpus callosum": 2, "Left lateral ventricle": 3, "Left thalamus": 1, "Left putamen": 1,
                "Left hippocampus": 1, "Pons": 2, "Left cerebellum": 2}
        stops = re.findall(r'\{ name: "([^"]+)", at: \[(-?\d+), (-?\d+), (-?\d+)\]', page)
        self.assertEqual([s[0] for s in stops], list(want))
        data, (nx, ny, nz), origin = vols["icbm152-tissue"]
        for name, x, y, z in stops:
            i, j, k = (round(float(v) - o) for v, o in zip((x, y, z), origin))
            with self.subTest(landmark=name):
                self.assertEqual(data[i + nx * (j + ny * k)], want[name])
        self.assertIn('data-kind="measured">Measured, averaged', page)
        self.assertIn("cannot be used to read or diagnose", page)

    def test_explore_membrane_shows_basic_glutamate_receptors(self):
        page = read("app")
        # The membrane level teaches the basic receptors of a spine synapse, not drug targets.
        for old in ("TrkB", "p75NTR", "5-HT2A", "Receptors where drugs act"):
            self.assertNotIn(old, page)
        for name in ("'AMPA'", "'NMDA'", "'mGluR'"):
            self.assertIn(name, page)
        # Both sources cited in its caption are on the Sources page.
        dois = {r.get("doi") for r in json.loads((ROOT / "data" / "references.json").read_text(encoding="utf8"))}
        self.assertIn("10.1124/pr.109.002451", dois)
        self.assertIn("10.1146/annurev.pharmtox.011008.145533", dois)

    def test_receptor_card_is_sourced_and_loads_only_local_code(self):
        page = read("pharma")
        # The caption says what the structure is, where it came from and what it leaves out.
        for text in ('data-kind="measured"', "PDB 9AS8", "2.54 &Aring;", "cryo-electron microscopy", "mini-Gq",
                     "is not shown here", "It is drawn as a plain slab", "262 of the receptor&rsquo;s 471 amino acids",
                     "https://doi.org/10.1038/s41467-025-57956-7"):
            self.assertIn(text, page)
        dois = {r.get("doi") for r in json.loads((ROOT / "data" / "references.json").read_text(encoding="utf8"))}
        self.assertIn("10.1038/s41467-025-57956-7", dois)
        # three.js r160 is vendored from the npm package, and these are the files' SHA-384 hashes.
        pinned = {
            "assets/vendor/three-r160/three.module.min.js": "8/hf5tabFfIo0BPku31TKUvGIKpWGYaMwNtlSNqNyZzXgZCMd4lnOGWbJElML9dv",
            "assets/vendor/three-r160/loaders/GLTFLoader.js": "oxY9vSeh7Mrt5WmhN8xfWoDRnmoW9krEiRBY7vJKaK90jMUidM0fhbUwcblpBgTu",
            "assets/vendor/three-r160/utils/BufferGeometryUtils.js": "jHGXS4+FuVOBnZkNme2ury3Ccg5DWDLYK22xX/WGdZCZsjRM4J+3n6Qc4CXx1Hjf",
            "assets/vendor/three-r160/controls/OrbitControls.js": "qlO/ZugKPxAQUAvTlQoo0QECzxJIJySZmCF/DHdb2Xn/hHndFwX/vfUAC9Hbk6LP",
        }
        for path, want in pinned.items():
            with self.subTest(file=path):
                got = base64.b64encode(hashlib.sha384((ROOT / path).read_bytes()).digest()).decode()
                self.assertEqual(got, want)
        self.assertIn("The MIT License", (ROOT / "assets/vendor/three-r160/LICENSE").read_text(encoding="utf8"))
        # The viewer imports nothing from outside the repository and respects reduced motion.
        viewer = (ROOT / "assets" / "receptor-viewer.js").read_text(encoding="utf8")
        for spec in re.findall(r"from '([^']+)'", viewer):
            self.assertTrue(spec == "three" or spec.startswith("./vendor/three-r160/"), spec)
        self.assertNotRegex(viewer, r"https?://")
        self.assertIn("controls.autoRotate = !reduce", viewer)
        self.assertIn("IntersectionObserver", viewer)
        # The page loads the viewer only when asked, and the model stays within its size budget.
        self.assertIn("import('./assets/receptor-viewer.js')", page)
        self.assertNotRegex(page, r'<script[^>]+src="[^"]*three')
        self.assertTrue((ROOT / "tools" / "blender" / "receptor_card.py").is_file())
        self.assertTrue((ROOT / "tools" / "blender" / "membrane_plane.py").is_file())

    def test_every_drug_class_has_a_sourced_receptor_card(self):
        page = read("pharma")
        dois = {r.get("doi") for r in json.loads((ROOT / "data" / "references.json").read_text(encoding="utf8"))}
        cards = {"psy": ("5ht2a-psilocin-9as8", "9AS8", "10.1038/s41467-025-57956-7"),
                 "dis": ("nmda-ketamine-7eu7", "7EU7", "10.1038/s41586-021-03769-9"),
                 "stim": ("dat-cocaine-9eo4", "9EO4", "10.1038/s41586-024-07804-3"),
                 "op": ("mor-morphine-8ef6", "8EF6", "10.1016/j.cell.2022.09.041"),
                 "benzo": ("gabaa-diazepam-6x3x", "6X3X", "10.1038/s41586-020-2654-5"),
                 "cb": ("cb1-amg315-8ghv", "8GHV", "10.1038/s41467-023-37864-4")}
        data = json.loads(re.search(r"/\*rc:start\*/(.*?)/\*rc:end\*/", page, re.S).group(1).replace("\n psy:", '\n "psy":')
                          .replace("\n dis:", '\n "dis":').replace("\n stim:", '\n "stim":').replace("\n op:", '\n "op":')
                          .replace("\n benzo:", '\n "benzo":').replace("\n cb:", '\n "cb":'))
        self.assertEqual(set(data), set(cards))
        for key, (name, pdb, doi) in cards.items():
            with self.subTest(card=key):
                card = data[key]
                self.assertEqual(card["file"], name)
                # Each caption names its entry, method and resolution, says the membrane is drawn in, and links its paper.
                limits = " ".join(card["limits"])
                self.assertIn("Protein Data Bank entry " + pdb, limits)
                self.assertRegex(limits, r"cryo-electron microscopy at a resolution of [0-9.]+ &Aring;")
                self.assertIn("It is drawn as a plain slab", limits)
                self.assertIn("https://doi.org/" + doi, card["cite"])
                self.assertIn("PDB " + pdb, card["cite"])
                self.assertIn(doi, dois)
                self.assertGreater(len(card["alt"]), 80)
                self.assertGreaterEqual(len(card["labels"]), 3)
                # The model, the still image and the thumbnail are in the repository, and the model is within budget.
                model = (ROOT / "assets" / "models" / (name + ".glb")).read_bytes()
                self.assertEqual(model[:4], b"glTF")
                self.assertLess(len(model), 600_000)
                for suffix in (".webp", "-thumb.webp"):
                    self.assertTrue((ROOT / "assets" / "img" / (name + suffix)).is_file())
                self.assertIn('"%s"' % name, (ROOT / "tools" / "blender" / "receptor_card.py").read_text(encoding="utf8"))
        # The cannabinoid card says plainly that it is not THC, and the retracted CB1 entries are never used.
        self.assertIn("It is not THC", page)
        for retracted in ("5XRA", "5XR8"):
            self.assertNotIn(retracted, page)

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
            scripts = re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", read(name), re.S)
            for i, (attrs, code) in enumerate(scripts):
                if 'type="importmap"' in attrs:
                    # An import map is JSON, and it may only point at files in this repository.
                    for url in json.loads(code)["imports"].values():
                        self.assertTrue(url.startswith("./assets/vendor/"), url)
                        self.assertTrue((ROOT / url[2:]).is_file(), url)
                    continue
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
                  "pharma": "autoplay=!reduce",
                  "timecells": "var zoom = reduce ? 1 : 0"}
        for name, code in checks.items():
            with self.subTest(page=name):
                page = read(name)
                self.assertRegex(page, r"= *(window\.matchMedia && )?matchMedia\('\(prefers-reduced-motion: ?reduce\)'\)\.matches;")
                self.assertIn(code, page)
        self.assertIn("ry=reduce?1.25:0.5", read("index"))

    def test_pharmacology_scenes_follow_the_mechanism_steps(self):
        page = read("pharma")
        for ctl in ('id="syn-prev"', 'id="syn-play"', 'id="syn-next"', 'aria-live="polite"'):
            self.assertIn(ctl, page)
        for cid in ("psy", "dis", "stim", "op", "benzo", "cb"):
            with self.subTest(cls=cid):
                start = page.index("{id:'%s'," % cid)
                block = page[start:page.index("\n why:", start)]
                steps = block.count("\n        '") + 1
                scene = page.index("\n%s:{key:" % cid)
                caps = page[page.index("cap:[", scene):page.index("paint:function", scene)]
                # one caption for the step without the drug, then one per numbered Mechanism step
                self.assertEqual(len(re.findall(r"\['[^']*','", caps)), steps + 1)

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
