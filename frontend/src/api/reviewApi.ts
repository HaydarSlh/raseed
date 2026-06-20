// Review queue + confirm + review-mode client (Phase 5, US1)
import { getAuthHeaders, API_BASE_URL } from './client';

export interface ReviewItem {
  transaction_id: string;
  description: string | null;
  merchant: string | null;
  amount: number | null;
  occurred_at: string | null;
  current_category: string;
  confidence: number | null;
  provenance: string;
  quarantined: boolean;
}

export interface ReviewQueueResponse {
  items: ReviewItem[];
  review_mode: 'manual' | 'auto_relabel';
}

export interface ConfirmResponse {
  transaction_id: string;
  category: string;
  provenance: string;
  needs_review: boolean;
}

export interface RelabelAllResponse {
  queued: boolean;
  user_id: string;
}

export const reviewApi = {
  async getQueue(): Promise<ReviewQueueResponse> {
    const res = await fetch(`${API_BASE_URL}/review/queue`, {
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<ReviewQueueResponse>;
  },

  async confirm(transactionId: string, category: string): Promise<ConfirmResponse> {
    const res = await fetch(`${API_BASE_URL}/review/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ transaction_id: transactionId, category }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<ConfirmResponse>;
  },

  async getReviewMode(): Promise<{ review_mode: string }> {
    const res = await fetch(`${API_BASE_URL}/settings/review-mode`, {
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<{ review_mode: string }>;
  },

  async setReviewMode(mode: 'manual' | 'auto_relabel'): Promise<{ review_mode: string }> {
    const res = await fetch(`${API_BASE_URL}/settings/review-mode`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ review_mode: mode }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<{ review_mode: string }>;
  },

  async relabelAll(): Promise<RelabelAllResponse> {
    const res = await fetch(`${API_BASE_URL}/review/relabel-all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<RelabelAllResponse>;
  },
};
