import { useState, useMemo } from 'react';
import { useStore } from '../../store/useStore';
import { useI18n } from '../../i18n';
import type { ExecutionRecord } from '../../types/mcp';

function formatLabel(entry: ExecutionRecord): string {
  const time = entry.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  return `${entry.toolName} @ ${time} (${entry.status === 'success' ? 'OK' : 'ERR'})`;
}

// Simple LCS-based line diff
function lineDiff(a: string, b: string): Array<{ text: string; type: 'same' | 'add' | 'rem' }> {
  const aLines = a.split('\n');
  const bLines = b.split('\n');
  const result: Array<{ text: string; type: 'same' | 'add' | 'rem' }> = [];

  const m = aLines.length, n = bLines.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--)
    for (let j = n - 1; j >= 0; j--)
      dp[i][j] = aLines[i] === bLines[j]
        ? dp[i + 1][j + 1] + 1
        : Math.max(dp[i + 1][j], dp[i][j + 1]);

  let i = 0, j = 0;
  while (i < m || j < n) {
    if (i < m && j < n && aLines[i] === bLines[j]) {
      result.push({ text: aLines[i], type: 'same' });
      i++; j++;
    } else if (j < n && (i >= m || dp[i][j + 1] >= dp[i + 1][j])) {
      result.push({ text: bLines[j], type: 'add' });
      j++;
    } else {
      result.push({ text: aLines[i], type: 'rem' });
      i++;
    }
  }
  return result;
}

export function CompareTab() {
  const t = useI18n();
  const { executionHistory } = useStore();
  const [leftId, setLeftId] = useState('');
  const [rightId, setRightId] = useState('');

  const leftEntry = executionHistory.find((e) => e.id === leftId);
  const rightEntry = executionHistory.find((e) => e.id === rightId);

  const diff = useMemo(() => {
    if (!leftEntry || !rightEntry) return null;
    const la = JSON.stringify(leftEntry.response ?? leftEntry.error, null, 2) ?? '';
    const ra = JSON.stringify(rightEntry.response ?? rightEntry.error, null, 2) ?? '';
    return lineDiff(la, ra);
  }, [leftEntry, rightEntry]);

  if (executionHistory.length < 2) {
    return (
      <div className="cmp-empty">{t.compare.noHistory}</div>
    );
  }

  const hasDiff = diff && diff.some((l) => l.type !== 'same');

  return (
    <div className="compare-panel">
      <div className="cmp-desc">{t.compare.selectFirst} / {t.compare.selectSecond}</div>

      <div className="cmp-selectors">
        <div className="cmp-sel-card">
          <div className="csc-label">{t.compare.left}</div>
          <select
            className="csc-select"
            value={leftId}
            onChange={(e) => setLeftId(e.target.value)}
          >
            <option value="">—</option>
            {executionHistory.map((e) => (
              <option key={e.id} value={e.id}>{formatLabel(e)}</option>
            ))}
          </select>
        </div>
        <div className="cmp-sel-card">
          <div className="csc-label">{t.compare.right}</div>
          <select
            className="csc-select"
            value={rightId}
            onChange={(e) => setRightId(e.target.value)}
          >
            <option value="">—</option>
            {executionHistory.map((e) => (
              <option key={e.id} value={e.id}>{formatLabel(e)}</option>
            ))}
          </select>
        </div>
      </div>

      {diff && (
        <div className="cmp-diff">
          <div className="diff-title">{t.compare.diff}</div>
          {!hasDiff ? (
            <div className="diff-same">{t.compare.same}</div>
          ) : (
            <div className="diff-row">
              <div className="diff-col">
                <div className="diff-col-label">{t.compare.left}</div>
                <div className="diff-col-content">
                  {diff.map((line, i) => (
                    line.type === 'same' || line.type === 'rem'
                      ? <div key={i} className={line.type === 'rem' ? 'diff-line-rem' : ''}>
                          {line.text || '\u00a0'}
                        </div>
                      : null
                  ))}
                </div>
              </div>
              <div className="diff-col">
                <div className="diff-col-label">{t.compare.right}</div>
                <div className="diff-col-content">
                  {diff.map((line, i) => (
                    line.type === 'same' || line.type === 'add'
                      ? <div key={i} className={line.type === 'add' ? 'diff-line-add' : ''}>
                          {line.text || '\u00a0'}
                        </div>
                      : null
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {leftEntry && rightEntry && (
        <div className="cmp-run-btn">
          {t.compare.diff}: {t.compare.linesDiffer(diff?.filter((l) => l.type !== 'same').length ?? 0)}
        </div>
      )}
    </div>
  );
}
