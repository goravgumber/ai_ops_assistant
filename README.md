# 🚀 AI Ops Assistant

> An intelligent terminal-style AI-powered operations assistant with multi-agent architecture, real-time tool execution, and web + CLI interfaces.

**🔗 Live Application:** [https://ai-ops-assistant-five.vercel.app/](https://ai-ops-assistant-five.vercel.app/)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Quick Start](#-quick-start)
- [Deployment](#-deployment)
- [API Documentation](#-api-documentation)
- [Example Commands](#-example-commands)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🧠 Overview

**AI Ops Assistant** simulates how engineers interact with systems — fast, structured, and command-driven. It combines autonomous agent reasoning with real-time tool execution to solve complex operational tasks.

### Core Philosophy

- **Autonomous**: Multi-agent system makes intelligent decisions
- **Reliable**: Validates results and enables self-healing
- **Extensible**: Easy to add new tools and integrations
- **User-Friendly**: Terminal-style interface mimics familiar workflows

---

## ✨ Features

### 🤖 Multi-Agent System

- **Planner Agent** → Analyzes tasks and creates execution plans
- **Executor Agent** → Performs actions using available tools with parallel execution
- **Verifier Agent** → Validates results and scores confidence
- **Memory Agent** → Maintains context and handles task chaining
- **Task Chain Processor** → Splits and orchestrates multi-step requests

### 💻 Dual Interfaces

- **🌐 Web App** → Terminal-style UI deployed on Vercel
- **⌨️ CLI** → Command-line interface for direct execution

### 🔗 Tool Integrations

- **🌦️ Weather API** → Real-time weather data and forecasts
- **📰 News API** → Latest news by category and keyword
- **🐙 GitHub API** → Repository search and trending discovery
- **🔍 Web Search** → General web search with links

### 🧠 Intelligent Capabilities

- ✅ **Task Chaining** → Process sequential multi-step requests
- ✅ **Caching** → Reduce redundant API calls and costs
- ✅ **Memory** → Maintain session context across requests
- ✅ **Self-Healing** → Retry failed steps with LLM adjustment
- ✅ **Cost Tracking** → Monitor LLM token usage and costs
- ✅ **Confidence Scoring** → Rate solution reliability

---

## 🏗️ Architecture

### System Design

```
User Input (Web/CLI)
    ↓
Task Chain Processor
    ↓
Planner Agent (LLM)
    ↓
Memory Agent (Context)
    ↓
Executor Agent (Parallel Tools)
    ↓
Tool Execution (APIs)
    ↓
Verifier Agent (Validation)
    ↓
Output with Scoring
```

### Directory Structure

```
ai_ops_assistant/
├── agents/              # Multi-agent system
│   ├── planner.py      # Task planning
│   ├── executor.py     # Tool execution
│   ├── verifier.py     # Result validation
│   ├── memory_agent.py # Context management
│   └── task_chain.py   # Multi-step orchestration
│
├── tools/              # External integrations
│   ├── weather_tool.py
│   ├── news_tool.py
│   ├── github_tool.py
│   └── web_search_tool.py
│
├── llm/                # Language model interface
│   └── client.py       # OpenAI integration with cost tracking
│
├── cache/              # Performance optimization
│   └── cache_manager.py # TTL-based caching
│
├── ui/                 # Terminal interface
│   └── terminal_ui.py
│
├── voice/              # Voice support (optional)
│   └── speech_handler.py
│
├── api_server.py       # FastAPI server
├── main.py             # CLI entry point
└── requirements.txt    # Python dependencies

frontend/              # React + Vite
├── src/
│   ├── components/    # React components
│   ├── hooks/         # Custom hooks
│   ├── services/      # API client
│   └── styles/        # CSS styling
├── public/
├── vite.config.js
└── package.json
```

---

## 🛠️ Tech Stack

### Backend

| Component     | Technology                   |
| ------------- | ---------------------------- |
| **Framework** | FastAPI 0.104.1              |
| **Server**    | Uvicorn                      |
| **LLM**       | OpenAI GPT-4 / GPT-3.5       |
| **Caching**   | cachetools (TTL)             |
| **APIs**      | OpenWeather, NewsAPI, GitHub |
| **Python**    | 3.10+                        |

### Frontend

| Component       | Technology            |
| --------------- | --------------------- |
| **Framework**   | React 18              |
| **Build Tool**  | Vite 4.4              |
| **Styling**     | CSS3 + Terminal Theme |
| **HTTP Client** | Fetch API             |

### Deployment

| Service      | Provider                         |
| ------------ | -------------------------------- |
| **Backend**  | Railway.app                      |
| **Frontend** | Vercel                           |
| **Domain**   | vercel.app (Railway handles API) |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- API Keys:
  - OpenAI (`OPENAI_API_KEY`)
  - OpenWeather (`OPENWEATHER_API_KEY`)
  - NewsAPI (`NEWSAPI_KEY`)
  - GitHub Token (`GITHUB_TOKEN`) — optional

### Backend Setup

```bash
# 1. Clone repository
git clone https://github.com/goravgumber/ai_ops_assistant.git
cd ai_ops_assistant

# 2. Install Python dependencies
cd ai_ops_assistant
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# Edit .env with your API keys

# 4. Run FastAPI server
uvicorn api_server:app --reload
# Server runs on http://localhost:8000
```

### Frontend Setup

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Configure environment (optional)
# Create .env.local for local development:
echo "VITE_API_URL=http://localhost:8000" > .env.local

# 4. Start dev server
npm run dev
# Frontend runs on http://localhost:3001
```

### Verify Installation

```bash
# Test backend health
curl http://localhost:8000/health

# Test a simple request
curl -X POST http://localhost:8000/planner \
  -H "Content-Type: application/json" \
  -d '{"task": "What is 2+2?"}'
```

---

## 📲 Deployment

### Backend Deployment (Railway)

1. **Connect GitHub** → Railway auto-detects Python project
2. **Environment Variables** → Set in Railway dashboard:
   ```
   OPENAI_API_KEY=sk-...
   OPENWEATHER_API_KEY=...
   NEWSAPI_KEY=...
   GITHUB_TOKEN=...
   ```
3. **Build Command** → `pip install -r requirements.txt`
4. **Start Command** → `uvicorn ai_ops_assistant.api_server:app --host 0.0.0.0 --port $PORT`
5. **Deploy** → Railway auto-deploys on push

**Public URL**: `https://aiopsassistant-production.up.railway.app` (auto-generated)

### Frontend Deployment (Vercel)

1. **Connect GitHub** → Vercel auto-detects Vite project
2. **Environment Variable**:
   ```
   VITE_API_URL=https://aiopsassistant-production.up.railway.app
   ```
3. **Build Command** → `npm run build`
4. **Output Directory** → `dist`
5. **Deploy** → Vercel auto-deploys on push

**Live URL**: [https://ai-ops-assistant-five.vercel.app/](https://ai-ops-assistant-five.vercel.app/)

---

## 🔌 API Documentation

### Core Endpoints

#### 1. Full Pipeline (Plan → Execute → Verify)

```http
POST /task
Content-Type: application/json

{
  "task": "Get weather in London",
  "use_cache": true,
  "parallel_execution": false
}
```

#### 2. Streaming Response

```http
POST /task/stream
Content-Type: application/json

{
  "task": "Your task here"
}
```

Returns: Server-Sent Events (SSE) with real-time updates

#### 3. Individual Agents

**Planner Only**

```http
POST /planner
{"task": "Analyze this request"}
```

**Executor Only**

```http
POST /executor
{"plan": {"steps": [...]}}
```

**Verifier Only**

```http
POST /verifier
{"plan": {...}, "results": {...}}
```

#### 4. System Endpoints

| Endpoint   | Method     | Description                     |
| ---------- | ---------- | ------------------------------- |
| `/health`  | GET        | System status and request count |
| `/cost`    | GET        | LLM cost report and statistics  |
| `/cache`   | GET/DELETE | Cache stats and clearing        |
| `/memory`  | GET/DELETE | Session memory and history      |
| `/history` | GET        | Previous tasks and results      |

---

## 💡 Example Commands

### Web Interface

Open [https://ai-ops-assistant-five.vercel.app/](https://ai-ops-assistant-five.vercel.app/) and type:

```
What's the weather in London?
```

```
Show me trending Python repositories
```

```
Get latest AI news
```

```
Plan and execute: check weather AND get news
```

### CLI Interface

```bash
python main.py

# Then type commands:
> What's 2+2?
> Who is the Prime Minister of India?
> Get weather for New York
```

### API Calls

```bash
curl -X POST https://aiopsassistant-production.up.railway.app/task \
  -H "Content-Type: application/json" \
  -d '{
    "task": "What is the current weather in Tokyo?",
    "use_cache": true
  }' | jq
```

---

## 🔒 Environment Variables

Create `.env` file in `ai_ops_assistant/`:

```env
# LLM Configuration
OPENAI_API_KEY=sk-your-key-here

# Tool APIs
OPENWEATHER_API_KEY=your-openweather-key
NEWSAPI_KEY=your-newsapi-key
GITHUB_TOKEN=your-github-token

# Optional
DEBUG=false
LOG_LEVEL=INFO
```

---

## 📊 Performance & Monitoring

### Cost Tracking

Track OpenAI token usage and costs in real-time:

- View endpoint: `GET /cost`
- See per-task and cumulative costs
- Monitor prompt vs completion tokens

### Caching Statistics

Check cache performance:

- View endpoint: `GET /cache`
- Clear cache: `DELETE /cache`
- Reduces redundant API calls

### Memory Management

Monitor session context:

- View endpoint: `GET /memory`
- Clear memory: `DELETE /memory`
- Maintain 10-task history by default

---

## 🤝 Contributing

Contributions welcome! To contribute:

1. **Fork** the repository
2. **Create feature branch**: `git checkout -b feature/amazing-feature`
3. **Commit changes**: `git commit -m 'Add amazing feature'`
4. **Push to branch**: `git push origin feature/amazing-feature`
5. **Open Pull Request**

### Areas for Contribution

- [ ] Additional tool integrations
- [ ] Enhanced UI/UX
- [ ] Performance optimization
- [ ] Test coverage
- [ ] Documentation

---

## 🚧 Roadmap

- [ ] User authentication system
- [ ] Persistent database for memory
- [ ] Docker containerization
- [ ] Analytics dashboard
- [ ] Advanced LLM orchestration
- [ ] Web hooks and integrations
- [ ] Rate limiting and quotas

---

## 📜 License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Gorav Gumber**

- GitHub: [@goravgumber](https://github.com/goravgumber)
- Website: [Portfolio](#)

---

## 🙏 Acknowledgments

- OpenAI for GPT models
- FastAPI and Vite communities
- Railway and Vercel for hosting

---

## 📞 Support

For issues, feature requests, or questions:

- 🐛 [Open an Issue](https://github.com/goravgumber/ai_ops_assistant/issues)
- 💬 [Start a Discussion](https://github.com/goravgumber/ai_ops_assistant/discussions)
- 📧 Email: [your-email@example.com](mailto:your-email@example.com)

---

<div align="center">

**⭐ If you find this useful, please star the repository! ⭐**

Made with ❤️ by Gorav Gumber

</div>
