"""FastAPI server and web dashboard for the AI Operations Assistant."""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from ai_ops_assistant.agents.executor import executor_agent
from ai_ops_assistant.agents.memory_agent import memory_agent
from ai_ops_assistant.agents.planner import planner_agent
from ai_ops_assistant.agents.task_chain import task_chain_processor
from ai_ops_assistant.agents.verifier import verifier_agent
from ai_ops_assistant.cache.cache_manager import cache_manager
from ai_ops_assistant.llm.client import cost_tracker


class TaskRequest(BaseModel):
    """Request payload for submitting a task to the 3-agent pipeline."""

    task: str
    use_cache: bool = True
    parallel_execution: bool = False
    use_voice_narration: bool = False


class TaskResponse(BaseModel):
    """Response payload for task execution status and results."""

    task_id: str
    status: str
    plan: dict | None = None
    result: dict | None = None
    execution_time: float | None = None
    error: str | None = None
    timestamp: str
    confidence_score: int | None = None
    confidence_grade: str | None = None
    is_chain: bool = False
    chain_steps: int | None = None
    self_healed_count: int | None = None
    pipeline_timeline: dict | None = None
    from_cache: bool = False


app = FastAPI(title="AI Operations Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

task_history: list[dict[str, Any]] = []


def _make_final_response_cache_key(task: str) -> str:
    """Create a stable cache key for a fully formatted task response."""
    return cache_manager.make_key("TaskPipeline", "final_response", task=task.strip())


def _get_cached_task_response(task: str) -> dict[str, Any] | None:
    """Return a cached final task response when available."""
    cached = cache_manager.get(_make_final_response_cache_key(task))
    if not isinstance(cached, dict):
        return None
    return dict(cached)


def _store_cached_task_response(task: str, response_payload: dict[str, Any]) -> None:
    """Persist a fully formatted task response for repeated identical tasks."""
    cache_manager.set(_make_final_response_cache_key(task), dict(response_payload))


def _validate_environment_or_exit() -> None:
    """Validate required environment keys and report optional key warnings."""
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not openrouter_key:
        print(
            "Error: OPENROUTER_API_KEY is required for planner/verifier LLM calls.\n"
            "Set it in .env as OPENROUTER_API_KEY=<your_key>.\n"
            "Get a key from https://openrouter.ai/keys"
        )
        sys.exit(1)

    for key in ["OPENWEATHER_API_KEY", "NEWSAPI_KEY", "GITHUB_TOKEN"]:
        if not os.getenv(key, "").strip():
            print(f"Warning: {key} is not configured. Some tool features may be limited.")


def _json_response(payload: dict[str, Any], status_code: int, started_at: float) -> JSONResponse:
    """Build JSON responses that include standardized response-time metadata."""
    response_payload = dict(payload)
    response_payload["response_time_seconds"] = round(time.time() - started_at, 4)
    return JSONResponse(status_code=status_code, content=response_payload)


def _trim_history() -> None:
    """Keep task history bounded to a maximum of 50 entries."""
    while len(task_history) > 50:
        task_history.pop(0)


@app.exception_handler(HTTPException)
def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Return standardized JSON errors for HTTP exceptions."""
    started_at = time.time()
    return _json_response({"error": exc.detail}, status_code=exc.status_code, started_at=started_at)


@app.post("/task")
def run_task(request: TaskRequest, background_tasks: BackgroundTasks) -> JSONResponse:
    """Run the full Plan → Execute → Verify pipeline for a submitted task."""
    started_at = time.time()
    if not request.task or not request.task.strip():
        raise HTTPException(status_code=400, detail="Task cannot be empty")

    task_id = str(uuid.uuid4())[:8]
    clean_task = request.task.strip()

    try:
        if not request.use_cache:
            cache_manager.clear()

        cached_response = _get_cached_task_response(clean_task) if request.use_cache else None
        if cached_response is not None:
            cached_response["task_id"] = task_id
            cached_response["timestamp"] = datetime.now().isoformat()
            cached_response["execution_time"] = 0.0
            cached_response["from_cache"] = True

            task_history.append(
                {
                    "task_id": task_id,
                    "task": clean_task,
                    "status": cached_response.get("status", "success"),
                    "timestamp": cached_response["timestamp"],
                    "execution_time": 0.0,
                    "plan": cached_response.get("plan"),
                    "result": cached_response.get("result"),
                    "pipeline_timeline": cached_response.get("pipeline_timeline"),
                    "from_cache": True,
                }
            )
            background_tasks.add_task(_trim_history)
            return _json_response(cached_response, status_code=200, started_at=started_at)

        if task_chain_processor.is_chained_task(clean_task):
            chain_start = time.time()
            chain_result = task_chain_processor.execute_chain(clean_task, ui_callback=None)
            execution_time = round(time.time() - started_at, 4)
            chain_timeline = {
                "planner": {
                    "duration_seconds": round(max(0.0, chain_start - started_at), 4),
                    "step_count": 0,
                    "status": "success",
                },
                "executor": {
                    "duration_seconds": round(chain_result.get("total_execution_time", 0.0), 4),
                    "steps_executed": int(chain_result.get("completed_steps", 0) or 0),
                    "steps_total": int(chain_result.get("total_chain_steps", 0) or 0),
                    "cache_hits": 0,
                    "self_healed": 0,
                    "status": "success",
                },
                "verifier": {
                    "duration_seconds": 0.0,
                    "confidence_score": int(chain_result.get("average_confidence", 0) or 0),
                    "confidence_grade": "N/A",
                    "status": "success",
                },
            }
            response = TaskResponse(
                task_id=task_id,
                status="success",
                plan=None,
                result=chain_result,
                execution_time=execution_time,
                timestamp=datetime.now().isoformat(),
                confidence_score=int(chain_result.get("average_confidence", 0) or 0),
                confidence_grade="N/A",
                is_chain=True,
                chain_steps=int(chain_result.get("total_chain_steps", 0) or 0),
                self_healed_count=0,
                pipeline_timeline=chain_timeline,
                from_cache=False,
            )
            _store_cached_task_response(clean_task, response.model_dump())
            task_history.append(
                {
                    "task_id": task_id,
                    "task": clean_task,
                    "status": "success",
                    "timestamp": response.timestamp,
                    "execution_time": execution_time,
                    "plan": None,
                    "result": chain_result,
                    "pipeline_timeline": chain_timeline,
                }
            )
            background_tasks.add_task(_trim_history)
            return _json_response(response.model_dump(), status_code=200, started_at=started_at)

        pipeline_timeline: dict[str, Any] = {
            "planner": {"duration_seconds": 0.0, "step_count": 0, "status": "success"},
            "executor": {
                "duration_seconds": 0.0,
                "steps_executed": 0,
                "steps_total": 0,
                "cache_hits": 0,
                "self_healed": 0,
                "status": "success",
            },
            "verifier": {
                "duration_seconds": 0.0,
                "confidence_score": 0,
                "confidence_grade": "N/A",
                "status": "success",
            },
        }

        p_start = time.time()
        memory_context = memory_agent.get_context_for_task(clean_task)
        resolved_task = memory_agent.resolve_references(clean_task)
        plan = planner_agent.plan_with_reasoning(resolved_task, memory_context)
        pipeline_timeline["planner"]["duration_seconds"] = round(time.time() - p_start, 4)
        pipeline_timeline["planner"]["step_count"] = len(plan.get("steps", [])) if isinstance(plan, dict) else 0

        if not isinstance(plan, dict) or plan.get("error"):
            pipeline_timeline["planner"]["status"] = "error"
            raise RuntimeError(plan.get("error", "Planning failed"))

        is_valid, reason = planner_agent.validate_plan(plan)
        if not is_valid:
            pipeline_timeline["planner"]["status"] = "error"
            raise RuntimeError(f"Invalid plan: {reason}")

        e_start = time.time()
        if request.parallel_execution:
            results = executor_agent.execute_parallel(plan)
        else:
            results = executor_agent.execute(plan)
        pipeline_timeline["executor"]["duration_seconds"] = round(time.time() - e_start, 4)
        pipeline_timeline["executor"]["steps_executed"] = int(results.get("steps_executed", 0))
        pipeline_timeline["executor"]["steps_total"] = int(results.get("steps_total", 0))
        pipeline_timeline["executor"]["cache_hits"] = int(results.get("cache_hits", 0))
        pipeline_timeline["executor"]["self_healed"] = int(results.get("self_healed_count", 0))
        if results.get("errors"):
            pipeline_timeline["executor"]["status"] = "error"

        v_start = time.time()
        final = verifier_agent.verify(plan, results)
        memory_agent.store_task(resolved_task, plan, final)
        pipeline_timeline["verifier"]["duration_seconds"] = round(time.time() - v_start, 4)
        pipeline_timeline["verifier"]["confidence_score"] = int(final.get("confidence_score", 0) or 0)
        pipeline_timeline["verifier"]["confidence_grade"] = str(final.get("confidence_grade", "N/A"))
        if final.get("verified") is False:
            pipeline_timeline["verifier"]["status"] = "error"

        execution_time = round(time.time() - started_at, 4)
        response = TaskResponse(
            task_id=task_id,
            status="success",
            plan=plan,
            result=final,
            execution_time=execution_time,
            timestamp=datetime.now().isoformat(),
            confidence_score=int(final.get("confidence_score", 0) or 0),
            confidence_grade=str(final.get("confidence_grade", "N/A")),
            is_chain=bool(final.get("is_chain", False)),
            chain_steps=int(final.get("total_chain_steps", 0) or 0) if final.get("is_chain") else None,
            self_healed_count=int(results.get("self_healed_count", 0) or 0),
            pipeline_timeline=pipeline_timeline,
            from_cache=False,
        )

        _store_cached_task_response(clean_task, response.model_dump())
        task_history.append(
            {
                "task_id": task_id,
                "task": clean_task,
                "status": "success",
                "timestamp": response.timestamp,
                "execution_time": execution_time,
                "plan": plan,
                "result": final,
                "pipeline_timeline": pipeline_timeline,
            }
        )
        background_tasks.add_task(_trim_history)
        return _json_response(response.model_dump(), status_code=200, started_at=started_at)

    except Exception as exc:
        execution_time = round(time.time() - started_at, 4)
        error_response = TaskResponse(
            task_id=task_id,
            status="error",
            error=str(exc),
            execution_time=execution_time,
            timestamp=datetime.now().isoformat(),
        )

        task_history.append(
            {
                "task_id": task_id,
                "task": clean_task,
                "status": "error",
                "timestamp": error_response.timestamp,
                "execution_time": execution_time,
                "error": str(exc),
            }
        )
        background_tasks.add_task(_trim_history)
        return _json_response(error_response.model_dump(), status_code=500, started_at=started_at)


@app.post("/planner")
def run_planner_only(request: dict) -> dict[str, Any]:
    """Run only the Planner Agent and return the plan."""
    try:
        task = str(request.get("task", "")).strip()
        if not task:
            raise HTTPException(status_code=400, detail="Task cannot be empty")

        plan = planner_agent.plan_with_reasoning(task, "")
        return {
            "plan": plan,
            "step_count": len(plan.get("steps", [])) if isinstance(plan, dict) else 0,
            "task_summary": plan.get("task_summary", "") if isinstance(plan, dict) else "",
            "reasoning": plan.get("reasoning", {}) if isinstance(plan, dict) else {},
            "status": "success" if isinstance(plan, dict) and "error" not in plan else "error",
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/executor")
def run_executor_only(request: dict) -> dict[str, Any]:
    """Run only the Executor Agent on a provided plan."""
    try:
        plan = request.get("plan", {})
        steps = plan.get("steps", []) if isinstance(plan, dict) else []
        if not steps:
            raise HTTPException(status_code=400, detail="Invalid plan")

        results = executor_agent.execute(plan)
        return {
            "results": results,
            "steps_executed": results["steps_executed"],
            "steps_total": results["steps_total"],
            "cache_hits": results["cache_hits"],
            "execution_time": results["execution_time_seconds"],
            "status": "success",
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/verifier")
def run_verifier_only(request: dict) -> dict[str, Any]:
    """Run only the Verifier Agent on provided plan and results."""
    try:
        plan = request.get("plan", {})
        results = request.get("results", {})
        if not plan or not results:
            raise HTTPException(status_code=400, detail="Plan and results are required")

        final = verifier_agent.verify(plan, results)
        if isinstance(final, dict):
            final["status"] = "success"
            return final
        return {"status": "error", "error": "Verifier returned invalid response"}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/task/stream")
async def run_task_stream(request: TaskRequest) -> StreamingResponse:
    """Streaming endpoint that emits SSE events for each pipeline stage."""
    if not request.task or not request.task.strip():
        raise HTTPException(status_code=400, detail="Task cannot be empty")

    async def event_generator() -> AsyncGenerator[str, None]:
        """Yield SSE messages while task progresses through the pipeline."""
        task_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        clean_task = request.task.strip()

        try:
            yield f"data: {json.dumps({'event': 'task_received', 'task_id': task_id, 'task': clean_task})}\n\n"
            await asyncio.sleep(0.1)

            cached_response = _get_cached_task_response(clean_task) if request.use_cache else None
            if cached_response is not None:
                cached_response["task_id"] = task_id
                cached_response["timestamp"] = datetime.now().isoformat()
                cached_response["execution_time"] = 0.0
                cached_response["from_cache"] = True
                yield f"data: {json.dumps({'event': 'cache_hit', 'message': 'Returning cached formatted response'})}\n\n"
                yield f"data: {json.dumps({'event': 'complete', **cached_response})}\n\n"
                return

            yield f"data: {json.dumps({'event': 'planning_start'})}\n\n"

            is_chain = task_chain_processor.is_chained_task(clean_task)
            if is_chain:
                yield f"data: {json.dumps({'event': 'chain_detected', 'message': 'Task chain detected'})}\n\n"
                sub_tasks = task_chain_processor.split_chain(clean_task)
                yield f"data: {json.dumps({'event': 'chain_split', 'sub_tasks': sub_tasks, 'count': len(sub_tasks)})}\n\n"
                yield f"data: {json.dumps({'event': 'execution_start'})}\n\n"
                chain_result = task_chain_processor.execute_chain(clean_task, ui_callback=None)
                execution_time = round(time.time() - start_time, 2)
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "event": "complete",
                            "task_id": task_id,
                            "result": chain_result,
                            "execution_time": execution_time,
                            "confidence_score": int(chain_result.get("average_confidence", 0) or 0),
                            "confidence_grade": "N/A",
                            "from_cache": False,
                        }
                    )
                    + "\n\n"
                )
                _store_cached_task_response(
                    clean_task,
                    {
                        "task_id": task_id,
                        "status": "success",
                        "plan": None,
                        "result": chain_result,
                        "execution_time": execution_time,
                        "error": None,
                        "timestamp": datetime.now().isoformat(),
                        "confidence_score": int(chain_result.get("average_confidence", 0) or 0),
                        "confidence_grade": "N/A",
                        "is_chain": True,
                        "chain_steps": int(chain_result.get("total_chain_steps", 0) or 0),
                        "self_healed_count": 0,
                        "pipeline_timeline": None,
                        "from_cache": False,
                    },
                )
                return

            if not request.use_cache:
                cache_manager.clear()

            memory_context = memory_agent.get_context_for_task(clean_task)
            resolved_task = memory_agent.resolve_references(clean_task)
            plan = planner_agent.plan_with_reasoning(resolved_task, memory_context)

            if not isinstance(plan, dict) or plan.get("error"):
                raise RuntimeError(plan.get("error", "Planning failed"))

            yield (
                f"data: {json.dumps({'event': 'plan_ready', 'plan': plan, 'step_count': len(plan.get('steps', []))})}\n\n"
            )
            await asyncio.sleep(0.1)

            yield f"data: {json.dumps({'event': 'execution_start'})}\n\n"

            if request.parallel_execution:
                results = executor_agent.execute_parallel(plan)
            else:
                results = executor_agent.execute(plan)

            for step_result in results.get("results", []):
                event_payload = {
                    "event": "step_complete",
                    "step": step_result.get("step"),
                    "tool": step_result.get("tool"),
                    "action": step_result.get("action"),
                    "success": step_result.get("success"),
                    "from_cache": step_result.get("from_cache"),
                    "self_healed": step_result.get("self_healed", False),
                }
                yield f"data: {json.dumps(event_payload)}\n\n"
                await asyncio.sleep(0.05)

            yield (
                f"data: {json.dumps({'event': 'execution_complete', 'steps_executed': results.get('steps_executed', 0), 'cache_hits': results.get('cache_hits', 0)})}\n\n"
            )

            yield f"data: {json.dumps({'event': 'verification_start'})}\n\n"
            final = verifier_agent.verify(plan, results)
            memory_agent.store_task(resolved_task, plan, final)

            execution_time = round(time.time() - start_time, 2)
            response_payload = {
                "task_id": task_id,
                "status": "success",
                "plan": plan,
                "result": final,
                "execution_time": execution_time,
                "error": None,
                "timestamp": datetime.now().isoformat(),
                "confidence_score": final.get("confidence_score", 0),
                "confidence_grade": final.get("confidence_grade", "N/A"),
                "is_chain": False,
                "chain_steps": None,
                "self_healed_count": int(results.get("self_healed_count", 0) or 0),
                "pipeline_timeline": None,
                "from_cache": False,
            }
            _store_cached_task_response(clean_task, response_payload)
            yield (
                f"data: {json.dumps({'event': 'complete', **response_payload})}\n\n"
            )
        except Exception as exc:
            error_payload = {"event": "error", "message": str(exc), "task_id": task_id}
            yield f"data: {json.dumps(error_payload)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/history")
def get_history() -> JSONResponse:
    """Return the latest 20 task history entries for dashboard display."""
    started_at = time.time()
    try:
        return _json_response({"history": task_history[-20:]}, status_code=200, started_at=started_at)
    except Exception as exc:
        return _json_response({"error": f"Failed to fetch history: {exc}"}, 500, started_at)


@app.get("/cost")
def get_cost_summary() -> JSONResponse:
    """Return token and cost summary across all LLM requests."""
    started_at = time.time()
    try:
        return _json_response(cost_tracker.get_summary(), 200, started_at)
    except Exception as exc:
        return _json_response({"error": f"Failed to fetch cost summary: {exc}"}, 500, started_at)


@app.get("/cache")
def get_cache_stats() -> JSONResponse:
    """Return current cache occupancy and hit/miss statistics."""
    started_at = time.time()
    try:
        return _json_response(cache_manager.get_stats(), 200, started_at)
    except Exception as exc:
        return _json_response({"error": f"Failed to fetch cache stats: {exc}"}, 500, started_at)


@app.delete("/cache")
def clear_cache() -> JSONResponse:
    """Clear all in-memory cache entries and return reset confirmation."""
    started_at = time.time()
    try:
        cache_manager.clear()
        return _json_response({"message": "Cache cleared", "timestamp": datetime.now().isoformat()}, 200, started_at)
    except Exception as exc:
        return _json_response({"error": f"Failed to clear cache: {exc}"}, 500, started_at)


@app.delete("/cost")
def clear_cost_tracking() -> JSONResponse:
    """Reset accumulated token/cost logs and return confirmation."""
    started_at = time.time()
    try:
        cost_tracker.reset()
        return _json_response({"message": "Cost tracking reset", "timestamp": datetime.now().isoformat()}, 200, started_at)
    except Exception as exc:
        return _json_response({"error": f"Failed to reset cost tracking: {exc}"}, 500, started_at)


@app.get("/memory")
def get_memory() -> JSONResponse:
    """Return current session memory summary."""
    started_at = time.time()
    try:
        return _json_response(memory_agent.get_session_summary(), 200, started_at)
    except Exception as exc:
        return _json_response({"error": f"Failed to fetch memory: {exc}"}, 500, started_at)


@app.delete("/memory")
def clear_memory() -> JSONResponse:
    """Clear session memory."""
    started_at = time.time()
    try:
        memory_agent.clear()
        return _json_response({"message": "Memory cleared", "timestamp": datetime.now().isoformat()}, 200, started_at)
    except Exception as exc:
        return _json_response({"error": f"Failed to clear memory: {exc}"}, 500, started_at)


@app.get("/health")
def health_check() -> JSONResponse:
    """Provide service health status and key runtime counters."""
    started_at = time.time()
    try:
        cache_stats = cache_manager.get_stats()
        cost_stats = cost_tracker.get_summary()
        payload = {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "cache_size": cache_stats.get("cache_size", 0),
            "total_requests": cost_stats.get("total_requests", 0),
        }
        return _json_response(payload, 200, started_at)
    except Exception as exc:
        return _json_response({"status": "unhealthy", "error": str(exc)}, 500, started_at)


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    """Serve dashboard with streaming timeline and live event log support."""
    html = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI Ops Assistant Dashboard</title>
  <style>
    :root { --bg:#0d1117; --card:#161b22; --border:#30363d; --text:#e6edf3; --cyan:#58a6ff; --green:#3fb950; --yellow:#d29922; --red:#f85149; }
    body { margin:0; font-family:system-ui, sans-serif; background:var(--bg); color:var(--text); }
    .container { width:min(1280px,96%); margin:20px auto; display:grid; gap:16px; }
    .card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:20px; }
    .grid-4 { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
    .grid-2 { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
    .timeline-container { display:flex; align-items:center; justify-content:space-between; gap:10px; margin:20px 0; }
    .timeline-agent-box { flex:1; background:#1c2128; border:1px solid #30363d; border-radius:8px; padding:16px; text-align:center; transition:border-color .3s; }
    .timeline-agent-box.success { border-color:#3fb950; }
    .timeline-agent-box.error { border-color:#f85149; }
    .timeline-agent-box.running { border-color:#58a6ff; animation:pulse 1s infinite; }
    .timeline-arrow { font-size:24px; color:#58a6ff; flex-shrink:0; }
    @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.5; } }
    .confidence-bar-container { background:#0d1117; border-radius:4px; height:12px; width:100%; margin:8px 0; overflow:hidden; }
    .confidence-bar-fill { height:100%; border-radius:4px; transition:width 1s ease-in-out; }
    .event-log { background:#0d1117; border:1px solid #30363d; border-radius:6px; padding:12px; font-family:monospace; font-size:13px; max-height:200px; overflow-y:auto; margin:10px 0; }
    .event-line { padding:2px 0; }
    .event-line.planning { color:#79c0ff; }
    .event-line.executing { color:#56d364; }
    .event-line.verifying { color:#d2a8ff; }
    .event-line.complete { color:#3fb950; }
    .event-line.error { color:#f85149; }
    .event-line.cache { color:#e3b341; }
    .event-line.healed { color:#ff9500; }
    .toast { position:fixed; bottom:24px; right:24px; padding:12px 20px; border-radius:8px; font-size:14px; z-index:9999; animation:slideIn .3s ease; max-width:300px; }
    @keyframes slideIn { from { transform:translateX(100px); opacity:0; } to { transform:translateX(0); opacity:1; } }
    .btn { padding:10px 14px; border:none; border-radius:6px; cursor:pointer; }
    table { width:100%; border-collapse:collapse; }
    th,td { border-bottom:1px solid var(--border); padding:8px; text-align:left; }
    @media (max-width: 980px) { .grid-4,.grid-2 { grid-template-columns:1fr; } .timeline-container{flex-direction:column;} .timeline-arrow{transform:rotate(90deg);} }
  </style>
</head>
<body>
  <div class="container">
    <div class="card" style="display:flex;justify-content:space-between;align-items:center;">
      <div>
        <div style="font-size:1.6rem;color:#58a6ff;font-weight:700;">🤖 AI Operations Assistant</div>
        <div style="color:#8b949e;">Plan → Execute → Verify</div>
      </div>
      <div id="liveClock" style="color:#3fb950;font-family:monospace;"></div>
    </div>

    <section class="grid-4">
      <div class="card"><div style="color:#8b949e;">API Status</div><div id="apiStatus">Checking...</div></div>
      <div class="card"><div style="color:#8b949e;">Total Requests</div><div id="totalRequests">0</div></div>
      <div class="card"><div style="color:#8b949e;">Cache Hit Rate</div><div id="cacheHitRate">0%</div></div>
      <div class="card"><div style="color:#8b949e;">Total Cost</div><div id="totalCost">$0.000000</div></div>
    </section>

    <div class="card"><div style="display:flex;justify-content:space-between;align-items:center;"><h3>🧠 Session Memory</h3><button class="btn" onclick="clearMemory()">Clear Memory</button></div><div id="memoryCount">0 tasks</div></div>

    <div class="card">
      <h3 style="color:#58a6ff; margin-bottom:16px;">🚀 Run AI Task</h3>
      <textarea id="taskInput" placeholder="Examples:\n• Find top Python repos and weather in London\n• Latest AI news → Trending JS repos → Weather in NYC\n• Get weather in Tokyo and search climate news" style="width:100%;height:100px;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:10px;font-size:14px;resize:vertical;box-sizing:border-box;"></textarea>
      <div style="display:flex; gap:16px; margin:12px 0; align-items:center; flex-wrap:wrap;">
        <label style="color:#8b949e; cursor:pointer;"><input type="checkbox" id="useCache" checked> 💾 Use Cache</label>
        <label style="color:#8b949e; cursor:pointer;"><input type="checkbox" id="parallelExec"> ⚡ Parallel Execution</label>
        <label style="color:#8b949e; cursor:pointer;"><input type="checkbox" id="useStream" checked> 📡 Live Streaming</label>
      </div>
      <button onclick="runTask()" id="runBtn" style="width:100%; padding:12px; background:#238636;color:white;border:none;border-radius:6px;font-size:16px; cursor:pointer;">🚀 Run Task</button>
    </div>

    <div class="card" id="eventLogCard" style="display:none;">
      <h3 style="color:#58a6ff; margin-bottom:12px;">📡 Live Agent Activity</h3>
      <div class="event-log" id="eventLog"></div>
    </div>

    <div class="card" id="timelineCard" style="display:none;">
      <h3 style="color:#58a6ff; margin-bottom:16px;">⏱️ Agent Execution Timeline</h3>
      <div class="timeline-container">
        <div class="timeline-agent-box" id="plannerBox">
          <div style="font-size:24px;">🧠</div>
          <div style="color:#58a6ff; font-weight:bold;">PLANNER</div>
          <div id="plannerTime" style="color:#8b949e; font-size:13px;">--</div>
          <div id="plannerSteps" style="color:#8b949e; font-size:12px;">--</div>
          <div id="plannerStatus" style="margin-top:8px;">⏳</div>
        </div>
        <div class="timeline-arrow">──▶</div>
        <div class="timeline-agent-box" id="executorBox">
          <div style="font-size:24px;">⚙️</div>
          <div style="color:#3fb950; font-weight:bold;">EXECUTOR</div>
          <div id="executorTime" style="color:#8b949e; font-size:13px;">--</div>
          <div id="executorSteps" style="color:#8b949e; font-size:12px;">--</div>
          <div id="executorCache" style="color:#e3b341; font-size:12px;">--</div>
          <div id="executorStatus" style="margin-top:8px;">⏳</div>
        </div>
        <div class="timeline-arrow">──▶</div>
        <div class="timeline-agent-box" id="verifierBox">
          <div style="font-size:24px;">🔍</div>
          <div style="color:#d2a8ff; font-weight:bold;">VERIFIER</div>
          <div id="verifierTime" style="color:#8b949e; font-size:13px;">--</div>
          <div id="verifierConfidence" style="color:#8b949e; font-size:13px;">--</div>
          <div class="confidence-bar-container"><div class="confidence-bar-fill" id="confidenceBarFill" style="width:0%; background:#3fb950;"></div></div>
          <div id="verifierStatus" style="margin-top:8px;">⏳</div>
        </div>
      </div>
      <div id="totalPipelineTime" style="text-align:center; color:#8b949e; font-size:13px; margin-top:8px;"></div>
    </div>

    <div class="card" id="planCard" style="display:none;"><h3>Execution Plan</h3><table><thead><tr><th>Step</th><th>Tool</th><th>Action</th><th>Parameters</th></tr></thead><tbody id="planBody"></tbody></table></div>
    <div class="card" id="resultCard" style="display:none;"><h3>Results</h3><pre id="resultJson" style="max-height:400px;overflow:auto;background:#0d1117;padding:12px;border-radius:6px;"></pre></div>

    <div class="grid-2">
      <div class="card"><h3>Cost Report</h3><table><thead><tr><th>Agent</th><th>Input</th><th>Output</th><th>Cost</th></tr></thead><tbody id="costBody"></tbody></table></div>
      <div class="card"><h3>Task History</h3><table><thead><tr><th>Task ID</th><th>Task</th><th>Status</th><th>Duration</th></tr></thead><tbody id="historyBody"></tbody></table></div>
    </div>
  </div>

  <script>
    let latestResult = null;
    let pipelineStartTime = null;
    let plannerStartTime = null;
    let executorStartTime = null;
    let verifierStartTime = null;

    function updateClock(){ document.getElementById('liveClock').textContent = new Date().toLocaleString(); }

    function showToast(message, type='success'){
      const toast = document.createElement('div');
      toast.className = 'toast';
      toast.style.background = type==='error' ? '#3a1f22' : (type==='warning' ? '#3a321f' : '#1f3326');
      toast.style.border = '1px solid #30363d';
      toast.textContent = message;
      document.body.appendChild(toast);
      setTimeout(()=>toast.remove(), 3000);
    }

    function resetTimeline(){
      ['planner','executor','verifier'].forEach((a)=>{
        document.getElementById(a+'Box').className='timeline-agent-box';
        document.getElementById(a+'Status').textContent='⏳';
      });
      ['plannerTime','executorTime','verifierTime','plannerSteps','executorSteps','executorCache','verifierConfidence','totalPipelineTime'].forEach((id)=>{ const el=document.getElementById(id); if(el) el.textContent='--'; });
      document.getElementById('confidenceBarFill').style.width='0%';
    }

    function setAgentRunning(agentId){ document.getElementById(agentId+'Box').className='timeline-agent-box running'; document.getElementById(agentId+'Status').textContent='🔄'; }
    function setAgentComplete(agentId, ok=true){ document.getElementById(agentId+'Box').className='timeline-agent-box '+(ok?'success':'error'); document.getElementById(agentId+'Status').textContent=ok?'✅':'❌'; }

    function addEventLog(message, type=''){
      const log = document.getElementById('eventLog');
      const line = document.createElement('div');
      line.className = 'event-line ' + type;
      line.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
      log.appendChild(line);
      log.scrollTop = log.scrollHeight;
    }

    function updateConfidenceBar(score){
      const fill=document.getElementById('confidenceBarFill');
      fill.style.width = `${score}%`;
      fill.style.background = score>=80 ? '#3fb950' : (score>=60 ? '#d29922' : '#f85149');
    }

    function displayPlan(plan){
      const body=document.getElementById('planBody'); body.innerHTML='';
      const steps=(plan&&plan.steps)?plan.steps:[];
      steps.forEach((s)=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${s.step??''}</td><td>${s.tool??''}</td><td>${s.action??''}</td><td><code>${JSON.stringify(s.params??{})}</code></td>`; body.appendChild(tr); });
      document.getElementById('planCard').style.display='block';
    }

    function displayResult(result){ latestResult=result; document.getElementById('resultJson').textContent = JSON.stringify(result??{}, null, 2); document.getElementById('resultCard').style.display='block'; }

    async function runTask(){
      const task=document.getElementById('taskInput').value.trim();
      if(!task){ showToast('Please enter a task','error'); return; }

      const useCache=document.getElementById('useCache').checked;
      const parallel=document.getElementById('parallelExec').checked;
      const useStream=document.getElementById('useStream').checked;

      document.getElementById('runBtn').disabled=true;
      document.getElementById('runBtn').textContent='⏳ Running...';
      document.getElementById('eventLogCard').style.display='block';
      document.getElementById('timelineCard').style.display='block';
      document.getElementById('eventLog').innerHTML='';
      resetTimeline();
      pipelineStartTime = Date.now();

      if(useStream){ await runTaskStreaming(task, useCache, parallel); }
      else { await runTaskNormal(task, useCache, parallel); }

      document.getElementById('runBtn').disabled=false;
      document.getElementById('runBtn').textContent='🚀 Run Task';
    }

    async function runTaskStreaming(task, useCache, parallel){
      try{
        const response = await fetch('/task/stream',{method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({task,use_cache:useCache,parallel_execution:parallel})});
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while(true){
          const {done, value} = await reader.read();
          if(done) break;
          buffer += decoder.decode(value, {stream:true});

          let boundary = buffer.indexOf('\n\n');
          while(boundary !== -1){
            const raw = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);
            const lines = raw.split('\n').filter((l)=>l.startsWith('data: '));
            for(const line of lines){
              try{ handleStreamEvent(JSON.parse(line.slice(6))); }catch(_e){}
            }
            boundary = buffer.indexOf('\n\n');
          }
        }
      }catch(err){
        addEventLog('Stream error: ' + err.message, 'error');
        showToast('Streaming failed', 'error');
      }
    }

    function handleStreamEvent(data){
      switch(data.event){
        case 'task_received': addEventLog(`Task received [${data.task_id}]: ${data.task}`, 'planning'); break;
        case 'planning_start': plannerStartTime=Date.now(); setAgentRunning('planner'); addEventLog('🧠 Planner Agent starting...', 'planning'); break;
        case 'chain_detected': addEventLog('🔗 Task chain detected', 'planning'); break;
        case 'chain_split': addEventLog(`🔗 Split into ${data.count} sub-tasks`, 'planning'); (data.sub_tasks||[]).forEach((t,i)=>addEventLog(`   ${i+1}. ${t}`, 'planning')); break;
        case 'plan_ready':
          document.getElementById('plannerTime').textContent = `⏱ ${((Date.now()-plannerStartTime)/1000).toFixed(1)}s`;
          document.getElementById('plannerSteps').textContent = `📋 ${data.step_count} steps`;
          setAgentComplete('planner'); addEventLog(`✅ Plan ready: ${data.step_count} steps`, 'planning'); displayPlan(data.plan);
          executorStartTime = Date.now(); setAgentRunning('executor');
          break;
        case 'step_complete':
          addEventLog(`${data.success?'✅':'❌'} Step ${data.step}: ${data.tool}.${data.action}${data.from_cache?' 💾':''}${data.self_healed?' 🔧':''}`, data.from_cache?'cache':(data.self_healed?'healed':'executing'));
          break;
        case 'execution_complete':
          document.getElementById('executorTime').textContent = `⏱ ${((Date.now()-executorStartTime)/1000).toFixed(1)}s`;
          document.getElementById('executorSteps').textContent = `✅ ${data.steps_executed} done`;
          document.getElementById('executorCache').textContent = `💾 ${data.cache_hits} cached`;
          setAgentComplete('executor'); verifierStartTime=Date.now(); setAgentRunning('verifier'); addEventLog('🔍 Verifier Agent starting...', 'verifying');
          break;
        case 'verification_start': addEventLog('🔍 Verification in progress...', 'verifying'); break;
        case 'complete':
          const total=((Date.now()-pipelineStartTime)/1000).toFixed(1);
          document.getElementById('verifierTime').textContent = `⏱ ${((Date.now()-verifierStartTime)/1000).toFixed(1)}s`;
          document.getElementById('verifierConfidence').textContent = `📊 ${data.confidence_score||0}/100 (${data.confidence_grade||'N/A'})`;
          updateConfidenceBar(data.confidence_score||0);
          setAgentComplete('verifier');
          document.getElementById('totalPipelineTime').textContent = `Total pipeline: ${total}s`;
          addEventLog(`✅ Complete! Confidence: ${data.confidence_score||0}/100 in ${total}s`, 'complete');
          displayResult(data.result); refreshStats(); showToast(`Done! ${data.confidence_score||0}/100 confidence in ${total}s`, 'success');
          break;
        case 'error': addEventLog(`Error: ${data.message}`, 'error'); showToast(data.message || 'Task failed', 'error'); setAgentComplete('planner', false); break;
      }
    }

    async function runTaskNormal(task, useCache, parallel){
      try{
        addEventLog('Running task (non-streaming mode)...','planning');
        const response = await fetch('/task',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({task,use_cache:useCache,parallel_execution:parallel})});
        const data = await response.json();
        if(data.status==='error'){ addEventLog('Error: '+data.error,'error'); showToast(data.error,'error'); return; }
        displayPlan(data.plan); displayResult(data.result);
        const score=data.confidence_score||0; updateConfidenceBar(score);
        setAgentComplete('planner'); setAgentComplete('executor'); setAgentComplete('verifier');
        addEventLog(`Complete in ${(data.execution_time||0).toFixed ? data.execution_time.toFixed(1) : data.execution_time}s`, 'complete');
        refreshStats(); showToast('Task complete!','success');
      }catch(err){ addEventLog('Error: '+err.message,'error'); showToast('Request failed','error'); }
    }

    async function clearMemory(){ await fetch('/memory',{method:'DELETE'}); showToast('Memory cleared','success'); refreshStats(); }

    async function refreshStats(){
      const [health,cost,cache,history,memory] = await Promise.all([
        fetch('/health').then(r=>r.json()),
        fetch('/cost').then(r=>r.json()),
        fetch('/cache').then(r=>r.json()),
        fetch('/history').then(r=>r.json()),
        fetch('/memory').then(r=>r.json()),
      ]);

      document.getElementById('apiStatus').textContent = health.status === 'healthy' ? '🟢 Healthy' : '🔴 Unhealthy';
      document.getElementById('totalRequests').textContent = cost.total_requests || 0;
      document.getElementById('totalCost').textContent = `$${Number(cost.total_cost_usd || 0).toFixed(6)}`;
      const hits = Number(cache.hit_count || 0), misses = Number(cache.miss_count || 0), total = hits + misses;
      document.getElementById('cacheHitRate').textContent = `${total ? ((hits/total)*100).toFixed(1) : 0}%`;
      document.getElementById('memoryCount').textContent = `${memory.total_tasks || 0} tasks`;

      const costBody=document.getElementById('costBody'); costBody.innerHTML='';
      (cost.log||[]).forEach((row)=>{ const tr=document.createElement('tr'); tr.innerHTML=`<td>${row.agent||''}</td><td>${row.input_tokens||0}</td><td>${row.output_tokens||0}</td><td>$${Number(row.cost_usd||0).toFixed(6)}</td>`; costBody.appendChild(tr); });

      const historyBody=document.getElementById('historyBody'); historyBody.innerHTML='';
      (history.history||[]).forEach((row)=>{ const tr=document.createElement('tr'); tr.style.cursor='pointer'; tr.innerHTML=`<td>${row.task_id||''}</td><td>${(row.task||'').slice(0,48)}</td><td>${row.status||''}</td><td>${row.execution_time||0}s</td>`; tr.onclick=()=>{ if(row.plan) displayPlan(row.plan); if(row.result) displayResult(row.result); }; historyBody.appendChild(tr); });
    }

    updateClock(); setInterval(updateClock, 1000);
    refreshStats(); setInterval(refreshStats, 30000);
  </script>
</body>
</html>
    """
    return HTMLResponse(content=html)


_validate_environment_or_exit()


if __name__ == "__main__":
    print("🚀 Starting AI Operations Assistant API Server")
    print("📡 Dashboard: http://localhost:8000")
    print("📚 API Docs:  http://localhost:8000/docs")
    print("Press Ctrl+C to stop")
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="warning",
    )
