// Typed client to the FastAPI backend. Bearer token stored in localStorage;
// sent on every authenticated request via getAuthHeaders().
import type {
  DashboardView,
  ForecastView,
  ManualEntryInput,
  ManualTransactionResultView,
  RegisterInput,
  SubscriptionView,
  UploadResultView,
  UserView,
} from './types';

export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000';

export function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('raseed_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders(), ...(init.headers ?? {}) },
  });
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem('raseed_token');
      window.location.href = '/login';
      throw new Error('Session expired');
    }
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res;
}

export const authApi = {
  async register(input: RegisterInput): Promise<void> {
    await apiFetch('/auth/register', {
      method: 'POST',
      body: JSON.stringify(input),
    });
  },

  async login(email: string, password: string): Promise<string> {
    const form = new URLSearchParams({ username: email, password });
    const res = await fetch(`${API_BASE_URL}/auth/jwt/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString(),
    });
    if (!res.ok) throw new Error('Login failed');
    const data = (await res.json()) as { access_token: string };
    return data.access_token;
  },

  async me(): Promise<UserView> {
    const res = await apiFetch('/users/me');
    return res.json() as Promise<UserView>;
  },

  logout(): void {
    localStorage.removeItem('raseed_token');
  },
};

export const dashboardApi = {
  async getDashboard(): Promise<DashboardView> {
    const res = await apiFetch('/dashboard');
    return res.json() as Promise<DashboardView>;
  },

  async getForecast(): Promise<ForecastView> {
    const res = await apiFetch('/forecast');
    return res.json() as Promise<ForecastView>;
  },

  async getSubscriptions(): Promise<SubscriptionView[]> {
    const res = await apiFetch('/subscriptions');
    return res.json() as Promise<SubscriptionView[]>;
  },

  async uploadStatement(file: File): Promise<UploadResultView> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE_URL}/uploads`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: formData,
    });
    if (!res.ok) {
      if (res.status === 401) {
        localStorage.removeItem('raseed_token');
        window.location.href = '/login';
        throw new Error('Session expired');
      }
      const body = await res.json().catch(() => ({}));
      throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
    }
    return res.json() as Promise<UploadResultView>;
  },

  async addTransaction(input: ManualEntryInput): Promise<ManualTransactionResultView> {
    const res = await apiFetch('/transactions', {
      method: 'POST',
      body: JSON.stringify(input),
    });
    return res.json() as Promise<ManualTransactionResultView>;
  },
};
