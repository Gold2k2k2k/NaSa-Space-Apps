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
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200
        b = client.post("/api/bench")
        assert b.status_code == 200 and b.json()["all_pass"]
        return f"bench={b.json()['passed']}/{b.json()['total']}"

    check("Engine & Harmonization Pipeline", step_engine)
    check("Cryptographic Receipt Offline Verifier", step_receipt)
    check("HTTP API & 12-Case Benchmark", step_http)

    for status, name, detail in results:
        print(f"[{status}] {name}: {detail}")

    return 0 if all(s == "PASS" for s, _, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
