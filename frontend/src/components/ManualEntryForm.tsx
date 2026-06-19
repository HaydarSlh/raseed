import { useState } from 'react';
import { dashboardApi } from '../api/client';

interface Props {
  onSuccess: () => void;
}

export default function ManualEntryForm({ onSuccess }: Props): JSX.Element {
  const [txnDate, setTxnDate] = useState('');
  const [amount, setAmount] = useState('');
  const [description, setDescription] = useState('');
  const [merchant, setMerchant] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const amountNum = parseFloat(amount);
  const isValid =
    txnDate.trim() !== '' &&
    !isNaN(amountNum) &&
    amountNum !== 0 &&
    description.trim() !== '';

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid) return;
    setSubmitting(true);
    setErrorMsg('');
    setSuccessMsg('');
    try {
      const result = await dashboardApi.addTransaction({
        txn_date: `${txnDate}T00:00:00Z`,
        amount: amountNum,
        description: description.trim(),
        merchant: merchant.trim() || null,
        currency: 'USD',
      });
      setSuccessMsg(
        `Added — categorized as "${result.category ?? 'uncategorized'}".`,
      );
      setTimeout(onSuccess, 1200);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to add transaction.';
      setErrorMsg(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label
            htmlFor="txn-date"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Date
          </label>
          <input
            id="txn-date"
            type="date"
            value={txnDate}
            onChange={(e) => setTxnDate(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
        </div>
        <div>
          <label
            htmlFor="txn-amount"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Amount (negative = spend)
          </label>
          <input
            id="txn-amount"
            type="number"
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="-8.99"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
        </div>
      </div>

      <div>
        <label
          htmlFor="txn-description"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Description
        </label>
        <input
          id="txn-description"
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="e.g. APPLE MUSIC"
          maxLength={1024}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
        />
      </div>

      <div>
        <label
          htmlFor="txn-merchant"
          className="block text-sm font-medium text-gray-700 mb-1"
        >
          Merchant <span className="text-gray-400 font-normal">(optional)</span>
        </label>
        <input
          id="txn-merchant"
          type="text"
          value={merchant}
          onChange={(e) => setMerchant(e.target.value)}
          placeholder="e.g. Apple"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
        />
      </div>

      {errorMsg && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <p className="text-sm text-red-700">{errorMsg}</p>
        </div>
      )}

      {successMsg && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3">
          <p className="text-sm text-green-700">{successMsg}</p>
        </div>
      )}

      <button
        type="submit"
        disabled={!isValid || submitting}
        className="w-full py-2 px-4 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? 'Adding…' : 'Add transaction'}
      </button>
    </form>
  );
}
