"""Planner agent that converts natural language tasks into structured execution plans."""

from __future__ import annotations

import json
import re
from typing import Any

from cache.cache_manager import cache_manager
from llm.client import cost_tracker, llm_client


class PlannerAgent:
    """Create and validate tool-execution plans for user tasks.

    This agent delegates intent understanding to the LLM and enforces a strict
    JSON output contract that downstream agents can execute safely.
    """

    def plan(self, user_task: str) -> dict[str, Any]:
        """Backward-compatible planning entrypoint.

        Args:
            user_task: Raw user request to be converted into actionable steps.

        Returns:
            Structured plan dictionary, including reasoning when available.
        """
        return self.plan_with_reasoning(user_task=user_task, memory_context="")

    def plan_with_reasoning(self, user_task: str, memory_context: str = "") -> dict[str, Any]:
        """Generate a structured plan with explicit reasoning transparency.

        Args:
            user_task: User request to break into tool actions.
            memory_context: Optional session context retrieved from MemoryAgent.

        Returns:
            Parsed and validated plan dictionary, or safe error dictionary.
        """
        print("🧠 Planning task...")

        context_text = memory_context.strip() if memory_context.strip() else "No previous context"
        cache_key = cache_manager.make_key(
            "PlannerAgent",
            "plan_with_reasoning",
            user_task=user_task.strip(),
            memory_context=context_text,
        )
        task_only_cache_key = cache_manager.make_key(
            "PlannerAgent",
            "plan_with_reasoning_task_only",
            user_task=user_task.strip(),
        )

        cached_plan = self._get_cached_plan(cache_key)
        if cached_plan is not None:
            print("💾 Using cached planner result")
            self._print_reasoning(cached_plan)
            print(f"✅ Plan created with {len(cached_plan.get('steps', []))} steps")
            return cached_plan

        cached_task_only_plan = self._get_cached_plan(task_only_cache_key)
        if cached_task_only_plan is not None:
            print("💾 Using cached planner result for repeated task")
            self._print_reasoning(cached_task_only_plan)
            print(f"✅ Plan created with {len(cached_task_only_plan.get('steps', []))} steps")
            return cached_task_only_plan

        system_prompt = f"""
      You are a planning agent for an AI Operations Assistant.
      
      Available tools and their actions:
      - GitHubTool:
          * search_repos(query, sort, limit)
          * get_trending(language, limit)
          * get_repo_info(full_name)
      - WeatherTool:
          * get_current_weather(city)
          * get_forecast(city, days)
      - NewsTool:
          * get_top_headlines(category, country, limit)
          * search_news(query, limit)
      - WebSearchTool:
          * search(query, limit)      - search the web
          * get_answer(query)         - get direct answer

      MEMORY CONTEXT (use if relevant):
      {context_text}

      You MUST respond with ONLY this JSON format:
      {{
        "task_summary": "one sentence summary",
        "reasoning": {{
          "task_interpretation": "what you understood the task to be",
          "tool_selection_reasoning": "why you chose these specific tools",
          "parameter_reasoning": "how you determined the parameters",
          "potential_issues": "any concerns or assumptions made"
        }},
        "steps": [
          {{
            "step": 1,
            "tool": "ToolName",
            "action": "method_name",
            "params": {{}},
            "description": "what this step does",
            "why": "why this step is needed"
          }}
        ],
        "expected_output": "description of final answer"
      }}

      Rules:
      - Use ONLY the tools listed above
      - Keep steps minimal — do not add unnecessary steps
      - If the task cannot be done with available tools, return:
        {{"error": "Task cannot be completed with available tools", "steps": []}}
      - Always infer city names, languages, and parameters from context
      """

        try:
            response = llm_client.chat(system_prompt, user_task, expect_json=True)
            cost_tracker.log("PlannerAgent", f"{memory_context}\n\n{user_task}", response)

            parsed = self._parse_json_response(response)
            if not isinstance(parsed, dict):
                fallback_plan = self._get_cached_plan(cache_key) or self._get_cached_plan(task_only_cache_key)
                if fallback_plan is not None:
                    print("💾 Falling back to cached planner result after invalid response")
                    return fallback_plan
                return {"error": "Planning failed", "steps": []}

            is_valid, reason = self.validate_plan(parsed)
            if not is_valid:
                print(f"⚠️ Generated plan is invalid: {reason}")
                fallback_plan = self._get_cached_plan(cache_key) or self._get_cached_plan(task_only_cache_key)
                if fallback_plan is not None:
                    print("💾 Falling back to cached planner result after validation failure")
                    return fallback_plan
                return {"error": reason, "steps": []}

            cache_manager.set(cache_key, parsed)
            cache_manager.set(task_only_cache_key, parsed)
            self._print_reasoning(parsed)
            step_count = len(parsed.get("steps", []))
            print(f"✅ Plan created with {step_count} steps")
            return parsed
        except Exception as exc:
            print(f"⚠️ Planning failed with exception: {exc}")
            fallback_plan = self._get_cached_plan(cache_key) or self._get_cached_plan(task_only_cache_key)
            if fallback_plan is not None:
                print("💾 Falling back to cached planner result after exception")
                return fallback_plan
            return {"error": "Planning failed", "steps": []}

    def validate_plan(self, plan: dict[str, Any]) -> tuple[bool, str]:
        """Validate the minimum structure and allowed tool usage of a plan.

        Args:
            plan: Candidate plan dictionary.

        Returns:
            Tuple of `(is_valid, reason)` where `reason` explains invalid state.
        """
        allowed_tools = {"GitHubTool", "WeatherTool", "NewsTool", "WebSearchTool"}

        if "steps" not in plan:
            return False, "Plan is missing 'steps' key"

        steps = plan.get("steps")
        if not isinstance(steps, list) or not steps:
            return False, "Plan steps must be a non-empty list"

        required_step_keys = {"step", "tool", "action", "params"}
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                return False, f"Step {index} is not a dictionary"

            missing = required_step_keys.difference(step.keys())
            if missing:
                return False, f"Step {index} missing keys: {sorted(missing)}"

            if step.get("tool") not in allowed_tools:
                return False, f"Step {index} uses invalid tool: {step.get('tool')}"

            if not isinstance(step.get("params"), dict):
                return False, f"Step {index} params must be an object"

        return True, "Valid"

    def _parse_json_response(self, response: str) -> dict[str, Any] | None:
        """Parse a JSON response robustly, including regex extraction fallback."""
        try:
            data = json.loads(response)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", response, re.DOTALL)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None

    def _get_cached_plan(self, cache_key: str) -> dict[str, Any] | None:
        """Return a validated cached plan when available."""
        cached = cache_manager.get(cache_key)
        if not isinstance(cached, dict):
            return None

        is_valid, _reason = self.validate_plan(cached)
        if not is_valid:
            return None

        return dict(cached)

    def _print_reasoning(self, plan: dict[str, Any]) -> None:
        """Print planner reasoning block in a readable terminal format."""
        reasoning = plan.get("reasoning", {}) if isinstance(plan, dict) else {}
        if not isinstance(reasoning, dict):
            return

        interpretation = str(reasoning.get("task_interpretation", "")).strip()
        tool_reasoning = str(reasoning.get("tool_selection_reasoning", "")).strip()
        parameter_reasoning = str(reasoning.get("parameter_reasoning", "")).strip()
        potential_issues = str(reasoning.get("potential_issues", "")).strip()

        print("▫️ " + "─" * 58)
        print("🧠 Planner Reasoning:")
        if interpretation:
            print(f"   📌 Interpreted as: {interpretation}")
        if tool_reasoning:
            print(f"   🔧 Tools chosen because: {tool_reasoning}")
        if parameter_reasoning:
            print(f"   📊 Parameters: {parameter_reasoning}")
        if potential_issues:
            print(f"   ⚠️  Assumptions: {potential_issues}")
        print("▫️ " + "─" * 58)


planner_agent = PlannerAgent()


if __name__ == "__main__":
    """Run a simple self-test to generate and validate a sample plan."""
    sample_task = "Find trending Python repositories and summarize top tech headlines in the US."
    generated_plan = planner_agent.plan_with_reasoning(sample_task)
    print("\nGenerated plan:")
    print(json.dumps(generated_plan, indent=2))
    print("\nValidation:")
    print(planner_agent.validate_plan(generated_plan))
