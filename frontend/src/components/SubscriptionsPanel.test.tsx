import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SubscriptionsPanel from './SubscriptionsPanel';
import type { SubscriptionView } from '../api/types';

const subscriptions: SubscriptionView[] = [
  {
    merchant: 'Netflix',
    cadence: 'monthly',
    typical_amount: 9.99,
    next_charge_date: '2026-07-02',
    price_increase: false,
  },
  {
    merchant: 'Spotify',
    cadence: 'monthly',
    typical_amount: 11.99,
    next_charge_date: null,
    price_increase: true,
  },
];

describe('SubscriptionsPanel', () => {
  it('renders nothing when subscriptions list is empty', () => {
    const { container } = render(<SubscriptionsPanel subscriptions={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders one card per subscription with merchant, cadence, and amount', () => {
    render(<SubscriptionsPanel subscriptions={subscriptions} />);
    expect(screen.getByText('Netflix')).toBeInTheDocument();
    expect(screen.getByText('Spotify')).toBeInTheDocument();
    expect(screen.getAllByText(/monthly/i)).toHaveLength(2);
    expect(screen.getByText(/9\.99/)).toBeInTheDocument();
    expect(screen.getByText(/11\.99/)).toBeInTheDocument();
  });

  it('shows "price increased" badge when price_increase is true', () => {
    render(<SubscriptionsPanel subscriptions={subscriptions} />);
    expect(screen.getByText(/price increased/i)).toBeInTheDocument();
  });

  it('does not show price-increased badge when price_increase is false', () => {
    render(<SubscriptionsPanel subscriptions={[subscriptions[0]]} />);
    expect(screen.queryByText(/price increased/i)).not.toBeInTheDocument();
  });
});
