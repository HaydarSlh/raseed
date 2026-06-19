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
          ? 'bg-blue-50 text-blue-700 border border-blue-200'
          : 'bg-purple-50 text-purple-700 border border-purple-200'
      }`}
    >
      {isRule ? 'rule' : 'model'}
    </span>
  );
}

export default function TransactionTable({ transactions, anomalyIds }: Props): JSX.Element {
  const sorted = [...transactions].sort((a, b) => {
    if (!a.txn_date) return 1;
    if (!b.txn_date) return -1;
    return b.txn_date.localeCompare(a.txn_date);
  });

  if (sorted.length === 0) {
    return <p className="text-sm text-gray-400">No transactions.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white shadow-sm">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100 bg-gray-50">
            <th className="px-4 py-3 text-left font-medium text-gray-600">Date</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Description</th>
            <th className="px-4 py-3 text-right font-medium text-gray-600">Amount</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Category</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Source</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {sorted.map((txn) => {
            const isAnomaly = txn.is_anomaly || anomalyIds.has(txn.id);
            return (
              <tr
                key={txn.id}
                className={`hover:bg-gray-50 transition-colors ${
                  isAnomaly ? 'bg-amber-50 hover:bg-amber-100' : ''
                }`}
              >
                <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                  {formatDate(txn.txn_date)}
                </td>
                <td className="px-4 py-3 text-gray-800 max-w-xs truncate">
                  <span className="flex items-center gap-2">
                    {txn.needs_review && (
                      <span
                        title="Needs review"
                        className="inline-block w-2 h-2 rounded-full bg-amber-400 shrink-0"
                        aria-label="needs review"
                      />
                    )}
                    <span className="text-gray-700">
                      {txn.description ?? '—'}
                    </span>
                  </span>
                </td>
                <td
                  className={`px-4 py-3 text-right font-mono whitespace-nowrap ${
                    txn.amount !== null && txn.amount < 0 ? 'text-red-600' : 'text-green-600'
                  } ${txn.amount === null ? 'text-gray-400' : ''}`}
                >
                  {formatAmount(txn.amount)}
                </td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700 border border-gray-200">
                    {txn.category ?? 'uncategorized'}
                  </span>
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
