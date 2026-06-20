// Tests: review queue page — renders rows, confirm calls API, quarantined rows are labeled
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import Review from './Review';

vi.mock('../api/reviewApi', () => ({
  reviewApi: {
    getQueue: vi.fn(),
    confirm: vi.fn(),
    getReviewMode: vi.fn(),
    setReviewMode: vi.fn(),
    relabelAll: vi.fn(),
  },
}));

import { reviewApi } from '../api/reviewApi';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const mockReviewApi = reviewApi as any as {
  getQueue: ReturnType<typeof vi.fn>;
  confirm: ReturnType<typeof vi.fn>;
  setReviewMode: ReturnType<typeof vi.fn>;
  relabelAll: ReturnType<typeof vi.fn>;
};

const NORMAL_ITEM = {
  transaction_id: 'txn-001',
  description: 'TESCO METRO',
  merchant: 'TESCO',
  amount: -12.50,
  occurred_at: '2026-06-01T10:00:00Z',
  current_category: 'groceries',
  confidence: 0.95,
  provenance: 'human',
  quarantined: false,
};

const QUARANTINED_ITEM = {
  transaction_id: 'txn-002',
  description: 'MYSTERY SHOP',
  merchant: null,
  amount: -5.00,
  occurred_at: '2026-06-02T11:00:00Z',
  current_category: 'other',
  confidence: 0.40,
  provenance: 'llm',
  quarantined: true,
};

function renderReview() {
  return render(
    <MemoryRouter>
      <Review />
    </MemoryRouter>,
  );
}

describe('Review page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders queue rows for flagged transactions', async () => {
    mockReviewApi.getQueue.mockResolvedValue({
      items: [NORMAL_ITEM],
      review_mode: 'manual',
    });

    renderReview();
    await waitFor(() => expect(screen.getByTestId('review-row')).toBeDefined());
    expect(screen.getByText('TESCO METRO')).toBeDefined();
  });

  it('labels quarantined rows as awaiting confirmation', async () => {
    mockReviewApi.getQueue.mockResolvedValue({
      items: [QUARANTINED_ITEM],
      review_mode: 'manual',
    });

    renderReview();
    await waitFor(() => expect(screen.getByTestId('review-row-quarantined')).toBeDefined());
    expect(screen.getAllByText(/awaiting confirmation/i).length).toBeGreaterThan(0);
  });

  it('calls confirm API when confirm button clicked', async () => {
    mockReviewApi.getQueue.mockResolvedValue({
      items: [NORMAL_ITEM],
      review_mode: 'manual',
    });
    mockReviewApi.confirm.mockResolvedValue({
      transaction_id: 'txn-001',
      category: 'groceries',
      provenance: 'human',
      needs_review: false,
    });

    renderReview();
    await waitFor(() => expect(screen.getByTestId('review-row-confirm')).toBeDefined());

    await act(async () => {
      fireEvent.click(screen.getByTestId('review-row-confirm'));
    });

    await waitFor(() =>
      expect(mockReviewApi.confirm).toHaveBeenCalledWith('txn-001', 'groceries'),
    );
  });

  it('removes the row from the queue after confirm (UI reflects persisted state)', async () => {
    mockReviewApi.getQueue.mockResolvedValue({
      items: [NORMAL_ITEM],
      review_mode: 'manual',
    });
    mockReviewApi.confirm.mockResolvedValue({
      transaction_id: 'txn-001',
      category: 'groceries',
      provenance: 'human',
      needs_review: false,
    });

    renderReview();
    await waitFor(() => expect(screen.getByTestId('review-row-confirm')).toBeDefined());

    await act(async () => {
      fireEvent.click(screen.getByTestId('review-row-confirm'));
    });

    // Row is removed from the parent's items state — the done banner is gone
    // and the "No items to review" empty state appears.
    await waitFor(() =>
      expect(screen.queryByTestId('review-row-done')).toBeNull(),
    );
    expect(screen.getByText('No items to review.')).toBeDefined();
  });

  it('renders mode toggle', async () => {
    mockReviewApi.getQueue.mockResolvedValue({ items: [], review_mode: 'manual' });
    renderReview();
    await waitFor(() => expect(screen.getByTestId('review-mode-toggle')).toBeDefined());
  });

  it('renders the LLM label all button beside the toggle', async () => {
    mockReviewApi.getQueue.mockResolvedValue({ items: [], review_mode: 'manual' });
    renderReview();
    await waitFor(() => expect(screen.getByTestId('review-relabel-all')).toBeDefined());
  });

  it('calls relabelAll when the LLM label all button is clicked', async () => {
    mockReviewApi.getQueue.mockResolvedValue({ items: [], review_mode: 'manual' });
    mockReviewApi.relabelAll.mockResolvedValue({ queued: true, user_id: 'u-1' });

    renderReview();
    await waitFor(() => expect(screen.getByTestId('review-relabel-all')).toBeDefined());

    await act(async () => {
      fireEvent.click(screen.getByTestId('review-relabel-all'));
    });

    await waitFor(() => expect(mockReviewApi.relabelAll).toHaveBeenCalled());
    expect(screen.getByTestId('review-relabel-msg')).toBeDefined();
  });
});
