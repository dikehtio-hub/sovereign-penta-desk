# 🧠 Dexter: Second-Brain Engine & Agent Orchestration

Welcome to **Dexter**, a unified local-first agentic operating system combining **Google Gemini**, **Google Antigravity**, **Anthropic Claude**, and **Claude Code** into a single cohesive control center powered by **Obsidian**.

Dexter is split across two locations by design:
- **This folder (`DEV/Dexter/`)** — the engine: process control for the agents/bots under `DEV/AGENTS/`, task tracking, model dispatch, memory sync.
- **`Desktop/Dexter/`** — the actual Obsidian vault, the second brain itself: notes, decisions, dashboards. The engine reads and writes there directly; it isn't duplicated inside this project.

---

## ⚡ Key Highlights

- 🗂️ **Obsidian Command Center:** Open `Desktop/Dexter/` directly in Obsidian to get an instant visual dashboard (`Dashboard.md`), visual workflow canvas, and automated task queue.
- 🎛️ **Agent/Bot Process Control:** `python -m core.cli start/stop/status <id>` starts and stops the real trading agents/bots listed in `registry.yaml`, with real health-checking (not just cached state) and full run logs written into the vault.
- 🪐 **Google Antigravity Integration:** IDE-native autonomous planning, subagents, and skills orchestration.
- 🤖 **Claude & Claude Code Integration:** Terminal-level coding agent, architectural reasoning, and MCP-powered vault manipulation.
- ♊ **Google Gemini Integration:** 1M–2M token context window for full-codebase analysis, multimodal inputs, and research synthesis.
- 🧩 **Extensible Roles:** Drop a new file in `core/roles/` to add a capability (e.g. a market watcher) without touching the core.
- 🧠 **Cross-Model Persistent Memory:** Unified user directives, preferences, and workspace facts synced across all models.

---

## 🚀 Quickstart Guide

### Step 1: Environment Setup
1. Copy the example environment file:
   ```powershell
   Copy-Item configs/.env.example configs/.env
   ```
2. Add your API keys to `configs/.env`:
   - `GEMINI_API_KEY` (from [Google AI Studio](https://aistudio.google.com/))
   - `ANTHROPIC_API_KEY` (from [Anthropic Console](https://console.anthropic.com/))

3. Install Python dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

### Step 2: Open the Vault
1. Open **Obsidian**.
2. Click **"Open folder as vault"** and select:
   ```
   C:\Users\ixis1\Desktop\Dexter
   ```
3. Open `Dashboard.md` for your HUD or the canvas file for the visual map.
4. *(Recommended)* Follow the [Obsidian Setup Guide](file:///c:/Users/ixis1/Desktop/DEV/Dexter/OBSIDIAN_SETUP.md) to install Dataview and Templater.

---

## 🎛️ Controlling Agents & Bots

From `DEV/Dexter/`:

```powershell
python -m core.cli list                 # every registered agent/bot + live state
python -m core.cli start arbitrage-agent
python -m core.cli status               # health-checked, not just cached
python -m core.cli stop arbitrage-agent
```

Nothing runs automatically — every start is a command you type. `enabled: true` in
`registry.yaml` only means *allowed to be started*, not auto-run. See `registry.yaml`
for the full list and how to register a new agent/bot.

---

## 🗒️ Task Tracking

```powershell
python -m core.cli task add "Review funding agent leverage settings" --priority high
python -m core.cli task list
python -m core.cli task done T-0001
```

Tasks are plain notes in `Desktop/Dexter/02_Tasks_&_Workflows/`, addressable by a
short id (`T-0001`) so you don't need the full filename.

---

## 🛠️ Dispatching Tasks to a Model

```powershell
# Auto-route a prompt to the best model
python -m core.dispatcher "Summarize all files in 04_Memory_&_Context"

# Run a terminal coding task with Claude Code
python -m core.dispatcher "Refactor nice_funcs.py" --engine claude-code

# Run a large-context multimodal query with Gemini
python -m core.dispatcher "Analyze full project logs" --engine gemini

# Execute a structured Obsidian task file
python -m core.dispatcher "02_Tasks_&_Workflows/Active/TASK_001_Setup_Dexter_Ecosystem.md"
```

---

## 📚 Documentation Links
- [System Architecture](file:///c:/Users/ixis1/Desktop/DEV/Dexter/ARCHITECTURE.md)
- [Obsidian Setup Guide](file:///c:/Users/ixis1/Desktop/DEV/Dexter/OBSIDIAN_SETUP.md)
- [Agent Fleet Registry](file:///c:/Users/ixis1/Desktop/Dexter/01_Agents/Agent_Registry.md)
- [MCP Configurations](file:///c:/Users/ixis1/Desktop/DEV/Dexter/mcp/README.md)
