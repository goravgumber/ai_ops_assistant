"""Main terminal entry point for the AI Operations Assistant application."""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import json
import os
import signal
import sys
import threading
import time
from datetime import datetime
from typing import Any

from ai_ops_assistant.agents.executor import executor_agent
from ai_ops_assistant.agents.memory_agent import memory_agent
from ai_ops_assistant.agents.planner import planner_agent
from ai_ops_assistant.agents.task_chain import task_chain_processor
from ai_ops_assistant.agents.verifier import verifier_agent
from ai_ops_assistant.cache.cache_manager import cache_manager
from ai_ops_assistant.llm.client import cost_tracker
from ai_ops_assistant.ui.terminal_ui import terminal_ui
from ai_ops_assistant.voice.speech_handler import speech_handler


class AIOperationsAssistant:
    """Coordinate UI, agents, voice, cache, memory, and cost tracking in one CLI app."""

    def __init__(self) -> None:
        """Initialize session state, signal hooks, and startup diagnostics."""
        self.session_task_count = 0
        self.last_result: dict[str, Any] | None = None
        self.last_plan: dict[str, Any] | None = None
        self.running = True
        self.voice_mode_active = False

        signal.signal(signal.SIGINT, self._handle_exit)

        # Silent diagnostics for maintainers/debugging.
        self._diagnostics = {
            "startup_time": datetime.now().isoformat(),
            "python": sys.version.split()[0],
            "cwd": os.getcwd(),
        }

    def run_task(self, task: str) -> dict[str, Any] | None:
        """Run the full Plan → Execute → Verify pipeline for one task.

        Args:
            task: User task text.

        Returns:
            Verified result dictionary, or `None` when the task fails/aborts.
        """
        cleaned_task = (task or "").strip()
        if not cleaned_task:
            terminal_ui.show_warning("Task cannot be empty.")
            return None

        # Check for task chaining.
        if task_chain_processor.is_chained_task(cleaned_task):
            terminal_ui.show_success("🔗 Chain detected — splitting into sub-tasks")
            sub_tasks = task_chain_processor.split_chain(cleaned_task)
            if speech_handler.available:
                speech_handler.narrate_pipeline_start(cleaned_task)
            for index, sub_task in enumerate(sub_tasks, start=1):
                if speech_handler.available:
                    speech_handler.narrate_chain_step(index, len(sub_tasks), sub_task)
            chain_result = task_chain_processor.execute_chain(
                cleaned_task,
                ui_callback=lambda _r: None,
            )
            task_chain_processor.display_chain_summary(chain_result)
            terminal_ui.show_chain_timeline(chain_result)
            if speech_handler.available:
                speech_handler.narrate_chain_complete(
                    int(chain_result.get("completed_steps", 0)),
                    int(chain_result.get("total_chain_steps", len(sub_tasks))),
                )
                speech_handler.narrate_final_result(chain_result)
            self.last_result = chain_result
            self.session_task_count += 1
            return chain_result

        # Check memory for context (non-chained tasks).
        original_task = cleaned_task
        cleaned_task = memory_agent.resolve_references(cleaned_task)
        terminal_ui.show_reference_resolution(original_task, cleaned_task)
        memory_context = memory_agent.get_context_for_task(cleaned_task)
        terminal_ui.show_memory_context(memory_context)

        terminal_ui.print_separator("NEW TASK")

        pipeline_timing: dict[str, dict[str, Any]] = {
            "planner": {"start": time.time()},
            "executor": {},
            "verifier": {},
        }
        if speech_handler.available:
            speech_handler.narrate_pipeline_start(cleaned_task)
            speech_handler.narrate_planning_start()

        # STEP 1 — PLANNING
        terminal_ui.show_planning()
        plan = planner_agent.plan_with_reasoning(cleaned_task, memory_context)

        if not isinstance(plan, dict) or plan.get("error") or not plan.get("steps"):
            message = "Unknown planner error"
            if isinstance(plan, dict):
                message = str(plan.get("error", message))
            pipeline_timing["planner"]["status"] = "error"
            terminal_ui.show_error(f"Planning failed: {message}")
            return None

        is_valid, reason = planner_agent.validate_plan(plan)
        if not is_valid:
            pipeline_timing["planner"]["status"] = "error"
            terminal_ui.show_error(f"Invalid plan: {reason}")
            return None

        pipeline_timing["planner"]["duration_seconds"] = (
            time.time() - float(pipeline_timing["planner"].get("start", time.time()))
        )
        pipeline_timing["planner"]["step_count"] = len(plan.get("steps", []))
        pipeline_timing["planner"]["status"] = "success"
        if speech_handler.available:
            speech_handler.narrate_plan_ready(len(plan.get("steps", [])))

        terminal_ui.show_plan(plan)
        self.last_plan = plan

        if not terminal_ui.confirm(f"Execute this plan? ({len(plan.get('steps', []))} steps)"):
            terminal_ui.show_warning("Execution cancelled by user.")
            return None

        # STEP 2 — EXECUTION
        terminal_ui.show_success("Starting execution...")
        pipeline_timing["executor"]["start"] = time.time()
        execution_results = executor_agent.execute(plan)

        results = execution_results.get("results", []) if isinstance(execution_results, dict) else []
        total = execution_results.get("steps_total", len(results)) if isinstance(execution_results, dict) else len(results)
        for idx, step_result in enumerate(results, start=1):
            step_num = int(step_result.get("step", idx))
            if speech_handler.available:
                speech_handler.narrate_step_start(
                    step_num,
                    int(total),
                    str(step_result.get("tool", "Tool")),
                    str(step_result.get("action", "action")),
                )
                speech_handler.narrate_step_complete(
                    step_num,
                    bool(step_result.get("success", False)),
                    bool(step_result.get("from_cache", False)),
                )
                if step_result.get("self_healed"):
                    speech_handler.narrate_self_healing(step_num)

            terminal_ui.show_execution_progress(step_result, idx, int(total))

            if step_result.get("self_healed"):
                terminal_ui.show_self_heal_notification(
                    step_num,
                    str(step_result.get("original_step", {}).get("action", "?")),
                    str(step_result.get("action", "?")),
                )

        errors = execution_results.get("errors", []) if isinstance(execution_results, dict) else []
        if errors:
            terminal_ui.show_warning(f"{len(errors)} step(s) had errors but continuing...")

        pipeline_timing["executor"]["duration_seconds"] = (
            time.time() - float(pipeline_timing["executor"].get("start", time.time()))
        )
        pipeline_timing["executor"]["steps_executed"] = execution_results.get("steps_executed", 0)
        pipeline_timing["executor"]["steps_total"] = execution_results.get("steps_total", 0)
        pipeline_timing["executor"]["cache_hits"] = execution_results.get("cache_hits", 0)
        pipeline_timing["executor"]["self_healed"] = execution_results.get("self_healed_count", 0)
        pipeline_timing["executor"]["status"] = "error" if errors else "success"

        # STEP 3 — VERIFICATION
        pipeline_timing["verifier"]["start"] = time.time()
        if speech_handler.available:
            speech_handler.narrate_verification_start()

        terminal_ui.show_verification()
        final_result = verifier_agent.verify(plan, execution_results)
        terminal_ui.show_final_result(final_result)

        pipeline_timing["verifier"]["duration_seconds"] = (
            time.time() - float(pipeline_timing["verifier"].get("start", time.time()))
        )
        pipeline_timing["verifier"]["confidence_score"] = final_result.get("confidence_score", 0)
        pipeline_timing["verifier"]["confidence_grade"] = final_result.get("confidence_grade", "N/A")
        pipeline_timing["verifier"]["status"] = "success" if final_result.get("verified", False) else "error"

        terminal_ui.show_agent_timeline(pipeline_timing)
        if "confidence_score" in final_result:
            terminal_ui.show_confidence_bar(
                int(final_result.get("confidence_score", 0) or 0),
                str(final_result.get("confidence_grade", "?")),
                str(final_result.get("confidence_reason", "")),
            )

        if speech_handler.available:
            speech_handler.narrate_confidence(
                int(final_result.get("confidence_score", 0) or 0),
                str(final_result.get("confidence_grade", "N/A")),
            )
            speech_handler.narrate_final_result(final_result)

        # Store memory for future context.
        memory_agent.store_task(cleaned_task, plan, final_result)

        # POST PROCESSING
        self.session_task_count += 1
        self.last_result = final_result

        if speech_handler.available and self.voice_mode_active:
            speech_handler.speak_result_summary(final_result)

        terminal_ui.show_success(
            f"Task complete in {execution_results.get('execution_time_seconds', 0.0):.1f}s"
            f" | Cache hits: {execution_results.get('cache_hits', 0)}"
            f" | Steps: {execution_results.get('steps_executed', 0)}"
            f"/{execution_results.get('steps_total', 0)}"
        )

        return final_result

    def handle_text_task(self) -> None:
        """Handle a text-based task from input through execution."""
        task = terminal_ui.get_task_input()
        if task.strip().lower() == "back":
            return
        self.run_task(task)
        input("Press Enter to return to menu...")

    def handle_voice_task(self) -> None:
        """Handle one-shot voice task capture and optional fallback to text."""
        if not speech_handler.available:
            terminal_ui.show_warning("Voice not available. Falling back to text input.")
            self.handle_text_task()
            return

        terminal_ui.show_success("🎤 Voice mode activated")
        terminal_ui.show_loading("Listening for your command...", 0)
        speech_handler.speak("Please tell me what you would like to know")

        command = speech_handler.listen_for_command()
        if command is None:
            terminal_ui.show_warning("No voice input received")
            if terminal_ui.confirm("Would you like to type instead?"):
                self.handle_text_task()
            return

        terminal_ui.show_success(f"🎤 Heard: '{command}'")
        if terminal_ui.confirm(f"Run task: '{command}'?"):
            self.run_task(command)

        input("Press Enter to return to menu...")

    def handle_cost_report(self) -> None:
        """Show current token/cost summary and optionally reset tracking."""
        summary = cost_tracker.get_summary()
        terminal_ui.show_cost_report(summary)
        if terminal_ui.confirm("Reset cost tracking?"):
            cost_tracker.reset()
            terminal_ui.show_success("Cost tracking reset")
        input("Press Enter to return to menu...")

    def handle_cache_stats(self) -> None:
        """Show cache stats and optionally clear all cache entries."""
        stats = cache_manager.get_stats()
        terminal_ui.show_cache_stats(stats)
        if terminal_ui.confirm("Clear cache?"):
            cache_manager.clear()
            terminal_ui.show_success("Cache cleared")
        input("Press Enter to return to menu...")

    def handle_last_result(self) -> None:
        """Display the last result, session memory, and optional file export."""
        if self.last_result is None:
            terminal_ui.show_warning("No task has been run yet")
            return

        terminal_ui.show_final_result(self.last_result)

        memory_summary = memory_agent.get_session_summary()
        try:
            from rich.panel import Panel

            terminal_ui.console.print(
                Panel(
                    json.dumps(memory_summary, indent=2, ensure_ascii=False),
                    title="🧠 Session Memory",
                    border_style="dim white",
                    style="dim white",
                )
            )
        except Exception:
            print("🧠 Session Memory")
            print(json.dumps(memory_summary, indent=2, ensure_ascii=False))

        if terminal_ui.confirm("Save result to file?"):
            filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            try:
                with open(filename, "w", encoding="utf-8") as file:
                    json.dump(self.last_result, file, indent=2, ensure_ascii=False)
                terminal_ui.show_success(f"Saved to {filename}")
            except Exception as exc:
                terminal_ui.show_error(f"Failed to save result: {exc}")

        input("Press Enter to return to menu...")

    def handle_voice_listen_mode(self) -> None:
        """Run continuous wake-word voice mode until interrupted."""
        if not speech_handler.available:
            terminal_ui.show_warning("Voice not available on this system")
            return

        terminal_ui.show_success(
            "🎤 Continuous voice mode starting...\n"
            "Say 'assistant' to wake me up\n"
            "Press Ctrl+C to stop"
        )

        self.voice_mode_active = True

        def on_command(command: str) -> None:
            """Receive voice command callbacks from the speech handler thread."""
            terminal_ui.show_success(f"🎤 Voice command: {command}")
            self.run_task(command)

        def start_worker() -> None:
            """Start speech handler loop in a daemon execution thread."""
            speech_handler.start_continuous_listening(on_command)

        listener_thread = threading.Thread(target=start_worker, daemon=True)
        listener_thread.start()

        previous_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, signal.default_int_handler)
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            speech_handler.stop_listening()
            self.voice_mode_active = False
            terminal_ui.show_warning("Voice mode stopped")
        finally:
            signal.signal(signal.SIGINT, previous_handler)

    def handle_help(self) -> None:
        """Display help screen plus advanced chain/memory guidance."""
        terminal_ui.show_help()
        print("\n🔗 TASK CHAINING:")
        print("Use → to chain multiple tasks:")
        print("\"Find Python repos → Weather in San Francisco → Tech news\"")
        print("\n🧠 MEMORY:")
        print("I remember previous tasks this session")
        print("Say \"what did I ask before?\" to see memory")
        print("References like \"there\" or \"that repo\" are auto-resolved")
        input("Press Enter to return to menu...")

    def handle_memory_view(self) -> None:
        """Display current session memory records and high-level memory stats."""
        summary = memory_agent.get_session_summary()
        if summary.get("total_tasks", 0) == 0:
            terminal_ui.show_warning("No tasks in memory yet. Run a task first.")
            input("Press Enter to return...")
            return

        terminal_ui.print_separator("🧠 SESSION MEMORY")
        try:
            terminal_ui.console.print(f"[dim]Session start: {summary.get('session_start', 'Unknown')}[/dim]")
        except Exception:
            print(f"🧠 Session start: {summary.get('session_start', 'Unknown')}")

        memories = summary.get("memories", [])
        for mem in memories:
            entities = []
            key_results = mem.get("key_results", {})
            if isinstance(key_results, dict):
                entities = key_results.get("entities", []) or []
            entities_preview = ", ".join(str(v) for v in entities[:5]) if entities else "None"

            content = (
                f"Task: {mem.get('task', '')}\n"
                f"Tools: {', '.join(mem.get('tools_used', []))}\n"
                f"Entities: {entities_preview}"
            )
            try:
                from rich.panel import Panel

                terminal_ui.console.print(
                    Panel(
                        content,
                        title=f"Task #{mem.get('id', '?')} — {mem.get('timestamp', '')}",
                        border_style="dim white",
                        style="dim white",
                    )
                )
            except Exception:
                print(f"🧠 Task #{mem.get('id', '?')} — {mem.get('timestamp', '')}")
                print(content)

        terminal_ui.show_success(
            f"Total tasks remembered: {summary.get('total_tasks', 0)}\n"
            f"Unique tools used: {', '.join(summary.get('tools_used', []))}"
        )
        input("Press Enter to return...")

    def handle_clear_all(self) -> None:
        """Clear session memory and cache after explicit confirmation."""
        if terminal_ui.confirm("This will clear ALL memory and cache. Continue?"):
            memory_agent.clear()
            cache_manager.clear()
            terminal_ui.show_success(
                "✅ Memory and cache cleared\n"
                "   Starting fresh for next task"
            )
        input("Press Enter to return...")

    def run(self) -> None:
        """Run the main interactive menu loop for the terminal app."""
        terminal_ui.show_splash()
        time.sleep(1)

        terminal_ui.show_success("Welcome! System ready. All agents initialized.")

        env_keys = [
            "OPENROUTER_API_KEY",
            "OPENWEATHER_API_KEY",
            "NEWSAPI_KEY",
            "GITHUB_TOKEN",
        ]
        missing_noncritical = []

        for key in env_keys:
            if os.getenv(key):
                print(f"✅ {key}: Connected")
            else:
                print(f"⚠️  {key}: Not configured")
                if key != "OPENROUTER_API_KEY":
                    missing_noncritical.append(key)

        if missing_noncritical:
            print()
            terminal_ui.show_warning("Tip: Configure all API keys in .env for full functionality")

        terminal_ui.show_success("🧠 Memory Agent: Active (session memory)")
        terminal_ui.show_success("🔗 Task Chaining: Use → to chain tasks")
        terminal_ui.show_success("🔧 Self-Healing: Enabled on all steps")
        terminal_ui.show_success("📊 Confidence Scoring: Active")

        while self.running:
            try:
                terminal_ui.session_tasks = self.session_task_count
                terminal_ui.show_main_menu()

                print("[bright_cyan]Enter choice (1-10): [/bright_cyan]")
                choice = input().strip().lower()

                if choice in {"1", "t"}:
                    self.handle_text_task()
                elif choice in {"2", "v"}:
                    self.handle_voice_task()
                elif choice in {"3", "c"}:
                    self.handle_cost_report()
                elif choice in {"4", "s"}:
                    self.handle_cache_stats()
                elif choice in {"5", "r"}:
                    self.handle_last_result()
                elif choice in {"6", "l"}:
                    self.handle_voice_listen_mode()
                elif choice in {"7", "h"}:
                    self.handle_help()
                elif choice in {"8", "q"}:
                    self._handle_exit()
                elif choice in {"9", "m"}:
                    self.handle_memory_view()
                elif choice in {"0", "x"}:
                    self.handle_clear_all()
                elif choice == "clear":
                    terminal_ui.clear_screen()
                elif choice == "":
                    continue
                else:
                    terminal_ui.show_warning(
                        f"Invalid choice: '{choice}'. Type 'h' for help."
                    )
            except SystemExit:
                raise
            except Exception as exc:
                terminal_ui.show_error(f"Unexpected application error: {exc}")

    def _handle_exit(self, *args: Any) -> None:
        """Gracefully close application resources and exit the process."""
        terminal_ui.print_separator()
        summary = cost_tracker.get_summary()
        terminal_ui.show_success(
            f"Session complete!\n"
            f"Tasks run: {self.session_task_count}\n"
            f"Total cost: ${summary.get('total_cost_usd', 0.0)}"
        )

        if speech_handler.available:
            try:
                speech_handler.stop_listening()
                speech_handler.speak("Goodbye! Session complete.")
            except Exception:
                pass

        mem_summary = memory_agent.get_session_summary()
        if mem_summary.get("total_tasks", 0) > 0:
            entities = mem_summary.get("entities_encountered", [])
            terminal_ui.show_success(
                f"Session memory: {mem_summary.get('total_tasks', 0)} tasks remembered\n"
                f"Entities encountered: {', '.join(list(entities)[:5])}"
            )

        self.running = False
        time.sleep(0.5)
        sys.exit(0)


def _validate_environment_or_exit() -> None:
    """Validate required environment keys and exit when critical keys are absent."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not openrouter_key:
        print(
            "Error: OPENROUTER_API_KEY is required to run AI planning and verification.\n"
            "Create a .env file and add OPENROUTER_API_KEY=<your_key>.\n"
            "Get a key from OpenRouter: https://openrouter.ai/keys"
        )
        sys.exit(1)

    optional_keys = ["OPENWEATHER_API_KEY", "NEWSAPI_KEY", "GITHUB_TOKEN"]
    for key in optional_keys:
        if not os.getenv(key, "").strip():
            print(f"Warning: {key} is not configured. Related features may have reduced functionality.")


if __name__ == "__main__":
    _validate_environment_or_exit()
    app = AIOperationsAssistant()
    app.run()
