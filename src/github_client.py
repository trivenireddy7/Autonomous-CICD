"""Small GitHub REST API client used by the security agent."""

from __future__ import annotations

import logging
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)


class GitHubAPIError(RuntimeError):
    """Raised when GitHub returns an unsuccessful response."""


class GitHubClient:
    """Authenticated client for pull request files, comments, and reviews."""

    def __init__(self, token: str, api_url: str = "https://api.github.com", session: requests.Session | None = None) -> None:
        if not token:
            raise ValueError("A GitHub token is required")
        self.api_url = api_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.session.request(method, f"{self.api_url}{path}", timeout=30, **kwargs)
        if not response.ok:
            raise GitHubAPIError(f"GitHub API {response.status_code}: {response.text[:500]}")
        if response.status_code == 204:
            return None
        return response.json()

    def get_pull_request(self, repository: str, pull_number: int) -> dict[str, Any]:
        return self._request("GET", f"/repos/{repository}/pulls/{pull_number}")

    def get_changed_files(self, repository: str, pull_number: int) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self._request("GET", f"/repos/{repository}/pulls/{pull_number}/files", params={"per_page": 100, "page": page})
            files.extend(batch)
            if len(batch) < 100:
                return files
            page += 1

    def post_issue_comment(self, repository: str, pull_number: int, body: str) -> dict[str, Any]:
        return self._request("POST", f"/repos/{repository}/issues/{pull_number}/comments", json={"body": body})

    def list_issue_comments(self, repository: str, pull_number: int) -> list[dict[str, Any]]:
        return self._request("GET", f"/repos/{repository}/issues/{pull_number}/comments", params={"per_page": 100})

    def update_issue_comment(self, repository: str, comment_id: int, body: str) -> dict[str, Any]:
        return self._request("PATCH", f"/repos/{repository}/issues/comments/{comment_id}", json={"body": body})

    def upsert_security_comment(self, repository: str, pull_number: int, body: str, marker: str = "<!-- autonomous-ci-cd-security-agent -->") -> dict[str, Any]:
        for comment in self.list_issue_comments(repository, pull_number):
            if marker in comment.get("body", ""):
                return self.update_issue_comment(repository, int(comment["id"]), body)
        return self.post_issue_comment(repository, pull_number, body)

    def create_review(self, repository: str, pull_number: int, body: str, comments: list[dict[str, Any]]) -> dict[str, Any]:
        payload: dict[str, Any] = {"body": body, "event": "COMMENT"}
        if comments:
            payload["comments"] = comments
        return self._request("POST", f"/repos/{repository}/pulls/{pull_number}/reviews", json=payload)
