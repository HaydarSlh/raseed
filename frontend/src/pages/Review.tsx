// Review queue page: flagged transactions + review-mode toggle (Phase 5, US1)
import { useCallback, useEffect, useState } from 'react';
import AppLayout from '../components/AppLayout';
import ReviewRow from '../components/ReviewRow';
import { reviewApi } from '../api/reviewApi';
import type { ReviewItem } from '../api/reviewApi';

export default function Review(): JSX.Element {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [mode, setMode] = useState<'manual' | 'auto_relabel'>('manual');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modeChanging, setModeChanging] = useState(false);
  const [relabelBusy, setRelabelBusy] = useState(false);
  const [relabelMsg, setRelabelMsg] = useState<string | null>(null);

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
    // Remove the confirmed row from the queue so the UI reflects the persisted
    // state immediately (the backend clears needs_review on commit).
    setItems(prev => prev.filter(i => i.transaction_id !== transactionId));
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

  async function handleRelabelAll() {
    setRelabelBusy(true);
    setRelabelMsg(null);
    try {
      await reviewApi.relabelAll();
      setRelabelMsg('LLM relabel queued — refresh shortly to review quarantined suggestions.');
    } catch (e) {
      setRelabelMsg(e instanceof Error ? e.message : 'Failed to queue LLM relabel');
    } finally {
      setRelabelBusy(false);
    }
  }

  const active = items.filter(i => !i.quarantined);
  const quarantined = items.filter(i => i.quarantined);

  return (
    <AppLayout>
      <main className="w-full px-6 py-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-ink">Review Queue</h1>
          <div className="flex items-center gap-3">
            <button
              data-testid="review-relabel-all"
              onClick={() => void handleRelabelAll()}
              disabled={relabelBusy || loading}
              className="text-sm px-3 py-1.5 border border-indigo-200 text-indigo-700 bg-indigo-50 rounded hover:bg-indigo-100 disabled:opacity-50 whitespace-nowrap"
            >
              {relabelBusy ? 'Queuing…' : 'LLM label all'}
            </button>
            <div className="flex items-center gap-2">
              <span className="text-sm text-faint">Auto-relabel</span>
              <button
                data-testid="review-mode-toggle"
                onClick={() => void handleToggleMode()}
                disabled={modeChanging}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors
                  ${mode === 'auto_relabel' ? 'bg-indigo-600' : 'bg-line'}
                  disabled:opacity-50`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-surface transition-transform
                    ${mode === 'auto_relabel' ? 'translate-x-6' : 'translate-x-1'}`}
                />
              </button>
            </div>
          </div>
        </div>

        {relabelMsg && (
          <p data-testid="review-relabel-msg" className="text-sm text-indigo-700">{relabelMsg}</p>
        )}

        {loading && (
          <p className="text-sm text-faint">Loading…</p>
        )}

        {error && (
          <p data-testid="review-error" className="text-sm text-red-600">{error}</p>
        )}

        {!loading && !error && (
          <>
            {active.length === 0 && quarantined.length === 0 && (
              <p className="text-sm text-faint">No items to review.</p>
            )}

            {active.length > 0 && (
              <section className="space-y-2">
                <h2 className="text-sm font-medium text-ink">
                  Flagged ({active.length})
                </h2>
                <div className="overflow-auto max-h-[24rem] space-y-2 pr-1">
                  {active.map(item => (
                    <ReviewRow
                      key={item.transaction_id}
                      item={item}
                      onConfirm={handleConfirm}
                    />
                  ))}
                </div>
              </section>
            )}

            {quarantined.length > 0 && (
              <section className="space-y-2">
                <h2 className="text-sm font-medium text-ink">
                  Auto-relabeled — awaiting confirmation ({quarantined.length})
                </h2>
                <div className="overflow-auto max-h-[24rem] space-y-2 pr-1">
                  {quarantined.map(item => (
                    <ReviewRow
                      key={item.transaction_id}
                      item={item}
                      onConfirm={handleConfirm}
                    />
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </main>
    </AppLayout>
  );
}
