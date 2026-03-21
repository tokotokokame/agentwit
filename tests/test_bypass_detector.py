"""Tests for BypassDetector: header injection and bypass detection."""
import pytest
from agentwit.security.bypass_detector import BypassDetector


@pytest.fixture()
def detector():
    return BypassDetector()


def test_inject_header_adds_proxy_header(detector):
    headers = {"Content-Type": "application/json"}
    result = detector.inject_header(headers)
    assert result["X-Agentwit-Proxy"] == "1"


def test_inject_header_returns_same_dict(detector):
    headers = {}
    result = detector.inject_header(headers)
    assert result is headers


def test_inject_header_preserves_existing_headers(detector):
    headers = {"Authorization": "Bearer token", "Content-Type": "application/json"}
    detector.inject_header(headers)
    assert "Authorization" in headers
    assert "Content-Type" in headers
    assert headers["X-Agentwit-Proxy"] == "1"


def test_check_request_no_header_returns_alert(detector):
    headers = {"Content-Type": "application/json"}
    result = detector.check_request(headers)
    assert result is not None
    assert result["type"] == "proxy_bypass_detected"
    assert result["severity"] == "HIGH"
    assert "X-Agentwit-Proxy" in result["detail"]


def test_check_request_with_header_returns_none(detector):
    headers = {"X-Agentwit-Proxy": "1", "Content-Type": "application/json"}
    result = detector.check_request(headers)
    assert result is None


def test_check_request_empty_headers_returns_alert(detector):
    result = detector.check_request({})
    assert result is not None
    assert result["type"] == "proxy_bypass_detected"


def test_inject_then_check_no_alert(detector):
    headers = {}
    detector.inject_header(headers)
    result = detector.check_request(headers)
    assert result is None
