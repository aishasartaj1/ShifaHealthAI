import { useEffect, useState } from "react";
import { getQualitySummary } from "../api/client";
import type { QualitySummary } from "../types/api";

export default function AdminOverview() {
  const [summary, setSummary] = useState<QualitySummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getQualitySummary()
      .then(setSummary)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load quality summary."));
  }, []);

  return (
    <section>
      <h1>AI/Data Operations Console</h1>
      <p>Governance, data quality, agent traces, and analytics.</p>

      {error && <p className="assistant-error">{error}</p>}
      {!summary && !error && <p>Loading…</p>}

      {summary && (
        <>
          <div className="stat-row">
            <div className="stat-tile">
              <strong>{summary.total_knowledge_count}</strong>
              <span>Knowledge records</span>
            </div>
            <div className="stat-tile">
              <strong>{summary.eligible_count}</strong>
              <span>AI-eligible</span>
            </div>
            <div className="stat-tile">
              <strong>{summary.eligible_percentage}%</strong>
              <span>Eligibility rate</span>
            </div>
            <div className="stat-tile">
              <strong>{summary.ineligible_records.length}</strong>
              <span>Flagged records</span>
            </div>
          </div>

          <h2>Coverage by topic</h2>
          <table className="admin-table">
            <thead>
              <tr>
                <th>Topic</th>
                <th>Total</th>
                <th>Eligible</th>
                <th>Needs review</th>
                <th>Expired</th>
                <th>Stale</th>
              </tr>
            </thead>
            <tbody>
              {summary.by_topic.map((row) => (
                <tr key={row.topic_id}>
                  <td>{row.topic_name}</td>
                  <td>{row.total_count}</td>
                  <td>{row.eligible_count}</td>
                  <td>{row.needs_review_count}</td>
                  <td>{row.expired_count}</td>
                  <td>{row.stale_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
