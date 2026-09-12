# Job Hunt Mind Mapper

![Coverage](coverage.svg)

**Job Hunt Mind Mapper** is a Python-based tool designed to transform your job search into a visual, interactive mind map within Obsidian. It leverages your professional experience and LinkedIn network to surface and prioritize relevant opportunities.

## What is it?

Instead of tracking applications in endless spreadsheets, this tool generates a dynamic **knowledge graph** of your job hunt.

- **Find Jobs**: Automates the search for roles that match your skills and experience.
- **Visualize Connections**: See who you know at target companies directly alongside job listings.
- **Email Alerts**: Receive daily digests of top job matches directly to your inbox.
- **Manage Workflow**: Use Obsidian's Kanban or Canvas features to track applications from "To Apply" to "Offer".

## Documentation

- [Features & Requirements](docs/REQUIREMENTS.md) - What the tool does.
- [CLI Reference](docs/CLI_REFERENCE.md) - Detailed guide for all command-line tools.
- [Mind Map Structure](docs/MIND_MAP_STRUCTURE.md) - How the Obsidian vault is organized to visualize your search.
- [Architecture](docs/ARCHITECTURE.md) - How the system is built.
- [Data Processing](docs/DATA_PROCESSING.md) - The logic behind job matching and scoring.
- [Vault Search](docs/VAULT_SEARCH.md) - Full-text search over the Obsidian vault via SQLite FTS5.
- [Development Plan](docs/DEVELOPMENT_PLAN.md) - Phased implementation guide with task lists.
- [Deployment Strategy](docs/DEPLOYMENT.md) - How to run and schedule the tool locally.
- [Code of Conduct](docs/CODE_OF_CONDUCT.md) - Design patterns (SOLID, OOP) and engineering standards.

## Quick Start 🚀

1. **Install**:
   ```bash
   pip install -e .
   playwright install chromium
   ```
   *(Or install standalone with `pipx install .`)*
2. **Initialize**: `mindmap init` (scaffolds `config.yaml`, `data/`, and `.env`).
3. **Configure**: [Follow the First Run Guide](docs/FIRST_RUN.md) to set your keywords, resume, and API keys.
4. **Validate**: `mindmap check` (verifies environment, vault path, and keys).
5. **Login**: `mindmap login` (saves your LinkedIn session).
6. **Search & Scrape**: `mindmap search && mindmap scrape` (finds & fetches job details).
7. **Score**: `mindmap score --all` (ranks jobs with AI).
8. **Visualize**: `mindmap sync` then open your Obsidian vault!

## How to Run

The application is controlled via the `mindmap` command:

```bash
mindmap [GLOBAL_OPTIONS] COMMAND [ARGS]...
```

**Global Options:**
- `-c, --config <path>`: Custom configuration file (default: `config.yaml` or `$MINDMAP_CONFIG`).
- `-v, --verbose`: Enable detailed DEBUG logging.
- `--version`: Show installed version.

**Core Commands:**
- `mindmap init`: Scaffold a new workspace with default configuration and folders.
- `mindmap check`: Validate configuration and environment readiness.
- `mindmap login`: Manual LinkedIn login to save session cookies.
- `mindmap search`: Discovery phase - find new job IDs.
- `mindmap scrape`: Extraction phase - get job descriptions.
- `mindmap score`: AI evaluation - calculate relevance against your resume.
- `mindmap network`: Network phase - map connections for a job or company.
- `mindmap notify`: Alert phase - send job digest email.
- `mindmap sync`: Sync jobs, companies, and people into Obsidian.
- `mindmap sync-back`: Pull status edits made in Obsidian back into SQLite.
- `mindmap evaluate-companies`: Score and cluster companies (fit + domain + network leverage).
- `mindmap companies`: Filter and list ranked companies.
- `mindmap company <NAME>`: Deep-dive a company's jobs, verified contacts, and outreach plan.
- `mindmap tailor <JOB_ID>`: Generate a tailored resume PDF for a specific job.
- `mindmap find <QUERY>`: Search the Obsidian vault (keyword or `--semantic`).

For detailed documentation of every command and flag, see the [CLI Reference](docs/CLI_REFERENCE.md).

## Tech Stack

- **Core**: Python 3.13+
- **Visualization**: Obsidian (Markdown + Canvas)
- **Data Sources**: LinkedIn (via automation/export)
- **Matching**: NLP/LLM for resume analysis

## Checkout

- https://x.com/AIPandaX/status/2025907777986867656
