import { useStore } from '../store/useStore';
import { useI18n } from '../i18n';
import { MonocularIcon } from './MonocularIcon';

// Infer simple tags from tool name / description
function inferTags(name: string, description?: string): string[] {
  const text = `${name} ${description ?? ''}`.toLowerCase();
  const tags: string[] = [];
  if (/write|create|insert|update|delete|post|put|patch|remove|save/.test(text)) tags.push('WRITE');
  if (/read|get|list|fetch|query|search|find|select|show/.test(text)) tags.push('READ');
  if (/exec|run|call|invoke|execute|spawn|start|launch/.test(text)) tags.push('EXEC');
  if (tags.length === 0) tags.push('READ'); // fallback
  return tags;
}

export function ToolList() {
  const t = useI18n();
  const {
    tools,
    selectedTool,
    toolFilter,
    setToolFilter,
    selectTool,
    connectionStatus,
  } = useStore();

  const filtered = tools.filter((tool) => {
    const q = toolFilter.toLowerCase();
    return !q || tool.name.toLowerCase().includes(q) || (tool.description ?? '').toLowerCase().includes(q);
  });

  return (
    <aside className="tool-list-panel">
      {/* Server meta section */}
      <div className="lp-section">
        <div className="lp-heading">{t.tools.server}</div>
        <div className="server-meta">
          <div className="sm-row">
            <span className="sm-key">{t.tools.statusLabel}</span>
            <span className={`sm-val ${connectionStatus === 'connected' ? 'ok' : connectionStatus === 'error' ? 'err' : ''}`}>
              {connectionStatus === 'connected'
                ? `● ${t.statusBar.connected}`
                : connectionStatus === 'connecting'
                ? `◌ ${t.statusBar.connecting}`
                : connectionStatus === 'error'
                ? `● ${t.statusBar.error}`
                : `○ ${t.statusBar.disconnected}`}
            </span>
          </div>
          <div className="sm-row">
            <span className="sm-key">{t.tools.protocolLabel}</span>
            <span className="sm-val">2024-11-05</span>
          </div>
        </div>
      </div>

      {/* Tools heading */}
      <div className="lp-section">
        <div className="lp-heading">
          {t.tools.title}
          {tools.length > 0 && (
            <span className="badge-count">{tools.length}</span>
          )}
        </div>
      </div>

      {/* Search */}
      <div className="tool-search-wrap">
        <input
          className="tool-search"
          type="text"
          placeholder={t.tools.search}
          value={toolFilter}
          onChange={(e) => setToolFilter(e.target.value)}
        />
      </div>

      {/* Tool list */}
      <div className="tool-scroller">
        {connectionStatus !== 'connected' && tools.length === 0 ? (
          <div className="tool-list-empty">
            <div className="tool-list-empty-icon">◈</div>
            <div>{t.tools.connect}</div>
          </div>
        ) : tools.length === 0 ? (
          <div className="tool-list-empty">
            <div className="tool-list-empty-icon">◈</div>
            <div>{t.tools.noTools}</div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="tool-list-empty">
            <div>{t.tools.noResults}</div>
          </div>
        ) : (
          filtered.map((tool) => {
            const tags = inferTags(tool.name, tool.description);
            return (
              <div
                key={tool.name}
                className={`tool-row ${selectedTool?.name === tool.name ? 'selected' : ''}`}
                onClick={() => selectTool(tool)}
              >
                <div className="tr-name">
                  {tool.name}
                  <MonocularIcon width={16} height={10} className="tr-hover-icon" />
                </div>
                {tool.description && (
                  <div className="tr-desc">{tool.description}</div>
                )}
                <div className="tr-tags">
                  {tags.map((tag) => (
                    <span
                      key={tag}
                      className={`tag ${tag === 'READ' ? 'tag-r' : tag === 'WRITE' ? 'tag-w' : 'tag-x'}`}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
}
