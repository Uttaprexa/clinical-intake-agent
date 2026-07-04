import { useState } from "react";
import { api } from "../lib/api";

/**
 * One-click export: calls the export endpoint, then triggers a browser
 * download of the returned FHIR JSON bundle so a reviewer can hand it
 * straight to an EHR import step.
 */
export function ExportButton({ recordId, disabled }: { recordId: string; disabled?: boolean }) {
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExport() {
    setExporting(true);
    setError(null);
    try {
      const bundle = await api.exportIntake(recordId);
      const blob = new Blob([JSON.stringify(bundle, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `intake-${recordId}-fhir.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="export-button-wrap">
      <button onClick={handleExport} disabled={disabled || exporting}>
        {exporting ? "Exporting..." : "Export to EHR (FHIR JSON)"}
      </button>
      {error && <div className="error-text">{error}</div>}
    </div>
  );
}
