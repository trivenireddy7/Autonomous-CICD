"""Markdown report generation for pull request security findings."""

from __future__ import annotations

from collections.abc import Iterable

from .security_analyzer import Finding

MARKER = "<!-- autonomous-ci-cd-security-agent -->"


def generate_report(findings: Iterable[Finding]) -> str:
    """Create a concise summary followed by actionable finding details."""
    items = list(findings)
    lines = [MARKER, "# Code Security Analysis", ""]
    if not items:
        lines.append("**Status: PASS** - No significant security vulnerabilities detected.")
        return "\n".join(lines) + "\n"

    lines.extend(["**Status: FAIL** - Security issues detected.", "", "## Findings", "", "| Severity | Type | File | Line |", "| --- | --- | --- | ---: |"])
    for finding in items:
        lines.append(f"| {finding.severity} | {finding.type} | `{finding.file}` | {finding.line or '-'} |")
    lines.append("")
    for finding in items:
        lines.extend([
            f"## {finding.severity} - {finding.type}",
            "",
            f"**File:** `{finding.file}`  ",
            f"**Line:** {finding.line or 'Changed code'}", "",
            "**Issue:**", finding.description, "",
            "**Recommended Fix:**", finding.recommendation, "", "---", "",
        ])
    return "\n".join(lines).rstrip() + "\n"
