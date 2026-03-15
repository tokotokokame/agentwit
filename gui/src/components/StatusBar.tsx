import { useStore } from '../store/useStore';
import { useI18n } from '../i18n';

export function StatusBar() {
  const t = useI18n();
  const { connectionStatus, connectionConfig, tools, auditLogEnabled } = useStore();

  const ledClass =
    connectionStatus === 'connected'   ? 'g' :
    connectionStatus === 'connecting'  ? 'a' :
    connectionStatus === 'error'       ? 'r' : 'd';

  const statusLabel =
    connectionStatus === 'connected'   ? t.statusBar.connected :
    connectionStatus === 'connecting'  ? t.statusBar.connecting :
    connectionStatus === 'error'       ? t.statusBar.error :
    t.statusBar.disconnected;

  const transport = connectionConfig.type.toUpperCase();

  return (
    <div className="status-bar">
      <div className="sb-item">
        <div className={`sb-led ${ledClass}`} />
        {statusLabel}
      </div>

      <span className="sb-sep">|</span>

      <div className="sb-item">
        <div className="sb-led a" />
        {transport}
      </div>

      <span className="sb-sep">|</span>

      <div className="sb-item">
        {tools.length} {t.statusBar.tools}
      </div>

      <span className="sb-sep">|</span>

      <div className="sb-item">
        {t.statusBar.auditLog}:{' '}
        <span className={auditLogEnabled ? 'sb-aw' : ''}>
          {auditLogEnabled ? t.statusBar.auditLogOn : t.statusBar.auditLogOff}
        </span>
      </div>
    </div>
  );
}
