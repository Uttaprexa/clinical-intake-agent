// Typed API client for the FastAPI backend. Centralizing fetch calls here
// keeps the pages/components free of URL strings and response parsing.

export type FieldValue = {
  value: string | null;
  confidence: number;
  source_span: string | null;
  flagged: boolean;
};

export type ExtractedFields = {
  patient_name: FieldValue;
  date_of_birth: FieldValue;
  chief_complaint: FieldValue;
  symptom_onset: FieldValue;
  current_medications: FieldValue;
  allergies: FieldValue;
  past_medical_history: FieldValue;
  insurance_provider: FieldValue;
};

export type ValidationIssue = {
  field: string;
  issue: string;
  severity: "error" | "warning";
};

export type ValidationResult = {
  is_valid: boolean;
  overall_confidence: number;
  issues: ValidationIssue[];
  fields_needing_review: string[];
};

export type IntakeRecord = {
  id: string;
  filename: string;
  status:
    | "uploaded"
    | "extracting"
    | "needs_review"
    | "validated"
    | "exported"
    | "failed";
  extracted_fields: ExtractedFields | null;
  validation: ValidationResult | null;
  clinical_summary: string | null;
  fhir_export: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  error: string | null;
};

const BASE = "/api";

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  async uploadIntake(file: File): Promise<{ id: string; status: string }> {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${BASE}/intake/upload`, {
      method: "POST",
      body: formData,
    });
    return handle(res);
  },

  async getQueue(status?: string): Promise<IntakeRecord[]> {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    const res = await fetch(`${BASE}/intake/queue${query}`);
    return handle(res);
  },

  async getIntake(id: string): Promise<IntakeRecord> {
    const res = await fetch(`${BASE}/intake/${id}`);
    return handle(res);
  },

  async updateField(
    id: string,
    fieldName: string,
    newValue: string
  ): Promise<IntakeRecord> {
    const res = await fetch(`${BASE}/intake/${id}/field`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ field_name: fieldName, new_value: newValue }),
    });
    return handle(res);
  },

  async exportIntake(id: string): Promise<Record<string, unknown>> {
    const res = await fetch(`${BASE}/intake/${id}/export`, { method: "POST" });
    return handle(res);
  },

  async getEvalReport(): Promise<EvalReport> {
    const res = await fetch(`${BASE}/eval/latest`);
    return handle(res);
  },
};

export type FieldEvalResult = {
  form: string;
  field: string;
  predicted: string | null;
  ground_truth: string | null;
  correct: boolean;
  hallucinated: boolean;
  reasoning: string;
};

export type EvalReport = {
  total_fields: number;
  correct_fields: number;
  hallucinated_fields: number;
  accuracy: number;
  hallucination_rate: number;
  results: FieldEvalResult[];
};
