// One flagged transaction with a category selector and confirm action (Phase 5, US1)
import { useState } from 'react';
import type { ReviewItem } from '../api/reviewApi';

const CATEGORIES = [
  'groceries', 'dine_out', 'bills', 'travel', 'other_shopping',
  'savings', 'income', 'cash', 'entertainment', 'health', 'other',
];

interface Props {
  item: ReviewItem;
  onConfirm: (transactionId: string, category: string) => Promise<void>;
}

export default function ReviewRow({ item, onConfirm }: Props): JSX.Element {
  const [selected, setSelected] = useState(item.current_category);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function handleConfirm() {
    setBusy(true);
    try {
      await onConfirm(item.transaction_id, selected);
      setDone(true);
    } finally {
      setBusy(false);
    }
  }

  const dateStr = item.occurred_at
    ? new Date(item.occurred_at).toLocaleDateString()
    : '—';

  const amountStr = item.amount != null
    ? `$${Math.abs(item.amount).toFixed(2)}`
    : '—';

  if (done) {
    return (
      <div
        data-testid="review-row-done"
        className="flex items-center gap-3 px-4 py-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700"
      >
        <span className="flex-1">{item.description ?? item.merchant ?? item.transaction_id}</span>
        <span>Confirmed as <strong>{selected}</strong></span>
      </div>
    );
  }

  if (item.quarantined) {
    return (
      <div
        data-testid="review-row-quarantined"
        className="flex items-center gap-3 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg text-sm"
      >
        <div className="flex-1 min-w-0">
          <p className="font-medium text-gray-800 truncate">
            {item.description ?? item.merchant ?? '(no description)'}
          </p>
          <p className="text-xs text-gray-500">{dateStr} · {amountStr}</p>
        </div>
        <span className="text-amber-600 font-medium text-xs whitespace-nowrap">
          Awaiting confirmation · {item.current_category}
        </span>
      </div>
    );
  }

  return (
    <div
      data-testid="review-row"
      className="flex items-center gap-3 px-4 py-3 bg-white border border-gray-200 rounded-lg text-sm"
    >
      <div className="flex-1 min-w-0">
        <p className="font-medium text-gray-800 truncate">
          {item.description ?? item.merchant ?? '(no description)'}
        </p>
        <p className="text-xs text-gray-500">{dateStr} · {amountStr}</p>
      </div>

      <select
        data-testid="review-row-select"
        value={selected}
        onChange={e => setSelected(e.target.value)}
        disabled={busy}
        className="text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-indigo-400"
      >
        {CATEGORIES.map(cat => (
          <option key={cat} value={cat}>{cat}</option>
        ))}
      </select>

      <button
        data-testid="review-row-confirm"
        onClick={() => void handleConfirm()}
        disabled={busy}
        className="text-sm px-3 py-1 bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50 whitespace-nowrap"
      >
        {busy ? '…' : 'Confirm'}
      </button>
    </div>
  );
}
