import type {
  AgentTraceSummary,
  AnalyticsSummary,
  ChatResponse,
  ClientEventType,
  KnowledgeSummary,
  QualitySummary,
  Topic,
} from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${options?.method ?? "GET"} ${path} failed: ${response.status} ${body}`);
  }
  return response.json();
}

export async function getHealth(): Promise<{ status: string; service: string; environment: string }> {
  return request("/health");
}

export async function postChat(message: string, sessionId?: string): Promise<ChatResponse> {
  return request("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId ?? null }),
  });
}

export async function getTopics(): Promise<Topic[]> {
  return request("/api/topics");
}

export async function getTopicKnowledge(topicId: string): Promise<KnowledgeSummary[]> {
  return request(`/api/topics/${encodeURIComponent(topicId)}/knowledge`);
}

export async function getQualitySummary(): Promise<QualitySummary> {
  return request("/api/admin/quality");
}

export async function getRecentAgentTraces(limit = 20): Promise<AgentTraceSummary[]> {
  return request(`/api/admin/agents?limit=${limit}`);
}

export async function getAgentTrace(traceId: string): Promise<AgentTraceSummary> {
  return request(`/api/admin/agents/${encodeURIComponent(traceId)}`);
}

export async function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  return request("/api/admin/analytics");
}

interface PostEventParams {
  eventType: ClientEventType;
  sessionId: string;
  traceId?: string;
  topicId?: string;
  knowledgeId?: string;
  rating?: "up" | "down";
}

/** Fire-and-forget: interaction telemetry should never block the UI or surface an error to the
 * user if it fails - it's failed the same way analytics beacons everywhere fail silently. */
export function postEvent(params: PostEventParams): void {
  fetch(`${API_BASE_URL}/api/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    keepalive: true,
    body: JSON.stringify({
      event_type: params.eventType,
      session_id: params.sessionId,
      trace_id: params.traceId ?? null,
      topic_id: params.topicId ?? null,
      knowledge_id: params.knowledgeId ?? null,
      rating: params.rating ?? null,
    }),
  }).catch((err) => {
    console.warn("Failed to record interaction event", err);
  });
}
