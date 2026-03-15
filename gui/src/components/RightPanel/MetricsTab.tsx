import { useMemo } from 'react';
import { useStore } from '../../store/useStore';
import { useI18n } from '../../i18n';

export function MetricsTab() {
  const t = useI18n();
  const { executionHistory } = useStore();

  const metrics = useMemo(() => {
    if (executionHistory.length === 0) return null;

    const total = executionHistory.length;
    const successes = executionHistory.filter((e) => e.status === 'success').length;
    const successRate = Math.round((successes / total) * 100);
    const avgLatency = Math.round(
      executionHistory.reduce((sum, e) => sum + e.duration, 0) / total
    );
    const lastCall = executionHistory[0]?.timestamp;

    // Per-tool counts
    const perTool: Record<string, number> = {};
    for (const e of executionHistory) {
      perTool[e.toolName] = (perTool[e.toolName] ?? 0) + 1;
    }
    const maxCount = Math.max(...Object.values(perTool));

    // Last 10 latency bars
    const last10 = [...executionHistory].slice(0, 10).reverse();
    const maxLat = Math.max(...last10.map((e) => e.duration), 1);
    const peak = Math.max(...last10.map((e) => e.duration));

    return { total, successRate, avgLatency, lastCall, perTool, maxCount, last10, maxLat, peak };
  }, [executionHistory]);

  if (!metrics) {
    return (
      <div className="metrics-empty">{t.metrics.empty}</div>
    );
  }

  const { total, successRate, avgLatency, lastCall, perTool, maxCount, last10, maxLat, peak } = metrics;

  return (
    <div className="metrics-panel">
      {/* Overview cards */}
      <div className="metric-block">
        <div className="metric-block-title">{t.metrics.sessionOverview}</div>
        <div className="metric-grid">
          <div className="metric-card">
            <div className="mc-val a">{total}</div>
            <div className="mc-lbl">{t.metrics.totalCalls}</div>
          </div>
          <div className="metric-card">
            <div className="mc-val g">{successRate}%</div>
            <div className="mc-lbl">{t.metrics.successRate}</div>
          </div>
          <div className="metric-card">
            <div className="mc-val b">{avgLatency}<span style={{ fontSize: 12 }}>ms</span></div>
            <div className="mc-lbl">{t.metrics.avgLatency}</div>
          </div>
          <div className="metric-card">
            <div className="mc-val w" style={{ fontSize: 13, paddingTop: 4 }}>
              {lastCall ? lastCall.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : t.metrics.never}
            </div>
            <div className="mc-lbl">{t.metrics.lastCall}</div>
          </div>
        </div>
      </div>

      {/* Latency chart */}
      <div className="metric-block">
        <div className="metric-block-title">{t.metrics.latencyLast(last10.length)}</div>
        <div className="lat-chart-wrap">
          <div className="lat-chart-title">
            {t.metrics.ms}
            <span>{t.metrics.peak}: {peak} {t.metrics.ms}</span>
          </div>
          <div className="bar-row">
            {last10.length === 0 ? (
              <div className="bar-no-data">{t.metrics.noData}</div>
            ) : (
              last10.map((entry, i) => (
                <div
                  key={entry.id}
                  className={`lbar ${i === last10.length - 1 ? 'cur' : ''} ${entry.status === 'error' ? 'err-bar' : ''}`}
                  style={{ height: `${Math.max(4, Math.round((entry.duration / maxLat) * 48))}px` }}
                  title={`${entry.toolName}: ${entry.duration}ms`}
                />
              ))
            )}
          </div>
          <div className="bar-axis">
            <span>{last10[0] ? last10[0].timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}</span>
            <span>{t.metrics.now}</span>
          </div>
        </div>
      </div>

      {/* Tool usage */}
      <div className="metric-block">
        <div className="metric-block-title">{t.metrics.perTool}</div>
        <div className="usage-list">
          {Object.entries(perTool)
            .sort((a, b) => b[1] - a[1])
            .map(([name, count]) => (
              <div key={name} className="usage-row">
                <div className="ur-top">
                  <span>{name}</span>
                  <span className="ur-n">{count} {t.metrics.calls}</span>
                </div>
                <div className="ur-track">
                  <div
                    className="ur-fill"
                    style={{ width: `${Math.round((count / maxCount) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
