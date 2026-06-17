// Tests: ops dashboard — renders champion, promotable list, retrain button, drift metrics
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import Ops from './Ops';

vi.mock('../api/opsApi', () => ({
  opsApi: {
    getModels: vi.fn(),
    getDrift: vi.fn(),
    getRetrains: vi.fn(),
    triggerRetrain: vi.fn(),
    promote: vi.fn(),
  },
}));

import { opsApi } from '../api/opsApi';

const mockOpsApi = opsApi as {
  getModels: ReturnType<typeof vi.fn>;
  getDrift: ReturnType<typeof vi.fn>;
  getRetrains: ReturnType<typeof vi.fn>;
  triggerRetrain: ReturnType<typeof vi.fn>;
  promote: ReturnType<typeof vi.fn>;
};

const MODELS_RESPONSE = {
  champion: {
    id: 'champ-id',
    version: 'v2.1.0',
    sha256: 'abc123abc123abc123abc123',
    metrics: { macro_f1: 0.88 },
    gate_verdict: null,
  },
  promotable: [
    {
      id: 'chal-id',
      version: 'v2.2.0',
      sha256: 'def456def456def456def456',
      metrics: { macro_f1: 0.91 },
      gate_verdict: 'beats',
    },
  ],
};

const DRIFT_RESPONSE = {
  current: {
    evaluated_at: '2026-06-01T00:00:00Z',
    mean_confidence: 0.60,
    correction_rate: 0.05,
    psi: 0.03,
    new_merchant_rate: 0.08,
    fired: true,
    fired_signals: ['mean_confidence'],
    triggered_retrain: true,
  },
  thresholds: {
    mean_confidence_min: 0.70,
    correction_rate_max: 0.20,
    psi_max: 0.20,
    new_merchant_rate_max: 0.15,
  },
  series: [
    { evaluated_at: '2026-05-31T00:00:00Z', mean_confidence: 0.65, correction_rate: 0.04 },
    { evaluated_at: '2026-06-01T00:00:00Z', mean_confidence: 0.60, correction_rate: 0.05 },
  ],
};

const RETRAINS_RESPONSE = {
  runs: [
    {
      id: 'run-001',
      trigger_reason: 'drift',
      status: 'completed',
      champion_macro_f1: 0.88,
      challenger_macro_f1: 0.91,
      gate_verdict: 'beats',
      labels_used: 150,
      challenger_id: 'chal-id',
      created_at: '2026-06-01T10:00:00Z',
      completed_at: '2026-06-01T10:15:00Z',
    },
  ],
};

function renderOps() {
  return render(
    <MemoryRouter>
      <Ops />
    </MemoryRouter>,
  );
}

describe('Ops page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockOpsApi.getModels.mockResolvedValue(MODELS_RESPONSE);
    mockOpsApi.getDrift.mockResolvedValue(DRIFT_RESPONSE);
    mockOpsApi.getRetrains.mockResolvedValue(RETRAINS_RESPONSE);
  });

  it('renders champion version', async () => {
    renderOps();
    await waitFor(() => expect(screen.getByTestId('champion-version')).toBeDefined());
    expect(screen.getByTestId('champion-version').textContent).toBe('v2.1.0');
  });

  it('renders promotable challenger row', async () => {
    renderOps();
    await waitFor(() => expect(screen.getByTestId('promotable-row')).toBeDefined());
  });

  it('calls triggerRetrain when Trigger Retrain clicked', async () => {
    mockOpsApi.triggerRetrain.mockResolvedValue({ retrain_run_id: 'new-run', status: 'enqueued' });
    renderOps();
    await waitFor(() => expect(screen.getByTestId('retrain-btn')).toBeDefined());

    await act(async () => {
      fireEvent.click(screen.getByTestId('retrain-btn'));
    });

    expect(mockOpsApi.triggerRetrain).toHaveBeenCalledWith(false);
  });

  it('renders retrain history row', async () => {
    renderOps();
    await waitFor(() => expect(screen.getByTestId('retrain-run-row')).toBeDefined());
    expect(screen.getByText('drift')).toBeDefined();
  });

  it('shows drift fired signal alert', async () => {
    renderOps();
    await waitFor(() => expect(screen.getByText(/mean_confidence/)).toBeDefined());
  });
});
