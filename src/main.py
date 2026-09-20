"""Command-line entry point for the GitHub Actions security agent."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from .diff_parser import extract_changed_lines
from .github_client import GitHubClient, GitHubAPIError
from .report_generator import generate_report
from .security_analyzer import SecurityAnalyzer, SecurityAnalyzerError, Finding

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze changed pull request code for security vulnerabilities.")
    parser.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY"), help="GitHub owner/repository")
    parser.add_argument("--pull-number", type=int, default=int(os.getenv("GITHUB_PR_NUMBER", "0")), help="Pull request number")
    return parser.parse_args()


def review_comments(findings: list[Finding]) -> list[dict[str, object]]:
    """Convert findings into GitHub review comments for changed lines."""
    return [
        {"path": finding.file, "line": finding.line, "side": "RIGHT", "body": f"**{finding.severity}: {finding.type}**\n\n{finding.description}\n\n**Recommended fix:** {finding.recommendation}"}
        for finding in findings if finding.line is not None
    ]


def run(repository: str, pull_number: int) -> int:
    token = os.getenv("GITHUB_TOKEN")
    api_key = os.getenv("LLM_API_KEY")
    api_url = os.getenv("LLM_API_URL")
    if not repository or not pull_number or not token or not api_key or not api_url:
        LOGGER.error("GITHUB_REPOSITORY, GITHUB_PR_NUMBER, GITHUB_TOKEN, LLM_API_KEY, and LLM_API_URL are required")
        return 2

    github = GitHubClient(token)
    try:
        files = github.get_changed_files(repository, pull_number)
        changes = extract_changed_lines(files)
        findings = SecurityAnalyzer(api_key, api_url, os.getenv("LLM_MODEL", "gpt-4o-mini")).analyze(changes)
        report = generate_report(findings)
        github.upsert_security_comment(repository, pull_number, report)
        print(report)
        comments = review_comments(findings)
        if comments:
            try:
                github.create_review(repository, pull_number, "Security findings tied to changed lines.", comments)
            except GitHubAPIError as exc:
                LOGGER.warning("Could not create line-specific review comments: %s", exc)
        return 1 if any(item.severity in {"CRITICAL", "HIGH"} for item in findings) else 0
    except (GitHubAPIError, SecurityAnalyzerError) as exc:
        LOGGER.error("Security analysis failed: %s", exc)
        return 2


def main() -> int:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(levelname)s %(message)s")
    args = parse_args()
    return run(args.repository, args.pull_number)


if __name__ == "__main__":
    sys.exit(main())
