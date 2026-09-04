#  Obsidian Setup & Configuration Guide for Dexter

This guide walks you through configuring Obsidian as the primary human-AI control center for your second brain.

---

## 1. Opening the Vault in Obsidian

1. Launch **Obsidian**.
2. On the Obsidian Vault switcher screen, click **"Open folder as vault"** (or in the bottom-left vault switcher icon, choose *Open another vault* -> *Open folder as vault*).
3. Navigate to and select:
   ```
   C:\Users\ixis1\Desktop\Dexter
   ```
4. Click **Open**. Your complete Dexter vault will load with `Dashboard.md`, canvas, templates, and categorized folders.

---

## 2. Recommended Obsidian Community Plugins

To get the full interactive experience (automated task tables, template shortcuts, and AI chat directly inside Obsidian), install the following community plugins:

### 📊 1. Dataview (Highly Recommended)
- **Why:** Dynamically powers the task tables, agent fleet status, and log query feeds in `Dashboard.md`.
- **Installation:**
  1. Open Obsidian Settings -> **Community Plugins** -> Turn off *Restricted mode*.
  2. Click **Browse** and search for `Dataview`.
  3. Click **Install** then **Enable**.
  4. In Dataview settings, ensure *Enable JavaScript Queries* and *Enable Inline Queries* are turned on.

### 📝 2. Templater
- **Why:** Automatically applies frontmatter, timestamps, and formatting when creating new task notes or daily notes from `Templates/`.
- **Installation:**
  1. Search for `Templater` in Community Plugins -> Install & Enable.
  2. In Templater Settings, set **Template folder location** to `Templates`.

### 🌐 3. Local REST API (Optional for HTTP Agent Bridges)
- **Why:** Exposes a secure local REST API allowing Python scripts or external agents to manipulate notes over HTTPS — and ships its own built-in MCP server, which is the recommended way to connect Claude Code/Claude Desktop (see `mcp/README.md`).
- **Installation:**
  1. Search for `Local REST API` in Community Plugins -> Install & Enable.
  2. Copy your API Key to `DEV/Dexter/configs/.env` under `OBSIDIAN_API_KEY`.

### 🤖 4. Copilot / Smart Connections (Optional for In-Vault LLM Chat)
- **Why:** Chat with your Gemini or Claude models directly in an Obsidian sidebar tab.
- **Installation:**
  1. Search for `Copilot` or `Smart Connections`.
  2. Enter your `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` in the plugin settings.

---

## 3. Using the Interactive Visual Canvas

1. In the Obsidian file explorer, click on the canvas file at the vault root.
2. This displays the visual relationship between:
   - You (The Operator)
   - The Obsidian Vault
   - Google Antigravity
   - Claude & Claude Code
   - Google Gemini
   - Shared Persistent Memory
3. You can double click anywhere on the canvas to add project mindmaps, pin active task cards, or link live notes.

---

## 4. Key Workflows

### Creating a New Task:
1. Create a note in `02_Tasks_&_Workflows/Active/` using `Templates/Task_Template.md`, or run `python -m core.cli task add "<title>"` from `DEV/Dexter/`.
2. Fill in the objective and assign an agent (`gemini`, `antigravity`, `claude-code`).
3. Run the dispatcher via terminal, or let Antigravity / Claude Code process it.
4. When finished, the agent automatically moves the task to `Completed/` and appends its execution summary.

### Starting/Stopping an Agent or Bot:
1. From `DEV/Dexter/`, run `python -m core.cli list` to see everything registered.
2. `python -m core.cli start <id>` / `stop <id>` — nothing runs unless you type this yourself.
3. Check `05_Logs_&_Telemetry/<id>_Runs/` in the vault for the start/stop history.
