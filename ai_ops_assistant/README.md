# AI Operations Assistant

A production-ready scaffold for an AI-driven operations assistant with agent, tool, API, and voice interfaces.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Create your environment file:
   ```bash
   cp .env.example .env
   ```
3. Run the application:
   ```bash
   python main.py
   ```

## Agents

- **Planner Agent** (`agents/planner.py`): Breaks requests into actionable, ordered steps.
- **Executor Agent** (`agents/executor.py`): Executes the planned tasks through available tools.
- **Verifier Agent** (`agents/verifier.py`): Validates outcomes for correctness, safety, and completeness.

## Tools

- **GitHub Tool** (`tools/github_tool.py`): Intended for repository insights, issues, PRs, and workflow status.
- **Weather Tool** (`tools/weather_tool.py`): Intended for weather conditions and forecast retrieval.
- **News Tool** (`tools/news_tool.py`): Intended for headline and article aggregation.

## Voice Commands

Voice support is scaffolded under `voice/speech_handler.py`.

Planned flow:
- Capture microphone input via speech recognition.
- Convert text responses to speech output.
- Route spoken commands through the same agent pipeline as terminal input.

## FastAPI Endpoint Usage

API server scaffolding is located in `api_server.py`.

Planned usage pattern:
1. Start the API server with Uvicorn:
   ```bash
   uvicorn api_server:app --reload
   ```
2. Send requests from clients to defined assistant endpoints.
3. Use JSON payloads for command submission and structured responses.
