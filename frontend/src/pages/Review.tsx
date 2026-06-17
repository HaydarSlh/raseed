// Review queue page: flagged transactions + review-mode toggle (Phase 5, US1)
import { useCallback, useEffect, useState } from 'react';
import NavBar from '../components/NavBar';
import ReviewRow from '../components/ReviewRow';
import { reviewApi } from '../api/reviewApi';
import type { ReviewItem } from '../api/reviewApi';

export default function Review(): JSX.Element {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [mode, setMode] = useState<'manual' | 'auto_relabel'>('manual');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modeChanging, setModeChanging] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await reviewApi.getQueue();
      setItems(data.items);
      setMode(data.review_mode as 'manual' | 'auto_relabel');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load review queue');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function handleConfirm(transactionId: string, category: string) {
    await reviewApi.confirm(transactionId, category);
  }

  async function handleToggleMode() {
    const next = mode === 'manual' ? 'auto_relabel' : 'manual';
    setModeChanging(true);
    try {
      const res = await reviewApi.setReviewMode(next);
      setMode(res.review_mode as 'manual' | 'auto_relabel');
    } finally {
      setModeChanging(false);
    }
  }

  const active = items.filter(i => !i.quarantined);
  const quarantined = items.filter(i => i.quarantined);

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar />
      <main className="max-w-3xl mx-auto px-4 py-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-800">Review Queue</h1>
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600">Auto-relabel</span>
            <button
              data-testid="review-mode-toggle"
              onClick={() => void handleToggleMode()}
              disabled={modeChanging}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors
                ${mode === 'auto_relabel' ? 'bg-indigo-600' : 'bg-gray-300'}
                disabled:opacity-50`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform
                  ${mode === 'auto_relabel' ? 'translate-x-6' : 'translate-x-1'}`}
              />
            </button>
          </div>
        </div>

        {loading && (
          <p className="text-sm text-gray-500">Loading…</p>
        )}

        {error && (
          <p data-testid="review-error" className="text-sm text-red-600">{error}</p>
        )}

        {!loading && !error && (
          <>
            {active.length === 0 && quarantined.length === 0 && (
              <p className="text-sm text-gray-500">No items to review.</p>
            )}

            {active.length > 0 && (
              <section className="space-y-2">
                <h2 className="text-sm font-medium text-gray-700">
                  Flagged ({active.length})
                </h2>
                {active.map(item => (
                  <ReviewRow
                    key={item.transaction_id}
                    item={item}
                    onConfirm={handleConfirm}
                  />
                ))}
              </section>
            )}

            {quarantined.length > 0 && (
              <section className="space-y-2">
                <h2 className="text-sm font-medium text-gray-700">
                  Auto-relabeled — awaiting confirmation ({quarantined.length})
                </h2>
                {quarantined.map(item => (
                  <ReviewRow
                    key={item.transaction_id}
                    item={item}
                    onConfirm={handleConfirm}
                  />
                ))}
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
