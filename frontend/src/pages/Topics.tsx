import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getTopicKnowledge, getTopics } from "../api/client";
import type { KnowledgeSummary, Topic } from "../types/api";

export default function Topics() {
  const [searchParams] = useSearchParams();
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(searchParams.get("topic"));
  const [records, setRecords] = useState<KnowledgeSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTopics()
      .then(setTopics)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load topics."));
  }, []);

  useEffect(() => {
    if (!selectedTopicId) {
      setRecords([]);
      return;
    }
    getTopicKnowledge(selectedTopicId)
      .then(setRecords)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load topic knowledge."));
  }, [selectedTopicId]);

  return (
    <section>
      <h1>Knowledge & Topic Explorer</h1>
      {error && <p className="assistant-error">{error}</p>}

      <div className="topic-list">
        {topics.map((topic) => (
          <button
            key={topic.topic_id}
            className={`topic-list-item ${topic.topic_id === selectedTopicId ? "active" : ""}`}
            onClick={() => setSelectedTopicId(topic.topic_id)}
          >
            <strong>{topic.topic_name}</strong>
            <span>{topic.parent_category}</span>
          </button>
        ))}
      </div>

      {selectedTopicId && (
        <div className="knowledge-list">
          <h2>Knowledge records</h2>
          {records.length === 0 && <p>No records yet.</p>}
          {records.map((record) => (
            <div key={record.knowledge_id} className="knowledge-card">
              <strong>{record.title}</strong>
              <p>{record.summary}</p>
              <span className={`status-badge ${record.ai_eligible ? "eligible" : "ineligible"}`}>
                {record.ai_eligible ? "AI-eligible" : `${record.review_status} / ${record.content_status}`}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
