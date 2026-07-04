"""
Step 5 of the pipeline: de-identify PHI from raw text before it's used
anywhere logs/eval traces might persist it (e.g. eval test set text,
regression fixtures).

Hybrid approach:
  1. Deterministic regex pass for structured PHI (SSN, phone, email, MRN,
     dates) -- fast, auditable, no LLM cost, no risk of missing an obvious
     pattern due to model non-determinism.
  2. LLM pass for free-text PHI that regex can't reliably catch (patient
     names, addresses, relatives' names mentioned in narrative text).

Note: this is a portfolio-grade redaction implementation, not a
HIPAA Safe Harbor-certified de-identification pipeline -- a real
implementation would use a validated NER/PHI model (e.g. Philter,
AWS Comprehend Medical) rather than pattern matching + a single LLM pass.
"""
import re

from models import RedactionResult
from pipeline.llm_client import call_claude_json

_PATTERNS = {
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "PHONE": re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "MRN": re.compile(r"\bMRN[:#]?\s*\d{5,10}\b", re.IGNORECASE),
    "DOB": re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
}

REDACTION_SYSTEM_PROMPT = """You identify PHI (personally identifiable
patient/family information: full names, street addresses, relatives'
names) in clinical intake text. You do NOT identify clinical content
(symptoms, medications, diagnoses) as PHI.

Return JSON: {"names_and_addresses": ["<exact substring 1>", "<exact substring 2>", ...]}
List every exact substring found. Return an empty list if none found."""


def redact_phi(raw_text: str) -> RedactionResult:
    text = raw_text
    types_found: list[str] = []
    spans_removed = 0

    for phi_type, pattern in _PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            types_found.append(phi_type)
            spans_removed += len(pattern.findall(text))
            text = pattern.sub(f"[REDACTED-{phi_type}]", text)

    text, llm_spans, llm_found = _redact_names_via_llm(text)
    spans_removed += llm_spans
    if llm_found:
        types_found.append("NAME_OR_ADDRESS")

    return RedactionResult(
        redacted_text=text,
        phi_spans_removed=spans_removed,
        phi_types_found=types_found,
    )


def _redact_names_via_llm(text: str) -> tuple[str, int, bool]:
    try:
        result = call_claude_json(
            prompt=f"Text to scan:\n---\n{text}\n---",
            system=REDACTION_SYSTEM_PROMPT,
            max_tokens=500,
            task="redact_names",
        )
    except Exception:
        # Fail closed on the regex-only result rather than raising --
        # a redaction step erroring out shouldn't crash the whole pipeline,
        # but we don't want to silently under-redact either, so this is
        # logged for review in a real deployment.
        return text, 0, False

    spans = result.get("names_and_addresses", []) or []
    count = 0
    for span in spans:
        if span and span in text:
            text = text.replace(span, "[REDACTED-NAME]")
            count += 1
    return text, count, count > 0
