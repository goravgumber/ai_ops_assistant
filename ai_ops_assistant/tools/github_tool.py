"""GitHub API tool for repository search, trending discovery, and repo details."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()


class GitHubTool:
    """Utility wrapper for common GitHub repository API operations."""

    BASE_URL = "https://api.github.com"

    def __init__(self) -> None:
        """Initialize API headers and authentication state."""
        self.token = os.getenv("GITHUB_TOKEN", "").strip()
        if not self.token:
            print("Warning: GITHUB_TOKEN is missing. GitHub API rate limits will be lower.")

        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-ops-assistant",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    def search_repos(self, query: str, sort: str = "stars", limit: int = 5) -> list[dict]:
        """Search GitHub repositories using a query string.

        Args:
            query: GitHub search query.
            sort: Sort field (for example, stars).
            limit: Maximum number of repositories to return.

        Returns:
            A list of normalized repository dictionaries.
        """
        try:
            params = {
                "q": query,
                "sort": sort,
                "per_page": max(1, min(limit, 100)),
            }
            response = requests.get(
                f"{self.BASE_URL}/search/repositories",
                headers=self.headers,
                params=params,
                timeout=15,
            )
            if response.status_code == 403:
                print("Warning: GitHub API rate limit hit (403). Returning empty results.")
                return []
            response.raise_for_status()

            items = response.json().get("items", [])
            return [self._normalize_repo(item) for item in items]
        except Exception as exc:
            print(f"Warning: Failed to search GitHub repositories: {exc}")
            return []

    def get_trending(self, language: str = "python", limit: int = 5) -> list[dict]:
        """Get trending repositories created in the last 7 days.

        Args:
            language: Repository language filter.
            limit: Maximum number of repositories to return.

        Returns:
            A list of normalized repository dictionaries.
        """
        try:
            seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
            query = f"language:{language} created:>{seven_days_ago}"
            return self.search_repos(query=query, sort="stars", limit=limit)
        except Exception as exc:
            print(f"Warning: Failed to fetch trending repositories: {exc}")
            return []

    def get_repo_info(self, full_name: str) -> dict:
        """Get detailed information for a single repository.

        Args:
            full_name: Full repository name in owner/repo format.

        Returns:
            A normalized repository detail dictionary.
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/repos/{full_name}",
                headers=self.headers,
                timeout=15,
            )
            if response.status_code == 404:
                print(f"Warning: Repository not found: {full_name}")
                return {}
            if response.status_code == 403:
                print("Warning: GitHub API rate limit hit (403).")
                return {}
            response.raise_for_status()
            data = response.json()

            return {
                "name": data.get("name"),
                "stars": data.get("stargazers_count", 0),
                "forks": data.get("forks_count", 0),
                "open_issues": data.get("open_issues_count", 0),
                "description": data.get("description") or "",
                "language": data.get("language") or "",
                "last_updated": data.get("updated_at") or "",
                "url": data.get("html_url") or "",
            }
        except Exception as exc:
            print(f"Warning: Failed to fetch repository info for '{full_name}': {exc}")
            return {}

    def _normalize_repo(self, item: dict) -> dict:
        """Normalize GitHub repository payload fields into a compact dict."""
        return {
            "name": item.get("name"),
            "full_name": item.get("full_name"),
            "stars": item.get("stargazers_count", 0),
            "forks": item.get("forks_count", 0),
            "description": item.get("description") or "",
            "url": item.get("html_url") or "",
            "language": item.get("language") or "",
        }


github_tool = GitHubTool()


if __name__ == "__main__":
    """Run a basic local self-test for GitHub tool connectivity and parsing."""
    print("GitHub search sample:")
    print(github_tool.search_repos(query="python automation", limit=2))
    print("\nGitHub trending sample:")
    print(github_tool.get_trending(language="python", limit=2))
    print("\nGitHub repo info sample:")
    print(github_tool.get_repo_info(full_name="psf/requests"))
