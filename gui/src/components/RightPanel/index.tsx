import { useStore } from '../../store/useStore';
import { useI18n } from '../../i18n';
import { HistoryTab } from './HistoryTab';
import { MetricsTab } from './MetricsTab';
import { CompareTab } from './CompareTab';

export function RightPanel() {
  const t = useI18n();
  const { activeRightTab, setActiveRightTab, executionHistory } = useStore();

  const tabs = [
    { id: 'history' as const, label: t.history.title },
    { id: 'metrics' as const, label: t.metrics.title },
    { id: 'compare' as const, label: t.compare.title },
  ];

  return (
    <aside className="right-panel">
      <div className="rp-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`rp-tab ${activeRightTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveRightTab(tab.id)}
          >
            {tab.label}
            {tab.id === 'history' && executionHistory.length > 0 && (
              <span className="tab-badge">{executionHistory.length}</span>
            )}
          </button>
        ))}
      </div>

      <div className="rp-body">
        <div className={`tab-panel ${activeRightTab === 'history' ? 'active' : ''}`}>
          <HistoryTab />
        </div>
        <div className={`tab-panel ${activeRightTab === 'metrics' ? 'active' : ''}`}>
          <MetricsTab />
        </div>
        <div className={`tab-panel ${activeRightTab === 'compare' ? 'active' : ''}`}>
          <CompareTab />
        </div>
      </div>
    </aside>
  );
}
