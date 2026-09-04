# Model Context Protocol (MCP) Setup for Dexter

This directory contains MCP configurations for connecting **Claude Code**, **Claude Desktop**, and **Antigravity** directly to your **Obsidian Vault**.

---

## 1. Using with Claude Code / Claude Desktop

`core/vault_bridge.py` is a plain importable Python class, not an MCP server — it
has no `__main__` entry point and speaks no MCP protocol, so pointing an MCP client
at `python -m Dexter.core.vault_bridge` will not work. The path that actually works
today:

1. Install the **Local REST API with MCP** community plugin in Obsidian (see
   `OBSIDIAN_SETUP.md`, section 2.3). It ships its own built-in MCP server — no
   custom Python server code needed.
2. Copy the plugin's bearer token and port, then add it to your MCP client config:

```json
{
  "mcpServers": {
    "obsidian-vault": {
      "transport": "http",
      "url": "http://localhost:27123/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

Claude Code can add this directly from the CLI instead of hand-editing config:

```
claude mcp add --transport http obsidian-vault http://localhost:27123/mcp \
  --header "Authorization: Bearer YOUR_TOKEN"
```

This scopes MCP access to the vault content itself (notes, tasks, frontmatter) via
the plugin's semantic vault API — not raw filesystem access to `DEV/`.

---

## 2. Using with Google Antigravity

Google Antigravity natively executes filesystem tools, custom skills, and subagents across your workspace.

To enable Antigravity to treat the Obsidian Vault as primary storage:
- Keep the `04_Memory_&_Context/` folder updated with user directives.
- Tasks created in `02_Tasks_&_Workflows/Active/` are immediately actionable by Antigravity agents.
- Agent run logs are automatically archived into `05_Logs_&_Telemetry/Antigravity_Runs/`.

---

## 3. Filesystem MCP server (fallback, scope it deliberately)

If a client can't do HTTP-transport MCP, the generic filesystem server is a fallback
— but only point it at the vault, never at the whole `DEV/` tree, since that would
also expose `dontshare.py`/`.env` secret files in `AGENTS/`/`BOTS/`:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "C:/Users/ixis1/Desktop/Dexter"
      ]
    }
  }
}
```
