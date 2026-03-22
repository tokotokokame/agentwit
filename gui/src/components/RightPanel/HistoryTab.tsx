import { useState, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { save } from '@tauri-apps/plugin-dialog';
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

  const handleExportReport = useCallback(async () => {
    const today = new Date().toISOString().slice(0, 10);
    const defaultName = `agentwit-report-${today}.html`;

    const outputPath = await save({
      defaultPath: defaultName,
      filters: [{ name: 'HTML files', extensions: ['html'] }],
    });
    if (!outputPath) return;

    const home = (window as unknown as { __TAURI_INTERNALS__?: { metadata?: { currentDir?: string } } })
      ?.__TAURI_INTERNALS__?.metadata?.currentDir ?? '';
    const sessionPath = `${home}/.agentwit`;

    try {
      await invoke<string>('generate_report', {
        sessionPath,
        outputPath,
      });
      // トースト通知（シンプルなアラートで代替）
      const msg = document.createElement('div');
      msg.textContent = 'レポートを生成しました';
      Object.assign(msg.style, {
        position: 'fixed', bottom: '24px', right: '24px',
        background: 'var(--amber)', color: '#000',
        padding: '10px 18px', borderRadius: '6px',
        fontFamily: 'var(--mono)', fontSize: '13px',
        zIndex: '9999', boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
      });
      document.body.appendChild(msg);
      setTimeout(() => msg.remove(), 3000);
    } catch (err) {
      alert(`レポート生成に失敗しました: ${err}`);
    }
  }, []);

  const isEmpty = executionHistory.length === 0;

  return (
    <>
      <div className="hist-header">
        <span className="hist-header-label">{t.history.title}</span>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            onClick={handleExportReport}
            disabled={isEmpty}
            style={{
              background: isEmpty ? 'var(--bg-04)' : '#f5a623',
              color: isEmpty ? 'var(--text-lo)' : '#000',
              border: 'none',
              borderRadius: '4px',
              padding: '4px 12px',
              fontSize: '12px',
              fontFamily: 'var(--mono)',
              cursor: isEmpty ? 'not-allowed' : 'pointer',
              letterSpacing: '0.05em',
              fontWeight: 600,
              transition: 'background .15s',
            }}
          >
            Export Report
          </button>
          <button className="mini-btn" onClick={clearHistory}>
            {t.history.clear}
          </button>
        </div>
      </div>
      {isEmpty ? (
        <div className="hist-empty">
          <div className="hist-empty-icon">◈</div>
          <div>{t.history.empty}</div>
          <div className="hist-empty-sub">{t.history.runHint}</div>
        </div>
      ) : (
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
      )}
    </>
  );
}
