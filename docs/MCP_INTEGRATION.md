# MCP Server Integration Guide

This project implements the Model Context Protocol (MCP), allowing it to be used as a tool-set for AI agents (like Claude Desktop). This transforms the Job Hunt Mindmap from a CLI tool into an active agentic pipeline.

## 🚀 Setup & Installation

### 1. Prerequisites
- [Claude Desktop](https://claude.ai/download) installed.
- `uv` installed on your machine.
- A valid `config.yaml` and resume PDF in the project root.

### 2. Configuration
To connect the server to Claude, you must edit your `claude_desktop_config.json` file.

**File Locations:**
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the following entry to the `mcpServers` section:

```json
{
  "mcpServers": {
    "job-hunt-mindmap": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/anirban/Personal/mindmap",
        "run",
        "src/mcp_server.py"
      ],
      "env": {
        "MINDMAP_CONFIG_PATH": "/Users/anirban/Personal/mindmap/config.yaml",
        "MINDMAP_MCP_KEY": "your-secret-access-key",
        "GEMINI_API_KEY": "your-google-api-key"
      }
    }
  }
}
```

### 🔑 Security & Access Control
For security, the MCP server requires an `access_key` for every tool call. 
1. Set the `MINDMAP_MCP_KEY` environment variable in the config above to a secret string of your choice.
2. When prompting Claude, it must provide this key as an argument to the tool.

## 🛠 Available Tools

The server exposes the following tools to the AI agent:

| Tool | Description | Key Arguments |
| :--- | :--- | :--- |
| `search_jobs` | Finds new postings using dynamic keyword expansion. | `access_key` (req), `headless`, `external_only` |
| `scrape_and_score` | Extracts full JDs and ranks them against your resume. | `access_key` (req), `limit`, `force` |
| `sync_to_obsidian` | Pushes all processed data to your Obsidian vault. | `access_key` (req) |
| `analyze_career_gaps` | Identifies missing skills and generates a growth plan. | `access_key` (req), `min_score` |

## 🤖 Example Agent Workflow

You can now give Claude high-level goals instead of running CLI commands:

> *"Search for new AI Engineering roles in Bengaluru, scrape the top 5, and sync them to my Obsidian vault. Use my access key `your-secret-access-key`."*

Claude will then:
1. Call `search_jobs` $\rightarrow$ identify new leads.
2. Call `scrape_and_score` $\rightarrow$ analyze the best matches.
3. Call `sync_to_obsidian` $\rightarrow$ update your knowledge base.

## ⚠️ Troubleshooting
- **Session Issues**: If the browser fails to launch, ensure you have run `uv run mindmap login` once in the terminal to handle initial authentication.
- **Logs**: MCP server logs are routed through the standard project logger. Check `logs/mindmap.log` for detailed execution traces.
