import { useState, useCallback } from 'react';
import { useStore } from '../store/useStore';
import { useI18n } from '../i18n';
import { MCPClient, MCPClientError, setClient, getClient } from '../lib/mcpClient';
import type { TransportType } from '../types/mcp';

interface ConnectionPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ConnectionPanel({ isOpen, onClose }: ConnectionPanelProps) {
  const t = useI18n();
  const {
    connectionConfig,
    connectionStatus,
    setConnectionConfig,
    setConnectionStatus,
    setLastError,
    setTools,
    selectTool,
  } = useStore();

  const [headersText, setHeadersText] = useState(
    connectionConfig.headers ? JSON.stringify(connectionConfig.headers, null, 2) : ''
  );
  const [argsText, setArgsText] = useState(
    connectionConfig.args ? connectionConfig.args.join(' ') : ''
  );
  const [localError, setLocalError] = useState<string | null>(null);

  const isConnected  = connectionStatus === 'connected';
  const isConnecting = connectionStatus === 'connecting';

  const handleTransportChange = useCallback((type: TransportType) => {
    setConnectionConfig({ type });
  }, [setConnectionConfig]);

  const handleConnect = useCallback(async () => {
    setLocalError(null);
    setLastError(null);
    setConnectionStatus('connecting');

    let headers: Record<string, string> = {};
    if (headersText.trim()) {
      try {
        headers = JSON.parse(headersText) as Record<string, string>;
      } catch {
        setLocalError('Invalid JSON in headers field');
        setConnectionStatus('error');
        return;
      }
    }

    const args = argsText.split(/\s+/).map((a) => a.trim()).filter(Boolean);
    const config = { ...connectionConfig, headers, args };
    setConnectionConfig({ headers, args });

    try {
      const existing = getClient();
      if (existing) { await existing.disconnect(); setClient(null); }

      const client = new MCPClient(config);
      await client.connect();
      await client.initialize();

      setClient(client);
      setConnectionStatus('connected');

      const tools = await client.listTools();
      setTools(tools);
      setLastError(null);
      onClose();
    } catch (e) {
      const msg = e instanceof MCPClientError ? e.message : String(e);
      setLocalError(msg);
      setLastError(msg);
      setConnectionStatus('error');
      setClient(null);
    }
  }, [connectionConfig, headersText, argsText, setConnectionConfig, setConnectionStatus, setLastError, setTools, onClose]);

  const handleDisconnect = useCallback(async () => {
    const client = getClient();
    if (client) { await client.disconnect(); setClient(null); }
    setConnectionStatus('disconnected');
    setTools([]);
    selectTool(null);
    setLastError(null);
    onClose();
  }, [setConnectionStatus, setTools, selectTool, setLastError, onClose]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">{t.connection.configure}</div>
          <button className="modal-close" onClick={onClose} aria-label={t.connection.close}>✕</button>
        </div>

        <div className="modal-body">
          {localError && (
            <div className="alert alert-error">
              <span className="alert-icon">⚠</span>
              {localError}
            </div>
          )}

          {/* Transport selector */}
          <div className="form-group">
            <div className="form-label">{t.connection.transport}</div>
            <div className="transport-group" style={{ width: 'fit-content' }}>
              {(['stdio', 'http', 'sse'] as TransportType[]).map((tp) => (
                <button
                  key={tp}
                  className={`tp-btn ${connectionConfig.type === tp ? 'active' : ''}`}
                  onClick={() => handleTransportChange(tp)}
                  disabled={isConnecting}
                >
                  {tp.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {connectionConfig.type === 'stdio' ? (
            <>
              <div className="form-group">
                <div className="form-label">{t.connection.command}</div>
                <input
                  className="form-input"
                  type="text"
                  placeholder={t.connection.commandPlaceholder}
                  value={connectionConfig.command ?? ''}
                  onChange={(e) => setConnectionConfig({ command: e.target.value })}
                  disabled={isConnecting}
                />
              </div>
              <div className="form-group">
                <div className="form-label">{t.connection.args}</div>
                <input
                  className="form-input"
                  type="text"
                  placeholder={t.connection.argsPlaceholder}
                  value={argsText}
                  onChange={(e) => setArgsText(e.target.value)}
                  disabled={isConnecting}
                />
              </div>
            </>
          ) : (
            <>
              <div className="form-group">
                <div className="form-label">{t.connection.url}</div>
                <input
                  className="form-input"
                  type="url"
                  placeholder={t.connection.urlPlaceholder}
                  value={connectionConfig.url ?? ''}
                  onChange={(e) => setConnectionConfig({ url: e.target.value })}
                  disabled={isConnecting}
                />
              </div>
              <div className="form-group">
                <div className="form-label">{t.connection.headers}</div>
                <textarea
                  className="form-textarea"
                  placeholder={t.connection.headersPlaceholder}
                  value={headersText}
                  onChange={(e) => setHeadersText(e.target.value)}
                  rows={4}
                  disabled={isConnecting}
                />
              </div>
            </>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={isConnecting}>
            {t.connection.close}
          </button>
          {isConnected ? (
            <button className="btn btn-danger" onClick={handleDisconnect}>
              {t.connection.disconnect}
            </button>
          ) : (
            <button className="btn btn-primary" onClick={handleConnect} disabled={isConnecting}>
              {isConnecting ? (
                <><span className="spinner" /> {t.connection.connecting}</>
              ) : (
                t.connection.connect
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
