"""OWASP LLM Top 10 mapper for agentwit risk indicators.

Maps internal pattern names to OWASP LLM Top 10 (2025) category identifiers
and enriches event lists with OWASP metadata.
"""
from __future__ import annotations

OWASP_MAPPING: dict[str, str] = {
    'instruction_override': 'LLM01',
    'role_hijack': 'LLM01',
    'jailbreak': 'LLM01',
    'hidden_instruction': 'LLM01',
    'data_extraction': 'LLM01',
    'credential_access': 'LLM02',
    'credential_access_extended': 'LLM02',
    'data_exfiltration': 'LLM02',
    'privilege_escalation': 'LLM06',
    'persistence': 'LLM06',
    'lateral_movement': 'LLM06',
    'tool_schema_change': 'LLM08',
    'proxy_bypass_detected': 'LLM08',
    'call_rate_anomaly': 'LLM10',
    'session_cost_exceeded': 'LLM10',
}

OWASP_DESCRIPTIONS: dict[str, str] = {
    'LLM01': 'Prompt Injection',
    'LLM02': 'Sensitive Information Disclosure',
    'LLM06': 'Excessive Agency',
    'LLM08': 'Vector and Embedding Weaknesses / Integrity Failures',
    'LLM10': 'Unbounded Consumption',
}


class OWASPMapper:
    """Maps agentwit risk patterns to OWASP LLM Top 10 categories."""

    def map(self, pattern: str) -> str | None:
        """Return the OWASP category ID for *pattern*, or ``None`` if unknown."""
        return OWASP_MAPPING.get(pattern)

    def describe(self, owasp_id: str) -> str:
        """Return the human-readable description for *owasp_id*.

        Returns ``'Unknown'`` for unrecognised IDs.
        """
        return OWASP_DESCRIPTIONS.get(owasp_id, 'Unknown')

    def map_events(self, events: list[dict]) -> list[dict]:
        """Enrich each event's ``risk_indicators`` with OWASP metadata.

        For every indicator whose ``pattern`` maps to a known OWASP category,
        two fields are added in-place on a shallow copy of the indicator:
        ``owasp_category`` and ``owasp_name``.

        Args:
            events: List of event dicts (as produced by :class:`WitnessLogger`).

        Returns:
            A new list of event dicts with enriched indicators.
        """
        result: list[dict] = []
        for event in events:
            event = dict(event)
            if 'risk_indicators' in event and event['risk_indicators']:
                enriched: list[dict] = []
                for indicator in event['risk_indicators']:
                    indicator = dict(indicator)
                    owasp_cat = self.map(indicator.get('pattern', ''))
                    if owasp_cat:
                        indicator['owasp_category'] = owasp_cat
                        indicator['owasp_name'] = self.describe(owasp_cat)
                    enriched.append(indicator)
                event['risk_indicators'] = enriched
            result.append(event)
        return result

    def summary(self, events: list[dict]) -> dict[str, int]:
        """Return a count of OWASP categories across all events.

        Counts each occurrence of ``owasp_category`` found in
        ``risk_indicators``.  Events should be pre-enriched by
        :meth:`map_events` for non-zero results.

        Returns:
            Dict mapping OWASP ID → occurrence count,
            e.g. ``{'LLM01': 3, 'LLM06': 1}``.
        """
        counts: dict[str, int] = {}
        for event in events:
            for indicator in event.get('risk_indicators') or []:
                cat = indicator.get('owasp_category')
                if cat:
                    counts[cat] = counts.get(cat, 0) + 1
        return counts
