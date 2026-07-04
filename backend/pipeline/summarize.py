"""
Step 4 of the pipeline: generate a clinician-facing clinical note summary
from the validated, structured fields (not the raw text) -- summarizing
from structured fields rather than free text reduces the chance the
summary introduces details the extraction step didn't actually capture.
"""
from models import ExtractedFields
from pipeline.llm_client import call_claude

SUMMARY_SYSTEM_PROMPT = """You are a clinical documentation assistant.
Write a concise clinical intake summary (3-5 sentences) in the style of
a physician's note, using ONLY the structured fields provided. Do not
add, infer, or embellish any clinical detail not present in the fields.
If a field is null, simply omit it rather than noting its absence."""


def summarize_intake(fields: ExtractedFields) -> str:
    data = fields.model_dump()
    field_lines = "\n".join(
        f"- {name}: {info['value']}"
        for name, info in data.items()
        if info["value"] not in (None, "")
    )

    if not field_lines:
        return "Insufficient extracted information to generate a summary."

    prompt = f"""Structured intake fields:
{field_lines}

Write the clinical intake summary now."""

    return call_claude(prompt, system=SUMMARY_SYSTEM_PROMPT, max_tokens=400, task="summarize")
