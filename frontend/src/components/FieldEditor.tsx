import { useState } from "react";
import type { FieldValue } from "../lib/api";
import { ConfidenceFlag } from "./ConfidenceFlag";

type Props = {
  label: string;
  fieldName: string;
  field: FieldValue;
  onSave: (fieldName: string, newValue: string) => Promise<void>;
};

/**
 * One row in the Review page: label, value (editable on click), and a
 * confidence badge. Saving pins the field's confidence to 1.0 server-side
 * since a human has now verified it.
 */
export function FieldEditor({ label, fieldName, field, onSave }: Props) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(field.value ?? "");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(fieldName, draft);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={`field-row ${field.flagged ? "field-flagged" : ""}`}>
      <div className="field-label">{label}</div>
      {editing ? (
        <div className="field-edit">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            autoFocus
          />
          <button onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </button>
          <button onClick={() => setEditing(false)} disabled={saving}>
            Cancel
          </button>
        </div>
      ) : (
        <div className="field-display" onClick={() => setEditing(true)}>
          <span className="field-value">{field.value ?? "—"}</span>
          <ConfidenceFlag field={field} />
        </div>
      )}
    </div>
  );
}
