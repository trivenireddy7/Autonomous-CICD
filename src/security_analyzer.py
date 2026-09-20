"""LLM-backed security analysis with strict, provider-neutral JSON validation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Iterable

import requests

from .diff_parser import ChangedLine

LOGGER = logging.getLogger(__name__)
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


class SecurityAnalyzerError(RuntimeError):
    """Raised when the auditor cannot return a valid analysis."""


@dataclass(frozen=True)
class Finding:
    file: str
    line: int | None
    severity: str
    type: str
    description: str
    recommendation: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "file": self.file, "line": self.line, "severity": self.severity,
            "type": self.type, "description": self.description, "recommendation": self.recommendation,
        }


SYSTEM_PROMPT = """You are a senior application security auditor. Analyze only the supplied added or modified code.
Report issues only when the changed code provides reasonable evidence; do not report theoretical or stylistic concerns.
Look for SQL injection, command injection, XSS, hardcoded credentials, authentication bypass,
authorization flaws, IDOR, path traversal, SSRF, unsafe deserialization, weak cryptography,
sensitive information exposure, insecure API usage, input validation problems, dangerous shell execution,
and dependency or security configuration issues.
Return strict JSON and no Markdown in exactly this shape:
{\"findings\":[{\"file\":\"path\",\"line\":25,\"severity\":\"HIGH\",\"type\":\"SQL Injection\",\"description\":\"...\",\"recommendation\":\"...\"}]}
Severity must be exactly one of CRITICAL, HIGH, MEDIUM, LOW. Use null for line only when a finding cannot be tied to a changed line."""


class SecurityAnalyzer:
    """Call an OpenAI-compatible chat completion endpoint and validate its result."""

    def __init__(self, api_key: str, api_url: str, model: str = "gpt-4o-mini", session: requests.Session | None = None, timeout: int = 60) -> None:
        if not api_key or not api_url:
            raise ValueError("LLM API key and URL are required")
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.session = session or requests.Session()
        self.timeout = timeout

    def analyze(self, changes: Iterable[ChangedLine]) -> list[Finding]:
        change_list = list(changes)
        if not change_list:
            return []
        code_payload = "\n".join(f"{item.file}:{item.line} [{item.language}] {item.code}" for item in change_list)
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": code_payload}],
        }
        try:
            response = self.session.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            response_data = response.json()
            content = response_data["choices"][0]["message"]["content"]
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            raise SecurityAnalyzerError(f"LLM API request failed: {exc}") from exc
        return self.validate_response(content)

    @staticmethod
    def validate_response(content: str | dict[str, Any]) -> list[Finding]:
        if isinstance(content, str):
            cleaned = content.strip()
            if cleaned.startswith("```json") and cleaned.endswith("```"):
                cleaned = cleaned[7:-3].strip()
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                raise SecurityAnalyzerError("LLM returned invalid JSON") from exc
        elif isinstance(content, dict):
            data = content
        else:
            raise SecurityAnalyzerError("LLM response must be a JSON object")

        if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
            raise SecurityAnalyzerError("LLM response must contain a findings array")

        findings: list[Finding] = []
        for item in data["findings"]:
            if not isinstance(item, dict):
                raise SecurityAnalyzerError("Each finding must be an object")
            required = ("file", "severity", "type", "description", "recommendation")
            if any(not isinstance(item.get(field), str) or not item[field].strip() for field in required):
                raise SecurityAnalyzerError("Finding has missing or invalid required fields")
            severity = item["severity"].upper()
            if severity not in SEVERITIES:
                raise SecurityAnalyzerError(f"Unsupported severity: {item['severity']}")
            line = item.get("line")
            if line is not None and (isinstance(line, bool) or not isinstance(line, int) or line < 1):
                raise SecurityAnalyzerError("Finding line must be a positive integer or null")
            findings.append(Finding(item["file"], line, severity, item["type"].strip(), item["description"].strip(), item["recommendation"].strip()))
        return findings
