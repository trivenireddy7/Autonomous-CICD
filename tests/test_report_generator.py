from src.report_generator import generate_report
from src.security_analyzer import Finding


def test_report_passes_when_no_findings():
    report = generate_report([])
    assert "Status: PASS" in report
    assert "No significant security vulnerabilities" in report


def test_report_contains_summary_and_recommendation():
    report = generate_report([Finding("app.py", 25, "HIGH", "SQL Injection", "Unsafe query.", "Use parameters.")])
    assert "Status: FAIL" in report
    assert "| HIGH | SQL Injection | `app.py` | 25 |" in report
    assert "Use parameters." in report
