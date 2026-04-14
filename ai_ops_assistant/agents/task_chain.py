"""Task chaining processor for splitting and executing multi-step compound requests."""

from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

from agents.executor import executor_agent
from agents.memory_agent import memory_agent
from agents.planner import planner_agent
from agents.verifier import verifier_agent
from llm.client import cost_tracker, llm_client


class TaskChainProcessor:
    """Split chained tasks and execute each sub-task sequentially with memory context."""

    def is_chained_task(self, task: str) -> bool:
        """Check whether task appears to contain multiple chained instructions."""
        text = (task or "").strip().lower()
        if not text:
            return False

        if "→" in text or "->" in text:
            return True

        if len(text) > 20:
            keywords = ["then", "after that", "followed by", "and then"]
            return any(keyword in text for keyword in keywords)

        return False

    def split_chain(self, task: str) -> list[str]:
        """Split a compound task into ordered sub-task strings."""
        clean_task = (task or "").strip()
        if not clean_task:
            return []

        if "→" in clean_task or "->" in clean_task:
            raw_parts = re.split(r"→|->", clean_task)
            return [part.strip() for part in raw_parts if part.strip()]

        if self.is_chained_task(clean_task):
            system_prompt = """
          Split this compound task into individual sequential tasks.
          Return ONLY a JSON array of task strings.
          Example: ["task 1", "task 2", "task 3"]
          Keep each task self-contained and specific.
          """
            try:
                response = llm_client.chat(system_prompt, clean_task, expect_json=True)
                cost_tracker.log("TaskChainProcessor", clean_task, response)
                parsed = json.loads(response)
                if isinstance(parsed, list):
                    tasks = [str(item).strip() for item in parsed if str(item).strip()]
                    if tasks:
                        return tasks
            except Exception:
                pass

        return [clean_task]

    def execute_chain(self, task: str, ui_callback: Callable[[list[dict[str, Any]]], None] | None = None) -> dict[str, Any]:
        """Execute chained tasks sequentially while sharing session memory context.

        Args:
            task: Full user task string.
            ui_callback: Optional progress callback receiving chain_results.

        Returns:
            Chain summary dictionary containing per-step results and aggregate stats.
        """
        sub_tasks = self.split_chain(task)
        if not sub_tasks:
            return {
                "is_chain": True,
                "total_chain_steps": 0,
                "completed_steps": 0,
                "chain_results": [],
                "combined_summary": "No chain tasks to execute",
                "total_execution_time": 0.0,
                "average_confidence": 0.0,
                "verified": False,
            }

        print(f"🔗 Task chain detected: {len(sub_tasks)} linked tasks")
        for i, sub_task in enumerate(sub_tasks, start=1):
            print(f"   {i}. {sub_task}")

        chain_results: list[dict[str, Any]] = []
        chain_start = time.time()

        for i, sub_task in enumerate(sub_tasks):
            print(f"\n{'=' * 50}")
            print(f"🔗 Chain Step {i + 1}/{len(sub_tasks)}: {sub_task}")
            print(f"{'=' * 50}")

            try:
                resolved = memory_agent.resolve_references(sub_task)
                if resolved != sub_task:
                    print(f"🔗 Resolved to: '{resolved}'")

                context = memory_agent.get_context_for_task(resolved)
                plan = planner_agent.plan_with_reasoning(resolved, context)
                if not isinstance(plan, dict) or plan.get("error"):
                    chain_results.append(
                        {
                            "chain_step": i + 1,
                            "task": resolved,
                            "original_task": sub_task,
                            "error": plan.get("error", "Planning failed") if isinstance(plan, dict) else "Planning failed",
                            "confidence": 0,
                        }
                    )
                    if ui_callback:
                        ui_callback(chain_results)
                    continue

                results = executor_agent.execute(plan)
                final = verifier_agent.verify(plan, results)
                memory_agent.store_task(resolved, plan, final)

                chain_results.append(
                    {
                        "chain_step": i + 1,
                        "task": resolved,
                        "original_task": sub_task,
                        "plan": plan,
                        "result": final,
                        "confidence": final.get("confidence_score", 0),
                    }
                )

                if ui_callback:
                    ui_callback(chain_results)

                time.sleep(0.5)
            except Exception as exc:
                chain_results.append(
                    {
                        "chain_step": i + 1,
                        "task": sub_task,
                        "original_task": sub_task,
                        "error": str(exc),
                        "confidence": 0,
                    }
                )
                if ui_callback:
                    ui_callback(chain_results)

        completed_steps = sum(1 for item in chain_results if "result" in item)
        confidence_values = [float(item.get("confidence", 0)) for item in chain_results if isinstance(item.get("confidence"), (int, float))]
        avg_confidence = round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else 0.0

        summary = {
            "is_chain": True,
            "total_chain_steps": len(sub_tasks),
            "completed_steps": completed_steps,
            "chain_results": chain_results,
            "combined_summary": self._summarize_chain(chain_results),
            "total_execution_time": round(time.time() - chain_start, 4),
            "average_confidence": avg_confidence,
            "verified": True,
        }
        return summary

    def _summarize_chain(self, chain_results: list[dict[str, Any]]) -> str:
        """Create one cohesive narrative summary across all chain results."""
        compact = []
        for item in chain_results:
            if "result" in item and isinstance(item.get("result"), dict):
                compact.append(
                    {
                        "step": item.get("chain_step"),
                        "task": item.get("task"),
                        "summary": item["result"].get("summary", ""),
                        "confidence": item.get("confidence", 0),
                    }
                )
            else:
                compact.append(
                    {
                        "step": item.get("chain_step"),
                        "task": item.get("task"),
                        "error": item.get("error", "Unknown error"),
                    }
                )

        system_prompt = """
      Write a single cohesive 3-4 sentence summary that connects
      all these task results into one unified narrative.
      Write it as if presenting findings to a user.
      Return plain text only, no JSON.
      """

        try:
            user_message = json.dumps(compact, ensure_ascii=False, default=str)
            response = llm_client.chat(system_prompt, user_message, expect_json=False)
            cost_tracker.log("TaskChainProcessor", user_message, response)
            return response.strip() or "Chain completed successfully"
        except Exception:
            return "Chain completed successfully"

    def display_chain_summary(self, chain_result: dict[str, Any]) -> None:
        """Print visual chain summary timeline, narrative, and aggregate stats."""
        total = int(chain_result.get("total_chain_steps", 0))
        completed = int(chain_result.get("completed_steps", 0))
        avg_confidence = chain_result.get("average_confidence", 0)
        total_time = float(chain_result.get("total_execution_time", 0.0))

        print("\n🔗 CHAIN EXECUTION COMPLETE")
        print("-" * 50)

        rows = chain_result.get("chain_results", []) if isinstance(chain_result, dict) else []
        for idx, row in enumerate(rows, start=1):
            status = "✅" if row.get("result") else "❌"
            confidence = row.get("confidence", 0)
            task = str(row.get("task", ""))
            preview = task[:40] + ("..." if len(task) > 40 else "")
            print(f"{status} Step {idx}: {preview} [Confidence: {confidence}/100]")
            if idx < len(rows):
                print("    ↓")

        combined_summary = str(chain_result.get("combined_summary", "Chain completed successfully"))
        print("\n" + "=" * 50)
        print("📦 Combined Summary")
        print("=" * 50)
        print(combined_summary)
        print("=" * 50)

        print(f"⏱️  Total time: {total_time:.1f}s")
        print(f"📊 Avg confidence: {avg_confidence}/100")
        print(f"✅ {completed}/{total} steps successful")


task_chain_processor = TaskChainProcessor()
