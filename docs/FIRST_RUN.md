# First Run Guide 🚀

Follow these steps to set up the **Job Hunt Mind Mapper** for the first time.

## 1. Prerequisites

Before you begin, ensure you have the following installed:
- **Python 3.13+**
- **Obsidian** (to view the mind map)
- **Chrome or Firefox** (for the automated browser parts)
- **LaTeX** (for resume generation; see below)

## 2. Setting Up the Environment

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/anirban-1009/JobHuntMindMap.git
    cd JobHuntMindMap
    ```

2.  **Create a virtual environment**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  **Install dependencies and package**:
    ```bash
    pip install -e .
    playwright install chromium
    ```
    *(Or install globally as a tool via `pipx install .`)*

## 2.5. Install LaTeX (for Resume Generation)

The `tailor` command compiles a tailored resume PDF using `pdflatex`, so a LaTeX distribution is required.

### macOS
Install the lightweight **BasicTeX** distribution via Homebrew:
```bash
brew install --cask basictex
```

> **Note:** BasicTeX is a minimal TeX Live distribution. If the resume template requires a package that isn't included, install it with `tlmgr` (e.g. `sudo tlmgr install <package>`). For a full distribution, use `brew install --cask mactex` instead.

### Windows
Install **MiKTeX** from [miktex.org](https://miktex.org/download).

### Linux
Install TeX Live via your package manager, e.g.:
```bash
sudo apt-get install texlive-latex-base texlive-latex-extra texlive-fonts-recommended
```

## 3. Workspace Initialization & Configuration

1.  **Initialize your workspace**:
    ```bash
    mindmap init
    ```
    This automatically creates `config.yaml` from template, creates `data/` and `logs/` directories, and generates a `.env` file.

2.  **Edit `config.yaml`**:
    - Update `obsidian.vault_path` to point to where you want the Obsidian vault generated.
    - Update `user.full_name` and `user.email`.
    - Place your resume PDF in `data/resume.pdf` (or update `user.resume_path`).
    - Adjust `search.keywords` and `search.location` for your target jobs.

## 4. Get Your API Keys

### Google Gemini Key (Required for AI Scoring)
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Create a new API key.
3. Add it to your `.env` file (`GEMINI_API_KEY=your_key_here`) or in `config.yaml` under `ai.gemini.api_key`.

### LinkedIn Session (Required for Scraping)
LinkedIn uses strict anti-bot measures. We use your real session cookies to safely fetch data.

1. Run the login command:
   ```bash
   mindmap login
   ```
2. A browser window will open. **Log in to LinkedIn manually**.
3. Once you're on the LinkedIn feed, the tool will automatically detect the login, save your session to `data/session.json`, and close the browser.

## 5. Validating Setup

Run the check command to verify your configuration, Obsidian vault path, resume PDF, and environment:
```bash
mindmap check
```
*(Tip: Add `-v` or `--verbose` for detailed debug logging: `mindmap -v check`)*

## 6. Test AI Connection

Verify that your Gemini API key and AI provider are connected:
```bash
mindmap test-ai
```

---

Next Step: [Deployment Guide](DEPLOYMENT.md) for daily usage and scheduling.
