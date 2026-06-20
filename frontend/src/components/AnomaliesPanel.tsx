import { useState } from 'react';
import type { AnomalyView } from '../api/types';

interface Props {
  anomalies: AnomalyView[];
}

const LABELS: Record<string, string> = {
  duplicate_charge: 'Duplicate charge',
  statistical_outlier: 'Statistical outlier',
  unusual_merchant: 'Unusual merchant',
  large_transaction: 'Large transaction',
};

function humanLabel(anomalyType: string): string {
  return LABELS[anomalyType] ?? anomalyType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function AnomaliesPanel({ anomalies }: Props): JSX.Element | null {
  const [open, setOpen] = useState(true);

  if (anomalies.length === 0) return null;

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-5 py-4 text-left"
        aria-expanded={open}
      >
        <span className="font-semibold text-amber-800 dark:text-amber-300">
          Unusual Transactions ({anomalies.length})
        </span>
        <span className="text-amber-500 text-sm">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <ul className="divide-y divide-amber-100 dark:divide-amber-500/20 border-t border-amber-200 dark:border-amber-500/30">
          {anomalies.map((a) => (
            <li key={a.transaction_id} className="px-5 py-3">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200 dark:bg-amber-500/15 dark:text-amber-300 dark:border-amber-500/30 mb-1">
                {humanLabel(a.anomaly_type)}
              </span>
              <p className="text-sm text-ink">{a.reason}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
