import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import type { ForecastView } from '../api/types';

interface Props {
  forecast: ForecastView;
}

export default function ForecastChart({ forecast }: Props): JSX.Element {
  const showColdStart = forecast.is_cold_start || forecast.points.length === 0;

  if (showColdStart) {
    return (
      <div className="card p-8 text-center">
        <p className="text-faint text-sm">
          Not enough history yet — upload at least 30 days of transactions to see your
          balance forecast.
        </p>
      </div>
    );
  }

  const chartData = forecast.points.map((p) => ({
    date: p.date,
    balance: p.projected_balance,
  }));

  return (
    <div className="card p-6" data-testid="forecast-chart">
      <h2 className="text-lg font-semibold text-ink mb-4">Balance Forecast</h2>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#94a3b8" strokeOpacity={0.18} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: '#9ca3af' }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#9ca3af' }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `$${v.toFixed(0)}`}
          />
          <Tooltip
            formatter={(value: number) => [`$${value.toFixed(2)}`, 'Projected balance']}
            labelStyle={{ fontSize: 11 }}
            contentStyle={{
              fontSize: 12,
              borderRadius: 8,
              border: '1px solid rgb(var(--c-line))',
              background: 'rgb(var(--c-surface))',
              color: 'rgb(var(--c-ink))',
            }}
          />
          <Line
            type="monotone"
            dataKey="balance"
            stroke="#6366f1"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-2 text-xs text-faint text-right">
        {forecast.horizon_days}-day projection
      </p>
    </div>
  );
}
