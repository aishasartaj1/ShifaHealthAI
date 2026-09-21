import { useState } from "react";
import { postChat } from "../api/client";
import type { ChatResponse } from "../types/api";

interface Turn {
  question: string;
  response?: ChatResponse;
  error?: string;
}

export default function Assistant() {
  const [sessionId] = useState(() => crypto.randomUUID());
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const question = input.trim();
    if (!question || loading) return;

    setInput("");
    setLoading(true);
    setTurns((prev) => [...prev, { question }]);

    try {
      const response = await postChat(question, sessionId);
      setTurns((prev) => prev.map((t, i) => (i === prev.length - 1 ? { ...t, response } : t)));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Something went wrong.";
      setTurns((prev) => prev.map((t, i) => (i === prev.length - 1 ? { ...t, error: message } : t)));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="assistant">
      <h1>Women's Health Assistant</h1>
      <p className="assistant-intro">
        Ask an educational question about menstrual health, PCOS, menopause, contraception, pregnancy
        education, or cervical health screening.
      </p>

      <div className="assistant-turns">
        {turns.map((turn, i) => (
          <article key={i} className="assistant-turn">
            <p className="assistant-question">{turn.question}</p>

            {turn.error && <p className="assistant-error">{turn.error}</p>}

            {turn.response && (
              <div className="assistant-answer">
                <p>{turn.response.answer}</p>

                {turn.response.sources.length > 0 && (
                  <div className="source-cards">
                    <h3>Sources</h3>
                    {turn.response.sources.map((source) => (
                      <a
                        key={source.knowledge_id}
                        className="source-card"
                        href={source.source_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <strong>{source.title}</strong>
                        <span>
                          {source.source_name} · last reviewed {source.last_reviewed_date}
                        </span>
                      </a>
                    ))}
                  </div>
                )}

                {turn.response.related_topics.length > 0 && (
                  <div className="related-topics">
                    <h3>Related topics</h3>
                    {turn.response.related_topics.map((topic) => (
                      <span key={topic.topic_id} className="topic-chip">
                        {topic.topic_name}
                      </span>
                    ))}
                  </div>
                )}

                <p className="disclaimer">{turn.response.disclaimer}</p>
              </div>
            )}
          </article>
        ))}
        {loading && <p className="assistant-loading">Thinking…</p>}
      </div>

      <form className="assistant-form" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. Can PCOS cause irregular periods?"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          Ask
        </button>
      </form>
    </section>
  );
}
