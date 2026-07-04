import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, type IntakeRecord } from "../lib/api";
import { FieldEditor } from "../components/FieldEditor";
import { ExportButton } from "../components/ExportButton";

const FIELD_LABELS: Record<string, string> = {
  patient_name: "Patient Name",
  date_of_birth: "Date of Birth",
  chief_complaint: "Chief Complaint",
  symptom_onset: "Symptom Onset",
  current_medications: "Current Medications",
  allergies: "Allergies",
  past_medical_history: "Past Medical History",
  insurance_provider: "Insurance Provider",
};

export function Review() {
  const { id } = useParams<{ id: string }>();
  const [record, setRecord] = useState<IntakeRecord | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    if (!id) return;
    const data = await api.getIntake(id);
    setRecord(data);
    setLoading(false);
  }

  useEffect(() => {
    refresh();
  }, [id]);

  async function handleFieldSave(fieldName: string, newValue: string) {
    if (!id) return;
    const updated = await api.updateField(id, fieldName, newValue);
    setRecord(updated);
  }

  if (loading) return <div className="page">Loading...</div>;
  if (!record) return <div className="page">Record not found.</div>;

  return (
    <div className="page">
      <Link to="/">&larr; Back to queue</Link>
      <h1>{record.filename}</h1>

      {record.status === "extracting" && (
        <p className="empty-state">Still processing this form — check back shortly.</p>
      )}

      {record.status === "failed" && (
        <p className="error-text">Pipeline failed: {record.error}</p>
      )}

      {record.validation && record.validation.issues.length > 0 && (
        <div className="issues-box">
          <h3>Validation Issues</h3>
          <ul>
            {record.validation.issues.map((issue, i) => (
              <li key={i} className={`issue-${issue.severity}`}>
                <strong>{FIELD_LABELS[issue.field] ?? issue.field}:</strong> {issue.issue}
              </li>
            ))}
          </ul>
        </div>
      )}

      {record.extracted_fields && (
        <div className="fields-box">
          <h3>Extracted Fields</h3>
          {Object.entries(record.extracted_fields).map(([fieldName, field]) => (
            <FieldEditor
              key={fieldName}
              fieldName={fieldName}
              label={FIELD_LABELS[fieldName] ?? fieldName}
              field={field}
              onSave={handleFieldSave}
            />
          ))}
        </div>
      )}

      {record.clinical_summary && (
        <div className="summary-box">
          <h3>Clinical Summary</h3>
          <p>{record.clinical_summary}</p>
        </div>
      )}

      {record.extracted_fields && (
        <ExportButton recordId={record.id} disabled={record.status === "extracting"} />
      )}
    </div>
  );
}
