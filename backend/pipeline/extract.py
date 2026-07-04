"""
Step 2 of the pipeline: extract structured clinical fields from raw
intake text using Claude, with a per-field confidence score returned
by the model itself (self-reported confidence, cross-checked in
validate.py against heuristic signals).
"""
from models import ExtractedFields, FieldValue, CONFIDENCE_REVIEW_THRESHOLD
from pipeline.llm_client import call_claude_json

EXTRACTION_SYSTEM_PROMPT = """You are a clinical intake extraction assistant.
Extract structured fields from a patient intake form's raw text.

For EVERY field, return:
- "value": the extracted value, or null if not present in the text
- "confidence": your confidence the value is correct AND actually present
  in the source text, from 0.0 to 1.0. Use LOW confidence (<0.5) if you are
  inferring or guessing rather than reading an explicit value.
- "source_span": the exact snippet of the original text you extracted this from,
  or null if the field wasn't found.

Never invent information that is not present in the text. If a field is
absent, set value to null and confidence to 0.0 rather than guessing."""

FIELDS = [
    "patient_name",
    "date_of_birth",
    "chief_complaint",
    "symptom_onset",
    "current_medications",
    "allergies",
    "past_medical_history",
    "insurance_provider",
]


def _build_prompt(raw_text: str) -> str:
    field_list = "\n".join(f"- {f}" for f in FIELDS)
    return f"""Extract the following fields from this intake form text:
{field_list}

Return a JSON object where each key is one of the field names above and
each value is an object of the form:
{{"value": ..., "confidence": 0.0-1.0, "source_span": "..."}}

INTAKE FORM TEXT:
---
{raw_text}
---"""


def extract_fields(raw_text: str) -> ExtractedFields:
    result = call_claude_json(
        prompt=_build_prompt(raw_text),
        system=EXTRACTION_SYSTEM_PROMPT,
        max_tokens=1500,
        task="extract",
    )

    field_values = {}
    for field_name in FIELDS:
        raw_field = result.get(field_name) or {}
        confidence = float(raw_field.get("confidence", 0.0))
        field_values[field_name] = FieldValue(
            value=raw_field.get("value"),
            confidence=confidence,
            source_span=raw_field.get("source_span"),
            flagged=confidence < CONFIDENCE_REVIEW_THRESHOLD,
        )

    return ExtractedFields(**field_values)
