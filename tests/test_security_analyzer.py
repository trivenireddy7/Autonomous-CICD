import json

import pytest
import requests

from src.diff_parser import ChangedLine
from src.security_analyzer import SecurityAnalyzer, SecurityAnalyzerError


def test_validate_response_normalizes_severity():
    findings = SecurityAnalyzer.validate_response(json.dumps({"findings": [{"file": "app.py", "line": 8, "severity": "high", "type": "SQL Injection", "description": "Input is concatenated into SQL.", "recommendation": "Use parameters."}]}))
    assert findings[0].severity == "HIGH"
    assert findings[0].line == 8


def test_validate_response_rejects_invalid_json():
    with pytest.raises(SecurityAnalyzerError, match="invalid JSON"):
        SecurityAnalyzer.validate_response("not-json")


def test_validate_response_rejects_bad_schema():
    with pytest.raises(SecurityAnalyzerError, match="findings array"):
        SecurityAnalyzer.validate_response({"issues": []})


def test_empty_changes_do_not_call_api():
    class NeverCalled:
        def post(self, *args, **kwargs):
            raise AssertionError("API should not be called")

    analyzer = SecurityAnalyzer("key", "https://example.test", session=NeverCalled())
    assert analyzer.analyze([]) == []


def test_api_timeout_is_reported_as_analyzer_error():
    class TimesOut:
        def post(self, *args, **kwargs):
            raise requests.Timeout("timed out")

    analyzer = SecurityAnalyzer("key", "https://example.test", session=TimesOut())
    changes = [ChangedLine("app.py", 1, "print('changed')", "python")]
    with pytest.raises(SecurityAnalyzerError, match="request failed"):
        analyzer.analyze(changes)
