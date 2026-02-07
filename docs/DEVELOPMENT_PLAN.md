# Development Plan: Job Hunt Mind Mapper

## Phase 1: Foundation & Data Ingestion
**Goal:** Set up the project and get user data (Resume + Connections) into the system.

- [x] **Task 1.1**: Project Initialization
    - [x] Set up `pyproject.toml` with dependencies (`pypdf`, `pandas`, `pyyaml`, `playwright`, `google-generativeai`).
    - [x] Create `src/` directory structure (`ingest`, `core`, `generator`, `utils`).
    - [x] Create `Dockerfile` with system dependencies (Python, Playwright Browsers, TexLive for LaTeX).
    - [x] Define `config.yaml` structure for user inputs.
- [x] **Task 1.2**: Resume Parsing
    - [x] Implement `src/ingest/resume_parser.py`.
    - [x] Extract text from PDF using `pypdf`.
    - [x] Create a `ResumeParser` interface for extensibility.
    - [x] Write unit tests with sample PDFs.
    - [x] (Advanced) Use Gemini/LLM to structure the resume into a JSON profile.
- [x] **Task 1.3**: Network Ingestion
    - [x] Implement `src/ingest/linkedin_parser.py`.
    - [x] Parse LinkedIn Data Export (CSV) to get connections + companies.
    - [x] Clean and normalize company names.

## Phase 2: Job Discovery (The Scraper)
**Goal:** Automate fetching relevant job listings from LinkedIn (via Browser).

- [ ] **Task 2.1**: Browser Automation Setup
    - Set up Playwright with a `BrowserManager` class.
    - Handle LinkedIn Login (manual first run to save cookies/state).
- [ ] **Task 2.2**: Job Search Implementation
    - Internal logic to construct search URLs based on config (location, keywords).
    - Scrape search results (Title, Company, Link, ID).
- [ ] **Task 2.3**: Job Details Extraction
    - Visit individual job URLs.
    - Extract full description, posted date, and metadata.
    - Save raw job data to a temporary JSON/Cache (to avoid re-scraping).

## Phase 3: Intelligence & Matching
**Goal:** Use AI to score jobs and link them to your network.

- [ ] **Task 3.1**: AI Engine Integration
    - Implement `src/core/llm_client.py`.
    - Support Google Gemini (Free Tier) and Ollama.
- [ ] **Task 3.2**: Relevance Scorer
    - Create prompt for "Resume vs Job Description" analysis.
    - Output: Score (0-100), key matching skills, missing skills, reasoning.
- [ ] **Task 3.3**: Network Graph Builder
    - Logic to match specific job companies with user's connection companies.
    - Logic to track "Last Contacted" and recent achievements.
- [ ] **Task 3.4**: Gap Analysis (Feedback Loop)
    - Logic to aggregate missing skills from High-Match jobs.
    - Logic to track "Rejected" status and prompt (or deduce) improvement areas.

## Phase 4: Artifact Generation (Obsidian & Resume)
**Goal:** Generate the "Mind Map" vault and tailored application materials.

- [ ] **Task 4.1**: Obsidian Template Implementation
    - Create Jinja2 templates for `Job.md`, `Company.md`, `Person.md`.
- [ ] **Task 4.2**: Vault/File Manager
    - Logic to create folders and update Markdown files.
- [ ] **Task 4.3**: Canvas Dashboard
    - Generate `Dashboard.canvas` JSON.
- [ ] **Task 4.4**: Resume Tailoring Engine
    - Create a `.tex` master template.
    - Implement logic to use Gemini to rewrite summary/skills for a specific job.
    - Compile customized PDF using `pdflatex`.

## Phase 5: Notifications, Deployment & Polish
**Goal:** Make the tool robust, easy to run, and schedule.

- [ ] **Task 5.1**: Email Notification System
    - Implement `src/notification/email_service.py`.
    - Generate HTML digest of new high-scoring jobs.
- [ ] **Task 5.2**: Deployment Packaging
    - Create `Dockerfile` for containerized execution.
    - Write `scripts/run_daily.sh` for cron jobs.
    - Add `setup.py` or `pyproject.toml` scripts for easy installation.
- [ ] **Task 5.3**: Documentation & Instructions
    - Update `README.md` with "How to Run".
    - Add "First Run" guide (getting Cookie for LinkedIn, getting Gemini Key).
