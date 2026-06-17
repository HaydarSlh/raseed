import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ManualEntryForm from './ManualEntryForm';
import * as client from '../api/client';

vi.mock('../api/client', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../api/client')>();
  return { ...mod, dashboardApi: { ...mod.dashboardApi, addTransaction: vi.fn() } };
});

const mockAdd = vi.mocked(client.dashboardApi.addTransaction);

beforeEach(() => {
  vi.clearAllMocks();
});

describe('ManualEntryForm', () => {
  it('disables submit until all required fields are filled', async () => {
    render(<ManualEntryForm onSuccess={() => undefined} />);
    const submitBtn = screen.getByRole('button', { name: /add transaction/i });
    expect(submitBtn).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/date/i), '2026-06-17');
    expect(submitBtn).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/amount/i), '-8.99');
    expect(submitBtn).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/description/i), 'Coffee');
    expect(submitBtn).toBeEnabled();
  });

  it('calls addTransaction with valid form data', async () => {
    mockAdd.mockResolvedValueOnce({
      id: 'new-uuid',
      category: 'food',
      confidence: 0.9,
      provenance: 'model',
      needs_review: false,
    });

    render(<ManualEntryForm onSuccess={() => undefined} />);

    await userEvent.type(screen.getByLabelText(/date/i), '2026-06-17');
    await userEvent.type(screen.getByLabelText(/amount/i), '-8.99');
    await userEvent.type(screen.getByLabelText(/description/i), 'Coffee');

    await userEvent.click(screen.getByRole('button', { name: /add transaction/i }));

    await waitFor(() => {
      expect(mockAdd).toHaveBeenCalledOnce();
    });
  });

  it('shows "already recorded" message on 409 duplicate error', async () => {
    mockAdd.mockRejectedValueOnce(new Error('already recorded'));

    render(<ManualEntryForm onSuccess={() => undefined} />);

    await userEvent.type(screen.getByLabelText(/date/i), '2026-06-17');
    await userEvent.type(screen.getByLabelText(/amount/i), '-8.99');
    await userEvent.type(screen.getByLabelText(/description/i), 'Coffee');

    await userEvent.click(screen.getByRole('button', { name: /add transaction/i }));

    await waitFor(() => {
      expect(screen.getByText(/already recorded/i)).toBeInTheDocument();
    });
  });
});
