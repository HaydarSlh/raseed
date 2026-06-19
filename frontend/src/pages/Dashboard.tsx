import { useEffect, useState } from 'react';
import NavBar from '../components/NavBar';
import TransactionTable from '../components/TransactionTable';
import ForecastChart from '../components/ForecastChart';
import AnomaliesPanel from '../components/AnomaliesPanel';
import SubscriptionsPanel from '../components/SubscriptionsPanel';
import { dashboardApi } from '../api/client';
import type { DashboardView, TransactionView } from '../api/types';

type Status = 'loading' | 'error' | 'empty' | 'loaded';

function csvCell(value: string | number | boolean | null): string {
  if (value === null) return '';
  const str = String(value);
  // Quote fields containing commas, quotes, or newlines; escape embedded quotes.
  return /[",\n]/.test(str) ? `"${str.replace(/"/g, '""')}"` : str;
}

function downloadTransactionsCsv(transactions: TransactionView[]): void {
  const header = [
    'date', 'description', 'amount', 'category',
    'source', 'confidence', 'needs_review', 'is_anomaly',
  ];
  const rows = transactions.map((t) => [
    t.txn_date ? t.txn_date.slice(0, 10) : '',
    csvCell(t.description ?? ''),
    t.amount ?? '',
    t.category ?? '',
    t.provenance,
    t.confidence ?? '',
    t.needs_review,
    t.is_anomaly,
  ].map(csvCell).join(','));

  const csv = [header.join(','), ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `raseed-transactions-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export default function Dashboard(): JSX.Element {
  const [status, setStatus] = useState<Status>('loading');
  const [data, setData] = useState<DashboardView | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  async function fetchDashboard() {
    setStatus('loading');
    setErrorMsg('');
    try {
      const result = await dashboardApi.getDashboard();
      setData(result);
      setStatus(result.transactions.length === 0 ? 'empty' : 'loaded');
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Failed to load dashboard.');
      setStatus('error');
    }
  }

  useEffect(() => {
    void fetchDashboard();
  }, []);

  const anomalyIds = new Set(data?.anomalies.map((a) => a.transaction_id) ?? []);

  return (
    <div className="min-h-screen bg-gray-50">
      <NavBar />
      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          {status === 'loaded' && data && (
            <div className="flex items-center gap-3">
              <button
                onClick={() => downloadTransactionsCsv(data.transactions)}
                className="px-4 py-2 text-sm font-medium text-indigo-600 border border-indigo-300 rounded-lg hover:bg-indigo-50 transition-colors"
              >
                Download CSV
              </button>
              <button
                onClick={() => void fetchDashboard()}
                className="px-4 py-2 text-sm font-medium text-indigo-600 border border-indigo-300 rounded-lg hover:bg-indigo-50 transition-colors"
              >
                Refresh
              </button>
            </div>
          )}
        </div>

        {status === 'loading' && (
          <div className="flex justify-center py-16">
            <div className="text-gray-500 text-sm">Loading your data…</div>
          </div>
        )}

        {status === 'error' && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
            <p className="text-red-700 font-medium mb-3">{errorMsg}</p>
            <button
              onClick={() => void fetchDashboard()}
              className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {status === 'empty' && (
          <div className="rounded-lg border-2 border-dashed border-gray-300 bg-white p-12 text-center">
            <p className="text-gray-500 text-lg mb-2">No transactions yet</p>
            <p className="text-gray-400 text-sm mb-6">
              Upload a bank statement to get started.
            </p>
            <a
              href="/upload"
              className="inline-block px-5 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
            >
              Upload statement
            </a>
          </div>
        )}

        {status === 'loaded' && data && (
          <>
            <section className="mb-8">
              <ForecastChart forecast={data.forecast} />
            </section>

            <section className="mb-8">
              <h2 className="text-lg font-semibold text-gray-800 mb-3">Transactions</h2>
              <TransactionTable
                transactions={data.transactions}
                anomalyIds={anomalyIds}
              />
            </section>

            {data.anomalies.length > 0 && (
              <section className="mb-8">
                <AnomaliesPanel anomalies={data.anomalies} />
              </section>
            )}

            {data.subscriptions.length > 0 && (
              <section>
                <SubscriptionsPanel subscriptions={data.subscriptions} />
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
