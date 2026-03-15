import { useState, useMemo } from 'react';
import './App.css';
import { ConnectionPanel } from './components/ConnectionPanel';
import { ToolList } from './components/ToolList';
import { ExecutionPanel } from './components/ExecutionPanel';
import { RightPanel } from './components/RightPanel';
import { StatusBar } from './components/StatusBar';
import { MonocularIcon } from './components/MonocularIcon';
import { I18nContext, getTranslations } from './i18n';
import { useStore } from './store/useStore';
import type { TransportType } from './types/mcp';

function Header({ onOpenConnection }: { onOpenConnection: () => void }) {
  const {
    connectionConfig,
    connectionStatus,
    language,
    setLanguage,
    setConnectionConfig,
    auditLogEnabled,
    toggleAuditLog,
  } = useStore();
  const t = getTranslations(language);

  const connLabel = connectionStatus === 'connected'
    ? (connectionConfig.type === 'stdio'
        ? connectionConfig.command || 'stdio'
        : connectionConfig.url || '...')
    : t.connection.disconnected;

  return (
    <header className="app-header">
      {/* Logo */}
      <div className="header-left">
        <div className="app-logo-box">
          <MonocularIcon width={22} height={14} className="logo-lens-shine-parent" />
        </div>
        <div className="app-title">MCP<em>INSPECTOR</em></div>
        <div className="header-version">v0.1.0</div>
      </div>

      <div className="header-divider" />

      {/* Connection pill */}
      <div className="conn-pill" onClick={onOpenConnection}>
        <div className={`conn-led ${connectionStatus}`} />
        <span>{connLabel}</span>
        <span className="conn-arrow">▾</span>
      </div>

      {/* Transport group */}
      <div className="transport-group">
        {(['HTTP', 'SSE', 'stdio'] as const).map((tp) => {
          const val = tp.toLowerCase() as TransportType;
          return (
            <button
              key={tp}
              className={`tp-btn ${connectionConfig.type === val ? 'active' : ''}`}
              onClick={() => setConnectionConfig({ type: val })}
            >
              {tp}
            </button>
          );
        })}
      </div>

      {/* agentwit audit pill */}
      <div
        className={`aw-pill ${auditLogEnabled ? 'active' : ''}`}
        onClick={toggleAuditLog}
        title={`${t.statusBar.auditLog}: ${auditLogEnabled ? t.statusBar.auditLogOn : t.statusBar.auditLogOff}`}
      >
        <div className="aw-led" />
        agentwit audit
      </div>

      {/* Right */}
      <div className="header-right">
        <button
          className="header-icon-btn"
          onClick={onOpenConnection}
          title={t.connection.configure}
        >
          ⚙
        </button>

        <div className="lang-selector">
          <button
            className={`lang-btn ${language === 'en' ? 'active' : ''}`}
            onClick={() => setLanguage('en')}
          >
            EN
          </button>
          <span className="lang-divider">|</span>
          <button
            className={`lang-btn ${language === 'ja' ? 'active' : ''}`}
            onClick={() => setLanguage('ja')}
          >
            JP
          </button>
        </div>
      </div>
    </header>
  );
}

export default function App() {
  const [connectionPanelOpen, setConnectionPanelOpen] = useState(false);
  const { language } = useStore();
  const t = useMemo(() => getTranslations(language), [language]);

  return (
    <I18nContext.Provider value={t}>
      <div className="app-root">
        <Header onOpenConnection={() => setConnectionPanelOpen(true)} />

        <div className="app-body">
          <ToolList />
          <ExecutionPanel />
          <RightPanel />
        </div>

        <StatusBar />

        <ConnectionPanel
          isOpen={connectionPanelOpen}
          onClose={() => setConnectionPanelOpen(false)}
        />
      </div>
    </I18nContext.Provider>
  );
}
