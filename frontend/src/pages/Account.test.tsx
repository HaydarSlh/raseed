// Tests: Account page — erasure button, confirmation guard, result display
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import Account from './Account';

vi.mock('../api/accountApi', () => ({
  accountApi: {
    requestErasure: vi.fn(),
  },
}));

import { accountApi } from '../api/accountApi';

const mockAccountApi = accountApi as {
  requestErasure: ReturnType<typeof vi.fn>;
};

const ERASURE_RESPONSE = {
  audit_id: 'audit-uuid-123',
  status: 'completed',
  deleted_counts: { transactions: 10, goals: 2 },
  message: 'All your data has been permanently deleted. This action cannot be undone.',
};

describe('Account page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the erasure button', async () => {
    render(
      <MemoryRouter>
        <Account />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('erasure-btn')).toBeInTheDocument();
    expect(screen.getByTestId('erasure-confirm-input')).toBeInTheDocument();
  });

  it('confirmation input blocks accidental deletion — button disabled until DELETE typed', () => {
    render(
      <MemoryRouter>
        <Account />
      </MemoryRouter>,
    );
    const btn = screen.getByTestId('erasure-btn') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);

    const input = screen.getByTestId('erasure-confirm-input');
    fireEvent.change(input, { target: { value: 'delete' } }); // lowercase — must NOT enable
    expect(btn.disabled).toBe(true);

    fireEvent.change(input, { target: { value: 'DELETE' } }); // exact match
    expect(btn.disabled).toBe(false);
  });

  it('successful erasure shows result message', async () => {
    mockAccountApi.requestErasure.mockResolvedValueOnce(ERASURE_RESPONSE);

    render(
      <MemoryRouter>
        <Account />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByTestId('erasure-confirm-input'), { target: { value: 'DELETE' } });
    fireEvent.click(screen.getByTestId('erasure-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('erasure-result')).toBeInTheDocument();
    });

    expect(mockAccountApi.requestErasure).toHaveBeenCalledOnce();
    expect(screen.getByTestId('erasure-result').textContent).toContain('permanently deleted');
  });
});
