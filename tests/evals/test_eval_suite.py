"""Pytest execution suite for MAX-AGENT Forensic Evaluation Baseline."""

import json
from pathlib import Path
from tests.evals.harness import EvalHarness

def test_run_eval_harness():
    harness = EvalHarness()
    report = harness.run_all()

    # Ensure evidence directory exists
    evidence_dir = Path(__file__).resolve().parent.parent.parent / "docs" / "evidence" / "p0"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = evidence_dir / "evals_baseline.json"

    with open(evidence_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    assert report["total_tasks"] == 25
    assert "route_accuracy" in report
    assert "false_success_rate" in report
    print(f"\n[EVAL REPORT] Route Accuracy: {report['route_accuracy']}% | False Success Rate: {report['false_success_rate']}%")
