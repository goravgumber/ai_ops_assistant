"""DuckDuckGo web search tool integration for general web queries."""

from __future__ import annotations

from typing import Any

import requests


class WebSearchTool:
    """Provide lightweight web search and direct-answer lookups via DuckDuckGo."""

    BASE_URL = "https://api.duckduckgo.com/"

    def search(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        """Search the web and return normalized results.

        Args:
            query: Search query text.
            limit: Maximum number of results to return.

        Returns:
            A list of dictionaries with title, snippet, and URL.
        """
        try:
            if not query.strip():
                return []

            response = requests.get(
                self.BASE_URL,
                params={
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            results: list[dict[str, str]] = []
            abstract = str(data.get("AbstractText", "")).strip()
            if abstract:
                results.append(
                    {
                        "title": "Direct Answer",
                        "snippet": abstract,
                        "url": str(data.get("AbstractURL", "")).strip(),
                    }
                )

            related_topics = data.get("RelatedTopics", [])
            if isinstance(related_topics, list):
                for topic in related_topics:
                    if len(results) >= limit:
                        break
                    if not isinstance(topic, dict):
                        continue

                    # Some entries are nested groups with a "Topics" list.
                    if isinstance(topic.get("Topics"), list):
                        for nested in topic["Topics"]:
                            if len(results) >= limit:
                                break
                            parsed = self._topic_to_result(nested)
                            if parsed:
                                results.append(parsed)
                        continue

                    parsed = self._topic_to_result(topic)
                    if parsed:
                        results.append(parsed)

            return results[:limit]
        except Exception as exc:
            print(f"⚠️ WebSearchTool.search failed: {exc}")
            return []

    def get_answer(self, query: str) -> dict[str, Any]:
        """Get a compact direct-answer payload for a query.

        Args:
            query: Query text.

        Returns:
            Dictionary containing answer/source/url and related topic titles.
        """
        try:
            if not query.strip():
                return {"answer": "", "source": ""}

            response = requests.get(
                self.BASE_URL,
                params={
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                },
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            related: list[str] = []
            related_topics = data.get("RelatedTopics", [])
            if isinstance(related_topics, list):
                for topic in related_topics:
                    if len(related) >= 3:
                        break
                    if not isinstance(topic, dict):
                        continue
                    if isinstance(topic.get("Topics"), list):
                        for nested in topic["Topics"]:
                            if len(related) >= 3:
                                break
                            title = self._extract_title(nested)
                            if title:
                                related.append(title)
                        continue
                    title = self._extract_title(topic)
                    if title:
                        related.append(title)

            return {
                "answer": str(data.get("AbstractText", "")).strip(),
                "source": str(data.get("AbstractSource", "")).strip(),
                "url": str(data.get("AbstractURL", "")).strip(),
                "related": related[:3],
            }
        except Exception as exc:
            print(f"⚠️ WebSearchTool.get_answer failed: {exc}")
            return {"answer": "", "source": ""}

    @staticmethod
    def _extract_title(topic: Any) -> str:
        """Extract a short topic title from a DuckDuckGo topic entry."""
        if not isinstance(topic, dict):
            return ""
        text = str(topic.get("Text", "")).strip()
        if not text:
            return ""
        return text.split(" - ", 1)[0].strip()

    def _topic_to_result(self, topic: Any) -> dict[str, str] | None:
        """Convert one DuckDuckGo topic item to normalized search result."""
        if not isinstance(topic, dict):
            return None
        text = str(topic.get("Text", "")).strip()
        url = str(topic.get("FirstURL", "")).strip()
        if not text:
            return None
        title = text.split(" - ", 1)[0].strip()
        return {"title": title or "Result", "snippet": text, "url": url}


web_search_tool = WebSearchTool()


if __name__ == "__main__":
    print("🔎 WebSearchTool self-test")
    print(web_search_tool.search("latest python release", limit=3))
    print(web_search_tool.get_answer("What is Python programming language?"))
