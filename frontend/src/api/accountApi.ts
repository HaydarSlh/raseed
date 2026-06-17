// Account API client: right-to-erasure (Phase 6, FR-008)
import { getAuthHeaders, API_BASE_URL } from './client';

export interface ErasureResponse {
  audit_id: string;
  status: string;
  deleted_counts: Record<string, number>;
  message: string;
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders(), ...(init.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const accountApi = {
  requestErasure(): Promise<ErasureResponse> {
    return apiFetch<ErasureResponse>('/users/me/erasure', { method: 'DELETE' });
  },
};
