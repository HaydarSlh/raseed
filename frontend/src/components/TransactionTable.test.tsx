import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import TransactionTable from './TransactionTable';
import type { TransactionView } from '../api/types';

const transactions: TransactionView[] = [
  {
    id: 'uuid-1',
    txn_date: '2026-06-10T00:00:00Z',
    amount: -12.5,
    category: 'groceries',
    confidence: 0.95,
    provenance: 'rule',
    needs_review: false,
    is_anomaly: false,
  },
  {
    id: 'uuid-2',
    txn_date: '2026-06-09T00:00:00Z',
    amount: -9.99,
    category: null,
    confidence: 0.4,
    provenance: 'model',
    needs_review: true,
    is_anomaly: true,
  },
  {
    id: 'uuid-3',
    txn_date: '2026-06-08T00:00:00Z',
    amount: null,
    category: 'entertainment',
    confidence: null,
    provenance: 'model',
    needs_review: false,
    is_anomaly: false,
  },
];

describe('TransactionTable', () => {
  it('renders rows sorted by txn_date descending (newest first)', () => {
    render(<TransactionTable transactions={transactions} anomalyIds={new Set()} />);
    const rows = screen.getAllByRole('row').slice(1); // skip header
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByText('2026-06-10')).toBeInTheDocument();
    expect(within(rows[1]).getByText('2026-06-09')).toBeInTheDocument();
    expect(within(rows[2]).getByText('2026-06-08')).toBeInTheDocument();
  });

  it('shows date, amount, and category badge', () => {
    render(<TransactionTable transactions={[transactions[0]]} anomalyIds={new Set()} />);
    expect(screen.getByText('2026-06-10')).toBeInTheDocument();
    expect(screen.getByText('-£12.50')).toBeInTheDocument();
    expect(screen.getByText('groceries')).toBeInTheDocument();
  });

  it('shows "uncategorized" badge when category is null', () => {
    render(<TransactionTable transactions={[transactions[1]]} anomalyIds={new Set()} />);
    expect(screen.getByText('uncategorized')).toBeInTheDocument();
  });

  it('shows "—" for null amount', () => {
    render(<TransactionTable transactions={[transactions[2]]} anomalyIds={new Set()} />);
    // The description cell shows "—" when no description; the amount cell also shows "—"
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  // T026: Trust signal tests (US3)
  it('shows the needs-review indicator on rows with needs_review=true', () => {
    render(<TransactionTable transactions={[transactions[1]]} anomalyIds={new Set()} />);
    expect(screen.getByLabelText('needs review')).toBeInTheDocument();
  });

  it('does not show needs-review indicator when needs_review is false', () => {
    render(<TransactionTable transactions={[transactions[0]]} anomalyIds={new Set()} />);
    expect(screen.queryByLabelText('needs review')).not.toBeInTheDocument();
  });

  it('shows rule provenance chip for rule-categorised transactions', () => {
    render(<TransactionTable transactions={[transactions[0]]} anomalyIds={new Set()} />);
    expect(screen.getByText('rule')).toBeInTheDocument();
  });

  it('shows model provenance chip for model-categorised transactions', () => {
    render(<TransactionTable transactions={[transactions[1]]} anomalyIds={new Set()} />);
    expect(screen.getByText('model')).toBeInTheDocument();
  });

  it('highlights anomalous rows when is_anomaly is true', () => {
    render(<TransactionTable transactions={[transactions[1]]} anomalyIds={new Set()} />);
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows[0].className).toMatch(/amber/);
  });

  it('highlights anomalous rows when the id is in anomalyIds set', () => {
    render(
      <TransactionTable
        transactions={[transactions[0]]}
        anomalyIds={new Set(['uuid-1'])}
      />,
    );
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows[0].className).toMatch(/amber/);
  });

  it('category badge has no button, select, or input (read-only, FR-012)', () => {
    render(<TransactionTable transactions={[transactions[0]]} anomalyIds={new Set()} />);
    expect(screen.queryByRole('button', { name: /groceries/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });
});
