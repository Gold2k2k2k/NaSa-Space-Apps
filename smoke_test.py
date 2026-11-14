"""Smoke test for FireTrace core engine, schema mapping, receipt verification, and HTTP API."""
from __future__ import annotations

import sys
from fastapi.testclient import TestClient

from app.agents import run_investigation
from app.api import app
from app.receipt import build_receipt
from verify import check_receipt


def main() -> int:
    results: list[tuple[str, str, str]] = []

    def check(name: str, fn) -> None:
        try:
            detail = fn() or ""
            results.append(("PASS", name, detail))
        except Exception as err:
            results.append(("FAIL", name, str(err)[:160]))

    def step_engine() -> str:
        out = run_investigation({"aoi_id": "AOI-AMZ"})
        assert out["verdict"] == "CRITICAL_ANOMALY"
        return f"verdict={out['verdict']} seal={out['verdict_sha256'][:12]}..."

    def step_receipt() -> str:
        out = run_investigation({"aoi_id": "AOI-MEK"})
        rec = build_receipt(out)
        v = check_receipt(rec)
        assert v["status"] == "VALID"
        return f"status={v['status']} queries={v['queries_checked']}"

    def step_http() -> str:
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            response = client.post("/api/analyze", json={"aoi_id": "AOI-MEK"})
            assert response.status_code == 200
            snapshot = response.json()
            run_id = snapshot["run_id"]
            assert client.get(f"/runs/{run_id}").json() == snapshot
            receipt = client.get(f"/runs/{run_id}/receipt").json()
            assert check_receipt(receipt)["status"] == "VALID"
            schedule = client.get("/api/passes", params={"run_id": run_id}).json()
            assert schedule == {"run_id": run_id, "aoi_id": snapshot["aoi"]["aoi_id"], **snapshot["passes"]}, "Stored schedule differs"
            assert client.post("/api/analyze", json={"focus_month": 13}).status_code == 422
            sample = "latitude,longitude,acq_date,satellite,confidence\n10,106,2026-07-01,N20,h\n"
            upload = client.post("/api/upload-csv", files={"file": ("sample.csv", sample, "text/csv")})
            assert upload.status_code == 200, upload.text
            assert upload.json()["verdict"] == "UNVERIFIABLE"
            assert upload.json()["calendar"]["focus_comparison"]["coverage_status"] == "records_only"
            b = client.post("/api/bench")
            assert b.status_code == 200 and b.json()["all_pass"]
            return f"snapshot, receipt, stored passes, validation, CSV coverage; bench={b.json()['passed']}/{b.json()['total']}"

    check("Engine & Harmonization Pipeline", step_engine)
    check("Unsigned Receipt Consistency Verifier", step_receipt)
    check("HTTP API & 12-Case Benchmark", step_http)

    for status, name, detail in results:
        print(f"[{status}] {name}: {detail}")

    return 0 if all(s == "PASS" for s, _, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
