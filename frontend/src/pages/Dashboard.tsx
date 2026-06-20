import { useEffect, useMemo, useState } from 'react';
import AppLayout from '../components/AppLayout';
import TransactionTable from '../components/TransactionTable';
import ForecastChart from '../components/ForecastChart';
import AnomaliesPanel from '../components/AnomaliesPanel';
import SubscriptionsPanel from '../components/SubscriptionsPanel';
import { dashboardApi } from '../api/client';
import type { DashboardView, TransactionView } from '../api/types';

type Status = 'loading' | 'error' | 'empty' | 'loaded';
type Flow = 'all' | 'income' | 'spending';
type SortKey = 'date' | 'amount';
type SortDir = 'asc' | 'desc';

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

const selectClass =
  'border border-line bg-surface text-ink rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40';

export default function Dashboard(): JSX.Element {
  const [status, setStatus] = useState<Status>('loading');
  const [data, setData] = useState<DashboardView | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  // Filter / sort / search state.
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');
  const [source, setSource] = useState('all');
  const [flow, setFlow] = useState<Flow>('all');
  const [sortKey, setSortKey] = useState<SortKey>('date');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

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

  const anomalyIds = useMemo(
    () => new Set(data?.anomalies.map((a) => a.transaction_id) ?? []),
    [data],
  );

  const categoryOptions = useMemo(() => {
    const set = new Set<string>();
    for (const t of data?.transactions ?? []) set.add(t.category ?? 'uncategorized');
    return [...set].sort();
  }, [data]);

  const sourceOptions = useMemo(() => {
    const set = new Set<string>();
    for (const t of data?.transactions ?? []) set.add(t.provenance);
    return [...set].sort();
  }, [data]);

  const displayed = useMemo(() => {
    let list = data?.transactions ?? [];
    const q = search.trim().toLowerCase();
    if (q) list = list.filter((t) => (t.description ?? '').toLowerCase().includes(q));
    if (category !== 'all') list = list.filter((t) => (t.category ?? 'uncategorized') === category);
    if (source !== 'all') list = list.filter((t) => t.provenance === source);
    if (flow === 'income') list = list.filter((t) => (t.amount ?? 0) > 0);
    else if (flow === 'spending') list = list.filter((t) => (t.amount ?? 0) < 0);

    const dir = sortDir === 'asc' ? 1 : -1;
    return [...list].sort((a, b) => {
      if (sortKey === 'amount') return ((a.amount ?? 0) - (b.amount ?? 0)) * dir;
      return (a.txn_date ?? '').localeCompare(b.txn_date ?? '') * dir;
    });
  }, [data, search, category, source, flow, sortKey, sortDir]);

  return (
    <AppLayout>
      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-ink">Dashboard</h1>
          {status === 'loaded' && data && (
            <div className="flex items-center gap-3">
              <button onClick={() => downloadTransactionsCsv(displayed)} className="btn-secondary">
                Download CSV
              </button>
              <button onClick={() => void fetchDashboard()} className="btn-secondary">
                Refresh
              </button>
            </div>
          )}
        </div>

        {status === 'loading' && (
          <div className="flex justify-center py-16">
            <div className="text-faint text-sm">Loading your data…</div>
          </div>
        )}

        {status === 'error' && (
          <div className="rounded-xl border border-red-200 dark:border-red-500/30 bg-red-50 dark:bg-red-500/10 p-6 text-center">
            <p className="text-red-700 dark:text-red-400 font-medium mb-3">{errorMsg}</p>
            <button
              onClick={() => void fetchDashboard()}
              className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {status === 'empty' && (
          <div className="rounded-xl border-2 border-dashed border-line bg-surface p-12 text-center">
            <p className="text-ink text-lg mb-2">No transactions yet</p>
            <p className="text-faint text-sm mb-6">
              Upload a bank statement to get started.
            </p>
            <a href="/upload" className="btn-primary px-5">
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
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-semibold text-ink">Transactions</h2>
                <span className="text-sm text-faint">
                  {displayed.length} of {data.transactions.length}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-2 mb-3">
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search description…"
                  aria-label="Search description"
                  className="flex-1 min-w-[12rem] border border-line bg-surface text-ink placeholder:text-faint rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/40"
                />
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  aria-label="Filter by category"
                  className={selectClass}
                >
                  <option value="all">All categories</option>
                  {categoryOptions.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
                <select
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  aria-label="Filter by source"
                  className={selectClass}
                >
                  <option value="all">All sources</option>
                  {sourceOptions.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <select
                  value={flow}
                  onChange={(e) => setFlow(e.target.value as Flow)}
                  aria-label="Filter by income or spending"
                  className={selectClass}
                >
                  <option value="all">Income &amp; spending</option>
                  <option value="income">Income (+)</option>
                  <option value="spending">Spending (−)</option>
                </select>
                <select
                  value={sortKey}
                  onChange={(e) => setSortKey(e.target.value as SortKey)}
                  aria-label="Sort by"
                  className={selectClass}
                >
                  <option value="date">Sort: Date</option>
                  <option value="amount">Sort: Amount</option>
                </select>
                <button
                  onClick={() => setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))}
                  aria-label="Toggle sort direction"
                  title={sortDir === 'asc' ? 'Ascending' : 'Descending'}
                  className="px-3 py-1.5 text-sm border border-line bg-surface text-ink rounded-lg hover:bg-elevated"
                >
                  {sortDir === 'asc' ? '↑' : '↓'}
                </button>
              </div>

              <TransactionTable transactions={displayed} anomalyIds={anomalyIds} />
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
    </AppLayout>
  );
}
