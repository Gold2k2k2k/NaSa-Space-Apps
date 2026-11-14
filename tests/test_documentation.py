"""Published schemas and demo instructions must describe actual outputs."""
import re
import unittest
from pathlib import Path

from app.agents import run_investigation
from app.schema_mapping import get_manifesto
from scripts.build_schema_docs import render

ROOT = Path(__file__).resolve().parents[1]


class TestDocumentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = run_investigation({"aoi_id": "AOI-MEK"})

    def test_schema_covers_actual_logical_views(self):
        schemas = get_manifesto()["target_schemas"]
        views = {
            "harmonized_hotspots": self.snapshot["_hotspots_all"][0],
            "burning_calendar_cells": self.snapshot["calendar"]["cells"][0],
            "fire_regime_summaries": self.snapshot["calendar"]["summary_records"],
            "sensor_calibration_audit": self.snapshot["sensor_calibration_audit"],
        }
        for name, row in views.items():
            with self.subTest(view=name):
                self.assertFalse(set(row) - set(schemas[name]))
        for name, field in [("harmonized_hotspots", "mir_bt_k"),
                            ("harmonized_hotspots", "hfre_mw"),
                            ("burning_calendar_cells", "value"),
                            ("fire_regime_summaries", "peak_year"),
                            ("sensor_calibration_audit", "bridge_r2")]:
            self.assertIn("nullable", schemas[name][field])

    def test_schema_states_limits_and_current_methods(self):
        text = str(get_manifesto())
        for required in ("60-minute", "0.18", "records_only", "assumed", "footprint_basis",
                         "not energy", "unsigned", "2024", "1000", "90%"):
            self.assertIn(required, text)
        for obsolete in ("floor(lat*100)", "AGRICULTURAL_BURN | WILDFIRE", "2012-present",
                         "radiative fire energy", "NOT NULL"):
            self.assertNotIn(obsolete, text)

    def test_published_local_links_resolve(self):
        for relative in ("README.md", "PROJECT-CONTEXT.md", "DESIGN.md", "docs/ARCHITECTURE.md",
                         "docs/MAPPING_MANIFESTO.md", "docs/SUBMISSION.md", "docs/SCIENCE.md",
                         "docs/INPUTS.md", "docs/RECEIPTS.md", "docs/EXPORTS.md"):
            path = ROOT / relative
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("#"):
                    continue
                with self.subTest(document=relative, target=target):
                    self.assertTrue((path.parent / target.split("#")[0]).exists())

    def test_generated_schema_document_matches_api_declarations(self):
        self.assertEqual((ROOT / "docs/MAPPING_MANIFESTO.md").read_text(encoding="utf-8"), render())


if __name__ == "__main__":
    unittest.main()

