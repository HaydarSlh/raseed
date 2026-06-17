import type { SubscriptionView } from '../api/types';

interface Props {
  subscriptions: SubscriptionView[];
}

export default function SubscriptionsPanel({ subscriptions }: Props): JSX.Element | null {
  if (subscriptions.length === 0) return null;

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-800 mb-3">Subscriptions</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {subscriptions.map((sub) => (
          <div
            key={sub.merchant}
            className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
          >
            <div className="flex items-start justify-between mb-2">
              <span className="font-semibold text-gray-800">{sub.merchant}</span>
              {sub.price_increase && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-200">
                  Price increased
                </span>
              )}
            </div>
            <p className="text-sm text-gray-500 capitalize">{sub.cadence}</p>
            <p className="text-lg font-bold text-gray-800 mt-1">
              £{sub.typical_amount.toFixed(2)}
            </p>
            {sub.next_charge_date && (
              <p className="text-xs text-gray-400 mt-1">
                Next: {sub.next_charge_date}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
