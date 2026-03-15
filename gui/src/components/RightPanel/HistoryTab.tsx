import { useState, useCallback } from 'react';
import { useStore } from '../../store/useStore';
import { useI18n } from '../../i18n';
import type { ExecutionRecord } from '../../types/mcp';

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function previewJson(value: unknown): string {
  const s = JSON.stringify(value);
  return s.length > 60 ? s.slice(0, 60) + '…' : s;
}

export function HistoryTab() {
  const t = useI18n();
  const { executionHistory, clearHistory } = useStore();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggle = useCallback((id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  }, []);

  if (executionHistory.length === 0) {
    return (
      <div className="hist-empty">
        <div className="hist-empty-icon">◈</div>
        <div>{t.history.empty}</div>
        <div className="hist-empty-sub">{t.history.runHint}</div>
      </div>
    );
  }

  return (
    <>
      <div className="hist-header">
        <span className="hist-header-label">{t.history.title}</span>
        <button className="mini-btn" onClick={clearHistory}>
          {t.history.clear}
        </button>
      </div>
      <div id="histList">
        {executionHistory.map((entry: ExecutionRecord) => {
          const isExpanded = expandedId === entry.id;
          const isOk = entry.status === 'success';
          return (
            <div
              key={entry.id}
              className={`hist-entry ${isExpanded ? 'expanded' : ''}`}
              onClick={() => toggle(entry.id)}
            >
              <div className="he-top">
                <span className="he-name">{entry.toolName}</span>
                <span className={`he-status ${isOk ? 'ok' : 'err'}`}>
                  {isOk ? '✓ OK' : '✗ ERR'}
                </span>
              </div>
              <div className="he-mid">
                <span>{formatTime(entry.timestamp)}</span>
                <span className="he-latency">{entry.duration} ms</span>
              </div>
              <div className="he-preview">
                {isOk
                  ? previewJson(entry.response)
                  : entry.error ?? 'error'}
              </div>
              {isExpanded && (
                <div className="he-detail">
                  <div>
                    <div className="he-detail-label">{t.history.params}</div>
                    <pre className="he-detail-pre">
                      {JSON.stringify(entry.params, null, 2)}
                    </pre>
                  </div>
                  {entry.response != null && (
                    <div>
                      <div className="he-detail-label">{t.history.response}</div>
                      <pre className="he-detail-pre">
                        {JSON.stringify(entry.response, null, 2)}
                      </pre>
                    </div>
                  )}
                  {entry.error && (
                    <div>
                      <div className="he-detail-label" style={{ color: 'var(--red)' }}>
                        {t.history.error}
                      </div>
                      <pre className="he-detail-pre" style={{ color: 'var(--red)' }}>
                        {entry.error}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
