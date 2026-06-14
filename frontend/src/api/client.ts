// Typed client to the FastAPI backend. Bearer token stored in localStorage;
// sent on every authenticated request via getAuthHeaders().
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
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `HTTP ${res.status}`);
  }
  return res;
}

export const authApi = {
  async register(email: string, password: string): Promise<void> {
    await apiFetch('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
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
    const data = await res.json();
    return data.access_token as string;
  },

  async me(): Promise<Record<string, unknown>> {
    const res = await apiFetch('/users/me');
    return res.json();
  },

  logout(): void {
    localStorage.removeItem('raseed_token');
  },
};
