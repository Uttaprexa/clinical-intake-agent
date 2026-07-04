"""
FastAPI app: upload intake forms, poll the queue, review/edit extracted
fields, and export the FHIR bundle. Heavy lifting (the LLM pipeline)
happens in worker.py via Celery -- this app only reads/writes Postgres
and enqueues jobs, so it stays responsive under load.
"""
import json
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from database import IntakeRepository, init_db
from models import (
    FieldUpdateRequest,
    IntakeRecord,
    IntakeStatus,
    UploadResponse,
)
from worker import process_intake

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/tmp/clinical-intake-uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Clinical Intake & Documentation Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.post("/api/intake/upload", response_model=UploadResponse)
async def upload_intake(file: UploadFile):
    if file.filename is None or not file.filename.lower().endswith((".pdf", ".txt")):
        raise HTTPException(400, "Only .pdf and .txt files are supported")

    record_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{record_id}_{file.filename}"
    dest.write_bytes(await file.read())

    record = IntakeRecord(id=record_id, filename=file.filename, status=IntakeStatus.UPLOADED)
    IntakeRepository.save(record)

    process_intake.delay(record_id, str(dest))

    return UploadResponse(id=record_id, status=record.status)


@app.get("/api/intake/queue", response_model=list[IntakeRecord])
def get_queue(status: str | None = None):
    return IntakeRepository.list(status=status)


@app.get("/api/intake/{record_id}", response_model=IntakeRecord)
def get_intake(record_id: str):
    record = IntakeRepository.get(record_id)
    if record is None:
        raise HTTPException(404, "Record not found")
    return record


@app.patch("/api/intake/{record_id}/field", response_model=IntakeRecord)
def update_field(record_id: str, update: FieldUpdateRequest):
    """
    Applies a human reviewer's correction to one field. Corrected fields
    are pinned to confidence=1.0 and unflagged, since a human has now
    verified them -- this is also where you'd log a (before, after) pair
    to build a fine-tuning/few-shot correction dataset over time.
    """
    record = IntakeRepository.get(record_id)
    if record is None:
        raise HTTPException(404, "Record not found")
    if record.extracted_fields is None:
        raise HTTPException(400, "Record has no extracted fields yet")

    fields_dict = record.extracted_fields.model_dump()
    if update.field_name not in fields_dict:
        raise HTTPException(400, f"Unknown field: {update.field_name}")

    fields_dict[update.field_name]["value"] = update.new_value
    fields_dict[update.field_name]["confidence"] = 1.0
    fields_dict[update.field_name]["flagged"] = False

    from models import ExtractedFields
    from pipeline.validate import validate_fields

    record.extracted_fields = ExtractedFields(**fields_dict)
    record.validation = validate_fields(record.extracted_fields)
    if record.validation.is_valid:
        record.status = IntakeStatus.VALIDATED

    IntakeRepository.save(record)
    return record


@app.post("/api/intake/{record_id}/export")
def export_intake(record_id: str):
    record = IntakeRepository.get(record_id)
    if record is None:
        raise HTTPException(404, "Record not found")
    if record.fhir_export is None:
        raise HTTPException(400, "Record has not been processed yet")

    record.status = IntakeStatus.EXPORTED
    IntakeRepository.save(record)
    return record.fhir_export


@app.get("/api/eval/latest")
def get_latest_eval_report():
    """
    Serves the most recent eval/harness.py run so the EvalDashboard page
    can show real accuracy/hallucination numbers without re-running the
    (LLM-calling, non-trivial-cost) eval suite on every page load.
    Run `python -m eval.harness` from backend/ to refresh this.
    """
    report_path = Path(__file__).parent / "eval" / "last_run_report.json"
    if not report_path.exists():
        raise HTTPException(
            404, "No eval report found yet. Run `python -m eval.harness` first."
        )
    return json.loads(report_path.read_text())


@app.get("/health")
def health():
    return {"status": "ok"}
