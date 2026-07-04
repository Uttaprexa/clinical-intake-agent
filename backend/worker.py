"""
Celery worker: orchestrates the 6-step pipeline as one async job so the
API can return immediately on upload and the frontend polls/receives
status updates instead of blocking an HTTP request on an LLM call chain.

Run with:
    celery -A worker worker --loglevel=info
"""
import os

from celery import Celery
from celery.utils.log import get_task_logger

from database import IntakeRepository, init_db
from models import IntakeRecord, IntakeStatus
from pipeline.ingest import IngestError, ingest_file
from pipeline.extract import extract_fields
from pipeline.validate import validate_fields
from pipeline.summarize import summarize_intake
from pipeline.redact import redact_phi
from pipeline.export import to_fhir_bundle

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("clinical_intake", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(task_track_started=True, task_time_limit=300)

logger = get_task_logger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def process_intake(self, record_id: str, file_path: str):
    """
    Runs the full pipeline for one uploaded intake form:
    ingest -> redact -> extract -> validate -> summarize -> export.

    Redaction runs right after ingest, before the raw text is used in any
    further LLM calls or persisted in eval traces, so PHI exposure is
    minimized as early as possible in the pipeline.
    """
    init_db()
    record = IntakeRepository.get(record_id)
    if record is None:
        record = IntakeRecord(id=record_id, filename=os.path.basename(file_path))

    try:
        record.status = IntakeStatus.EXTRACTING
        IntakeRepository.save(record)

        raw_text = ingest_file(file_path)
        record.raw_text = raw_text

        redaction = redact_phi(raw_text)
        record.redacted_text = redaction.redacted_text
        logger.info(
            "Redacted %d PHI spans (%s) for record %s",
            redaction.phi_spans_removed,
            redaction.phi_types_found,
            record_id,
        )

        fields = extract_fields(raw_text)
        record.extracted_fields = fields

        validation = validate_fields(fields)
        record.validation = validation

        record.clinical_summary = summarize_intake(fields)
        record.fhir_export = to_fhir_bundle(fields, record_id)

        record.status = (
            IntakeStatus.VALIDATED if validation.is_valid else IntakeStatus.NEEDS_REVIEW
        )

    except IngestError as exc:
        record.status = IntakeStatus.FAILED
        record.error = str(exc)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline failed for record %s", record_id)
        record.status = IntakeStatus.FAILED
        record.error = f"{type(exc).__name__}: {exc}"
        raise self.retry(exc=exc)
    finally:
        IntakeRepository.save(record)

    return record.status.value
