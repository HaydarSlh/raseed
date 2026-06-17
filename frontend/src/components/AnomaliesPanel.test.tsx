import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import AnomaliesPanel from './AnomaliesPanel';
import type { AnomalyView } from '../api/types';

const anomalies: AnomalyView[] = [
  {
    transaction_id: 'uuid-1',
    anomaly_type: 'duplicate_charge',
    reason: 'Same merchant and amount within 2 days',
  },
  {
    transaction_id: 'uuid-2',
    anomaly_type: 'statistical_outlier',
    reason: 'Amount is 4x the monthly average',
  },
];

describe('AnomaliesPanel', () => {
  it('renders nothing when anomalies list is empty', () => {
    const { container } = render(<AnomaliesPanel anomalies={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders anomaly type labels and reasons', () => {
    render(<AnomaliesPanel anomalies={anomalies} />);
    expect(screen.getByText(/duplicate charge/i)).toBeInTheDocument();
    expect(screen.getByText(/statistical outlier/i)).toBeInTheDocument();
    expect(screen.getByText('Same merchant and amount within 2 days')).toBeInTheDocument();
    expect(screen.getByText('Amount is 4x the monthly average')).toBeInTheDocument();
  });
});
