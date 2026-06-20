import type { TransactionView } from '../api/types';

interface Props {
  transactions: TransactionView[];
  anomalyIds: Set<string>;
}

function formatDate(iso: string | null): string {
  if (!iso) return '—';
  return iso.slice(0, 10);
}

function formatAmount(amount: number | null): string {
  if (amount === null) return '—';
  const abs = Math.abs(amount).toFixed(2);
  return amount < 0 ? `-$${abs}` : `+$${abs}`;
}

function ProvenanceChip({ provenance }: { provenance: string }): JSX.Element {
  const isRule = provenance === 'rule';
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${
        isRule
          ? 'bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-500/10 dark:text-blue-300 dark:border-blue-500/30'
          : 'bg-purple-50 text-purple-700 border border-purple-200 dark:bg-purple-500/10 dark:text-purple-300 dark:border-purple-500/30'
      }`}
    >
      {isRule ? 'rule' : 'model'}
    </span>
  );
}

export default function TransactionTable({ transactions, anomalyIds }: Props): JSX.Element {
  // Render in the order given — the parent (Dashboard) owns sorting/filtering so the
  // table stays presentational. Default order from the API is newest-first.
  const rows = transactions;

  if (rows.length === 0) {
    return <p className="text-sm text-faint">No transactions match your filters.</p>;
  }

  return (
    <div className="overflow-auto max-h-[28rem] rounded-xl border border-line bg-surface shadow-card">
      <table className="min-w-full text-sm">
        <thead className="sticky top-0 z-10 bg-elevated">
          <tr className="border-b border-line">
            <th className="px-4 py-3 text-left font-medium text-faint">Date</th>
            <th className="px-4 py-3 text-left font-medium text-faint">Description</th>
            <th className="px-4 py-3 text-right font-medium text-faint">Amount</th>
            <th className="px-4 py-3 text-left font-medium text-faint">Category</th>
            <th className="px-4 py-3 text-left font-medium text-faint">Source</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((txn) => {
            const isAnomaly = txn.is_anomaly || anomalyIds.has(txn.id);
            return (
              <tr
                key={txn.id}
                className={`transition-colors ${
                  isAnomaly
                    ? 'bg-amber-50 hover:bg-amber-100 dark:bg-amber-500/10 dark:hover:bg-amber-500/20'
                    : 'hover:bg-elevated'
                }`}
              >
                <td className="px-4 py-3 text-faint whitespace-nowrap">
                  {formatDate(txn.txn_date)}
                </td>
                <td className="px-4 py-3 text-ink max-w-xs truncate">
                  <span className="flex items-center gap-2">
                    {txn.needs_review && (
                      <span
                        title="Needs review"
                        className="inline-block w-2 h-2 rounded-full bg-amber-400 shrink-0"
                        aria-label="needs review"
                      />
                    )}
                    <span className="text-ink">
                      {txn.description ?? '—'}
                    </span>
                  </span>
                </td>
                <td
                  className={`px-4 py-3 text-right font-mono whitespace-nowrap ${
                    txn.amount === null
                      ? 'text-faint'
                      : txn.amount < 0
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-green-600 dark:text-green-400'
                  }`}
                >
                  {formatAmount(txn.amount)}
                </td>
                <td className="px-4 py-3">
                  <span className="badge capitalize">{txn.category ?? 'uncategorized'}</span>
                </td>
                <td className="px-4 py-3">
                  <ProvenanceChip provenance={txn.provenance} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
