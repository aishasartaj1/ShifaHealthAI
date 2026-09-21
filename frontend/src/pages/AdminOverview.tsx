import { useEffect, useState } from "react";
import { getAnalyticsSummary, getQualitySummary } from "../api/client";
import type { AnalyticsSummary, QualitySummary } from "../types/api";

export default function AdminOverview() {
  const [summary, setSummary] = useState<QualitySummary | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getQualitySummary()
      .then(setSummary)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load quality summary."));
    getAnalyticsSummary()
      .then(setAnalytics)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load analytics."));
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

      {analytics && (
        <>
          <h2>Interaction analytics</h2>
          <p className="analytics-note">
            From curated.fact_user_question, aggregated by scripts/refresh_analytics.py. Refreshed{" "}
            {analytics.computed_at ? new Date(analytics.computed_at).toLocaleString() : "never yet"}.
          </p>
          <div className="stat-row">
            <div className="stat-tile">
              <strong>{analytics.global.total_questions_asked ?? 0}</strong>
              <span>Questions asked</span>
            </div>
            <div className="stat-tile">
              <strong>{analytics.global.total_responses_generated ?? 0}</strong>
              <span>Responses generated</span>
            </div>
            <div className="stat-tile">
              <strong>{Math.round(analytics.global.avg_response_latency_ms ?? 0)} ms</strong>
              <span>Avg. response latency</span>
            </div>
            <div className="stat-tile">
              <strong>{analytics.global.total_source_opens ?? 0}</strong>
              <span>Source opens</span>
            </div>
            <div className="stat-tile">
              <strong>
                👍 {analytics.global.feedback_up_count ?? 0} / 👎 {analytics.global.feedback_down_count ?? 0}
              </strong>
              <span>Feedback</span>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
