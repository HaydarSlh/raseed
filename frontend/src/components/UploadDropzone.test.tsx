import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import UploadDropzone from './UploadDropzone';
import * as client from '../api/client';

vi.mock('../api/client', async (importOriginal) => {
  const mod = await importOriginal<typeof import('../api/client')>();
  return { ...mod, dashboardApi: { ...mod.dashboardApi, uploadStatement: vi.fn() } };
});

const mockUpload = vi.mocked(client.dashboardApi.uploadStatement);

beforeEach(() => {
  vi.clearAllMocks();
});

describe('UploadDropzone', () => {
  it('calls uploadStatement and renders import count banner on success', async () => {
    mockUpload.mockResolvedValueOnce({
      ingested: 5,
      needs_review: 4,
      duplicates_skipped: 0,
      recompute_enqueued: true,
    });

    render(<UploadDropzone onSuccess={() => undefined} />);

    const file = new File(['date,amount,desc\n2026-01-01,-10,Coffee'], 'statement.csv', {
      type: 'text/csv',
    });
    const input = screen.getByTestId('file-input');
    await userEvent.upload(input, file);

    const submitBtn = screen.getByRole('button', { name: /import/i });
    await userEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText(/5 imported/i)).toBeInTheDocument();
      expect(screen.getByText(/4 flagged for review/i)).toBeInTheDocument();
    });
  });

  it('renders "nothing new imported" when ingested is 0', async () => {
    mockUpload.mockResolvedValueOnce({
      ingested: 0,
      needs_review: 0,
      duplicates_skipped: 3,
      recompute_enqueued: false,
    });

    render(<UploadDropzone onSuccess={() => undefined} />);

    const file = new File(['date,amount,desc\n2026-01-01,-10,Coffee'], 'dupes.csv', {
      type: 'text/csv',
    });
    const input = screen.getByTestId('file-input');
    await userEvent.upload(input, file);
    fireEvent.click(screen.getByRole('button', { name: /import/i }));

    await waitFor(() => {
      expect(screen.getByText(/nothing new imported/i)).toBeInTheDocument();
    });
  });
});
