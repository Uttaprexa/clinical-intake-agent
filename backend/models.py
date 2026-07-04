"""
Pydantic schemas shared across the pipeline, API, and eval harness.

Design note: FieldValue carries a confidence score alongside every extracted
value so the frontend can render per-field confidence flags and reviewers
can triage low-confidence fields first, instead of re-reading every field.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class IntakeStatus(str, Enum):
    UPLOADED = "uploaded"
    EXTRACTING = "extracting"
    NEEDS_REVIEW = "needs_review"
    VALIDATED = "validated"
    EXPORTED = "exported"
    FAILED = "failed"


class FieldValue(BaseModel):
    value: Optional[Any] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    source_span: Optional[str] = None  # raw text the value was extracted from
    flagged: bool = False  # True if confidence < threshold, needs human review


class ExtractedFields(BaseModel):
    """The structured clinical intake schema we extract from raw forms.

    Kept intentionally flat and small for the portfolio version -- in a real
    system this would be a much larger, versioned schema (or map to FHIR
    Questionnaire/QuestionnaireResponse directly).
    """
    patient_name: FieldValue = Field(default_factory=FieldValue)
    date_of_birth: FieldValue = Field(default_factory=FieldValue)
    chief_complaint: FieldValue = Field(default_factory=FieldValue)
    symptom_onset: FieldValue = Field(default_factory=FieldValue)
    current_medications: FieldValue = Field(default_factory=FieldValue)
    allergies: FieldValue = Field(default_factory=FieldValue)
    past_medical_history: FieldValue = Field(default_factory=FieldValue)
    insurance_provider: FieldValue = Field(default_factory=FieldValue)


class ValidationIssue(BaseModel):
    field: str
    issue: str
    severity: str  # "error" | "warning"


class ValidationResult(BaseModel):
    is_valid: bool
    overall_confidence: float
    issues: list[ValidationIssue] = Field(default_factory=list)
    fields_needing_review: list[str] = Field(default_factory=list)


class RedactionResult(BaseModel):
    redacted_text: str
    phi_spans_removed: int
    phi_types_found: list[str] = Field(default_factory=list)


class IntakeRecord(BaseModel):
    id: str
    filename: str
    status: IntakeStatus = IntakeStatus.UPLOADED
    raw_text: Optional[str] = None
    redacted_text: Optional[str] = None
    extracted_fields: Optional[ExtractedFields] = None
    validation: Optional[ValidationResult] = None
    clinical_summary: Optional[str] = None
    fhir_export: Optional[dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None


class FieldUpdateRequest(BaseModel):
    """Payload for a human reviewer correcting a field in the Review UI."""
    field_name: str
    new_value: Any


class UploadResponse(BaseModel):
    id: str
    status: IntakeStatus


CONFIDENCE_REVIEW_THRESHOLD = 0.75
