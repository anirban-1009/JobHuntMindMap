# Deployment Plan: Local & Portable

## Philosophy
Since this is a personal productivity tool that manages sensitive data (resume, connections) and integrates with a local Obsidian vault, the "Deployment" is primarily about **Local Execution** and **Portability**.

We will not be deploying to a cloud server (AWS/Heroku) because:
1.  **LinkedIn Security**: Cloud IP addresses are easily flagged by LinkedIn's anti-bot systems. Running locally uses your residential IP and existing browser cookies.
2.  **Privacy**: Your personal data stays on your machine.
3.  **Obsidian Integration**: The tool needs direct write access to your local filesystem where your Vault lives.

> 💡 **New to the tool?** Follow the [First Run Guide](FIRST_RUN.md) before attempting deployment.

## Deployment Strategy

### 1. Docker Container (Primary)
The recommended way to run the tool to ensure all dependencies (Browsers, LaTeX, Python) are isolated and correct.

- **Image**: `mindmap:latest` (built from `Dockerfile`)
- **Run Command**:
  ```bash
  docker run -d \
    -v $(pwd)/config:/app/config \
    -v $(pwd)/data:/app/data \
    -v /Users/me/Obsidian/MindMap:/vault \
    --name job-mindmap \
    mindmap:latest
  ```
- **Volume Mounting**:
    - `/vault`: Maps to your local Obsidian Vault (Read/Write).
    - `/config`: Maps to your local config (resume, settings).
- **Networking**: Uses host networking or a residential proxy to avoid bot detection.

### 2. Local Python Environment (Development)
Useful for development or debugging.
- **Setup**: `pip install .`
- **Execution**: `mindmap run`

## Daily Scheduler (Mac/Linux)
To automate the daily email digest and vault update:

1.  **Create a Wrapper Script** (`run_mindmap.sh`):
    ```bash
    #!/bin/bash
    cd /path/to/mindmap
    source .venv/bin/activate
    python src/main.py --mode=daily
    ```
2.  **Add to Crontab**:
    - Run `crontab -e`
    - Add: `0 9 * * * /path/to/run_mindmap.sh` (Runs every day at 9:00 AM)

## Prerequisites Checklist
- [ ] Python 3.13+ installed.
- [ ] Obsidian installed.
- [ ] LaTeX installed (`mactex` on Mac, `miktex` on Windows) for resume generation.
- [ ] Chrome/Firefox installed (for Playwright).
