// Typed client seam to the FastAPI backend. The base URL comes from Vite env
// (VITE_API_BASE_URL); no real calls in Phase 0.
export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000';
