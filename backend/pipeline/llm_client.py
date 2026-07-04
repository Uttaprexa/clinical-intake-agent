"""
Shared LLM client used by every pipeline stage that needs a model call
(extract, summarize, redact-assist, and the eval graders).

Supports three providers via the LLM_PROVIDER env var, so the same
pipeline code runs unchanged whether you're demoing for free or paying
for real Claude quality:

  - "mock"      (default-free): no network calls, no API key. Uses
                 regex/heuristic logic to fake realistic responses
                 against the sample forms. Good for proving the whole
                 app works end-to-end at zero cost. Will NOT generalize
                 well to arbitrary new text you didn't design the demo around.
  - "ollama"    free, real LLM, runs locally via Ollama (no API key,
                 no per-call cost, slower, less accurate than Claude).
  - "anthropic" real Claude via the API (costs a small amount of credit,
                 most accurate, what you'd use for a final demo/recording).

Switch providers by setting LLM_PROVIDER in backend/.env -- no code
changes needed anywhere else in the pipeline.
"""
import json
import os
import re

import requests
from anthropic import Anthropic

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "mock").lower()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")

_client: Anthropic | None = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


def call_claude(
    prompt: str,
    system: str = "",
    max_tokens: int = 1024,
    model: str = DEFAULT_MODEL,
    task: str = "generic",
) -> str:
    """Single-turn text completion, routed to whichever provider is configured."""
    if LLM_PROVIDER == "mock":
        return _mock_text(task, prompt)
    if LLM_PROVIDER == "ollama":
        return _call_ollama(prompt, system, max_tokens)

    client = get_client()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def call_claude_json(
    prompt: str,
    system: str = "",
    max_tokens: int = 1024,
    model: str = DEFAULT_MODEL,
    task: str = "generic",
) -> dict:
    """Calls the configured provider and parses a JSON object out of the response."""
    if LLM_PROVIDER == "mock":
        return _mock_json(task, prompt)

    json_system = (
        system
        + "\n\nRespond with ONLY a valid JSON object. No preamble, no "
        "markdown code fences, no explanation before or after the JSON."
    )
    raw = call_claude(prompt, system=json_system, max_tokens=max_tokens, model=model, task=task)
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Could not parse JSON from model response: {raw[:300]}")


# --------------------------------------------------------------------------
# Ollama backend (free, local, real LLM)
# --------------------------------------------------------------------------

def _call_ollama(prompt: str, system: str, max_tokens: int) -> str:
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
            timeout=180,
        )
        resp.raise_for_status()
        return resp.json()["response"]
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            "Could not reach Ollama at "
            f"{OLLAMA_URL}. Is it running? Try `ollama serve` "
            f"and `ollama pull {OLLAMA_MODEL}` first."
        ) from exc


# --------------------------------------------------------------------------
# Mock backend (free, no network, heuristic-only -- see module docstring)
# --------------------------------------------------------------------------

_STOPWORDS = {"the", "a", "an", "of", "and", "or", "with", "for", "to", "in", "on", "at"}

_FIELD_PATTERNS = {
    "patient_name": r"(?:Patient Name|Full Name|Name)[ \t]*:[ \t]*([^\n]+)",
    "date_of_birth": r"(?:Date of Birth|DOB|Birth date|Birth Date)[ \t]*:[ \t]*([^\n]+)",
    "chief_complaint": r"(?:Reason for visit|Chief complaint|Presenting complaint|Complaint)[ \t]*:[ \t]*([^\n]+)",
    "current_medications": r"(?:Current medications|Medications|Current meds)[ \t]*:[ \t]*([^\n]+)",
    "allergies": r"Allergies[ \t]*:[ \t]*([^\n]+)",
    "past_medical_history": r"(?:Past medical history|History)[ \t]*:[ \t]*([^\n]+)",
    "insurance_provider": r"Insurance(?: Provider)?[ \t]*:[ \t]*([^\n]+)",
}

# \s+ (not a literal space) after "since"/"past" so line-wrapped forms
# ("...since\nyesterday evening") still match. The negative lookahead on
# "past" excludes "Past medical history" lines, which otherwise greedily
# swallowed as a false "onset" match.
_ONSET_PATTERN = re.compile(
    r"(since\s+[^.\n]+|"
    r"for\s+(?:about |roughly )?\d+\s*(?:day|week|month|year)s?(?:\s+ago)?|"
    r"past(?!\s*medical)\s+[^.\n]+|"
    r"[0-9]+\s+(?:day|week|month)s?\s+ago)",
    re.IGNORECASE,
)


