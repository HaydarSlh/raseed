// Streaming chat client and goals REST client (Phase 4, POST /chat NDJSON stream)
import { getAuthHeaders, API_BASE_URL } from './client';

export interface Citation {
  document_slug: string;
  heading_path: string;
}

export interface FinalEvent {
  done: true;
  route: 'deterministic' | 'agent';
  citations: Citation[];
  bounded: boolean;
}

export interface StreamCallbacks {
  onDelta: (text: string) => void;
  onFinal: (event: FinalEvent) => void;
  onError: (err: string) => void;
}

export async function streamChat(
  message: string,
  sessionId: string,
  callbacks: StreamCallbacks,
): Promise<void> {
  const headers = getAuthHeaders();
  headers['Content-Type'] = 'application/json';

  const res = await fetch(`${API_BASE_URL}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  if (!res.ok) {
    if (res.status === 401) {
      callbacks.onError('Session expired. Please log in again.');
      return;
    }
    callbacks.onError(`Server error: ${res.status}`);
    return;
  }

  const reader = res.body?.getReader();
  if (!reader) {
    callbacks.onError('No response body');
    return;
  }

  const decoder = new TextDecoder();
  let buffer = '';

  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        const event = JSON.parse(trimmed);
        if (event.delta !== undefined) {
          callbacks.onDelta(event.delta);
        } else if (event.done) {
          callbacks.onFinal(event as FinalEvent);
        }
      } catch {
        // Malformed line — skip
      }
    }
  }
}

export interface GoalOut {
  id: string;
  name: string;
  target_amount: number;
  target_date: string;
  status: 'active' | 'achieved' | 'abandoned';
  created_at: string;
  updated_at: string;
}

export const goalsApi = {
  async list(status?: string): Promise<GoalOut[]> {
    const qs = status ? `?status=${status}` : '';
    const res = await fetch(`${API_BASE_URL}/goals${qs}`, {
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<GoalOut[]>;
  },
};
