"""
Regression suite: fails CI if the pipeline's accuracy drops below, or
hallucination rate rises above, the thresholds below. This is what runs
in .github/workflows/ci.yml on every PR that touches prompts or pipeline
code, so a prompt tweak that quietly regresses extraction quality gets
caught before merge instead of in production.

Run with:
    pytest eval/regression.py -v
"""
import json
from pathlib import Path

import pytest

from eval.harness import run_eval

MIN_ACCURACY = 0.80
MAX_HALLUCINATION_RATE = 0.10

# Module-level cache so the (expensive, API-calling) eval only runs once
# per test session even though multiple assertions consume it.
_report = None


def _get_report():
    global _report
    if _report is None:
        _report = run_eval(verbose=False)
        report_path = Path(__file__).parent / "last_run_report.json"
        report_path.write_text(json.dumps(_report.to_dict(), indent=2))
    return _report


def test_extraction_accuracy_meets_threshold():
    report = _get_report()
    assert report.accuracy >= MIN_ACCURACY, (
        f"Extraction accuracy {report.accuracy:.1%} fell below the "
        f"{MIN_ACCURACY:.0%} threshold. Check eval/last_run_report.json "
        f"(or rerun `python -m eval.harness`) for which fields regressed."
    )


def test_hallucination_rate_within_threshold():
    report = _get_report()
    assert report.hallucination_rate <= MAX_HALLUCINATION_RATE, (
        f"Hallucination rate {report.hallucination_rate:.1%} exceeded the "
        f"{MAX_HALLUCINATION_RATE:.0%} threshold. This is a release blocker "
        f"-- do not merge prompt changes that increase fabricated clinical detail."
    )


def test_required_fields_never_hallucinated_when_absent():
    """
    Specifically checks the sparse form (form_004): fields genuinely absent
    from the source text must come back null, not a plausible-sounding guess.
    This targets the failure mode a plain accuracy score can miss.
    """
    report = _get_report()
    sparse_results = [r for r in report.results if r["form"] == "form_004_sparse.txt"]
    hallucinated_on_sparse = [r for r in sparse_results if r["hallucinated"]]

    assert not hallucinated_on_sparse, (
        f"Pipeline hallucinated fields on a sparse/near-empty form: "
        f"{[r['field'] for r in hallucinated_on_sparse]}"
    )


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
