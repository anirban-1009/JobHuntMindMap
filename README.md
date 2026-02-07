# Job Hunt Mind Mapper

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

## Getting Started (Planned)
1.  **Configure**: Set up your profile and search criteria in `config.yaml`.
2.  **Run**: Execute the script to fetch jobs and connections.
3.  **Explore**: Open the generated Vault in Obsidian and start navigating your opportunities.

## Tech Stack
-   **Core**: Python 3.13+
-   **Visualization**: Obsidian (Markdown + Canvas)
-   **Data Sources**: LinkedIn (via automation/export)
-   **Matching**: NLP/LLM for resume analysis