def _extract_between(text: str, start: str, end: str) -> str:
    if start in text and end in text:
        return text.split(start, 1)[1].rsplit(end, 1)[0].strip()
    return text


def _mock_json(task: str, prompt: str) -> dict:
    if task == "extract":
        return _mock_extract(prompt)
    if task == "redact_names":
        return _mock_redact_names(prompt)
    if task == "grade_accuracy":
        return _mock_grade_accuracy(prompt)
    if task == "grade_hallucination":
        return _mock_grade_hallucination(prompt)
    return {}


def _mock_text(task: str, prompt: str) -> str:
    if task == "summarize":
        return _mock_summarize(prompt)
    return ""


def _mock_extract(prompt: str) -> dict:
    raw_text = _extract_between(prompt, "INTAKE FORM TEXT:\n---\n", "\n---")
    result = {}

    for field, pattern in _FIELD_PATTERNS.items():
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            value = match.group(1).strip().rstrip(".")
            result[field] = {"value": value, "confidence": 0.85, "source_span": match.group(0).strip()}
        else:
            result[field] = {"value": None, "confidence": 0.0, "source_span": None}

    onset_match = _ONSET_PATTERN.search(raw_text)
    if onset_match:
        cleaned_value = re.sub(r"\s+", " ", onset_match.group(0)).strip()
        result["symptom_onset"] = {
            "value": cleaned_value,
            "confidence": 0.7,
            "source_span": cleaned_value,
        }
    else:
        result["symptom_onset"] = {"value": None, "confidence": 0.0, "source_span": None}

    return result


def _mock_summarize(prompt: str) -> str:
    fields = dict(re.findall(r"- (\w+): (.+)", prompt))
    parts = []
    if fields.get("chief_complaint"):
        onset = f" ({fields['symptom_onset']})" if fields.get("symptom_onset") else ""
        parts.append(f"Patient presents with {fields['chief_complaint']}{onset}.")
    if fields.get("current_medications"):
        parts.append(f"Current medications: {fields['current_medications']}.")
    if fields.get("allergies"):
        parts.append(f"Allergies: {fields['allergies']}.")
    if fields.get("past_medical_history"):
        parts.append(f"Past medical history: {fields['past_medical_history']}.")
    return " ".join(parts) or "Insufficient extracted information to generate a summary."


def _mock_redact_names(prompt: str) -> dict:
    text = _extract_between(prompt, "Text to scan:\n---\n", "\n---")
    # Heuristic: two-or-more consecutive Capitalized Words, e.g. "Maria Gonzalez",
    # "Raj Patel" -- a crude stand-in for NER, good enough for a free demo.
    candidates = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text)
    return {"names_and_addresses": list(dict.fromkeys(candidates))}  # dedupe, keep order


def _significant_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _mock_grade_accuracy(prompt: str) -> dict:
    gt_match = re.search(r"Ground truth value:\s*(.+)", prompt)
    pred_match = re.search(r"Extracted value:\s*(.+)", prompt)
    gt = (gt_match.group(1).strip() if gt_match else "").lower()
    pred = (pred_match.group(1).strip() if pred_match else "").lower()

    gt_words = _significant_words(gt)
    pred_words = _significant_words(pred)
    overlap = gt_words & pred_words

    match = bool(overlap) and len(overlap) >= max(1, len(gt_words) // 2)
    return {"match": match, "reasoning": f"mock: {len(overlap)}/{len(gt_words)} key words overlap"}


def _mock_grade_hallucination(prompt: str) -> dict:
    pred_match = re.search(r"Extracted value:\s*(.+)", prompt)
    source = _extract_between(prompt, "Original source text:\n---\n", "\n---")
    pred = (pred_match.group(1).strip() if pred_match else "").lower()

    pred_words = _significant_words(pred)
    source_words = _significant_words(source)
    grounded = bool(pred_words) and len(pred_words & source_words) >= max(1, len(pred_words) // 2)

    return {
        "hallucinated": not grounded,
        "reasoning": "mock: extracted words " + ("found" if grounded else "not found") + " in source",
    }
