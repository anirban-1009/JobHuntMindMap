# CLI Reference

The **Job Hunt Mindmap** tool can be run directly using the `mindmap` command (or `uv run mindmap`). Each command is designed to be part of a larger workflow, from discovering jobs to synchronizing them with your Obsidian vault.

## Installation

Install into your local environment or globally via `pipx`:

```bash
# Editable install for local development:
pip install -e .

# Or install globally with pipx:
pipx install .
```

## General Usage

```bash
mindmap [GLOBAL_OPTIONS] COMMAND [ARGS]...
```

### Global Options
- `-c, --config <path>`: Path to configuration YAML file (default: `config.yaml` or `MINDMAP_CONFIG` environment variable).
- `-v, --verbose`: Enable detailed DEBUG logging.
- `--version`: Show package version.
- `--help`: Show command documentation.

---

## Core Commands

### `init`
Scaffolds a new Job Hunt Mindmap workspace in the current directory, generating a starter `config.yaml` template, creating `data/` and `logs/` directories, and setting up a template `.env` file.

```bash
mindmap init [--force]
```
**Options:**
- `--force`: Overwrite existing `config.yaml` if it already exists.

### `check`
Validates your `config.yaml`, Obsidian vault path, candidate resume, and environment setup. Run this after `init` to ensure everything is configured properly.

```bash
mindmap check
```

### `login`
Launches a browser window for manual LinkedIn authentication. This saves your session cookies so that subsequent `search` and `scrape` commands can run headlessly.

```bash
mindmap login
```

### `search`
Discovers new job postings based on the keywords and locations defined in your `config.yaml`. This only finds the basic listing information (IDs and links).

```bash
mindmap search [--headless] [--external-only]
```
**Options:**
- `--headless`: Run browser without GUI.
- `--external-only`: Only search configured external job sites (e.g., job boards), skipping LinkedIn.

### `scrape`
Fetches the full job description and details for jobs found during the `search` phase.

```bash
mindmap scrape [JOB_ID] [OPTIONS]
```
**Options:**
- `--headless`: Run without a browser window.
- `--limit <int>`: Limit the number of jobs to process.
- `--force`: Ignore the database cache and re-scrape details.
- `--min-fast-score <int>`: Only scrape jobs that pass a basic keyword matching threshold (0-100).
- `--score`: Automatically run the AI scoring immediately after scraping.
- `--external-only`: Only scrape external site links.

### `refresh`
Re-scrapes details for existing jobs already in your database, updating stale postings or resolving missing information.

```bash
mindmap refresh [OPTIONS]
```
**Options:**
- `--headless`: Run browser headlessly.
- `--limit <int>`: Maximum number of jobs to refresh.
- `--score`: Perform LLM re-scoring after updating descriptions.
- `--unknown-only`: Only refresh jobs whose title or company is currently "Unknown".

### `score`
Ranks jobs against your resume using either your local (Ollama) or cloud (Gemini) LLM provider.

```bash
mindmap score [JOB_ID] [--all]
```
**Options:**
- `--all`: Score all jobs in the database that haven't been scored yet.
- `JOB_ID`: Score a specific job by its ID.

### `sync`
The "Mind Map Generator." This command exports your database (Jobs, Companies, Analysis) to your Obsidian vault. It automatically creates links between companies, connections, and jobs.

```bash
mindmap sync
```

### `sync-back`
Synchronizes changes made in Obsidian (like `#Status` tag updates or ticking the `applied: true` checkbox) back to the local database. This allows you to manage your application pipeline directly from Obsidian.

```bash
mindmap sync-back
```

---

## Networking & Referrals

### `network`
Finds professional connections from your LinkedIn export who work at a specific job's company.

```bash
mindmap network <JOB_ID>
```

### `network-all`
Scans all jobs in your database and identifies matching connections for every company.

```bash
mindmap network-all
```

### `refer`
Generates a personalized, concise LinkedIn referral request message using AI. It incorporates your skills and the specific job title.

```bash
mindmap refer <JOB_ID> [OPTIONS]
```
**Options:**
- `--name <text>`: Manually specify a person's name if not found in your network.
- `--max-chars <int>`: Set a character limit for the message (default: 200).
- *Output Example:* The tool shows the character count, e.g., `(158/190 chars)`.

---

## Utilities & Analysis

### `analyze-gaps`
Identifies common missing skills across high-scoring jobs. Helps you understand what to learn next or add to your resume. It also generates a detailed Markdown report with a gap table in your Obsidian vault's `Analysis/` folder.

```bash
mindmap analyze-gaps [--min-score <int>] [--tag <text>]
```
**Options:**
- `--min-score <int>`: Minimum relevance score to include in analysis (default: 0).
- `--tag <text>`: Filter analysis by a specific job specialization (e.g., `AI_ML`, `Backend`, `Python_Dev`).

*Output Example:* A table summarizing gaps for each job and an AI-generated improvement plan is saved as `Analysis/Gap Analysis - <Tag>.md`.

### `tailor`
Generates a job-optimized LaTeX resume PDF based on your master resume and the specific job description.

```bash
mindmap tailor <JOB_ID>
```

### `notify`
Sends an email digest of the top-ranked jobs found since the last notification.

```bash
mindmap notify [--min-score <int>]
```

### `test-ai`
Verifies your connection to the configured AI provider (Ollama or Gemini).

```bash
mindmap test-ai [--prompt <text>]
```

### `find`
Fast search across your entire Obsidian vault directly from the command line.

```bash
mindmap find <QUERY> [--semantic] [--limit <int>] [--reindex]
```
**Options:**
- `--semantic`: Use embedding-based semantic vector search instead of keyword FTS5.
- `--limit <int>`: Maximum number of results to display (default: 10).
- `--reindex`: Reindex modified vault notes before running the search.

### `prune`
Cleans up your Obsidian vault by removing Markdown files for jobs that are no longer present in your local database or were auto-rejected.

```bash
mindmap prune
```

---

## Company Evaluation & Outreach

### `evaluate-companies`
Evaluates and clusters all companies across discovered jobs and LinkedIn connections using the composite scoring model (45% Job Fit, 35% Company Domain Fit, 20% Network Leverage).

```bash
mindmap evaluate-companies
```

### `companies`
Lists scored and clustered companies with filtering and sorting options.

```bash
mindmap companies [OPTIONS]
```
**Options:**
- `--cluster [warm|direct|nurture|watchlist|all]`: Filter by action tier (e.g. `warm` for referral priority).
- `--domain <text>`: Filter by tech/domain cluster (e.g. `Generative AI`, `Enterprise`).
- `--min-score <int>`: Minimum company score (0-100).
- `--sort [score|jobs|network|name]`: Sort criteria (default: `score`).
- `--limit <int>`: Maximum number of companies to display (default: 25).

### `company`
Deep-dives into a specific company's dossier: displays company score, cluster, strategic action directive, all matching open jobs with direct apply links, and verified internal contacts classified by role (Recruiter/Talent, Engineering Manager/Lead, Peer Engineer).

```bash
mindmap company <COMPANY_NAME>
```


