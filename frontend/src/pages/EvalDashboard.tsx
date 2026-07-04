import { useEffect, useState } from "react";
import { api, type EvalReport } from "../lib/api";

const MIN_ACCURACY = 0.8;
const MAX_HALLUCINATION_RATE = 0.1;

export function EvalDashboard() {
  const [report, setReport] = useState<EvalReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getEvalReport()
      .then(setReport)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"));
  }, []);

  if (error) {
    return (
      <div className="page">
        <h1>Eval Dashboard</h1>
        <p className="empty-state">{error}</p>
        <p>
          Run <code>python -m eval.harness</code> in <code>backend/</code> to generate a report.
        </p>
      </div>
    );
  }

  if (!report) return <div className="page">Loading eval report...</div>;

  const accuracyPass = report.accuracy >= MIN_ACCURACY;
  const hallucinationPass = report.hallucination_rate <= MAX_HALLUCINATION_RATE;
  const failures = report.results.filter((r) => !r.correct || r.hallucinated);

  return (
    <div className="page">
      <h1>Eval Dashboard</h1>

      <div className="metrics-row">
        <div className={`metric-card ${accuracyPass ? "metric-pass" : "metric-fail"}`}>
          <div className="metric-label">Extraction Accuracy</div>
          <div className="metric-value">{(report.accuracy * 100).toFixed(1)}%</div>
          <div className="metric-threshold">threshold: ≥{MIN_ACCURACY * 100}%</div>
        </div>
        <div className={`metric-card ${hallucinationPass ? "metric-pass" : "metric-fail"}`}>
          <div className="metric-label">Hallucination Rate</div>
          <div className="metric-value">{(report.hallucination_rate * 100).toFixed(1)}%</div>
          <div className="metric-threshold">threshold: ≤{MAX_HALLUCINATION_RATE * 100}%</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Fields Graded</div>
          <div className="metric-value">{report.total_fields}</div>
        </div>
      </div>

      <h3>Failures &amp; Hallucinations</h3>
      {failures.length === 0 ? (
        <p className="empty-state">No failures in the last run.</p>
      ) : (
        <table className="queue-table">
          <thead>
            <tr>
              <th>Form</th>
              <th>Field</th>
              <th>Predicted</th>
              <th>Ground Truth</th>
              <th>Issue</th>
            </tr>
          </thead>
          <tbody>
            {failures.map((r, i) => (
              <tr key={i}>
                <td>{r.form}</td>
                <td>{r.field}</td>
                <td>{r.predicted ?? "—"}</td>
                <td>{r.ground_truth ?? "—"}</td>
                <td>
                  {!r.correct && <span className="badge badge-low">wrong</span>}{" "}
                  {r.hallucinated && <span className="badge badge-low">hallucinated</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
