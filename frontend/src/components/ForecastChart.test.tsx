import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ForecastChart from './ForecastChart';
import type { ForecastView } from '../api/types';

const coldStartForecast: ForecastView = {
  horizon_days: 30,
  is_cold_start: true,
  points: [],
};

const populatedForecast: ForecastView = {
  horizon_days: 30,
  is_cold_start: false,
  points: [
    { date: '2026-06-18', projected_balance: -1501.27, lower: -1600, upper: -1400 },
    { date: '2026-06-19', projected_balance: -1480.0, lower: -1580, upper: -1380 },
  ],
};

describe('ForecastChart', () => {
  it('renders the cold-start notice when is_cold_start is true', () => {
    render(<ForecastChart forecast={coldStartForecast} />);
    expect(screen.getByText(/not enough history/i)).toBeInTheDocument();
  });

  it('renders the cold-start notice when points array is empty', () => {
    const emptyForecast: ForecastView = { ...populatedForecast, is_cold_start: false, points: [] };
    render(<ForecastChart forecast={emptyForecast} />);
    expect(screen.getByText(/not enough history/i)).toBeInTheDocument();
  });

  it('renders the chart container when points exist and is_cold_start is false', () => {
    render(<ForecastChart forecast={populatedForecast} />);
    expect(screen.queryByText(/not enough history/i)).not.toBeInTheDocument();
    expect(screen.getByTestId('forecast-chart')).toBeInTheDocument();
  });
});
