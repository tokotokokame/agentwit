"""Tests for agentwit.analyzer.owasp_mapper.OWASPMapper."""
from __future__ import annotations

import pytest

from agentwit.analyzer.owasp_mapper import (
    OWASPMapper,
    OWASP_MAPPING,
    OWASP_DESCRIPTIONS,
)


# ===========================================================================
# 1. OWASPMapper.map — pattern → category
# ===========================================================================

class TestMap:
    def test_instruction_override_is_llm01(self) -> None:
        assert OWASPMapper().map('instruction_override') == 'LLM01'

    def test_role_hijack_is_llm01(self) -> None:
        assert OWASPMapper().map('role_hijack') == 'LLM01'

    def test_credential_access_is_llm02(self) -> None:
        assert OWASPMapper().map('credential_access') == 'LLM02'

    def test_data_exfiltration_is_llm02(self) -> None:
        assert OWASPMapper().map('data_exfiltration') == 'LLM02'

    def test_privilege_escalation_is_llm06(self) -> None:
        assert OWASPMapper().map('privilege_escalation') == 'LLM06'

    def test_persistence_is_llm06(self) -> None:
        assert OWASPMapper().map('persistence') == 'LLM06'

    def test_tool_schema_change_is_llm08(self) -> None:
        assert OWASPMapper().map('tool_schema_change') == 'LLM08'

    def test_proxy_bypass_detected_is_llm08(self) -> None:
        assert OWASPMapper().map('proxy_bypass_detected') == 'LLM08'

    def test_call_rate_anomaly_is_llm10(self) -> None:
        assert OWASPMapper().map('call_rate_anomaly') == 'LLM10'

    def test_session_cost_exceeded_is_llm10(self) -> None:
        assert OWASPMapper().map('session_cost_exceeded') == 'LLM10'

    def test_unknown_pattern_returns_none(self) -> None:
        assert OWASPMapper().map('no_such_pattern') is None

    def test_empty_string_returns_none(self) -> None:
        assert OWASPMapper().map('') is None

    def test_all_patterns_in_mapping_are_reachable(self) -> None:
        """Every key in OWASP_MAPPING should be mapped via map()."""
        mapper = OWASPMapper()
        for pattern, expected_id in OWASP_MAPPING.items():
            assert mapper.map(pattern) == expected_id, f"Failed for {pattern!r}"


# ===========================================================================
# 2. OWASPMapper.describe — category ID → description
# ===========================================================================

class TestDescribe:
    def test_llm01_prompt_injection(self) -> None:
        assert OWASPMapper().describe('LLM01') == 'Prompt Injection'

    def test_llm02_sensitive_info(self) -> None:
        assert 'Sensitive' in OWASPMapper().describe('LLM02')

    def test_llm06_excessive_agency(self) -> None:
        assert OWASPMapper().describe('LLM06') == 'Excessive Agency'

    def test_llm10_unbounded_consumption(self) -> None:
        assert OWASPMapper().describe('LLM10') == 'Unbounded Consumption'

    def test_unknown_id_returns_unknown(self) -> None:
        assert OWASPMapper().describe('LLM99') == 'Unknown'

    def test_all_descriptions_present(self) -> None:
        """Every key in OWASP_DESCRIPTIONS should be reachable via describe()."""
        mapper = OWASPMapper()
        for owasp_id, desc in OWASP_DESCRIPTIONS.items():
            assert mapper.describe(owasp_id) == desc


# ===========================================================================
# 3. OWASPMapper.map_events — event list enrichment
# ===========================================================================

