"""
Step 6 of the pipeline: shape validated extracted fields into a FHIR
R4-ish JSON bundle.

Scope note: this covers a small, plausible subset of FHIR resources
(Patient, Condition, AllergyIntolerance, MedicationStatement) relevant
to an intake form -- it is NOT a claim of full FHIR R4 compliance,
which would require a validated resource library and terminology
binding (SNOMED/RxNorm/LOINC codes) well beyond a portfolio project.
"""
import uuid
from datetime import datetime

from models import ExtractedFields


def _entry(resource: dict) -> dict:
    return {"resource": resource, "fullUrl": f"urn:uuid:{uuid.uuid4()}"}


def to_fhir_bundle(fields: ExtractedFields, record_id: str) -> dict:
    data = fields.model_dump()
    patient_id = f"patient-{record_id}"

    entries = [_entry(_patient_resource(data, patient_id))]

    if data["chief_complaint"]["value"]:
        entries.append(_entry(_condition_resource(data, patient_id)))

    if data["allergies"]["value"]:
        entries.append(_entry(_allergy_resource(data, patient_id)))

    if data["current_medications"]["value"]:
        entries.append(_entry(_medication_resource(data, patient_id)))

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "entry": entries,
    }


def _patient_resource(data: dict, patient_id: str) -> dict:
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "name": [{"text": data["patient_name"]["value"]}],
        "birthDate": data["date_of_birth"]["value"],
    }


def _condition_resource(data: dict, patient_id: str) -> dict:
    return {
        "resourceType": "Condition",
        "subject": {"reference": f"Patient/{patient_id}"},
        "code": {"text": data["chief_complaint"]["value"]},
        "onsetString": data["symptom_onset"]["value"],
    }


def _allergy_resource(data: dict, patient_id: str) -> dict:
    return {
        "resourceType": "AllergyIntolerance",
        "patient": {"reference": f"Patient/{patient_id}"},
        "code": {"text": data["allergies"]["value"]},
    }


def _medication_resource(data: dict, patient_id: str) -> dict:
    return {
        "resourceType": "MedicationStatement",
        "subject": {"reference": f"Patient/{patient_id}"},
        "medicationCodeableConcept": {"text": data["current_medications"]["value"]},
        "status": "active",
    }
