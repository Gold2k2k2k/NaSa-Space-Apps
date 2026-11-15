"""Real-server browser contracts, including source preservation and race handling."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import zipfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.test_http_boundaries import CSV
from verify import check_receipt

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get("FIRETRACE_VISUAL_DIR", ROOT / ".superpowers" / "browser-artifacts"))


class TestBrowserShowcase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUT.mkdir(parents=True, exist_ok=True)
        cls.artifacts = []
        cls.temp = tempfile.TemporaryDirectory()
        cls.log_path = Path(cls.temp.name) / "server.log"
        cls.log = cls.log_path.open("wb")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        cls.base = f"http://127.0.0.1:{port}"
        cls.server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.api:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT, stdout=cls.log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        cls.addClassCleanup(cls.cleanup)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(cls.base + "/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError("Browser-test server did not start: " + cls.log_path.read_text(errors="replace")[-2000:])
        cls.playwright = sync_playwright().start()
        try:
            cls.browser = cls.playwright.chromium.launch(channel="chrome", headless=True, timeout=15000)
        except Exception:
            cls.browser = cls.playwright.chromium.launch(headless=True, timeout=15000)

    @classmethod
    def cleanup(cls):
        if hasattr(cls, "browser"):
            cls.browser.close()
        if hasattr(cls, "playwright"):
            cls.playwright.stop()
        if hasattr(cls, "server") and cls.server.poll() is None:
            if os.name == "nt":
                # The venv launcher can have a child. Stop only this owned tree.
                subprocess.run(["taskkill", "/PID", str(cls.server.pid), "/T", "/F"],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                cls.server.terminate()
            try:
                cls.server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cls.server.kill()
        if hasattr(cls, "log"):
            cls.log.close()
        (OUT / "browser-evidence.json").write_text(json.dumps(cls.artifacts, indent=2), encoding="utf-8")
        if hasattr(cls, "temp"):
            cls.temp.cleanup()

    def setUp(self):
        self.errors, self.failures, self.external = [], [], []
        self.expected_statuses = set()
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        self.page = self.context.new_page()
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.context.on("response", lambda response: self.failures.append((response.status, response.url)) if response.status >= 400 else None)
        self.context.on("request", lambda request: self.external.append(request.url) if not request.url.startswith(self.base) and not request.url.startswith("file:") else None)

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [], "Uncaught browser errors")
        unexpected = [failure for failure in self.failures if failure[0] not in self.expected_statuses]
        self.assertEqual(unexpected, [], "Unexpected failed requests")
        self.assertEqual(self.external, [], "The application must not request remote assets")

    def ready(self):
        self.page.wait_for_function("document.querySelectorAll('.cal-cell').length > 0 && !document.getElementById('btn-analyze').disabled", timeout=60000)

    def open(self):
        self.page.goto(self.base, wait_until="domcontentloaded", timeout=15000)
        self.ready()
        self.page.evaluate("async () => { await document.fonts.ready; }")

    def action(self, callback, endpoint="/what_if"):
        with self.page.expect_response(lambda response: endpoint in response.url and response.request.method == "POST", timeout=60000) as pending:
            callback()
        self.assertEqual(pending.value.status, 200)
        data = pending.value.json()
        self.ready()
        return data

    def metrics(self):
        return self.page.evaluate("""() => ({
            viewport: innerWidth, documentWidth: document.documentElement.scrollWidth,
            headerHeight: document.querySelector('header').getBoundingClientRect().height,
            cellCount: document.querySelectorAll('.cal-cell').length,
            keyboardEntries: document.querySelectorAll('.cal-cell[tabindex="0"]').length,
            source: document.getElementById('source-badge').textContent,
            errorVisible: !document.getElementById('global-error').hidden
        })""")

    def test_00_all_five_views_at_phone_and_desktop_widths(self):
        self.open()
        for width, height in ((1440, 900), (375, 812)):
            self.page.set_viewport_size({"width": width, "height": height})
            for view in ("calendar", "bridge", "audit", "manifesto", "bench"):
                self.page.locator("#tab-" + view).click()
                self.page.locator("#view-" + view).wait_for(state="visible")
                if view == "manifesto":
                    self.page.wait_for_function("document.getElementById('manifesto-status').textContent.startsWith('Loaded')")
                self.page.wait_for_timeout(180)  # Complete the debounced layout redraw.
                evidence = {"view": view, "width": width, **self.metrics()}
                self.assertLessEqual(evidence["documentWidth"], width + 1, evidence)
                self.assertFalse(evidence["errorVisible"], evidence)
                self.assertIn("Generated demo", evidence["source"])
                self.page.screenshot(path=str(OUT / f"final-{view}-{width}.png"))
                self.artifacts.append(evidence)
            self.assertEqual(self.page.locator("#bench-tbody tr").count(), 12)
        self.page.locator("#tab-calendar").click()
        targets = self.page.locator(".cal-cell").evaluate_all("nodes => nodes.map(node => [node.getBoundingClientRect().width,node.getBoundingClientRect().height])")
        self.assertTrue(all(width >= 44 and height >= 44 for width, height in targets))
        self.assertEqual(self.page.locator('.cal-cell[tabindex="0"]').count(), 1)
        for name in ("science", "inputs", "receipts", "exports"):
            self.assertEqual(self.context.request.get(self.base + "/api/methods/" + name).status, 200)

    def test_70_real_case_guided_review_and_downloads(self):
        self.open()
        self.assertEqual(self.page.locator("#btn-real-case").count(), 1, "Actual NASA case entry is missing")
        real = self.action(lambda: self.page.locator("#btn-real-case").click(), "/api/case-studies/")
        self.assertEqual(real["provenance"]["source_kind"], "nasa_firms_archive")
        self.assertIn("NASA FIRMS", self.page.locator("#source-badge").inner_text())
        self.assertEqual(self.page.locator("#review-guide li").count(), 3)
        self.page.locator("#tab-audit").click()
        self.page.locator('#review-guide a[href="#calendar-matrix"]').click()
        self.page.locator("#view-calendar").wait_for(state="visible")
        self.page.wait_for_function("location.hash === '#calendar-matrix' && document.getElementById('calendar-matrix').getBoundingClientRect().top >= document.querySelector('header').getBoundingClientRect().bottom && document.getElementById('cal-title').getBoundingClientRect().bottom < innerHeight")
        self.assertIn("NASA FIRMS", self.page.locator("#source-badge").inner_text())
        for width, height in ((1440, 900), (375, 812)):
            self.page.set_viewport_size({"width": width, "height": height})
            for view in ("calendar", "bridge", "audit", "manifesto", "bench"):
                self.page.locator("#tab-" + view).click()
                self.page.locator("#view-" + view).wait_for(state="visible")
                self.page.wait_for_timeout(180)
                self.assertLessEqual(self.metrics()["documentWidth"], width + 1)
                self.page.screenshot(path=str(OUT / f"nasa-{view}-{width}.png"))
                self.artifacts.append({"case": "central-highlands", "view": view, "width": width, "run_id": real["run_id"], **self.metrics()})
        self.page.locator("#tab-audit").click()
        self.assertIn("coverage", self.page.locator("#manager-brief").inner_text().lower())
        self.assertIn(real["run_id"], self.page.locator("#manager-brief").inner_text())
        scenario = self.action(lambda: self.page.locator("#whatif-grid .sub-card").nth(2).get_by_role("button").click())
        self.assertEqual(scenario["provenance"]["source_kind"], "nasa_firms_archive")
        self.assertEqual(scenario["sensor_calibration_audit"]["calibration_model"], real["sensor_calibration_audit"]["calibration_model"])
        restored = self.action(lambda: self.page.locator("#btn-clear-scenario").click())
        changed = self.action(lambda: self.page.locator("#persona-select").select_option("scientist"))
        self.assertEqual(changed["provenance"]["source_records_sha256"], real["provenance"]["source_records_sha256"])
        self.page.locator("#tab-calendar").click()
        raw = self.action(lambda: self.page.locator("#btn-toggle-mode").click())
        self.assertEqual(raw["sensor_calibration_audit"]["calibration_model"], real["sensor_calibration_audit"]["calibration_model"])
        self.page.locator("#selection-panel > summary").click()
        self.page.locator("#in-y0").fill("2024")
        self.page.locator("#in-conf").select_option("high")
        changed = self.action(lambda: self.page.locator("#btn-analyze").click())
        self.assertEqual(changed["provenance"]["source_kind"], "nasa_firms_archive")
        self.assertNotEqual(changed["sensor_calibration_audit"]["calibration_model"]["model_id"], real["sensor_calibration_audit"]["calibration_model"]["model_id"])
        self.page.locator("#tab-audit").click()
        self.assertIn(changed["run_id"], self.page.locator("#dl-brief-package").get_attribute("href"))
        self.page.locator("#tab-calendar").click()
        with tempfile.TemporaryDirectory() as directory:
            for key in ("hotspots-csv", "calendar-csv", "geojson", "ics", "receipt", "package"):
                with self.page.expect_download() as pending:
                    self.page.locator("#dl-" + key).click()
                target = Path(directory) / pending.value.suggested_filename
                pending.value.save_as(target)
                self.assertGreater(target.stat().st_size, 100)
                if key == "receipt":
                    receipt = json.loads(target.read_text(encoding="utf-8"))
                    self.assertEqual(receipt["run_id"], changed["run_id"])
                    self.assertEqual(check_receipt(receipt)["status"], "VALID")
                elif key == "package":
                    with zipfile.ZipFile(target) as archive:
                        self.assertIn("case_manifest.json", archive.namelist())
        self.page.locator("#btn-real-case").focus()
        self.assertEqual(self.page.locator(":focus").get_attribute("id"), "btn-real-case")

    def test_80_late_case_response_cannot_replace_newer_generated_source(self):
        self.open()
        self.assertEqual(self.page.locator("#btn-real-case").count(), 1)
        self.page.evaluate("""() => {
            const native = window.fetch.bind(window); window.__caseHeld = false;
            window.fetch = async (url, options = {}) => {
                const response = await native(url, options);
                if (String(url).includes('/api/case-studies/')) {
                    window.__caseHeld = true;
                    await new Promise(resolve => window.__releaseCase = resolve);
                }
                return response;
            };
        }""")
        self.page.locator("#btn-real-case").click()
        self.page.wait_for_function("window.__caseHeld", timeout=60000)
        self.page.locator("#selection-panel > summary").click()
        generated = self.action(lambda: self.page.locator('[data-aoi="AOI-MEK"]').click(), "/api/analyze")
        self.page.evaluate("window.__releaseCase()")
        self.page.wait_for_timeout(200)
        self.assertEqual(generated["provenance"]["source_kind"], "generated_demo")
        self.assertIn("Generated demo", self.page.locator("#source-badge").inner_text())
        self.assertEqual(self.page.locator("#aoi-heading").inner_text(), generated["aoi"]["name"])

    def test_10_keyboard_ramps_motion_and_preview(self):
        self.open()
        active = self.page.locator('.cal-cell[tabindex="0"]')
        active.focus()
        self.page.keyboard.press("ArrowLeft")
        self.assertEqual(self.page.locator(":focus").get_attribute("data-cell-key"), "2025-9")
        self.page.keyboard.press("ArrowUp")
        changed = self.action(lambda: self.page.keyboard.press("Enter"))
        self.assertEqual(changed["calendar"]["focus_month"], 8)
        self.assertEqual(changed["calendar"]["focus_year"], 2025)
        for ramp in ("viridis", "cividis", "ylorrd", "diverging"):
            self.page.locator("#ramp-select").select_option(ramp)
            minimum = self.page.evaluate("""async () => {
                const theme = await import('/static/js/theme.js');
                const hex = value => '#' + value.match(/[\\d.]+/g).slice(0,3).map(n=>Math.round(Number(n)).toString(16).padStart(2,'0')).join('');
                return Math.min(...[...document.querySelectorAll('.cal-cell')].map(cell=>{
                    const style=getComputedStyle(cell); return theme.contrastRatio(hex(style.color),hex(style.backgroundColor));
                }));
            }""")
            self.assertGreaterEqual(minimum, 4.5, (ramp, minimum))
        self.page.locator("#btn-toggle-granularity").click()
        self.assertEqual(self.page.locator("#calendar-container tbody tr").count(), 36)
        self.page.locator("#btn-toggle-granularity").click()
        self.assertGreater(self.page.locator(".cal-cell").count(), 300)
        self.page.emulate_media(reduced_motion="reduce", color_scheme="light")
        self.assertEqual(self.page.locator("#btn-analyze").evaluate("node=>getComputedStyle(node).transitionDuration"), "0s")
        self.page.locator("#tab-manifesto").click()
        self.page.locator(".skip").focus()
        self.page.keyboard.press("Enter")
        self.assertTrue(self.page.locator("#view-manifesto").is_visible(), "Skip link must preserve the active view")
        self.page.goto((ROOT / "design-preview.html").as_uri(), wait_until="load")
        self.page.locator("#density").select_option("compact")
        self.assertTrue(self.page.locator("body").evaluate("node=>node.classList.contains('compact')"))
        self.page.locator("#ramp").select_option("cividis")
        self.page.locator("#motion").check()
        self.page.locator("#primary").click()
        self.assertIn("interaction completed", self.page.locator("#status").inner_text())
        self.assertIn("Minimum sample text contrast", self.page.locator("#contrast-status").inner_text())

    def test_20_upload_options_personas_and_all_six_downloads(self):
        self.open()
        uploaded = self.action(lambda: self.page.locator("#csv-file-input").set_input_files(
            {"name": "mixed.csv", "mimeType": "text/csv", "buffer": CSV.encode()}), "/api/upload-csv")
        self.page.locator("#tab-bridge").click()
        self.page.locator("#model-assessment").evaluate("element => element.open = true")
        self.assertIn("assumed identity", self.page.locator("#model-policy-note").inner_text().lower())
        self.assertIn("positive matched training windows", self.page.locator("#model-policy-note").inner_text())
        self.page.locator("#tab-calendar").click()
        self.assertIn("Uploaded CSV", self.page.locator("#source-badge").inner_text())
        self.assertIn("rejected 1", self.page.locator("#source-summary").inner_text())
        self.page.locator(".source-details > summary").click()
        self.assertIn("rejected 1", self.page.locator("#data-note").inner_text())
        original_geometry = uploaded["aoi"]["geometry"]
        changed = self.action(lambda: self.page.locator("#btn-toggle-mode").click())
        self.assertEqual(changed["aoi"]["geometry"], original_geometry)
        self.assertEqual(changed["provenance"]["source_records_sha256"], uploaded["provenance"]["source_records_sha256"])
        changed = self.action(lambda: self.page.locator("#btn-toggle-flare").click())
        self.assertFalse(changed["options"]["flare_guard"])
        self.assertEqual(changed["aoi"]["geometry"], original_geometry)
        self.page.locator("#selection-panel > summary").click()
        self.page.locator("#in-y0").fill("2020")
        self.page.locator("#in-fm").select_option("8")
        self.page.locator("#in-conf").select_option("high")
        changed = self.action(lambda: self.page.locator("#btn-analyze").click())
        self.assertEqual(changed["provenance"]["source_kind"], "uploaded_csv")
        self.assertEqual(changed["aoi"]["geometry"], original_geometry)
        self.assertEqual(changed["options"]["year_start"], 2020)
        for persona in ("scientist", "land_manager", "firefighter", "responder"):
            changed = self.action(lambda value=persona: self.page.locator("#persona-select").select_option(value))
            self.assertEqual(changed["options"]["persona"], persona)
            self.assertEqual(changed["reference_time"], uploaded["reference_time"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for key in ("hotspots-csv", "calendar-csv", "geojson", "ics", "receipt", "package"):
                with self.page.expect_download(timeout=60000) as download:
                    self.page.locator("#dl-" + key).click()
                target = root / key
                download.value.save_as(target)
                self.assertGreater(target.stat().st_size, 10)
                if key == "receipt":
                    receipt = json.loads(target.read_text(encoding="utf-8"))
                    self.assertEqual(receipt["run_id"], changed["run_id"])
                    self.assertEqual(check_receipt(receipt)["status"], "VALID")
                elif key == "package":
                    with zipfile.ZipFile(target) as bundle:
                        self.assertEqual(json.loads(bundle.read("receipt.json"))["run_id"], changed["run_id"])
        self.page.locator("#tab-audit").click()
        self.page.locator("#btn-load-receipt").click()
        self.page.locator("#receipt-json-box").wait_for(state="visible")
        self.assertIn(changed["run_id"], self.page.locator("#receipt-json-box").inner_text())

    def test_30_point_geometry_draw_and_median_restore(self):
        self.open()
        self.page.locator("#selection-panel > summary").click()
        self.page.locator("#btn-point-mode").click()
        self.page.locator("#in-lat").fill("10")
        self.page.locator("#in-lon").fill("105")
        self.page.locator("#in-radius").fill("10")
        point = self.action(lambda: self.page.locator("#btn-analyze").click(), "/api/analyze")
        self.assertEqual(point["provenance"]["source_kind"], "generated_demo")
        self.assertEqual(point["aoi"]["selection_model"], "approximate_rectangular_buffer")
        self.page.locator("#selection-panel > summary").click()
        self.page.locator(".geometry-input > summary").click()
        geometry = {"type": "MultiPolygon", "coordinates": [
            [[[105, 10], [105.2, 10], [105.2, 10.2], [105, 10.2], [105, 10]],
             [[105.05, 10.05], [105.05, 10.1], [105.1, 10.1], [105.1, 10.05], [105.05, 10.05]]],
            [[[105.3, 10], [105.4, 10], [105.4, 10.1], [105.3, 10.1], [105.3, 10]]]]}
        self.page.locator("#geojson-input").fill(json.dumps(geometry))
        pasted = self.action(lambda: self.page.locator("#btn-geojson").click(), "/api/analyze")
        self.assertEqual(pasted["aoi"]["geometry"]["type"], "MultiPolygon")
        self.assertEqual(len(pasted["aoi"]["geometry"]["coordinates"][0]), 2)
        self.page.locator("#btn-draw-mode").click()
        graphic = self.page.locator("#map-viewport svg")
        box = graphic.bounding_box()
        for x, y in ((.35, .3), (.7, .3), (.5, .7)):
            graphic.click(position={"x": box["width"] * x, "y": box["height"] * y})
        drawn = self.action(lambda: self.page.locator("#btn-draw-apply").click(), "/api/analyze")
        self.assertEqual(drawn["aoi"]["geometry"]["type"], "Polygon")
        self.assertEqual(len(drawn["aoi"]["geometry"]["coordinates"][0]), 4)
        self.page.locator("#tab-audit").click()
        median = self.action(lambda: self.page.locator("#whatif-grid .sub-card").nth(2).get_by_role("button").click())
        self.assertIsNotNone(median["counterfactual"])
        restored = self.action(lambda: self.page.locator("#btn-clear-scenario").click())
        self.assertIsNone(restored["counterfactual"])
        self.assertEqual(restored["calendar"]["focus_comparison"]["value"], drawn["calendar"]["focus_comparison"]["value"])

    def test_35_drop_upload_escape_and_relational_form_validation(self):
        self.open()
        self.assertEqual(self.page.locator("#csv-drop-zone").count(), 1)
        transfer = self.page.evaluate_handle("""text => {
            const transfer = new DataTransfer();
            transfer.items.add(new File([text], 'dropped.csv', {type: 'text/csv'}));
            return transfer;
        }""", CSV)
        uploaded = self.action(lambda: self.page.locator("#csv-drop-zone").dispatch_event(
            "drop", {"dataTransfer": transfer}), "/api/upload-csv")
        self.assertEqual(uploaded["provenance"]["source_kind"], "uploaded_csv")
        self.page.locator("#btn-draw-mode").click()
        self.page.keyboard.press("Escape")
        self.assertEqual(self.page.locator("#btn-draw-mode").get_attribute("aria-pressed"), "false")
        self.page.locator("#selection-panel > summary").click()
        self.page.locator("#in-y0").fill("2026")
        self.page.locator("#in-y1").fill("2025")
        posted = []
        self.page.on("request", lambda request: posted.append(request.url) if request.method == "POST" else None)
        self.page.locator("#btn-analyze").click()
        self.page.wait_for_function("!document.getElementById('global-error').hidden")
        self.assertIn("start", self.page.locator("#error-message").inner_text().lower())
        self.assertEqual(posted, [])
        self.page.locator("#in-y0").fill("2020")
        self.page.locator("#in-fy").fill("2026")
        self.page.locator("#btn-analyze").click()
        self.assertIn("focus", self.page.locator("#error-message").inner_text().lower())
        self.assertEqual(posted, [])

    def test_40_late_result_cannot_replace_a_newer_selection(self):
        self.open()
        self.page.evaluate("""() => {
            const native=window.fetch.bind(window); window.__heldResponse=false;
            window.fetch=async (url, options={})=>{
                const response=await native(url, options);
                if(String(url)==='/api/analyze' && JSON.parse(options.body).aoi_id==='AOI-MEK'){
                    const contents=await response.text();window.__heldResponse=true;
                    await new Promise(resolve=>setTimeout(resolve,2500));
                    return new Response(contents,{status:response.status,headers:response.headers});
                }
                return response;
            };
        }""")
        self.page.locator("#selection-panel > summary").click()
        self.page.locator('[data-aoi="AOI-MEK"]').click()
        self.page.wait_for_function("window.__heldResponse", timeout=60000)
        newer = self.action(lambda: self.page.locator('[data-aoi="AOI-AMZ"]').click(), "/api/analyze")
        self.page.wait_for_timeout(2800)
        self.assertEqual(newer["aoi"]["aoi_id"], "AOI-AMZ")
        self.assertEqual(self.page.locator("#aoi-heading").inner_text(), newer["aoi"]["name"])

    def test_50_errors_remain_visible_across_views_and_preserve_parent(self):
        self.open()
        parent = self.page.locator("#aoi-heading").inner_text()
        self.expected_statuses = {422, 503}
        self.page.route("**/api/analyze", lambda route: route.fulfill(status=503, json={"detail": "Analysis test failure"}))
        for view in ("calendar", "bridge", "audit"):
            self.page.locator("#tab-" + view).click()
            if not self.page.locator("#selection-panel").evaluate("node => node.open"):
                self.page.locator("#selection-panel > summary").click()
            self.page.locator('[data-aoi="AOI-MEK"]').click()
            self.page.wait_for_function("document.getElementById('error-message').textContent.includes('Analysis test failure')")
            self.assertEqual(self.page.locator("#aoi-heading").inner_text(), parent)
        self.page.route("**/runs/*/receipt", lambda route: route.fulfill(status=503, json={"detail": "Receipt test failure"}))
        self.page.locator("#btn-load-receipt").click()
        self.page.wait_for_function("document.getElementById('error-message').textContent.includes('Receipt test failure')")
        self.page.locator("#csv-file-input").set_input_files({"name": "invalid.csv", "mimeType": "text/csv", "buffer": b"bad,data\nbroken,bad\n"})
        self.page.wait_for_function("document.getElementById('global-status').textContent.startsWith('Request failed')")
        self.assertEqual(self.page.locator("#aoi-heading").inner_text(), parent)
        self.page.route("**/api/schema-mapping", lambda route: route.fulfill(status=503, json={"detail": "Schema test failure"}))
        self.page.locator("#tab-manifesto").click()
        self.page.wait_for_function("document.getElementById('error-message').textContent.includes('Schema test failure')")
        self.page.route("**/api/bench", lambda route: route.fulfill(status=503, json={"detail": "Bench test failure"}))
        self.page.locator("#tab-bench").click()
        self.page.locator("#btn-run-bench").click()
        self.page.wait_for_function("document.getElementById('error-message').textContent.includes('Bench test failure')")
        self.assertFalse(self.page.locator("#btn-run-bench").is_disabled())
        self.page.route("**/ui/setup", lambda route: route.fulfill(status=503, json={"detail": "Setup test failure"}))
        self.page.goto(self.base, wait_until="domcontentloaded")
        self.page.wait_for_function("document.getElementById('error-message').textContent.includes('Setup test failure')")
        self.assertTrue(self.page.locator("#global-error").is_visible())

    def test_60_generated_trap_bench_runs_through_real_http(self):
        self.open()
        self.page.locator("#tab-bench").click()
        with self.page.expect_response(lambda response: "/api/bench" in response.url, timeout=180000) as pending:
            self.page.locator("#btn-run-bench").click()
        result = pending.value.json()
        self.page.wait_for_function("document.getElementById('bench-summary').textContent.includes('12 / 12')", timeout=10000)
        self.assertTrue(result["all_pass"])
        self.assertEqual(result["total"], 12)
        for width, height in ((1440, 900), (375, 812)):
            self.page.set_viewport_size({"width": width, "height": height})
            self.page.screenshot(path=str(OUT / f"final-bench-{width}.png"))
        self.assertEqual(self.page.locator("#bench-tbody .tag.pass").count(), 12)


if __name__ == "__main__":
    unittest.main()
