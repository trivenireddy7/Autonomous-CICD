import pytest

from src.github_client import GitHubAPIError, GitHubClient


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self.ok = status_code < 400
        self._payload = payload if payload is not None else []
        self.text = text

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


def test_get_changed_files_uses_github_response():
    session = FakeSession(FakeResponse(payload=[{"filename": "app.py", "patch": "..."}]))
    client = GitHubClient("token", session=session)
    assert client.get_changed_files("owner/repo", 4)[0]["filename"] == "app.py"
    assert session.calls[0][0:2] == ("GET", "https://api.github.com/repos/owner/repo/pulls/4/files")


def test_api_failure_raises_actionable_error():
    client = GitHubClient("token", session=FakeSession(FakeResponse(403, text="forbidden")))
    with pytest.raises(GitHubAPIError, match="403"):
        client.get_pull_request("owner/repo", 4)
