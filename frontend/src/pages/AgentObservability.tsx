import { useEffect, useState } from "react";
import { getRecentAgentTraces } from "../api/client";
import type { AgentTraceSummary } from "../types/api";

export default function AgentObservability() {
  const [traces, setTraces] = useState<AgentTraceSummary[]>([]);
  const [selected, setSelected] = useState<AgentTraceSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRecentAgentTraces(20)
      .then(setTraces)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load agent traces."));
  }, []);

  return (
    <section>
      <h1>Agent Observability</h1>
      <p>
        Tool calls, retrieval candidate counts, and latency for recent questions. Traces are held
        in-memory by this backend instance (not yet persisted via the streaming pipeline — see Phase 7).
      </p>

      {error && <p className="assistant-error">{error}</p>}
      {traces.length === 0 && !error && <p>No traces yet — ask the assistant a question first.</p>}

      <div className="trace-layout">
        <ul className="trace-list">
          {traces.map((trace) => (
            <li key={trace.trace_id}>
              <button className={selected?.trace_id === trace.trace_id ? "active" : ""} onClick={() => setSelected(trace)}>
                <strong>{trace.question}</strong>
                <span>
                  {trace.tool_calls.length} tool call(s) · {trace.total_latency_ms} ms
                </span>
              </button>
            </li>
          ))}
        </ul>

        {selected && (
          <div className="trace-detail">
            <h2>{selected.question}</h2>
            <p>Total latency: {selected.total_latency_ms} ms</p>
            {selected.tool_calls.map((call, i) => (
              <div key={i} className="tool-call-card">
                <strong>{call.tool}</strong>
                <span>{call.latency_ms} ms</span>
                <pre>{JSON.stringify(call.args)}</pre>
                <pre>{JSON.stringify(call.result_summary)}</pre>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
