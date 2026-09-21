import { useEffect, useState } from "react";
import { getQualitySummary } from "../api/client";
import type { QualitySummary } from "../types/api";

export default function Governance() {
  const [summary, setSummary] = useState<QualitySummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getQualitySummary()
      .then(setSummary)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load governance data."));
  }, []);

  return (
    <section>
      <h1>Governance</h1>
      <p>
        Records that are currently excluded from AI generation context, and why. A record showing up
        here does not mean it was deleted — it means the governance gate (review status, source status,
        content status) is holding it back until it's re-reviewed.
      </p>

      {error && <p className="assistant-error">{error}</p>}
      {summary && summary.ineligible_records.length === 0 && <p>Everything currently passes governance.</p>}

      {summary && summary.ineligible_records.length > 0 && (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Topic</th>
              <th>Title</th>
              <th>Review status</th>
              <th>Content status</th>
            </tr>
          </thead>
          <tbody>
            {summary.ineligible_records.map((record) => (
              <tr key={record.knowledge_id}>
                <td>{record.topic_name}</td>
                <td>{record.title}</td>
                <td>
                  <span className="status-badge ineligible">{record.review_status}</span>
                </td>
                <td>{record.content_status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
