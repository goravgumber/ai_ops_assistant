"""Session memory agent for contextual recall, reference resolution, and summaries."""

from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime
from queue import Queue
from typing import Any

from llm.client import cost_tracker, llm_client


class MemoryAgent:
    """Manage short-term task memory and contextual retrieval for planning."""

    def __init__(self) -> None:
        """Initialize in-memory session store and metadata."""
        self.memory_store: list[dict[str, Any]] = []
        self.max_memories = 10
        self.session_start = datetime.now().isoformat()
        print("🧠 Memory Agent initialized")

    def store_task(self, task: str, plan: dict[str, Any], result: dict[str, Any]) -> None:
        """Store a completed task in memory.

        Args:
            task: Original user task text.
            plan: Planner output for the task.
            result: Final verified result for the task.
        """
        try:
            tools_used = [s.get("tool", "") for s in plan.get("steps", []) if isinstance(s, dict)]
            memory_id = len(self.memory_store) + 1
            entry = {
                "id": memory_id,
                "timestamp": datetime.now().isoformat(),
                "task": task,
                "task_summary": plan.get("task_summary", ""),
                "tools_used": tools_used,
                "key_results": self._extract_key_results(result),
                "data_sources": result.get("data_sources", []) if isinstance(result, dict) else [],
            }
            self.memory_store.append(entry)
            if len(self.memory_store) > self.max_memories:
                self.memory_store.pop(0)
                # Reindex to keep ids stable and sequential.
                for idx, mem in enumerate(self.memory_store, start=1):
                    mem["id"] = idx

            print(f"💾 Memory stored: Task #{entry['id']}")
        except Exception as exc:
            print(f"⚠️ Memory store skipped: {exc}")

    def _extract_key_results(self, result: dict[str, Any]) -> dict[str, Any]:
        """Extract concise key facts from a full result payload.

        Args:
            result: Final verified result dictionary.

        Returns:
            Key-fact dictionary suitable for compact session memory.
        """
        default_payload = {"entities": [], "facts": [], "numbers": {}}
        system_prompt = """
      You are a memory extraction agent.
      Extract only the KEY FACTS from this result that would be
      useful context for future tasks. Be very concise.
      
      Return ONLY this JSON format:
      {
        "entities": ["list of important names, cities, repos mentioned"],
        "facts": ["list of 3-5 key facts in one sentence each"],
        "numbers": {"key": "value pairs of important numbers"}
      }
      """

        response = self._chat_with_timeout(
            system_prompt=system_prompt,
            user_message=json.dumps(result, ensure_ascii=False, default=str),
            expect_json=True,
            timeout_seconds=3,
        )
        if response is None:
            return default_payload

        try:
            cost_tracker.log("MemoryAgent", str(result), response)
            parsed = self._parse_json_dict(response)
            if not parsed:
                return default_payload

            entities = parsed.get("entities", [])
            facts = parsed.get("facts", [])
            numbers = parsed.get("numbers", {})

            return {
                "entities": entities if isinstance(entities, list) else [],
                "facts": facts if isinstance(facts, list) else [],
                "numbers": numbers if isinstance(numbers, dict) else {},
            }
        except Exception:
            return default_payload

    def get_context_for_task(self, new_task: str) -> str:
        """Retrieve relevant memory context for a new task.

        Args:
            new_task: Incoming task text.

        Returns:
            Formatted context string for planner consumption, or empty string.
        """
        if not self.memory_store:
            return ""

        system_prompt = """
      You are a memory retrieval agent.
      Given a new user task and a list of past session memories,
      identify which past memories are RELEVANT to the new task.
      
      Return ONLY this JSON format:
      {
        "relevant_memory_ids": [list of relevant memory id numbers],
        "context_summary": "2-3 sentence summary of relevant past context",
        "referenced_entities": ["entities from past tasks relevant now"]
      }
      
      If no memories are relevant, return:
      {"relevant_memory_ids": [], "context_summary": "", 
       "referenced_entities": []}
      """

        payload = {"new_task": new_task, "memories": self.memory_store}
        response = self._chat_with_timeout(
            system_prompt=system_prompt,
            user_message=json.dumps(payload, ensure_ascii=False, default=str),
            expect_json=True,
            timeout_seconds=3,
        )
        if response is None:
            return ""

        try:
            cost_tracker.log("MemoryAgent", json.dumps(payload, ensure_ascii=False), response)
            parsed = self._parse_json_dict(response)
            if not parsed:
                return ""

            context_summary = str(parsed.get("context_summary", "")).strip()
            referenced_entities = parsed.get("referenced_entities", [])
            if not context_summary:
                return ""

            if not isinstance(referenced_entities, list):
                referenced_entities = []

            return (
                "PREVIOUS SESSION CONTEXT:\n"
                f"{context_summary}\n"
                f"Referenced entities: {', '.join(str(e) for e in referenced_entities)}\n"
                "Use this context if relevant to the current task.\n"
            )
        except Exception:
            return ""

    def resolve_references(self, task: str) -> str:
        """Resolve ambiguous references in a task using recent session memory.

        Args:
            task: User task possibly containing pronouns/references.

        Returns:
            Resolved task text, or original task when resolution is not possible.
        """
        if not self.memory_store:
            return task

        system_prompt = """
      You are a reference resolution agent.
      Resolve any ambiguous references in the user task using
      the session memory context provided.
      
      Examples of references to resolve:
      - "there", "that city", "that place" → actual city name
      - "that repo", "it", "the same one" → actual repo name
      - "the creator", "its author" → actual person/org name
      
      Return ONLY this JSON:
      {
        "resolved_task": "the task with all references resolved",
        "was_resolved": true/false,
        "resolutions_made": ["list of what was resolved and to what"]
      }
      """

        payload = {"task": task, "recent_memories": self.memory_store[-3:]}
        response = self._chat_with_timeout(
            system_prompt=system_prompt,
            user_message=json.dumps(payload, ensure_ascii=False, default=str),
            expect_json=True,
            timeout_seconds=3,
        )
        if response is None:
            return task

        try:
            cost_tracker.log("MemoryAgent", json.dumps(payload, ensure_ascii=False), response)
            parsed = self._parse_json_dict(response)
            if not parsed:
                return task

            resolved_task = str(parsed.get("resolved_task", task)).strip() or task
            was_resolved = bool(parsed.get("was_resolved", False))
            resolutions = parsed.get("resolutions_made", [])

            if was_resolved and isinstance(resolutions, list):
                for resolution in resolutions:
                    print(f"🔗 Resolved: {resolution}")

            return resolved_task
        except Exception:
            return task

    def get_session_summary(self) -> dict[str, Any]:
        """Return summary statistics and full records for current memory session."""
        all_tools: set[str] = set()
        all_entities: set[str] = set()

        for memory in self.memory_store:
            for tool in memory.get("tools_used", []):
                if tool:
                    all_tools.add(str(tool))
            key_results = memory.get("key_results", {})
            entities = key_results.get("entities", []) if isinstance(key_results, dict) else []
            for entity in entities:
                all_entities.add(str(entity))

        return {
            "session_start": self.session_start,
            "total_tasks": len(self.memory_store),
            "tools_used": sorted(all_tools),
            "entities_encountered": sorted(all_entities),
            "memories": self.memory_store,
        }

    def clear(self) -> None:
        """Clear all in-session memory entries."""
        self.memory_store = []
        print("🧠 Memory cleared")

    def _chat_with_timeout(
        self,
        system_prompt: str,
        user_message: str,
        expect_json: bool,
        timeout_seconds: int = 3,
    ) -> str | None:
        """Call LLM chat in a worker thread and enforce a strict timeout."""
        queue: Queue[tuple[str, str]] = Queue(maxsize=1)

        def _worker() -> None:
            try:
                text = llm_client.chat(system_prompt, user_message, expect_json=expect_json)
                queue.put(("ok", text))
            except Exception as exc:
                queue.put(("error", str(exc)))

        start = time.time()
        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join(timeout_seconds)

        elapsed = time.time() - start
        if thread.is_alive():
            print(f"⚠️ Memory timeout ({elapsed:.2f}s). Skipping memory operation.")
            return None

        if queue.empty():
            return None

        status, payload = queue.get()
        if status != "ok":
            return None

        if elapsed > 3:
            print(f"⚠️ Memory call exceeded budget ({elapsed:.2f}s). Ignoring result.")
            return None

        return payload

    @staticmethod
    def _parse_json_dict(text: str) -> dict[str, Any] | None:
        """Parse model output as dict with a regex fallback extraction path."""
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return None
            try:
                parsed = json.loads(match.group(0))
                return parsed if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                return None


memory_agent = MemoryAgent()
