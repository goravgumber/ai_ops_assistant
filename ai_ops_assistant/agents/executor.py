"""Executor agent that runs planning steps against tools with caching and retries."""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from ai_ops_assistant.cache.cache_manager import cache_manager
from ai_ops_assistant.llm.client import cost_tracker, llm_client
from ai_ops_assistant.tools.github_tool import github_tool
from ai_ops_assistant.tools.news_tool import news_tool
from ai_ops_assistant.tools.web_search_tool import web_search_tool
from ai_ops_assistant.tools.weather_tool import weather_tool


class ExecutorAgent:
    """Execute plan steps by dispatching tool actions with resilient behavior.

    The agent supports sequential execution as a default and grouped parallel
    execution for steps that share the same step number. It also includes one
    self-healing attempt per failed step.
    """

    TOOL_MAP = {
        "GitHubTool": {
            "search_repos": github_tool.search_repos,
            "get_trending": github_tool.get_trending,
            "get_repo_info": github_tool.get_repo_info,
        },
        "WeatherTool": {
            "get_current_weather": weather_tool.get_current_weather,
            "get_forecast": weather_tool.get_forecast,
        },
        "NewsTool": {
            "get_top_headlines": news_tool.get_top_headlines,
            "search_news": news_tool.search_news,
        },
        "WebSearchTool": {
            "search": web_search_tool.search,
            "get_answer": web_search_tool.get_answer,
        },
    }

    def __init__(self) -> None:
        """Initialize executor runtime state for retry diagnostics."""
        self._last_retry_error: str = ""

    def execute(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execute all steps in sequence and collect structured results.

        Args:
            plan: Planner output containing `task_summary` and `steps`.

        Returns:
            Standardized execution results dictionary with timing and errors.
        """
        start_time = time.time()
        steps = plan.get("steps", []) if isinstance(plan, dict) else []
        total_steps = len(steps)

        output: dict[str, Any] = {
            "task_summary": plan.get("task_summary", "") if isinstance(plan, dict) else "",
            "steps_executed": 0,
            "steps_total": total_steps,
            "results": [],
            "errors": [],
            "cache_hits": 0,
            "self_healed_count": 0,
            "execution_time_seconds": 0.0,
        }

        try:
            for idx, step in enumerate(steps, start=1):
                description = step.get("description", "No description provided")
                print(f"⚙️  Executing step {idx}/{total_steps}: {description}")
                step_result = self._execute_step(step)
                output["results"].append(step_result)

                if step_result.get("from_cache"):
                    output["cache_hits"] += 1
                if step_result.get("self_healed"):
                    output["self_healed_count"] += 1
                if not step_result.get("success", False):
                    output["errors"].append(
                        {
                            "step": step_result.get("step"),
                            "tool": step_result.get("tool"),
                            "action": step_result.get("action"),
                            "error": step_result.get("error"),
                        }
                    )

            output["steps_executed"] = len(output["results"])
            return output
        except Exception as exc:
            output["errors"].append({"error": f"Execution failed: {exc}"})
            return output
        finally:
            output["execution_time_seconds"] = round(time.time() - start_time, 4)

    def _execute_step(self, step: dict[str, Any]) -> dict[str, Any]:
        """Execute a single step using cache-first behavior and self-healing.

        Args:
            step: Individual plan step with tool/action/params metadata.

        Returns:
            Step execution record containing data, status, and cache/healing metadata.
        """
        step_number = step.get("step")
        tool_name = step.get("tool", "")
        action = step.get("action", "")
        params = step.get("params", {}) if isinstance(step.get("params"), dict) else {}

        base_payload = {
            "step": step_number,
            "tool": tool_name,
            "action": action,
            "description": step.get("description", ""),
            "result": None,
            "from_cache": False,
            "success": False,
            "error": None,
            "self_healed": False,
        }

        try:
            cache_key = cache_manager.make_key(tool_name, action, **params)
            cached = cache_manager.get(cache_key)
            if cached is not None:
                print(f"💾 Cache hit for step {step_number}")
                cached_payload = dict(cached)
                cached_payload["from_cache"] = True
                cached_payload.setdefault("self_healed", False)
                return cached_payload

            result = self._call_tool_with_retry(step)
            success = result is not None

            if success:
                payload = {
                    **base_payload,
                    "result": result,
                    "success": True,
                    "error": None,
                    "self_healed": False,
                }
                cache_manager.set(cache_key, payload)
                return payload

            # Retry attempts failed: attempt ONE self-healing path.
            last_error = self._last_retry_error or "Tool call failed after retries"
            healed_step = self._self_heal_step(step, last_error)
            if healed_step is not None:
                healed_result = self._call_tool_with_retry(healed_step, max_retries=1)
                if healed_result is not None:
                    payload = {
                        **base_payload,
                        "tool": healed_step.get("tool", tool_name),
                        "action": healed_step.get("action", action),
                        "description": healed_step.get("description", step.get("description", "")),
                        "result": healed_result,
                        "success": True,
                        "error": None,
                        "self_healed": True,
                        "original_step": step,
                    }
                    cache_manager.set(cache_key, payload)
                    return payload

            payload = {
                **base_payload,
                "success": False,
                "error": last_error,
                "self_healed": False,
            }
            cache_manager.set(cache_key, payload)
            return payload
        except Exception as exc:
            return {
                **base_payload,
                "success": False,
                "error": str(exc),
                "self_healed": False,
            }

    def _call_tool_with_retry(self, step: dict[str, Any], max_retries: int = 3) -> Any:
        """Invoke a mapped tool function with exponential-backoff retries.

        Args:
            step: Step descriptor containing tool/action/params.
            max_retries: Maximum number of attempts before giving up.

        Returns:
            Tool response object on success, otherwise `None`.

        Raises:
            ValueError: If the tool or action is not mapped.
        """
        tool_name = step.get("tool")
        action = step.get("action")
        params = step.get("params", {}) if isinstance(step.get("params"), dict) else {}

        tool_actions = self.TOOL_MAP.get(tool_name)
        if tool_actions is None:
            raise ValueError(f"Unknown tool '{tool_name}' in execution step")

        func = tool_actions.get(action)
        if func is None:
            raise ValueError(f"Unknown action '{action}' for tool '{tool_name}'")

        last_error: Exception | None = None
        self._last_retry_error = ""
        for attempt in range(1, max_retries + 1):
            try:
                return func(**params)
            except Exception as exc:
                last_error = exc
                self._last_retry_error = str(exc)
                if attempt < max_retries:
                    print(f"🔄 Retrying step {step.get('step')} (attempt {attempt + 1}/{max_retries})...")
                    wait_seconds = 2**attempt
                    time.sleep(wait_seconds)
                else:
                    print(f"⚠️ Step {step.get('step')} failed after {max_retries} attempts: {exc}")

        if last_error:
            print(f"⚠️ Final retry error for step {step.get('step')}: {last_error}")
        return None

    def _self_heal_step(self, failed_step: dict[str, Any], error: str) -> dict[str, Any] | None:
        """Suggest and return one alternative step when execution fails.

        Args:
            failed_step: Original step that failed.
            error: Last observed error message.

        Returns:
            Alternative step dict when healing is possible, else `None`.
        """
        system_prompt = """
      You are a self-healing executor agent.
      A tool call has failed. Suggest an alternative approach
      using the available tools.
      
      Available tools:
      - GitHubTool: search_repos, get_trending, get_repo_info
      - WeatherTool: get_current_weather, get_forecast
      - NewsTool: get_top_headlines, search_news
      
      Return ONLY this JSON:
      {
        "can_heal": true/false,
        "alternative_step": {
          "tool": "ToolName",
          "action": "method_name", 
          "params": {},
          "description": "what this alternative does"
        },
        "healing_reason": "why this alternative might work"
      }
      
      If no alternative exists, return:
      {"can_heal": false, "alternative_step": null, 
       "healing_reason": "No alternative available"}
      """

        payload = {
            "failed_step": failed_step,
            "error": error,
            "original_tool": failed_step.get("tool"),
            "original_action": failed_step.get("action"),
        }

        try:
            response = llm_client.chat(
                system_prompt=system_prompt,
                user_message=json.dumps(payload, ensure_ascii=False, default=str),
                expect_json=True,
            )
            cost_tracker.log("ExecutorAgent", json.dumps(payload, ensure_ascii=False), response)
            parsed = self._parse_json_dict(response)
            if not parsed:
                print(f"❌ Cannot heal step {failed_step.get('step')}: Invalid healing response")
                return None

            can_heal = bool(parsed.get("can_heal", False))
            healing_reason = str(parsed.get("healing_reason", "No alternative available"))
            if not can_heal:
                print(f"❌ Cannot heal step {failed_step.get('step')}: {healing_reason}")
                return None

            alternative = parsed.get("alternative_step")
            if not isinstance(alternative, dict):
                print(f"❌ Cannot heal step {failed_step.get('step')}: {healing_reason}")
                return None

            tool = alternative.get("tool")
            action = alternative.get("action")
            params = alternative.get("params", {})
            if not isinstance(params, dict):
                params = {}

            if tool not in self.TOOL_MAP or action not in self.TOOL_MAP.get(tool, {}):
                print(f"❌ Cannot heal step {failed_step.get('step')}: Suggested step is unsupported")
                return None

            print(f"🔧 Self-healing: {healing_reason}")
            print(f"   Trying alternative: {tool}.{action}")
            return {
                "step": failed_step.get("step"),
                "tool": tool,
                "action": action,
                "params": params,
                "description": alternative.get("description", "Self-healed alternative step"),
            }
        except Exception as exc:
            print(f"❌ Cannot heal step {failed_step.get('step')}: {exc}")
            return None

    def execute_parallel(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Execute plan steps in grouped parallel batches when possible.

        Steps sharing the same `step` number are run concurrently. Groups are
        processed in ascending step order.

        Args:
            plan: Planner output containing execution steps.

        Returns:
            Standardized execution results dictionary.
        """
        steps = plan.get("steps", []) if isinstance(plan, dict) else []
        if len(steps) <= 1:
            return self.execute(plan)

        start_time = time.time()
        total_steps = len(steps)
        output: dict[str, Any] = {
            "task_summary": plan.get("task_summary", "") if isinstance(plan, dict) else "",
            "steps_executed": 0,
            "steps_total": total_steps,
            "results": [],
            "errors": [],
            "cache_hits": 0,
            "self_healed_count": 0,
            "execution_time_seconds": 0.0,
        }

        try:
            grouped: dict[int, list[dict[str, Any]]] = {}
            for s in steps:
                step_number = int(s.get("step", 0))
                grouped.setdefault(step_number, []).append(s)

            ordered_numbers = sorted(grouped.keys())
            with ThreadPoolExecutor(max_workers=3) as pool:
                for step_number in ordered_numbers:
                    futures = []
                    current_group = grouped[step_number]
                    for step in current_group:
                        print(
                            f"⚙️  Executing step {step.get('step')}/{total_steps}: "
                            f"{step.get('description', 'No description provided')}"
                        )
                        futures.append(pool.submit(self._execute_step, step))

                    for future in as_completed(futures):
                        step_result = future.result()
                        output["results"].append(step_result)
                        if step_result.get("from_cache"):
                            output["cache_hits"] += 1
                        if step_result.get("self_healed"):
                            output["self_healed_count"] += 1
                        if not step_result.get("success", False):
                            output["errors"].append(
                                {
                                    "step": step_result.get("step"),
                                    "tool": step_result.get("tool"),
                                    "action": step_result.get("action"),
                                    "error": step_result.get("error"),
                                }
                            )

            output["results"].sort(key=lambda item: (item.get("step") is None, item.get("step")))
            output["steps_executed"] = len(output["results"])
            return output
        except Exception as exc:
            output["errors"].append({"error": f"Parallel execution failed: {exc}"})
            return output
        finally:
            output["execution_time_seconds"] = round(time.time() - start_time, 4)

    @staticmethod
    def _parse_json_dict(text: str) -> dict[str, Any] | None:
        """Parse model JSON dict with regex fallback extraction."""
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None


executor_agent = ExecutorAgent()


if __name__ == "__main__":
    """Run a simple self-test with a sample two-step plan."""
    sample_plan = {
        "task_summary": "Fetch top technology headlines and Python trending repos",
        "steps": [
            {
                "step": 1,
                "tool": "NewsTool",
                "action": "get_top_headlines",
                "params": {"category": "technology", "country": "us", "limit": 2},
                "description": "Get top US technology headlines",
            },
            {
                "step": 2,
                "tool": "GitHubTool",
                "action": "get_trending",
                "params": {"language": "python", "limit": 2},
                "description": "Get trending Python repositories",
            },
        ],
    }

    print("Sequential execution self-test:")
    sequential = executor_agent.execute(sample_plan)
    print(sequential)
    print("\nParallel execution self-test:")
    parallel = executor_agent.execute_parallel(sample_plan)
    print(parallel)
    print("\nCost tracker summary (for visibility):")
    print(cost_tracker.get_summary())
