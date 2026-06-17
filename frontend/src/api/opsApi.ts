// Ops API client: retrain, promote, model registry, drift, retrain history (Phase 5, US2-US4)
import { getAuthHeaders, API_BASE_URL } from './client';

export interface ModelSummary {
  id: string;
  version: string;
  sha256: string;
  metrics: Record<string, unknown> | null;
  gate_verdict: string | null;
}

export interface ModelsResponse {
  champion: ModelSummary | null;
  promotable: ModelSummary[];
}

export interface RetrainResponse {
  retrain_run_id: string;
  status: string;
}

export interface PromoteResponse {
  promoted: string;
  archived: string;
  model_server_reloaded: boolean;
}

export interface DriftStatus {
  evaluated_at: string | null;
  mean_confidence: number | null;
  correction_rate: number | null;
  psi: number | null;
  new_merchant_rate: number | null;
  fired: boolean;
  fired_signals: string[];
  triggered_retrain: boolean;
}

export interface DriftSeriesPoint {
  evaluated_at: string;
  mean_confidence: number;
  correction_rate: number;
}

export interface DriftResponse {
  current: DriftStatus;
  thresholds: Record<string, number>;
  series: DriftSeriesPoint[];
}

export interface RetrainHistoryItem {
  id: string;
  trigger_reason: string;
  status: string;
  champion_macro_f1: number | null;
  challenger_macro_f1: number | null;
  gate_verdict: string | null;
  labels_used: number | null;
  challenger_id: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface RetrainsResponse {
  runs: RetrainHistoryItem[];
}

export const opsApi = {
  async triggerRetrain(force = false): Promise<RetrainResponse> {
    const res = await fetch(`${API_BASE_URL}/ops/retrain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ force }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<RetrainResponse>;
  },

  async promote(modelRegistryId: string): Promise<PromoteResponse> {
    const res = await fetch(`${API_BASE_URL}/ops/promote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ model_registry_id: modelRegistryId }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<PromoteResponse>;
  },

  async getModels(): Promise<ModelsResponse> {
    const res = await fetch(`${API_BASE_URL}/ops/models`, {
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<ModelsResponse>;
  },

  async getDrift(): Promise<DriftResponse> {
    const res = await fetch(`${API_BASE_URL}/ops/drift`, {
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<DriftResponse>;
  },

  async getRetrains(): Promise<RetrainsResponse> {
    const res = await fetch(`${API_BASE_URL}/ops/retrains`, {
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json() as Promise<RetrainsResponse>;
  },
};
