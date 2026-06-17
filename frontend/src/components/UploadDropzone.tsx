import { DragEvent, useRef, useState } from 'react';
import { dashboardApi } from '../api/client';
import type { UploadResultView } from '../api/types';

interface Props {
  onSuccess: () => void;
}

type UploadState = 'idle' | 'uploading' | 'done' | 'error';

export default function UploadDropzone({ onSuccess }: Props): JSX.Element {
  const [file, setFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>('idle');
  const [result, setResult] = useState<UploadResultView | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  }

  async function handleSubmit() {
    if (!file) return;
    setUploadState('uploading');
    setErrorMsg('');
    try {
      const res = await dashboardApi.uploadStatement(file);
      setResult(res);
      setUploadState('done');
      if (res.ingested > 0) {
        setTimeout(onSuccess, 1500);
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Upload failed.');
      setUploadState('error');
    }
  }

  return (
    <div className="space-y-4">
      <div
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
          isDragging ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300 bg-white hover:border-indigo-300'
        }`}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        aria-label="Drop CSV file or click to select"
      >
        <input
          ref={inputRef}
          data-testid="file-input"
          type="file"
          accept=".csv"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); }}
        />
        {file ? (
          <p className="text-sm font-medium text-gray-700">{file.name}</p>
        ) : (
          <>
            <p className="text-gray-500 text-sm mb-1">Drop a CSV bank statement here</p>
            <p className="text-gray-400 text-xs">or click to select — max 10 MB</p>
          </>
        )}
      </div>

      {file && uploadState !== 'done' && (
        <button
          onClick={() => void handleSubmit()}
          disabled={uploadState === 'uploading'}
          className="w-full py-2 px-4 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
        >
          {uploadState === 'uploading' ? 'Importing…' : 'Import statement'}
        </button>
      )}

      {uploadState === 'error' && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm text-red-700">{errorMsg}</p>
        </div>
      )}

      {uploadState === 'done' && result && (
        <div className={`rounded-lg border px-4 py-3 ${result.ingested === 0 ? 'border-amber-200 bg-amber-50' : 'border-green-200 bg-green-50'}`}>
          {result.ingested === 0 ? (
            <p className="text-sm text-amber-700">
              Nothing new imported — all rows already recorded
              {result.duplicates_skipped > 0 ? ` (${result.duplicates_skipped} duplicate${result.duplicates_skipped !== 1 ? 's' : ''} skipped)` : ''}.
            </p>
          ) : (
            <p className="text-sm text-green-700">
              <strong>{result.ingested} imported</strong>,{' '}
              <strong>{result.needs_review} flagged for review</strong>.
              {result.recompute_enqueued ? ' Dashboard will refresh shortly.' : ''}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