class TestMapEvents:
    def _make_event(self, patterns: list[str]) -> dict:
        return {
            'action': 'tools/call',
            'tool': 'bash',
            'risk_indicators': [
                {'pattern': p, 'severity': 'high'} for p in patterns
            ],
        }

    def test_known_pattern_gets_owasp_category(self) -> None:
        mapper = OWASPMapper()
        events = [self._make_event(['privilege_escalation'])]
        result = mapper.map_events(events)
        ind = result[0]['risk_indicators'][0]
        assert ind['owasp_category'] == 'LLM06'

    def test_known_pattern_gets_owasp_name(self) -> None:
        mapper = OWASPMapper()
        events = [self._make_event(['instruction_override'])]
        result = mapper.map_events(events)
        ind = result[0]['risk_indicators'][0]
        assert ind['owasp_name'] == 'Prompt Injection'

    def test_unknown_pattern_no_owasp_fields(self) -> None:
        mapper = OWASPMapper()
        events = [self._make_event(['shell_exec'])]
        result = mapper.map_events(events)
        ind = result[0]['risk_indicators'][0]
        assert 'owasp_category' not in ind
        assert 'owasp_name' not in ind

    def test_event_without_risk_indicators_unchanged(self) -> None:
        mapper = OWASPMapper()
        events = [{'action': 'tools/list', 'risk_indicators': []}]
        result = mapper.map_events(events)
        assert result[0]['risk_indicators'] == []

    def test_event_with_no_risk_indicators_key(self) -> None:
        mapper = OWASPMapper()
        events = [{'action': 'tools/list'}]
        result = mapper.map_events(events)
        assert 'risk_indicators' not in result[0]

    def test_does_not_mutate_original_events(self) -> None:
        mapper = OWASPMapper()
        original_ind = {'pattern': 'credential_access', 'severity': 'high'}
        events = [{'action': 'a', 'risk_indicators': [original_ind]}]
        mapper.map_events(events)
        # Original dict must be untouched
        assert 'owasp_category' not in original_ind

    def test_multiple_indicators_mixed(self) -> None:
        mapper = OWASPMapper()
        events = [self._make_event(['jailbreak', 'shell_exec', 'data_exfiltration'])]
        result = mapper.map_events(events)
        indicators = result[0]['risk_indicators']
        assert indicators[0]['owasp_category'] == 'LLM01'
        assert 'owasp_category' not in indicators[1]
        assert indicators[2]['owasp_category'] == 'LLM02'

    def test_returns_new_list(self) -> None:
        mapper = OWASPMapper()
        events: list[dict] = []
        result = mapper.map_events(events)
        assert result is not events


# ===========================================================================
# 4. OWASPMapper.summary — OWASP category counts
# ===========================================================================

class TestSummary:
    def _enriched_events(self, patterns: list[str]) -> list[dict]:
        mapper = OWASPMapper()
        raw = [
            {
                'action': 'tools/call',
                'risk_indicators': [{'pattern': p, 'severity': 'high'}],
            }
            for p in patterns
        ]
        return mapper.map_events(raw)

    def test_empty_events_returns_empty_dict(self) -> None:
        assert OWASPMapper().summary([]) == {}

    def test_single_pattern_counted(self) -> None:
        events = self._enriched_events(['jailbreak'])
        counts = OWASPMapper().summary(events)
        assert counts == {'LLM01': 1}

    def test_multiple_same_category_aggregated(self) -> None:
        events = self._enriched_events(['jailbreak', 'instruction_override', 'role_hijack'])
        counts = OWASPMapper().summary(events)
        assert counts.get('LLM01') == 3

    def test_multiple_categories_counted_independently(self) -> None:
        events = self._enriched_events([
            'jailbreak',           # LLM01
            'credential_access',   # LLM02
            'privilege_escalation', # LLM06
        ])
        counts = OWASPMapper().summary(events)
        assert counts['LLM01'] == 1
        assert counts['LLM02'] == 1
        assert counts['LLM06'] == 1

    def test_unknown_patterns_not_counted(self) -> None:
        mapper = OWASPMapper()
        events = [{'action': 'a', 'risk_indicators': [{'pattern': 'shell_exec', 'severity': 'low'}]}]
        enriched = mapper.map_events(events)
        counts = mapper.summary(enriched)
        assert counts == {}

    def test_events_without_risk_indicators_ignored(self) -> None:
        events = [{'action': 'tools/list'}]
        counts = OWASPMapper().summary(events)
        assert counts == {}
