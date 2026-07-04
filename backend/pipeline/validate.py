"""
Step 3 of the pipeline: validate extracted fields against basic clinical
sanity rules and aggregate a confidence score. This is deliberately
heuristic/rule-based (not another LLM call) -- validation should be
deterministic and auditable, not another source of hallucination.
"""
import re
from datetime import datetime

from models import (
    CONFIDENCE_REVIEW_THRESHOLD,
    ExtractedFields,
    ValidationIssue,
    ValidationResult,
)

REQUIRED_FIELDS = ["patient_name", "date_of_birth", "chief_complaint"]

DOB_PATTERN = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$|^\d{4}-\d{2}-\d{2}$")


def validate_fields(fields: ExtractedFields) -> ValidationResult:
    issues: list[ValidationIssue] = []
    fields_needing_review: list[str] = []
    confidences: list[float] = []

    data = fields.model_dump()

    for field_name in REQUIRED_FIELDS:
        field = data[field_name]
        confidences.append(field["confidence"])
        if field["value"] in (None, ""):
            issues.append(
                ValidationIssue(
                    field=field_name,
                    issue="Required field is missing",
                    severity="error",
                )
            )
            fields_needing_review.append(field_name)
        elif field["confidence"] < CONFIDENCE_REVIEW_THRESHOLD:
            issues.append(
                ValidationIssue(
                    field=field_name,
                    issue=f"Low extraction confidence ({field['confidence']:.2f})",
                    severity="warning",
                )
            )
            fields_needing_review.append(field_name)

    for field_name, field in data.items():
        if field_name in REQUIRED_FIELDS:
            continue
        confidences.append(field["confidence"])
        if field["value"] is not None and field["confidence"] < CONFIDENCE_REVIEW_THRESHOLD:
            fields_needing_review.append(field_name)

    dob = data["date_of_birth"]["value"]
    if dob and not DOB_PATTERN.match(str(dob).strip()):
        issues.append(
            ValidationIssue(
                field="date_of_birth",
                issue=f"Date of birth '{dob}' doesn't match an expected date format",
                severity="warning",
            )
        )
        if "date_of_birth" not in fields_needing_review:
            fields_needing_review.append("date_of_birth")

    if dob:
        try:
            parsed = _parse_date(str(dob))
            if parsed and parsed > datetime.utcnow():
                issues.append(
                    ValidationIssue(
                        field="date_of_birth",
                        issue="Date of birth is in the future",
                        severity="error",
                    )
                )
        except ValueError:
            pass

    overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    has_errors = any(i.severity == "error" for i in issues)

    return ValidationResult(
        is_valid=not has_errors,
        overall_confidence=round(overall_confidence, 3),
        issues=issues,
        fields_needing_review=sorted(set(fields_needing_review)),
    )


def _parse_date(value: str) -> datetime | None:
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None
