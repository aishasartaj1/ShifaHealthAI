// Mirrors backend/src/schemas/chat.py and the repository/route return shapes in
// backend/src/repositories/bigquery.py + backend/src/api/*.py. Kept minimal and hand-written
// rather than generated, since the surface is small and stable enough that codegen would be
// more ceremony than value at this size.

export interface SourceCard {
  knowledge_id: string;
  title: string;
  source_name: string;
  source_url: string;
  last_reviewed_date: string;
}

export interface RelatedTopic {
  topic_id: string;
  topic_name: string;
}

export interface ChatResponse {
  answer: string;
  sources: SourceCard[];
  related_topics: RelatedTopic[];
  disclaimer: string;
  trace_id: string;
}

export interface Topic {
  topic_id: string;
  topic_name: string;
  parent_category: string;
  description: string;
}

export interface KnowledgeSummary {
  knowledge_id: string;
  title: string;
  summary: string;
  review_status: "APPROVED" | "NEEDS_REVIEW" | "EXPIRED";
  content_status: "CURRENT" | "STALE";
  ai_eligible: boolean;
}

export interface TopicQualitySummary {
  topic_id: string;
  topic_name: string;
  total_count: number;
  eligible_count: number;
  approved_count: number;
  needs_review_count: number;
  expired_count: number;
  stale_count: number;
}

export interface IneligibleRecord {
  knowledge_id: string;
  topic_id: string;
  topic_name: string;
  title: string;
  review_status: string;
  content_status: string;
}

export interface QualitySummary {
  total_knowledge_count: number;
  eligible_count: number;
  eligible_percentage: number;
  by_topic: TopicQualitySummary[];
  ineligible_records: IneligibleRecord[];
}

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  latency_ms: number;
  result_summary: Record<string, unknown>;
}

export interface AgentTraceSummary {
  trace_id: string;
  question: string;
  tool_calls: ToolCall[];
  total_latency_ms: number;
  candidate_knowledge_ids: string[];
}

// Matches backend/src/schemas/events.py's client-fireable event types - QUESTION_ASKED and
// RESPONSE_GENERATED are published server-side by chat.py, never from the browser.
export type ClientEventType = "SOURCE_OPENED" | "RELATED_TOPIC_OPENED" | "FEEDBACK_SUBMITTED";

export interface TopicAnalytics {
  topic_id: string;
  [metric: string]: number | string;
}

export interface AnalyticsSummary {
  global: Record<string, number>;
  by_topic: TopicAnalytics[];
  computed_at: string | null;
}
