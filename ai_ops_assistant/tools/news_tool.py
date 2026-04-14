"""NewsAPI tool for top headlines and keyword-based news search."""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()


class NewsTool:
    """Utility wrapper around NewsAPI endpoints for headline retrieval."""

    BASE_URL = "https://newsapi.org/v2/"

    def __init__(self) -> None:
        """Initialize NewsAPI credentials and request defaults."""
        self.api_key = os.getenv("NEWSAPI_KEY", "").strip()
        if not self.api_key:
            print("Warning: NEWSAPI_KEY is missing. News API requests will fail.")

    def get_top_headlines(
        self, category: str = "technology", country: str = "us", limit: int = 5
    ) -> list[dict]:
        """Fetch top headlines by category and country.

        Args:
            category: News category filter.
            country: ISO country code.
            limit: Maximum number of articles to return.

        Returns:
            A list of normalized article dictionaries.
        """
        try:
            if not self.api_key:
                raise RuntimeError("NEWSAPI_KEY is not configured.")

            response = requests.get(
                f"{self.BASE_URL}top-headlines",
                params={
                    "apiKey": self.api_key,
                    "category": category,
                    "country": country,
                    "pageSize": max(1, min(limit, 100)),
                },
                timeout=15,
            )
            response.raise_for_status()
            articles = response.json().get("articles", [])
            return [self._normalize_article(article) for article in articles]
        except Exception as exc:
            print(f"Warning: Failed to fetch top headlines: {exc}")
            return []

    def search_news(self, query: str, limit: int = 5) -> list[dict]:
        """Search news articles by keyword query.

        Args:
            query: Search text.
            limit: Maximum number of articles to return.

        Returns:
            A list of normalized article dictionaries.
        """
        try:
            if not self.api_key:
                raise RuntimeError("NEWSAPI_KEY is not configured.")

            response = requests.get(
                f"{self.BASE_URL}everything",
                params={
                    "apiKey": self.api_key,
                    "q": query,
                    "sortBy": "relevancy",
                    "pageSize": max(1, min(limit, 100)),
                },
                timeout=15,
            )
            response.raise_for_status()
            articles = response.json().get("articles", [])
            return [self._normalize_article(article) for article in articles]
        except Exception as exc:
            print(f"Warning: Failed to search news for '{query}': {exc}")
            return []

    @staticmethod
    def _normalize_article(article: dict) -> dict:
        """Normalize NewsAPI article payload fields into a compact response format."""
        source = article.get("source") or {}
        return {
            "title": article.get("title") or "",
            "source": source.get("name") or "",
            "description": article.get("description") or "",
            "url": article.get("url") or "",
            "published_at": article.get("publishedAt") or "",
        }


news_tool = NewsTool()


if __name__ == "__main__":
    """Run a basic local self-test for NewsAPI endpoints."""
    print("Top headlines sample:")
    print(news_tool.get_top_headlines(category="technology", country="us", limit=2))
    print("\nSearch news sample:")
    print(news_tool.search_news(query="AI operations", limit=2))
