import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type IntakeRecord } from "../lib/api";

const STATUS_LABELS: Record<string, string> = {
  uploaded: "Uploaded",
  extracting: "Processing...",
  needs_review: "Needs Review",
  validated: "Validated",
  exported: "Exported",
  failed: "Failed",
};

export function Queue() {
  const [records, setRecords] = useState<IntakeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploadError, setUploadError] = useState<string | null>(null);

  async function refresh() {
    try {
      const data = await api.getQueue();
      setRecords(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // Poll every 4s so in-flight LLM pipeline jobs show up without a manual refresh.
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
  }, []);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError(null);
    try {
      await api.uploadIntake(file);
      await refresh();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      e.target.value = "";
    }
  }

  return (
    <div className="page">
      <h1>Intake Queue</h1>

      <div className="upload-box">
        <label className="upload-label">
          Upload intake form (.pdf or .txt)
          <input type="file" accept=".pdf,.txt" onChange={handleUpload} hidden />
        </label>
        {uploadError && <div className="error-text">{uploadError}</div>}
      </div>

      {loading ? (
        <p>Loading queue...</p>
      ) : records.length === 0 ? (
        <p className="empty-state">No intake forms yet. Upload one to get started.</p>
      ) : (
        <table className="queue-table">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Status</th>
              <th>Confidence</th>
              <th>Uploaded</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {records.map((r) => (
              <tr key={r.id}>
                <td>{r.filename}</td>
                <td>
                  <span className={`status-pill status-${r.status}`}>
                    {STATUS_LABELS[r.status] ?? r.status}
                  </span>
                </td>
                <td>
                  {r.validation ? `${Math.round(r.validation.overall_confidence * 100)}%` : "—"}
                </td>
                <td>{new Date(r.created_at).toLocaleString()}</td>
                <td>
                  <Link to={`/review/${r.id}`}>Review</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
