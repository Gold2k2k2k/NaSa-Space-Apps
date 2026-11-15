"""Performance benchmarks for Central Highlands dynamic analysis pipeline.

Validates that on-the-fly execution on the 16,258-row dataset completes
strictly under 5.0 seconds across direct calls, explicit options, What-If
simulations, and API requests, while verifying non-cached dynamic execution.
"""
import copy
import time
import unittest

from fastapi.testclient import TestClient

from app.agents import apply_what_if, run_investigation
from app.api import app
from app.case_studies import load_case_study, run_case_study

LATENCY_BUDGET_SECONDS = 5.0


class TestPerformanceBenchmarks(unittest.TestCase):
    """Validate dynamic execution latency remains strictly under 5.0 seconds."""

    def test_run_case_study_default_latency(self):
        """run_case_study('central-highlands') default on-the-fly execution < 5.0s."""
        durations = []
        for i in range(2):
            t0 = time.perf_counter()
            result = run_case_study("central-highlands")
            duration = time.perf_counter() - t0
            durations.append(duration)

            # Functional contract assertions first
            self.assertEqual(result["verdict"], "UNVERIFIABLE")
            self.assertEqual(result["options"]["focus_month"], 2)

            # Latency budget assertion
            self.assertLess(
                duration,
                LATENCY_BUDGET_SECONDS,
                f"Run {i + 1} took {duration:.3f}s, exceeding budget {LATENCY_BUDGET_SECONDS}s",
            )

        avg_duration = sum(durations) / len(durations)
        self.assertLess(
            avg_duration,
            LATENCY_BUDGET_SECONDS,
            f"Average duration {avg_duration:.3f}s exceeds budget {LATENCY_BUDGET_SECONDS}s",
        )

    def test_run_case_study_explicit_options_latency(self):
        """Explicit options (focus_month=3, mode='raw', confidence_min='high') execute < 5.0s."""
        option_sets = [
            {"focus_month": 3},
            {"mode": "raw"},
            {"confidence_min": "high"},
        ]
        for opts in option_sets:
            with self.subTest(options=opts):
                t0 = time.perf_counter()
                result = run_case_study("central-highlands", opts)
                duration = time.perf_counter() - t0

                # Functional contract assertion
                self.assertEqual(result["verdict"], "UNVERIFIABLE")

                # Latency budget assertion
                self.assertLess(
                    duration,
                    LATENCY_BUDGET_SECONDS,
                    f"Options {opts} took {duration:.3f}s, exceeding budget {LATENCY_BUDGET_SECONDS}s",
                )

    def test_api_analyze_endpoint_latency(self):
        """POST /api/case-studies/central-highlands/analyze responds HTTP 200 in < 5.0s."""
        with TestClient(app) as client:
            t0 = time.perf_counter()
            response = client.post("/api/case-studies/central-highlands/analyze", json={})
            duration = time.perf_counter() - t0

            # Functional response contract assertions
            self.assertEqual(response.status_code, 200, f"Expected 200 OK, got: {response.text}")
            payload = response.json()
            self.assertEqual(payload["verdict"], "UNVERIFIABLE")
            self.assertEqual(payload["options"]["focus_month"], 2)

            # Latency budget assertion
            self.assertLess(
                duration,
                LATENCY_BUDGET_SECONDS,
                f"API response took {duration:.3f}s, exceeding budget {LATENCY_BUDGET_SECONDS}s",
            )

    def test_what_if_counterfactual_latency(self):
        """Counterfactual what-if re-execution on Central Highlands snapshot executes in < 5.0s."""
        snapshot = run_case_study("central-highlands", {"focus_month": 2})

        t0 = time.perf_counter()
        flipped = apply_what_if(snapshot, "mode", "raw")
        duration = time.perf_counter() - t0

        # Lineage and integrity assertions
        self.assertNotEqual(flipped["run_id"], snapshot["run_id"])
        self.assertEqual(flipped["what_if_applied"]["field"], "mode")
        self.assertEqual(flipped["what_if_applied"]["value"], "raw")

        # Latency budget assertion
        self.assertLess(
            duration,
            LATENCY_BUDGET_SECONDS,
            f"What-If counterfactual took {duration:.3f}s, exceeding budget {LATENCY_BUDGET_SECONDS}s",
        )

    def test_dynamic_execution_guard(self):
        """Verify computation is truly dynamic and not statically cached."""
        records, aoi = load_case_study("central-highlands")

        # Perturb one record's FRP value
        perturbed = [copy.deepcopy(r) for r in records]
        perturbed[0]["frp"] = "999.0"

        req = {
            "year_start": 2001,
            "year_end": 2024,
            "focus_year": 2024,
            "focus_month": 2,
        }
        run1 = run_investigation(req, raw_records_override=records, source_aoi=aoi)
        run2 = run_investigation(req, raw_records_override=perturbed, source_aoi=aoi)

        self.assertNotEqual(
            run1["run_id"],
            run2["run_id"],
            "Dynamic input change must produce a distinct run_id",
        )
        self.assertNotEqual(
            run1["provenance"]["source_records_sha256"],
            run2["provenance"]["source_records_sha256"],
            "Perturbed records must produce a different source_records_sha256",
        )


if __name__ == "__main__":
    unittest.main()
