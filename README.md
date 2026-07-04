# Clinical Intake & Documentation Agent

A 6-step LLM pipeline that turns a raw patient intake form (PDF or text)
into a validated, clinician-reviewable summary and a FHIR-shaped export,
with per-field confidence scoring, an eval harness with an LLM-as-judge
hallucination grader, and a React review UI.

Built as a portfolio project modeling the kind of clinical documentation
automation used in real EHR/RCM platforms — not a certified medical device
or HIPAA-compliant production system. See "Scope & honest limitations" below.

## Architecture

```
Upload (PDF/txt) --> FastAPI enqueues job --> Celery worker runs pipeline:

  1. ingest.py    parse PDF/text into raw string
  2. redact.py    strip PHI (regex + LLM) before further processing
  3. extract.py   Claude extracts structured fields + confidence + source span
  4. validate.py  deterministic rule-based validation + confidence aggregation
  5. summarize.py Claude writes a clinical note from the STRUCTURED fields
  6. export.py    shape fields into a FHIR-ish JSON bundle

Result persisted to Postgres (JSONB) --> polled by React Queue/Review UI
```

Extraction runs async via Celery so the upload endpoint returns immediately
instead of blocking an HTTP request on a chain of LLM calls.

## Why this design

- **Redaction runs before extraction's LLM call, not after.** Minimizes how
  much raw PHI transits/is logged by the LLM API in the first place.
- **Validation is deterministic, not another LLM call.** Validation should
  be auditable and reproducible; adding another model call here would just
  add a second source of hallucination risk to a step whose whole job is
  to catch the first one.
- **Summarization reads structured fields, not raw text.** Reduces the
  chance the summary invents detail the extraction step didn't actually
  capture — it can only summarize what's already been extracted.
- **The eval harness grades two different things separately**: accuracy
  (is the value right, semantically) and hallucination (is the value
  actually supported by the source text at all). A field can score "correct"
  by coincidence while still being ungrounded — the regression suite fails
  CI on either metric independently.

## Choosing an LLM provider (free options included)

Set `LLM_PROVIDER` in `backend/.env` -- no code changes needed anywhere else:

| Value | Cost | What it does |
|---|---|---|
| `mock` (default) | Free | Heuristic/regex logic fakes realistic responses. Proves the whole app works end-to-end at zero cost. Won't generalize well to arbitrary new text you didn't design the demo around -- best with the sample forms in `eval/test_set/`. |
| `ollama` | Free | Runs a real open-source LLM locally via [Ollama](https://ollama.com). Actually reasons over whatever you upload. Slower, and noticeably less reliable at structured extraction than Claude, so expect lower eval accuracy. |
| `anthropic` | Paid (small) | Real Claude via the API. Most accurate, what you'd use for a polished demo or recording. |

**To use Ollama:**
```bash
brew install ollama        # or see https://ollama.com/download
ollama serve                # in one terminal, leave running
ollama pull llama3.1        # in another terminal, one-time download (~4.7GB)
```
Then in `backend/.env`:
```
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1
```

## Running it locally

### 1. Backend + infra (Docker)

```bash
cd clinical-intake-agent
cp backend/.env.example backend/.env
# backend/.env defaults to LLM_PROVIDER=mock (free, no key needed) --
# edit it if you want ollama or anthropic instead

docker compose up --build
```

This starts Postgres, Redis, the FastAPI backend (`:8000`), the Celery
worker, and the frontend (`:5173`).

### 2. Or run backend pieces natively (no Docker)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set ANTHROPIC_API_KEY

# terminal 1: infra
docker run -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=clinical_intake postgres:16-alpine
docker run -p 6379:6379 redis:7-alpine

# terminal 2: API
uvicorn main:app --reload

# terminal 3: worker
celery -A worker worker --loglevel=info
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# open http://localhost:5173
```

### 4. Run the eval suite

```bash
cd backend
python -m eval.harness          # prints + writes eval/last_run_report.json
pytest eval/regression.py -v    # enforces 80% accuracy / <10% hallucination thresholds
```

The EvalDashboard page (`/eval` in the frontend) reads
`eval/last_run_report.json` via `GET /api/eval/latest` — run the harness at
least once before viewing it.

CI (`.github/workflows/ci.yml`) runs the regression suite on every push,
using an `ANTHROPIC_API_KEY` repo secret.

## Try it end to end

1. Start everything (`docker compose up --build`, or the native steps above).
2. Go to `http://localhost:5173`, upload one of the sample forms in
   `backend/eval/test_set/*.txt` (or your own `.pdf`/`.txt`).
3. Watch it move through `uploaded -> extracting -> needs_review/validated`
   in the Queue (polls every 4s).
4. Click "Review" — edit any flagged (low-confidence) field inline, then
   hit "Export to EHR (FHIR JSON)" to download the bundle.
5. Check `/eval` for the latest accuracy/hallucination numbers.

## Scope & honest limitations

This is a portfolio project, not production healthcare software:

- **Redaction** is a regex + single LLM pass, not a validated PHI
  de-identification model (e.g. Philter, AWS Comprehend Medical) — it's not
  a HIPAA Safe Harbor-certified pipeline.
- **FHIR export** covers a small, plausible subset of resources (Patient,
  Condition, AllergyIntolerance, MedicationStatement) with no
  terminology binding (no SNOMED/RxNorm/LOINC codes) — it is not a claim
  of full FHIR R4 compliance.
- **No auth/access control** is implemented. A real deployment needs
  authenticated, role-scoped access to patient data before anything else.
- **The eval test set is small and synthetic** (4 forms) — enough to
  demonstrate the harness mechanics and catch obvious regressions, not a
  statistically powered accuracy benchmark.
- **OCR is not implemented** for scanned/image-only PDFs — `ingest.py`
  raises a clear error in that case rather than silently failing.

## Repo layout

```
clinical-intake-agent/
├── backend/
│   ├── main.py, worker.py, models.py, database.py
│   ├── pipeline/           # the 6 pipeline steps + shared llm_client
│   └── eval/               # test set, graders, harness, regression suite
├── frontend/
│   └── src/{pages,components,lib}/
├── docker-compose.yml, Dockerfile.backend, Dockerfile.frontend
└── .github/workflows/ci.yml
```
