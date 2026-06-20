// Ops dashboard: model registry, drift monitor, retrain history (Phase 5, US2-US4, operator-only)
import { useCallback, useEffect, useState } from 'react';
import AppLayout from '../components/AppLayout';
import ConfidenceChart from '../components/ConfidenceChart';
import { opsApi } from '../api/opsApi';
import type { ModelsResponse, DriftResponse, RetrainsResponse } from '../api/opsApi';

export default function Ops(): JSX.Element {
  const [models, setModels] = useState<ModelsResponse | null>(null);
  const [drift, setDrift] = useState<DriftResponse | null>(null);
  const [retrains, setRetrains] = useState<RetrainsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrainBusy, setRetrainBusy] = useState(false);
  const [promoteBusy, setPromoteBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [m, d, r] = await Promise.all([
        opsApi.getModels(),
        opsApi.getDrift(),
        opsApi.getRetrains(),
      ]);
      setModels(m);
      setDrift(d);
      setRetrains(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load ops data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  }

  async function handleRetrain(force = false) {
    setRetrainBusy(true);
    try {
      const res = await opsApi.triggerRetrain(force);
      showToast(`Retrain ${res.retrain_run_id} — ${res.status}`);
      await load();
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Retrain failed');
    } finally {
      setRetrainBusy(false);
    }
  }

  async function handlePromote(modelId: string) {
    setPromoteBusy(modelId);
    try {
      const res = await opsApi.promote(modelId);
      showToast(`Promoted ${res.promoted.slice(0, 8)} · reloaded=${res.model_server_reloaded}`);
      await load();
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Promote failed');
    } finally {
      setPromoteBusy(null);
    }
  }

  return (
    <AppLayout>
      <main className="max-w-4xl mx-auto px-4 py-6 space-y-8">
        <h1 className="text-xl font-semibold text-ink">Ops Dashboard</h1>

        {toast && (
          <div
            data-testid="ops-toast"
            className="px-4 py-2 bg-indigo-50 border border-indigo-200 rounded text-sm text-indigo-800"
          >
            {toast}
          </div>
        )}

        {loading && <p className="text-sm text-faint">Loading…</p>}
        {error && <p data-testid="ops-error" className="text-sm text-red-600">{error}</p>}

        {!loading && !error && (
          <>
            {/* Model Registry */}
            <section className="bg-surface rounded-lg border border-line p-5 space-y-4">
              <h2 className="font-medium text-ink">Model Registry</h2>

              {models?.champion ? (
                <div className="text-sm">
                  <span className="font-medium text-ink">Champion: </span>
                  <span data-testid="champion-version">{models.champion.version}</span>
                  <span className="ml-2 text-faint font-mono text-xs">
                    {models.champion.sha256.slice(0, 12)}
                  </span>
                  {models.champion.metrics?.macro_f1 != null && (
                    <span className="ml-2 text-faint">
                      F1 {(models.champion.metrics.macro_f1 as number).toFixed(3)}
                    </span>
                  )}
                </div>
              ) : (
                <p className="text-sm text-faint">No champion deployed.</p>
              )}

              {models?.promotable && models.promotable.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-medium text-faint">Promotable challengers</h3>
                  {models.promotable.map(m => (
                    <div
                      key={m.id}
                      data-testid="promotable-row"
                      className="flex items-center gap-3 text-sm"
                    >
                      <span className="font-mono text-xs text-faint">{m.sha256.slice(0, 12)}</span>
                      <span className="text-ink">{m.version}</span>
                      {m.gate_verdict && (
                        <span className="text-green-600 text-xs">{m.gate_verdict}</span>
                      )}
                      <button
                        data-testid={`promote-btn-${m.id}`}
                        onClick={() => void handlePromote(m.id)}
                        disabled={promoteBusy === m.id}
                        className="ml-auto text-xs px-3 py-1 bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                      >
                        {promoteBusy === m.id ? '…' : 'Promote'}
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex gap-2 pt-2">
                <button
                  data-testid="retrain-btn"
                  onClick={() => void handleRetrain(false)}
                  disabled={retrainBusy}
                  className="text-sm px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                >
                  {retrainBusy ? 'Triggering…' : 'Trigger Retrain'}
                </button>
                <button
                  data-testid="retrain-force-btn"
                  onClick={() => void handleRetrain(true)}
                  disabled={retrainBusy}
                  className="text-sm px-4 py-2 bg-elevated text-ink rounded hover:bg-line disabled:opacity-50"
                >
                  Force
                </button>
              </div>
            </section>

            {/* Drift Monitor */}
            <section className="bg-surface rounded-lg border border-line p-5 space-y-4">
              <h2 className="font-medium text-ink">Drift Monitor</h2>

              {drift && (
                <>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <Metric
                      label="Mean confidence"
                      value={drift.current.mean_confidence}
                      threshold={drift.thresholds.mean_confidence_min}
                      direction="above"
                    />
                    <Metric
                      label="Correction rate"
                      value={drift.current.correction_rate}
                      threshold={drift.thresholds.correction_rate_max}
                      direction="below"
                    />
                    <Metric
                      label="PSI"
                      value={drift.current.psi}
                      threshold={drift.thresholds.psi_max}
                      direction="below"
                    />
                    <Metric
                      label="New merchant rate"
                      value={drift.current.new_merchant_rate}
                      threshold={drift.thresholds.new_merchant_rate_max}
                      direction="below"
                    />
                  </div>

                  {drift.current.fired && (
                    <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
                      Signals fired: {drift.current.fired_signals.join(', ')}
                      {drift.current.triggered_retrain && ' · retrain enqueued'}
                    </div>
                  )}

                  <ConfidenceChart
                    series={drift.series}
                    threshold={drift.thresholds.mean_confidence_min ?? 0.7}
                  />
                </>
              )}
            </section>

            {/* Retrain History */}
            <section className="bg-surface rounded-lg border border-line p-5 space-y-3">
              <h2 className="font-medium text-ink">Retrain History</h2>
              {retrains && retrains.runs.length === 0 && (
                <p className="text-sm text-faint">No retrains yet.</p>
              )}
              {retrains && retrains.runs.map(run => (
                <div
                  key={run.id}
                  data-testid="retrain-run-row"
                  className="flex items-start gap-4 text-sm border-b border-line pb-2 last:border-0 last:pb-0"
                >
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-ink">{run.trigger_reason}</p>
                    <p className="text-xs text-faint">
                      {new Date(run.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="text-right text-xs space-y-0.5">
                    <p className={`font-medium ${run.status === 'completed' ? 'text-green-600' : run.status === 'failed' ? 'text-red-600' : 'text-faint'}`}>
                      {run.status}
                    </p>
                    {run.gate_verdict && (
                      <p className="text-faint">{run.gate_verdict}</p>
                    )}
                    {run.champion_macro_f1 != null && run.challenger_macro_f1 != null && (
                      <p className="text-faint">
                        {run.champion_macro_f1.toFixed(3)} → {run.challenger_macro_f1.toFixed(3)}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </section>
          </>
        )}
      </main>
    </AppLayout>
  );
}

function Metric({
  label,
  value,
  threshold,
  direction,
}: {
  label: string;
  value: number | null;
  threshold: number | undefined;
  direction: 'above' | 'below';
}): JSX.Element {
  const violated =
    value != null && threshold != null &&
    (direction === 'above' ? value < threshold : value > threshold);

  return (
    <div className="bg-elevated rounded p-3">
      <p className="text-xs text-faint mb-1">{label}</p>
      <p className={`text-lg font-semibold ${violated ? 'text-red-600' : 'text-ink'}`}>
        {value != null ? value.toFixed(3) : '—'}
      </p>
      {threshold != null && (
        <p className="text-xs text-faint">
          {direction === 'above' ? 'min' : 'max'} {threshold}
        </p>
      )}
    </div>
  );
}
