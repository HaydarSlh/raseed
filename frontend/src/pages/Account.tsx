// Account settings page: right-to-erasure (Phase 6, US4)
import { useState } from 'react';
import NavBar from '../components/NavBar';
import { accountApi } from '../api/accountApi';
import type { ErasureResponse } from '../api/accountApi';

export default function Account(): JSX.Element {
  const [confirmValue, setConfirmValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ErasureResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canDelete = confirmValue === 'DELETE';

  async function handleErasure() {
    if (!canDelete) return;
    setLoading(true);
    setError(null);
    try {
      const data = await accountApi.requestErasure();
      setResult(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erasure failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar />
      <main className="max-w-2xl mx-auto px-4 py-8 space-y-8">
        <h1 className="text-xl font-semibold text-gray-800">Account Settings</h1>

        <section className="bg-white border border-red-200 rounded-lg p-6 space-y-4">
          <h2 className="text-base font-semibold text-red-700">Delete My Account</h2>
          <p className="text-sm text-gray-600">
            This permanently deletes all your transactions, goals, corrections, memories, and
            account data. This action <strong>cannot be undone</strong>.
          </p>

          {result ? (
            <div data-testid="erasure-result" className="rounded bg-green-50 border border-green-200 p-4 text-sm text-green-800">
              <p className="font-medium">Account deleted.</p>
              <p className="mt-1">{result.message}</p>
            </div>
          ) : (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Type <span className="font-mono font-bold">DELETE</span> to confirm
                </label>
                <input
                  data-testid="erasure-confirm-input"
                  type="text"
                  value={confirmValue}
                  onChange={e => setConfirmValue(e.target.value)}
                  placeholder="DELETE"
                  className="block w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
                  disabled={loading}
                />
              </div>

              {error && (
                <p className="text-sm text-red-600">{error}</p>
              )}

              <button
                data-testid="erasure-btn"
                onClick={() => void handleErasure()}
                disabled={!canDelete || loading}
                className="px-4 py-2 rounded bg-red-600 text-white text-sm font-medium
                  hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {loading ? 'Deleting…' : 'Delete My Account'}
              </button>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
