// Simple confidence trend chart: renders the drift series as an SVG sparkline (Phase 5, US4)
import type { DriftSeriesPoint } from '../api/opsApi';

interface Props {
  series: DriftSeriesPoint[];
  threshold: number;
}

const WIDTH = 420;
const HEIGHT = 80;
const PAD = { top: 8, right: 8, bottom: 8, left: 8 };

export default function ConfidenceChart({ series, threshold }: Props): JSX.Element {
  if (series.length === 0) {
    return (
      <div
        data-testid="confidence-chart-empty"
        className="flex items-center justify-center h-20 text-sm text-gray-400 bg-gray-50 rounded"
      >
        No drift data yet
      </div>
    );
  }

  const values = series.map(p => p.mean_confidence);
  const minV = Math.min(...values, threshold) - 0.05;
  const maxV = Math.max(...values, threshold) + 0.05;
  const innerW = WIDTH - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;

  function toX(i: number) {
    return PAD.left + (series.length > 1 ? (i / (series.length - 1)) * innerW : innerW / 2);
  }
  function toY(v: number) {
    return PAD.top + ((maxV - v) / (maxV - minV)) * innerH;
  }

  const linePath = values
    .map((v, i) => `${i === 0 ? 'M' : 'L'}${toX(i).toFixed(1)},${toY(v).toFixed(1)}`)
    .join(' ');

  const thresholdY = toY(threshold).toFixed(1);

  return (
    <svg
      data-testid="confidence-chart"
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      className="w-full h-20"
      aria-label="Mean confidence over time"
    >
      {/* Threshold line */}
      <line
        x1={PAD.left}
        y1={thresholdY}
        x2={WIDTH - PAD.right}
        y2={thresholdY}
        stroke="#ef4444"
        strokeWidth="1"
        strokeDasharray="4 2"
        opacity="0.7"
      />
      {/* Confidence sparkline */}
      <path
        d={linePath}
        fill="none"
        stroke="#6366f1"
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      {/* Data points */}
      {values.map((v, i) => (
        <circle
          key={i}
          cx={toX(i)}
          cy={toY(v)}
          r="3"
          fill={v < threshold ? '#ef4444' : '#6366f1'}
        />
      ))}
    </svg>
  );
}
