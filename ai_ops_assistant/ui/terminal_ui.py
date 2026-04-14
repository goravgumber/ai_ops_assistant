"""Rich-powered terminal interface for the AI Operations Assistant."""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

try:
    from rich.align import Align
    from rich.columns import Columns
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        BarColumn,
        Progress,
        SpinnerColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    from rich.prompt import Prompt
    from rich.rule import Rule
    from rich.spinner import Spinner
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.text import Text

    RICH_AVAILABLE = True
except ImportError:  # pragma: no cover - environment-dependent
    RICH_AVAILABLE = False

    class Console:  # type: ignore[override]
        """Minimal fallback console when rich is unavailable."""

        def print(self, *args: Any, **kwargs: Any) -> None:
            print(*args)

        def clear(self) -> None:
            print("\n" * 2)

    class Prompt:  # type: ignore[override]
        """Minimal fallback prompt implementation."""

        @staticmethod
        def ask(prompt: str, choices: list[str] | None = None, default: str | None = None) -> str:
            response = input(f"{prompt} ").strip()
            if not response and default is not None:
                return default
            if choices:
                lowered = response.lower()
                if lowered not in [choice.lower() for choice in choices]:
                    return default or ""
            return response


class TerminalUI:
    """Present interactive CLI views for planning, execution, and verification.

    The UI uses `rich` for visual structure while protecting each render path with
    plain-text fallbacks so display issues never crash the application.
    """

    def __init__(self) -> None:
        """Initialize console, theme colors, and session counters."""
        self.console = Console()

        self.PRIMARY = "bright_cyan"
        self.SUCCESS = "bright_green"
        self.WARNING = "bright_yellow"
        self.ERROR = "bright_red"
        self.ACCENT = "bright_magenta"
        self.DIM = "dim white"

        self.session_tasks = 0
        self.last_result: dict[str, Any] | None = None

    def show_splash(self) -> None:
        """Render animated startup banner, feature pills, and tagline."""
        banner_lines = [
            "╔═══════════════════════════════════════════════════════╗",
            "║     █████╗ ██╗ ██████╗ ██████╗ ███████╗              ║",
            "║    ██╔══██╗██║██╔═══██╗██╔══██╗██╔════╝              ║",
            "║    ███████║██║██║   ██║██████╔╝███████╗              ║",
            "║    ██╔══██║██║██║   ██║██╔═══╝ ╚════██║              ║",
            "║    ██║  ██║██║╚██████╔╝██║     ███████║              ║",
            "║    ╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝     ╚══════╝              ║",
            "║         AI Operations Assistant v1.0                  ║",
            "║      Powered by Claude + GitHub + Weather + News      ║",
            "╚═══════════════════════════════════════════════════════╝",
        ]

        try:
            self.console.clear()
            accumulated: list[str] = []
            with Live(console=self.console, refresh_per_second=20) as live:
                for line in banner_lines:
                    accumulated.append(line)
                    panel = Panel(
                        Align.center(Text("\n".join(accumulated), style=self.PRIMARY)),
                        border_style=self.PRIMARY,
                    )
                    live.update(panel)
                    time.sleep(0.05)

            pills = Columns(
                [
                    Text("🧠 3-Agent AI", style=self.PRIMARY),
                    Text("🎤 Voice Ready", style=self.SUCCESS),
                    Text("⚡ FastAPI", style=self.ACCENT),
                    Text("💾 Smart Cache", style=self.WARNING),
                ],
                equal=True,
                expand=True,
            )
            self.console.print(pills)
            self.console.print()
            self.console.print(
                Text("Plan → Execute → Verify | Type 'help' for commands", style=self.DIM),
                justify="center",
            )
        except Exception:
            print("AI Operations Assistant v1.0")
            print("Powered by Claude + GitHub + Weather + News")
            print("Plan -> Execute -> Verify | Type 'help' for commands")

    def show_main_menu(self) -> None:
        """Display primary action menu and current session footer."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self.console.print(Rule("MAIN MENU", style=self.PRIMARY))

            table = Table(show_header=True, header_style=self.PRIMARY, box=None)
            table.add_column("#", style="bold")
            table.add_column("Option")
            table.add_column("Shortcut", style=self.DIM)

            table.add_row("1", "Run AI Task (Text)", "Press 1 or 't'")
            table.add_row("2", "Run AI Task (Voice)", "Press 2 or 'v'")
            table.add_row("3", "View Cost Report", "Press 3 or 'c'")
            table.add_row("4", "View Cache Stats", "Press 4 or 's'")
            table.add_row("5", "View Last Result", "Press 5 or 'r'")
            table.add_row("6", "Start Voice Listen Mode", "Press 6 or 'l'")
            table.add_row("7", "Help", "Press 7 or 'h'")
            table.add_row("8", "Exit", "Press 8 or 'q'")
            table.add_row("9", "View Session Memory", "Press 9 or 'm'")
            table.add_row("10", "Clear Memory & Cache", "Press 0 or 'x'")

            self.console.print(Panel(table, border_style=self.PRIMARY, padding=(1, 2)))
            self.console.print(
                Text(f"Current time: {now} | Session tasks: {self.session_tasks}", style=self.DIM)
            )
        except Exception:
            print("MAIN MENU")
            print("1) Run AI Task (Text)  2) Run AI Task (Voice)  3) View Cost Report")
            print("4) View Cache Stats    5) View Last Result    6) Start Voice Listen Mode")
            print("7) Help                8) Exit")
            print("9) View Session Memory 0) Clear Memory & Cache")
            print(f"Current time: {now} | Session tasks: {self.session_tasks}")

    def get_task_input(self) -> str:
        """Prompt for a non-empty task with examples and input validation."""
        while True:
            try:
                self.console.print(Rule("ENTER YOUR TASK", style=self.PRIMARY))
                examples = (
                    "Examples:\n"
                    "• \"Find top 5 Python repos and weather in San Francisco\"\n"
                    "• \"Latest tech news and trending JavaScript repos\"\n"
                    "• \"Weather forecast for Tokyo and top AI news\""
                )
                self.console.print(Panel(examples, style=self.DIM, border_style=self.DIM))
                task = Prompt.ask("[bright_cyan]🤖 What would you like to know?[/bright_cyan]").strip()
            except Exception:
                task = input("What would you like to know? ").strip()

            if task:
                return task

            self.show_warning("Task cannot be empty. Please enter a valid request.")

    def show_planning(self) -> None:
        """Display planner activity using a spinner panel."""
        try:
            spinner = Spinner("dots", text="🧠 [bright_cyan]Planner Agent[/] is analyzing your task...")
            panel = Panel.fit(
                Columns([spinner, Text("Breaking down into executable steps...", style=self.DIM)]),
                border_style=self.PRIMARY,
            )
            with Live(panel, console=self.console, refresh_per_second=12):
                time.sleep(1.2)
        except Exception:
            print("Planner Agent is analyzing your task...")
            print("Breaking down into executable steps...")

    def show_plan(self, plan: dict[str, Any]) -> None:
        """Render structured plan steps and task summary."""
        steps = plan.get("steps", []) if isinstance(plan, dict) else []

        try:
            self.console.print(Rule("EXECUTION PLAN", style=self.PRIMARY))
            table = Table(header_style=self.PRIMARY)
            table.add_column("Step", justify="right")
            table.add_column("Tool")
            table.add_column("Action")
            table.add_column("Parameters")
            table.add_column("Description")

            tool_colors = {
                "GitHubTool": "cyan",
                "WeatherTool": "blue",
                "NewsTool": "magenta",
            }

            for step in steps:
                tool = str(step.get("tool", ""))
                color = tool_colors.get(tool, "white")
                params = json.dumps(step.get("params", {}), ensure_ascii=False)
                table.add_row(
                    str(step.get("step", "-")),
                    f"[{color}]{tool}[/{color}]",
                    str(step.get("action", "")),
                    params,
                    str(step.get("description", "")),
                )

            self.console.print(table)
            summary = str(plan.get("task_summary", "No task summary available"))
            self.console.print(Panel(summary, title="Task Summary", border_style=self.SUCCESS))
            self.console.print(Text(f"📋 {len(steps)} steps planned", style=self.WARNING))
        except Exception:
            print("EXECUTION PLAN")
            for step in steps:
                print(f"Step {step.get('step')}: {step.get('tool')}.{step.get('action')} - {step.get('description')}")
            print(f"Steps planned: {len(steps)}")

    def show_execution_progress(self, step: dict[str, Any], current: int, total: int) -> None:
        """Show progress for a single execution step with success/cache markers."""
        tool = str(step.get("tool", "UnknownTool"))
        action = str(step.get("action", "unknown_action"))
        from_cache = bool(step.get("from_cache", False))
        success = step.get("success", True)

        tool_colors = {
            "GitHubTool": "cyan",
            "WeatherTool": "blue",
            "NewsTool": "magenta",
        }
        tool_color = tool_colors.get(tool, "white")

        suffix = " [dim](from cache 💾)[/dim]" if from_cache else ""
        if success is False:
            message = f"❌ ⚙️  Step {current}/{total} → [{tool_color}]{tool}[/].{action}{suffix}"
            try:
                self.console.print(Text.from_markup(message), style=self.ERROR)
            except Exception:
                print(f"ERROR: Step {current}/{total} -> {tool}.{action}")
            return

        message = f"⚙️  Step {current}/{total} → [{tool_color}]{tool}[/].{action}{suffix}"
        try:
            self.console.print(Text.from_markup(message))
        except Exception:
            print(f"Step {current}/{total} -> {tool}.{action}{' (cache)' if from_cache else ''}")

    def show_verification(self) -> None:
        """Display verification activity using a lightweight spinner animation."""
        try:
            with Live(
                Spinner("dots", text="🔍 [bright_magenta]Verifier Agent[/] validating results..."),
                console=self.console,
                refresh_per_second=12,
            ):
                time.sleep(1.0)
        except Exception:
            print("Verifier Agent validating results...")

    def show_final_result(self, result: dict[str, Any]) -> None:
        """Render final verified results across repo, weather, and news sections."""
        if not isinstance(result, dict):
            self.show_error("Invalid result payload")
            return

        self.last_result = result
        self.session_tasks += 1

        try:
            self.console.print(Rule("✅ VERIFIED RESULTS", style=self.SUCCESS))
        except Exception:
            print("VERIFIED RESULTS")

        try:
            repo_items = self._extract_repo_items(result)
            if repo_items:
                repo_table = Table(title="Repository Results", header_style=self.PRIMARY)
                repo_table.add_column("Rank", justify="right")
                repo_table.add_column("Repo Name")
                repo_table.add_column("Stars ⭐", justify="right")
                repo_table.add_column("Language")
                repo_table.add_column("Description")

                for idx, repo in enumerate(repo_items, start=1):
                    stars = int(repo.get("stars", 0) or 0)
                    if stars > 100000:
                        star_text = f"[gold1]{stars}[/gold1]"
                    elif stars > 50000:
                        star_text = f"[yellow]{stars}[/yellow]"
                    else:
                        star_text = f"[white]{stars}[/white]"

                    name = repo.get("full_name") or repo.get("name") or "Unknown"
                    repo_table.add_row(
                        str(idx),
                        str(name),
                        star_text,
                        str(repo.get("language", "")),
                        str(repo.get("description", ""))[:70],
                    )
                self.console.print(repo_table)
        except Exception:
            print("Repo results available")

        try:
            weather_obj = self._extract_weather_data(result)
            if weather_obj:
                weather_lines = [
                    f"🌡️  Temperature: {weather_obj.get('temperature_c', 'N/A')} °C",
                    f"💧 Humidity: {weather_obj.get('humidity_percent', 'N/A')}%",
                    f"💨 Wind: {weather_obj.get('wind_kmh', 'N/A')} km/h",
                    f"👁️  Visibility: {weather_obj.get('visibility_km', 'N/A')} km",
                ]
                self.console.print(
                    Panel("\n".join(weather_lines), title="Weather", border_style="blue")
                )
        except Exception:
            print("Weather data available")

        try:
            news_items = self._extract_news_items(result)
            if news_items:
                lines = []
                for idx, item in enumerate(news_items, start=1):
                    source = item.get("source", "Unknown Source")
                    title = item.get("title", "Untitled")
                    lines.append(f"{idx}. {source} — {title}")
                self.console.print(Panel("\n".join(lines), title="News Headlines", border_style=self.ACCENT))
        except Exception:
            print("News results available")

        summary = str(result.get("summary", "No summary available"))
        try:
            self.console.print(
                Panel(summary, title="📝 Summary", title_align="left", border_style=self.PRIMARY)
            )
        except Exception:
            print(f"Summary: {summary}")

        verified = result.get("verified", False)
        timestamp = result.get("timestamp", "N/A")
        sources = result.get("data_sources", [])
        source_text = ", ".join(sources) if isinstance(sources, list) and sources else "None"
        meta = f"✅ Verified: {verified} | 🕐 {timestamp} | 📡 Sources: {source_text}"

        try:
            self.console.print(Text(meta, style=self.DIM))
        except Exception:
            print(meta)

        if "confidence_score" in result:
            self.show_confidence_bar(
                int(result.get("confidence_score", 0) or 0),
                str(result.get("confidence_grade", "?")),
                str(result.get("confidence_reason", "")),
            )

        if bool(result.get("is_chain")):
            self.show_chain_timeline(result)

    def show_cost_report(self, cost_summary: dict[str, Any]) -> None:
        """Display aggregate and per-request token/cost metrics."""
        try:
            self.console.print(Rule("💰 COST & TOKEN REPORT", style=self.WARNING))

            total_requests = cost_summary.get("total_requests", 0)
            total_input = cost_summary.get("total_input_tokens", 0)
            total_output = cost_summary.get("total_output_tokens", 0)
            total_cost = cost_summary.get("total_cost_usd", 0.0)

            cards = Columns(
                [
                    Panel(str(total_requests), title="Total Requests", border_style=self.PRIMARY),
                    Panel(str(total_input), title="Total Input Tokens", border_style=self.PRIMARY),
                    Panel(str(total_output), title="Total Output Tokens", border_style=self.PRIMARY),
                    Panel(f"${total_cost:.6f}", title="Total Cost USD", border_style=self.PRIMARY),
                ]
            )
            self.console.print(cards)

            table = Table(header_style=self.PRIMARY)
            table.add_column("Agent")
            table.add_column("Input Tokens", justify="right")
            table.add_column("Output Tokens", justify="right")
            table.add_column("Cost USD", justify="right")

            for entry in cost_summary.get("log", []):
                cost = float(entry.get("cost_usd", 0.0) or 0.0)
                if cost < 0.001:
                    cost_color = "green"
                elif cost < 0.01:
                    cost_color = "yellow"
                else:
                    cost_color = "red"

                table.add_row(
                    str(entry.get("agent", "Unknown")),
                    str(entry.get("input_tokens", 0)),
                    str(entry.get("output_tokens", 0)),
                    f"[{cost_color}]${cost:.6f}[/{cost_color}]",
                )

            self.console.print(table)
            self.console.print(Text("💡 Tip: Use caching to reduce costs", style=self.DIM))

            # Per-agent subtotal breakdown.
            subtotals: dict[str, dict[str, float]] = {}
            for entry in cost_summary.get("log", []):
                agent = str(entry.get("agent", "Unknown"))
                if agent not in subtotals:
                    subtotals[agent] = {"calls": 0, "cost": 0.0}
                subtotals[agent]["calls"] += 1
                subtotals[agent]["cost"] += float(entry.get("cost_usd", 0.0) or 0.0)

            for base_agent in ["MemoryAgent", "PlannerAgent", "ExecutorAgent", "VerifierAgent"]:
                subtotals.setdefault(base_agent, {"calls": 0, "cost": 0.0})

            agent_table = Table(title="Per-Agent Cost Breakdown", header_style=self.ACCENT)
            agent_table.add_column("Agent")
            agent_table.add_column("Total Calls", justify="right")
            agent_table.add_column("Total Cost", justify="right")

            for agent, values in subtotals.items():
                agent_table.add_row(
                    agent,
                    str(int(values["calls"])),
                    f"${values['cost']:.6f}",
                )
            self.console.print(agent_table)
            self.console.print(
                Text(
                    "💡 Memory Agent adds context quality but uses tokens",
                    style=self.WARNING,
                )
            )
        except Exception:
            print("Cost report unavailable in rich mode.")
            print(json.dumps(cost_summary, indent=2, default=str))

    def show_cache_stats(self, cache_stats: dict[str, Any]) -> None:
        """Render cache usage metrics with hit-rate color and visual bar."""
        hits = int(cache_stats.get("hit_count", 0) or 0)
        misses = int(cache_stats.get("miss_count", 0) or 0)
        total = hits + misses
        hit_rate = (hits / total * 100) if total else 0.0

        if hit_rate > 70:
            rate_color = "green"
        elif hit_rate > 40:
            rate_color = "yellow"
        else:
            rate_color = "red"

        bar_filled = int(round((hit_rate / 100) * 20))
        bar = "█" * bar_filled + "░" * (20 - bar_filled)

        try:
            self.console.print(Rule("💾 CACHE STATISTICS", style="bright_blue"))

            left = Table.grid(padding=(0, 1))
            left.add_row("Cache Size", str(cache_stats.get("cache_size", 0)))
            left.add_row("Max Size", str(cache_stats.get("max_size", 0)))
            left.add_row("TTL Seconds", str(cache_stats.get("ttl_seconds", 0)))

            right = Table.grid(padding=(0, 1))
            right.add_row("Hit Count", str(hits))
            right.add_row("Miss Count", str(misses))
            right.add_row("Hit Rate %", f"[{rate_color}]{hit_rate:.2f}%[/{rate_color}]")
            right.add_row("Rate Bar", f"[{rate_color}]{bar}[/{rate_color}]")

            self.console.print(
                Columns(
                    [
                        Panel(left, border_style=self.PRIMARY, title="Capacity"),
                        Panel(right, border_style=self.SUCCESS, title="Efficiency"),
                    ]
                )
            )
        except Exception:
            print("CACHE STATISTICS")
            print(cache_stats)
            print(f"Hit Rate: {hit_rate:.2f}% [{bar}]")

    def show_help(self) -> None:
        """Display command guidance for voice/text workflows and shortcuts."""
        help_text = (
            "🎤 VOICE COMMANDS:\n"
            "  Say \"assistant\" to wake up voice mode\n"
            "  Then speak your task naturally\n\n"
            "📝 TEXT COMMANDS:\n"
            "  Type your task in plain English\n"
            "  Mention cities, topics, languages naturally\n\n"
            "🛠️  AVAILABLE TOOLS:\n"
            "  GitHub  → repos, trending, repo info\n"
            "  Weather → current weather, forecasts\n"
            "  News    → headlines, topic search\n\n"
            "⌨️  KEYBOARD SHORTCUTS:\n"
            "  Ctrl+C → Exit at any time\n"
            "  'back' → Return to main menu\n"
            "  'clear' → Clear terminal"
        )

        try:
            self.console.print(Panel(help_text, title="Help", border_style=self.PRIMARY))
        except Exception:
            print(help_text)

    def show_agent_timeline(self, pipeline_data: dict[str, Any]) -> None:
        """Render a horizontal planner/executor/verifier timeline with safe defaults."""
        planner = pipeline_data.get("planner", {}) if isinstance(pipeline_data, dict) else {}
        executor = pipeline_data.get("executor", {}) if isinstance(pipeline_data, dict) else {}
        verifier = pipeline_data.get("verifier", {}) if isinstance(pipeline_data, dict) else {}

        try:
            self.console.print(Rule("AGENT EXECUTION TIMELINE", style=self.PRIMARY))

            def style_for(status: str) -> str:
                return self.SUCCESS if status == "success" else self.ERROR

            planner_panel = Panel(
                "\n".join(
                    [
                        "🧠 PLANNER",
                        f"⏱  {float(planner.get('duration_seconds', planner.get('duration', 0.0))):.1f}s",
                        f"📋 {int(planner.get('step_count', 0))} steps",
                        f"{'✅ Success' if planner.get('status', 'success') == 'success' else '❌ Error'}",
                    ]
                ),
                border_style=style_for(str(planner.get("status", "success"))),
            )

            executor_panel = Panel(
                "\n".join(
                    [
                        "⚙️ EXECUTOR",
                        f"⏱  {float(executor.get('duration_seconds', executor.get('duration', 0.0))):.1f}s",
                        f"✅ {int(executor.get('steps_executed', 0))}/{int(executor.get('steps_total', 0))} done",
                        f"💾 {int(executor.get('cache_hits', 0))} cached",
                        f"🔧 {int(executor.get('self_healed', 0))} healed",
                    ]
                ),
                border_style=style_for(str(executor.get("status", "success"))),
            )

            verifier_panel = Panel(
                "\n".join(
                    [
                        "🔍 VERIFIER",
                        f"⏱  {float(verifier.get('duration_seconds', verifier.get('duration', 0.0))):.1f}s",
                        f"📊 {int(verifier.get('confidence_score', 0))}/100",
                        f"Grade: {verifier.get('confidence_grade', 'N/A')}",
                        f"{'✅ Verified' if verifier.get('status', 'success') == 'success' else '❌ Error'}",
                    ]
                ),
                border_style=style_for(str(verifier.get("status", "success"))),
            )

            self.console.print(
                Columns(
                    [
                        planner_panel,
                        Align.center(Text("──▶", style=self.PRIMARY), vertical="middle"),
                        executor_panel,
                        Align.center(Text("──▶", style=self.PRIMARY), vertical="middle"),
                        verifier_panel,
                    ],
                    expand=True,
                )
            )
            total_duration = (
                float(planner.get("duration_seconds", planner.get("duration", 0.0)))
                + float(executor.get("duration_seconds", executor.get("duration", 0.0)))
                + float(verifier.get("duration_seconds", verifier.get("duration", 0.0)))
            )
            self.console.print(Text(f"Total pipeline: {total_duration:.1f}s", style=self.DIM))
        except Exception:
            print("⏱️ Agent timeline unavailable.")

    def show_chain_timeline(self, chain_result: dict[str, Any]) -> None:
        """Display vertical task-chain timeline with confidence coloring."""
        try:
            self.console.print(Rule("🔗 TASK CHAIN TIMELINE", style=self.ACCENT))
            steps = chain_result.get("chain_results", []) if isinstance(chain_result, dict) else []
            total = len(steps)
            for idx, step in enumerate(steps, start=1):
                confidence = int(step.get("confidence", 0) or 0)
                status_icon = "✅" if step.get("result") else "❌"
                if confidence >= 80:
                    grade_color = self.SUCCESS
                elif confidence >= 60:
                    grade_color = self.WARNING
                else:
                    grade_color = self.ERROR

                task = str(step.get("task", ""))[:45]
                self.console.print(f"{status_icon} [{idx}/{total}] {task}")
                self.console.print(f"    Confidence: [{grade_color}]{confidence}/100[/]")
                if idx < total:
                    self.console.print("    │")
                    self.console.print("    ▼")

            summary = str(chain_result.get("combined_summary", "Chain completed successfully"))
            self.console.print(Panel(summary, title="Combined Chain Summary", border_style=self.ACCENT))
        except Exception:
            print("🔗 Task chain timeline unavailable.")

    def show_memory_context(self, context: str) -> None:
        """Show visual indicator for applied memory context."""
        text = (context or "").strip()
        if not text:
            return
        if len(text) > 200:
            text = text[:200].rstrip() + "..."
        try:
            self.console.print(
                Panel(text, title="🧠 Memory Context Applied", border_style="dim", style=self.DIM)
            )
        except Exception:
            print(f"🧠 Memory Context Applied: {text}")

    def show_reference_resolution(self, original: str, resolved: str) -> None:
        """Show when references are auto-resolved."""
        if (original or "").strip() == (resolved or "").strip():
            return
        try:
            self.console.print(
                Text(
                    f"🔗 Auto-resolved: '{original}' → '{resolved}'",
                    style=self.WARNING,
                )
            )
        except Exception:
            print(f"🔗 Auto-resolved: '{original}' -> '{resolved}'")

    def show_confidence_bar(self, score: int, grade: str, reason: str) -> None:
        """Render visual confidence bar and summary line."""
        score = max(0, min(100, int(score)))
        filled = int(score / 5)
        empty = 20 - filled
        if score >= 80:
            color = self.SUCCESS
        elif score >= 60:
            color = self.WARNING
        else:
            color = self.ERROR
        bar = f"{'█' * filled}{'░' * empty}"
        try:
            self.console.print(
                f"📊 Confidence: [{color}]{bar}[/] {score}/100 ({grade})   {reason}"
            )
        except Exception:
            print(f"📊 Confidence: {bar} {score}/100 ({grade}) {reason}")

    def show_self_heal_notification(self, step_num: int, original_action: str, healed_action: str) -> None:
        """Notify when self-healing has altered the step action."""
        try:
            self.console.print(
                Panel(
                    "🔧 Self-Healing Applied on Step "
                    f"{step_num}\n   Original: {original_action}\n   Healed to: {healed_action}",
                    border_style=self.WARNING,
                )
            )
        except Exception:
            print(
                f"🔧 Self-Healing Applied on Step {step_num} | "
                f"Original: {original_action} | Healed to: {healed_action}"
            )

    def show_error(self, message: str) -> None:
        """Display an error panel or plain text fallback."""
        try:
            self.console.print(Panel(f"❌ {message}", border_style=self.ERROR))
        except Exception:
            print(f"ERROR: {message}")

    def show_success(self, message: str) -> None:
        """Display a success panel or plain text fallback."""
        try:
            self.console.print(Panel(f"✅ {message}", border_style=self.SUCCESS))
        except Exception:
            print(f"SUCCESS: {message}")

    def show_warning(self, message: str) -> None:
        """Display a warning panel or plain text fallback."""
        try:
            self.console.print(Panel(f"⚠️ {message}", border_style=self.WARNING))
        except Exception:
            print(f"WARNING: {message}")

    def show_loading(self, message: str, duration: float = 0) -> None:
        """Display either a timed progress bar or a spinner-style loading view.

        Args:
            message: Loading text shown to the user.
            duration: Seconds for progress mode; if zero, spinner mode is used.
        """
        try:
            if duration > 0:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("{task.description}"),
                    BarColumn(),
                    TimeElapsedColumn(),
                    console=self.console,
                ) as progress:
                    task_id = progress.add_task(message, total=100)
                    start = time.time()
                    while not progress.finished:
                        elapsed = time.time() - start
                        percent = min((elapsed / duration) * 100, 100)
                        progress.update(task_id, completed=percent)
                        time.sleep(0.05)
            else:
                with Live(Spinner("dots", text=message), console=self.console, refresh_per_second=12):
                    time.sleep(1.0)
        except Exception:
            print(f"Loading: {message}")
            if duration > 0:
                time.sleep(duration)

    def confirm(self, message: str) -> bool:
        """Ask the user for yes/no confirmation using `[y/N]` semantics."""
        try:
            choice = Prompt.ask(f"{message} [y/N]", default="n").strip().lower()
        except Exception:
            choice = input(f"{message} [y/N]: ").strip().lower()
        return choice in {"y", "yes"}

    def clear_screen(self) -> None:
        """Clear terminal output and show a compact assistant header."""
        try:
            self.console.clear()
            self.console.print(Text("AI Ops Assistant | Type 'help' for commands", style=self.DIM))
        except Exception:
            print("AI Ops Assistant | Type 'help' for commands")

    def print_separator(self, title: str = "") -> None:
        """Print a styled separator rule with optional title."""
        try:
            self.console.print(Rule(title if title else "", style=self.DIM))
        except Exception:
            if title:
                print(f"--- {title} ---")
            else:
                print("----------------")

    def _extract_repo_items(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract likely repository lists from arbitrary result payload fields."""
        repo_items: list[dict[str, Any]] = []
        for key, value in result.items():
            if isinstance(value, list) and "repo" in key.lower():
                for item in value:
                    if isinstance(item, dict):
                        repo_items.append(item)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and (
                        "stars" in item or "full_name" in item or "language" in item
                    ):
                        repo_items.append(item)
        return repo_items

    def _extract_weather_data(self, result: dict[str, Any]) -> dict[str, Any] | None:
        """Extract a likely weather dictionary from result payload fields."""
        for key, value in result.items():
            if "weather" in key.lower() and isinstance(value, dict):
                return value
        for value in result.values():
            if isinstance(value, dict) and (
                "temperature_c" in value or "humidity_percent" in value or "wind_kmh" in value
            ):
                return value
        return None

    def _extract_news_items(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract likely news/headline lists from result payload fields."""
        items: list[dict[str, Any]] = []
        for key, value in result.items():
            lowered = key.lower()
            if isinstance(value, list) and ("news" in lowered or "headline" in lowered):
                items.extend([v for v in value if isinstance(v, dict)])
            elif isinstance(value, list):
                for row in value:
                    if isinstance(row, dict) and ("title" in row and "source" in row):
                        items.append(row)
        return items


terminal_ui = TerminalUI()


if __name__ == "__main__":
    """Run a visual self-test covering major TerminalUI rendering methods."""
    ui = terminal_ui

    ui.show_splash()
    ui.show_main_menu()

    fake_plan = {
        "task_summary": "Collect trending Python repos, SF weather, and tech headlines.",
        "steps": [
            {
                "step": 1,
                "tool": "GitHubTool",
                "action": "get_trending",
                "params": {"language": "python", "limit": 3},
                "description": "Fetch trending Python repositories",
            },
            {
                "step": 2,
                "tool": "WeatherTool",
                "action": "get_current_weather",
                "params": {"city": "San Francisco"},
                "description": "Fetch current weather",
            },
            {
                "step": 3,
                "tool": "NewsTool",
                "action": "get_top_headlines",
                "params": {"category": "technology", "country": "us", "limit": 3},
                "description": "Fetch top technology headlines",
            },
        ],
    }

    fake_result = {
        "verified": True,
        "summary": "Trending repositories were retrieved, weather is mild, and top technology headlines were collected.",
        "data_sources": ["GitHubTool", "WeatherTool", "NewsTool"],
        "timestamp": datetime.now().isoformat(),
        "top_python_repos": [
            {
                "full_name": "pallets/flask",
                "stars": 67000,
                "language": "Python",
                "description": "A lightweight WSGI web application framework.",
            },
            {
                "full_name": "tiangolo/fastapi",
                "stars": 82000,
                "language": "Python",
                "description": "FastAPI framework, high performance and easy to use.",
            },
        ],
        "current_weather": {
            "temperature_c": 18.6,
            "humidity_percent": 72,
            "wind_kmh": 11.2,
            "visibility_km": 9.4,
        },
        "top_headlines": [
            {"source": "TechCrunch", "title": "New AI tooling gains momentum"},
            {"source": "The Verge", "title": "Cloud providers announce new GPU plans"},
        ],
    }

    ui.show_planning()
    ui.show_plan(fake_plan)

    for i, step in enumerate(fake_plan["steps"], start=1):
        ui.show_execution_progress({**step, "success": True, "from_cache": i == 1}, i, len(fake_plan["steps"]))
        time.sleep(0.2)

    ui.show_verification()
    ui.show_final_result(fake_result)

    ui.show_cost_report(
        {
            "total_requests": 3,
            "total_input_tokens": 1420,
            "total_output_tokens": 690,
            "total_cost_usd": 0.00621,
            "log": [
                {"agent": "PlannerAgent", "input_tokens": 410, "output_tokens": 120, "cost_usd": 0.00101},
                {"agent": "VerifierAgent", "input_tokens": 1010, "output_tokens": 570, "cost_usd": 0.0052},
            ],
        }
    )

    ui.show_cache_stats(
        {
            "cache_size": 8,
            "max_size": 200,
            "ttl_seconds": 300,
            "hit_count": 14,
            "miss_count": 6,
        }
    )

    ui.show_help()
    ui.show_success("UI self-test completed")
