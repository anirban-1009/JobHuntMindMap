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
*   [Features & Requirements](docs/REQUIREMENTS.md) - What the tool does.
*   [Mind Map Structure](docs/MIND_MAP_STRUCTURE.md) - How the Obsidian vault is organized to visualize your search.
*   [Architecture](docs/ARCHITECTURE.md) - How the system is built.
*   [Data Processing](docs/DATA_PROCESSING.md) - The logic behind job matching and scoring.
*   [Development Plan](docs/DEVELOPMENT_PLAN.md) - Phased implementation guide with task lists.
*   [Deployment Strategy](docs/DEPLOYMENT.md) - How to run and schedule the tool locally.
*   [Code of Conduct](docs/CODE_OF_CONDUCT.md) - Design patterns (SOLID, OOP) and engineering standards.

## Quick Start 🚀

1.  **Set up**: [Follow the First Run Guide](docs/FIRST_RUN.md) to install dependencies and configure API keys.
2.  **Login**: `python -m src.main login` (logs you into LinkedIn).
3.  **Search**: `python -m src.main search` (finds new jobs).
4.  **Scrape**: `python -m src.main scrape` (fetches details).
5.  **Score**: `python -m src.main score --all` (ranks jobs with AI).
6.  **Visualize**: Open your vault in Obsidian!

## How to Run

The tool is designed to be run via a CLI. After installation, you can use the following commands:

-   `python -m src.main check`: Validate config and environment.
-   `python -m src.main login`: Manual LinkedIn login to save session.
-   `python -m src.main search`: Discovery phase - finds job IDs.
-   `python -m src.main scrape`: Extraction phase - gets job descriptions.
-   `python -m src.main score`: AI phase - calculates relevance.
-   `python -m src.main network`: Network phase - finds connections for a job.
-   `python -m src.main notify`: Alert phase - sends email digest.

For advanced usage and automation, see the [Deployment Strategy](docs/DEPLOYMENT.md).

## Tech Stack
-   **Core**: Python 3.13+
-   **Visualization**: Obsidian (Markdown + Canvas)
-   **Data Sources**: LinkedIn (via automation/export)
-   **Matching**: NLP/LLM for resume analysis
