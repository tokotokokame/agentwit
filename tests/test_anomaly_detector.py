"""Tests for AnomalyDetector: call rate and repeated tool call detection."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
from agentwit.monitor.cost_guard import AnomalyDetector


@pytest.fixture()
def detector():
    return AnomalyDetector()


def test_no_alerts_for_normal_usage(detector):
    for _ in range(5):
        detector.record_call("read_file")
    alerts = detector.check_anomalies()
    assert alerts == []


def test_call_rate_anomaly_over_30_per_minute(detector):
    now = datetime.utcnow()
    # 31 calls within the last minute
    for i in range(31):
        detector._call_times.append(now - timedelta(seconds=i))
    alerts = detector.check_anomalies()
    rate_alerts = [a for a in alerts if a["type"] == "call_rate_anomaly"]
    assert len(rate_alerts) == 1
    assert rate_alerts[0]["severity"] == "HIGH"
    assert rate_alerts[0]["calls_per_minute"] == 31


def test_call_rate_exactly_30_no_alert(detector):
    now = datetime.utcnow()
    for i in range(30):
        detector._call_times.append(now - timedelta(seconds=i))
    alerts = detector.check_anomalies()
    rate_alerts = [a for a in alerts if a["type"] == "call_rate_anomaly"]
    assert len(rate_alerts) == 0


def test_old_calls_not_counted_in_rate(detector):
    now = datetime.utcnow()
    # 31 calls but older than 1 minute
    for i in range(31):
        detector._call_times.append(now - timedelta(minutes=2, seconds=i))
    alerts = detector.check_anomalies()
    rate_alerts = [a for a in alerts if a["type"] == "call_rate_anomaly"]
    assert len(rate_alerts) == 0


def test_repeated_tool_call_over_10(detector):
    for _ in range(11):
        detector.record_call("bash")
    alerts = detector.check_anomalies()
    repeated = [a for a in alerts if a["type"] == "repeated_tool_call"]
    assert len(repeated) == 1
    assert repeated[0]["severity"] == "MEDIUM"
    assert repeated[0]["tool"] == "bash"
    assert repeated[0]["count"] == 11


def test_repeated_tool_call_exactly_10_no_alert(detector):
    for _ in range(10):
        detector.record_call("bash")
    alerts = detector.check_anomalies()
    repeated = [a for a in alerts if a["type"] == "repeated_tool_call"]
    assert len(repeated) == 0


def test_multiple_tools_repeated(detector):
    for _ in range(11):
        detector.record_call("bash")
    for _ in range(12):
        detector.record_call("read_file")
    alerts = detector.check_anomalies()
    repeated = [a for a in alerts if a["type"] == "repeated_tool_call"]
    tools = {a["tool"] for a in repeated}
    assert "bash" in tools
    assert "read_file" in tools


def test_record_call_increments_count(detector):
    detector.record_call("bash")
    detector.record_call("bash")
    detector.record_call("bash")
    assert detector._tool_counts["bash"] == 3


def test_maxlen_on_call_times(detector):
    """deque maxlen=100 を超えても古いものが自動削除される"""
    for i in range(150):
        detector.record_call("tool")
    assert len(detector._call_times) == 100
