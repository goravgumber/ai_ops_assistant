# 🚀 AI Ops Assistant

A terminal-style AI-powered operations assistant with multi-agent architecture, real-time tools, and web + CLI interfaces.

## 🧠 Overview

**AI Ops Assistant** is designed to simulate how engineers interact with systems — fast, structured, and command-driven.

It combines:
* 🤖 **Multi-agent reasoning**
* ⚙️ **Tool execution**
* 🌐 **API integrations**
* 💻 **Terminal-style UI (CLI + Web)**

---

## ✨ Features

### 🧩 Multi-Agent System
* **Planner** → Breaks tasks into steps.
* **Executor** → Performs actions.
* **Verifier** → Validates results.

### 💻 Dual Interface
* **Terminal-based (CLI)**
* **Web app** styled like a hacking terminal.

### 🔗 Tool Integrations
* 🌦️ **Weather API**
* 📰 **News API**
* 🐙 **GitHub API**

### 🧠 Smart Capabilities
* Task chaining
* Memory handling
* Result validation
* Confidence scoring
* 🎙️ **Voice Ready** (Scaffolded)

---

## 🏗️ Architecture

```text
User Input
    ↓
Planner Agent
    ↓
Executor Agent
    ↓
Tools (APIs)
    ↓
Verifier Agent
    ↓
Final Output


ai_ops_assistant/
│
├── agents/
│   ├── planner.py
│   ├── executor.py
│   ├── verifier.py
│   ├── memory_agent.py
│   └── task_chain.py
│
├── llm/
│   ├── client.py
│   └── cache_manager.py
│
├── tools/
│   ├── weather_tool.py
│   ├── news_tool.py
│   ├── github_tool.py
│   └── web_search_tool.py
│
├── ui/
│   └── terminal_ui.py
│
├── voice/
│   └── speech_handler.py
│
├── api_server.py
├── main.py
├── requirements.txt
└── README.md

frontend/
│
├── src/
│   ├── components/
│   ├── hooks/
│   ├── services/
│   └── styles/
│
├── public/
├── index.html
└── vite.config.js


⚙️ Setup (Local)
🔹 1. Clone Repo
git clone [https://github.com/goravgumber/ai_ops_assistant.git](https://github.com/goravgumber/ai_ops_assistant.git)
cd ai_ops_assistant

🔹 2. Install Backend
pip install -r requirements.txt
🔹 3. Setup Environment
cp .env.example .env

Add your keys:

OPENROUTER_API_KEY=

OPENWEATHER_API_KEY=

NEWSAPI_KEY=

GITHUB_TOKEN=

🔹 4. Run Backend
python main.py
OR

uvicorn api_server:app --reload
🔹 5. Run Frontend
Bash
cd frontend
npm install
npm run dev

🌐 Deployment
🔹 Backend (Railway)
uvicorn api_server:app --host 0.0.0.0 --port $PORT

🔹 Frontend (Vercel)
Framework: Vite

Output: dist

🎯 Example Commands
"Who is the Prime Minister of India?"

"Get current weather in Ajmer"

"Latest tech news"

"Check GitHub repo status"

🔮 Future Improvements
🔐 Authentication system
🧠 Advanced memory (persistent DB)
🐳 Docker deployment
📊 Dashboard & analytics
🤖 Better LLM orchestration

🤝 Contributing
Contributions are welcome! Feel free to open issues or submit PRs.

📜 License
MIT License

👨‍💻 Author
Gorav Gumber
GitHub: https://github.com/goravgumber
