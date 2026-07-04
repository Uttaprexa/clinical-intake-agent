import type { FieldValue } from "../lib/api";

/**
 * Renders a small confidence badge next to an extracted field.
 * Reviewers scan for red/amber badges to triage which fields actually
 * need a human look, instead of re-reading every field on every form.
 */
export function ConfidenceFlag({ field }: { field: FieldValue }) {
  if (field.value === null) {
    return <span className="badge badge-neutral">not found</span>;
  }

  const pct = Math.round(field.confidence * 100);
  const level = field.confidence >= 0.9 ? "high" : field.confidence >= 0.75 ? "medium" : "low";

  return (
    <span className={`badge badge-${level}`} title={field.source_span ?? undefined}>
      {pct}%
    </span>
  );
}
