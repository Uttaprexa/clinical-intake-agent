"""
Graders used by the eval harness.

field_accuracy_grader: deterministic-ish semantic match between an
extracted value and the ground truth value, using Claude as a judge
since clinical text has many valid phrasings of the same fact
("sharp pain in lower right abdomen" vs "RLQ abdominal pain").

hallucination_grader: checks whether the extracted value is actually
supported by the source text at all -- this is the check that catches
the failure mode plain accuracy grading misses (a value that happens to
be right by coincidence, or a fabricated-but-plausible value that has
no ground truth ground_truth to compare against).
"""
from pipeline.llm_client import call_claude_json

ACCURACY_SYSTEM_PROMPT = """You are grading a clinical field extraction system.
Given a ground truth value and an extracted (predicted) value for the
same field, judge whether the extracted value is semantically correct --
i.e. conveys the same clinical fact, even if worded differently.

Both null/None should be treated as a MATCH (correctly extracted "not present").
A non-null value graded against a null ground truth, or vice versa, is a MISMATCH.

Return JSON: {"match": true|false, "reasoning": "<one sentence>"}"""

HALLUCINATION_SYSTEM_PROMPT = """You are checking a clinical field extraction
for hallucination. Given the ORIGINAL source text and an EXTRACTED value for
a specific field, judge whether the extracted value is actually supported by
the source text (explicitly stated or a direct, unambiguous paraphrase).

If the extracted value is null, that is never a hallucination.
If the extracted value introduces any detail, specificity, or claim not
present in the source text, that IS a hallucination.

Return JSON: {"hallucinated": true|false, "reasoning": "<one sentence>"}"""


def grade_field_accuracy(field_name: str, predicted, ground_truth) -> dict:
    if predicted == ground_truth:
        return {"match": True, "reasoning": "Exact match"}
    if predicted is None or ground_truth is None:
        return {"match": False, "reasoning": "One value is null, the other is not"}

    prompt = f"""Field: {field_name}
Ground truth value: {ground_truth}
Extracted value: {predicted}"""

    return call_claude_json(prompt, system=ACCURACY_SYSTEM_PROMPT, max_tokens=200, task="grade_accuracy")


def grade_hallucination(field_name: str, predicted, source_text: str) -> dict:
    if predicted is None:
        return {"hallucinated": False, "reasoning": "Null value, nothing to hallucinate"}

    prompt = f"""Field: {field_name}
Extracted value: {predicted}

Original source text:
---
{source_text}
---"""

    return call_claude_json(prompt, system=HALLUCINATION_SYSTEM_PROMPT, max_tokens=200, task="grade_hallucination")
