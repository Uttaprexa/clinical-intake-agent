"""
Eval harness: runs the extraction step against the synthetic test set,
grades each field for accuracy and hallucination, and prints a report.

Usage (from backend/):
    python -m eval.harness

This is the harness regression.py calls to enforce CI thresholds --
harness.py answers "how good is the pipeline right now", regression.py
answers "is it good enough to merge".
"""
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from pipeline.extract import extract_fields
from eval.graders import grade_field_accuracy, grade_hallucination

TEST_SET_DIR = Path(__file__).parent / "test_set"
GROUND_TRUTH_PATH = TEST_SET_DIR / "ground_truth.json"


@dataclass
class FieldResult:
    form: str
    field: str
    predicted: object
    ground_truth: object
    correct: bool
    hallucinated: bool
    reasoning: str


@dataclass
class EvalReport:
    total_fields: int
    correct_fields: int
    hallucinated_fields: int
    accuracy: float
    hallucination_rate: float
    results: list

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def load_test_set() -> dict[str, str]:
    forms = {}
    for path in sorted(TEST_SET_DIR.glob("*.txt")):
        forms[path.name] = path.read_text()
    return forms


def run_eval(verbose: bool = True) -> EvalReport:
    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text())
    forms = load_test_set()

    results: list[FieldResult] = []

    for form_name, raw_text in forms.items():
        gt = ground_truth.get(form_name)
        if gt is None:
            continue

        predicted = extract_fields(raw_text).model_dump()

        for field_name, gt_value in gt.items():
            pred_value = predicted[field_name]["value"]

            accuracy_verdict = grade_field_accuracy(field_name, pred_value, gt_value)
            hallucination_verdict = grade_hallucination(field_name, pred_value, raw_text)

            result = FieldResult(
                form=form_name,
                field=field_name,
                predicted=pred_value,
                ground_truth=gt_value,
                correct=bool(accuracy_verdict.get("match")),
                hallucinated=bool(hallucination_verdict.get("hallucinated")),
                reasoning=accuracy_verdict.get("reasoning", ""),
            )
            results.append(result)

            if verbose:
                status = "PASS" if result.correct else "FAIL"
                halluc_flag = " [HALLUCINATION]" if result.hallucinated else ""
                print(f"[{status}]{halluc_flag} {form_name} :: {field_name}")
                if not result.correct or result.hallucinated:
                    print(f"    predicted={pred_value!r} ground_truth={gt_value!r}")
                    print(f"    reasoning: {result.reasoning}")

    total = len(results)
    correct = sum(r.correct for r in results)
    hallucinated = sum(r.hallucinated for r in results)

    report = EvalReport(
        total_fields=total,
        correct_fields=correct,
        hallucinated_fields=hallucinated,
        accuracy=round(correct / total, 3) if total else 0.0,
        hallucination_rate=round(hallucinated / total, 3) if total else 0.0,
        results=[asdict(r) for r in results],
    )

    if verbose:
        print("\n--- Eval Summary ---")
        print(f"Total fields graded: {report.total_fields}")
        print(f"Accuracy: {report.accuracy:.1%}")
        print(f"Hallucination rate: {report.hallucination_rate:.1%}")

    return report


if __name__ == "__main__":
    report = run_eval()
    output_path = Path(__file__).parent / "last_run_report.json"
    output_path.write_text(json.dumps(report.to_dict(), indent=2))
    print(f"\nFull report written to {output_path}")
    sys.exit(0)
