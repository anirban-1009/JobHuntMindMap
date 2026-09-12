# Data Processing Strategy: Intelligent Job Hunt

This document details the algorithms and logic used to process job data and match it against your experience.

## 1. Resume Parsing & Profile Analysis

### Input Processing

The system accepts a resume (PDF/Text) or LinkedIn profile export.

- **Tool**: `pypdf` for PDFs, `beautifulsoup` for LinkedIn HTML exports.
- **Extraction**:
  - _Hard Skills_: Python, Docker, AWS, React, etc.
  - _Experience Level_: Years of experience based on job history dates.
  - _Role Titles_: Senior Backend Engineer, Tech Lead, etc.

### Profile Vectorization & Matching (Advanced)

Option to use:

- **Local LLMs**: (e.g., Ollama, Llama.cpp) for privacy-first semantic matching.
- **Gemini API (Free Tier)**: For high-quality reasoning and semantic matching without cost (within rate limits).
  This allows for "soft skill" matching and understanding nuanced job requirements beyond simple keyword hits.

## 2. Job Listing Analysis

### Requirement Extraction

When a job description is fetched:

- **Keyword Extraction**: Identify key technologies and soft skills.
- **Role Classification**: Determine seniority (Junior, Mid, Senior, Lead) and domain (Backend, Frontend, Fullstack, DevOps).
- **Location Constraints**: Identify Remote, Hybrid, On-site requirements.

### Relevance Scoring

Calculate a `match_score` (0-100) for each job:

- **Keyword Overlap**: `(Matching Skills / Total Required Skills) * Weight`
- **Title Match**: Bonus points if current/past titles align with job title.
- **Experience Match**: Does the job require `5+ years` and you have `7`? (Pass/Fail or weighted score).
- **Network Boost**: Add points if you have 1st or 2nd-degree connections at the company.

## 3. LinkedIn Connection Intelligence

### Network Graph Building

- **Company Mapping**: Normalize company names from connections to match job listings (e.g., `Google Inc.` -> `Google`).
- **Role Relevance**: Identify connections in relevant roles (e.g., Engineers, Managers, Recruiters) vs. unrelated roles.
- **Connection Strength**: Prioritize people you've interacted with (if message history is available) or those with stronger ties.

## 4. Company Evaluation & Clustering

Beyond scoring individual jobs, the tool **evaluates and clusters companies** to prioritize where to apply and who to reach out to first. Run `uv run mindmap evaluate-companies` to score every company with active jobs or network connections, then `uv run mindmap companies` / `uv run mindmap company <NAME>` to browse the results.

### Composite Company Score (0-100)

Each company is scored as a weighted composite of three components (`src/core/company_scorer.py`):

| Component                                  | Weight | What it measures                                                                                                                                                                     |
| :----------------------------------------- | :----: | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Job Opportunity Quality & Role Match**   |  45%   | Highest relevance score among open jobs, plus a density bonus (up to +15 pts) for multiple high-match (≥70) openings                                                                 |
| **Company Profile & Strategic Domain Fit** |  35%   | Alignment of the company's mission/domain with AI/ML/LLM focus (keyword analysis of titles, industries, and job descriptions), plus a baseline boost for configured target companies |
| **Network Leverage**                       |  20%   | Presence of high-leverage contacts: Recruiters/Talent (40 pts), Engineering Managers/Leads (35 pts), Peer Engineers (15 pts each, max 30), others (5 pts each, max 15)               |

Target companies (from `search.external_sites` or an explicit `search.target_companies` list) start with a high company-fit baseline (92) and are tagged `Target` tier; all others are `Standard`.

### Action Clusters (Outreach Playbook)

Each company is assigned to one of four strategic action tiers (`src/core/company_clusterer.py`), based on whether it has high-match jobs and/or network leverage:

1.  **Warm Outreach** — high job fit **and** connections. Recommended action: request an internal referral from the top key contact before applying.
2.  **Direct Apply** — high job fit but **no** network. Recommended action: apply directly and cold-message the hiring manager/technical recruiter.
3.  **Network Nurture** — connections but no urgent high-match role. Recommended action: informational chat / stay top-of-mind.
4.  **Watchlist** — neither. Monitor the career page for new openings.

### Domain Clusters

Companies are also classified into a tech/domain cluster from their name, industries, and job postings: `Generative AI & LLMs`, `Core ML & Computer Vision`, `Enterprise AI & Cloud Platforms`, `FinTech & E-Commerce AI`, `Healthcare & BioTech AI`, or `General Tech & Services` (fallback).

### Connection Role Classification

`NetworkGraphBuilder.classify_role()` tags each connection at a company by outreach leverage:

- `talent` — Recruiters, sourcers, HR/talent partners (fastest referral path).
- `engineering_lead` — Engineering managers, leads, directors, CTOs, founders (hiring decision makers).
- `peer_engineer` — AI/ML engineers, data scientists, software engineers (peer referrals).
- `other` — Other business functions.

### Persistence & Output

- Evaluations are stored in the `companies` table of `data/jobs.db` (score, clusters, job/connection counts, target tier, outreach tracking fields, and the full scoring breakdown as JSON).
- `sync` renders this into each `Companies/<Name>.md` note (score breakdown, action checklist, scored jobs with apply links, role-tagged contacts) and generates the `Companies/00_Company_Clusters.md` hub note grouping companies by action tier.

## 5. Automation Workflow

1.  **Ingest Profile**: Run once to build the "User Model".
2.  **Search Loop**:
    - Query job boards for "Python Developer".
    - Filter results (Location, Date Posted).
    - Fetch full descriptions for top targets.
3.  **Score & Rank**: Apply the matching logic.
4.  **Visualize**: Output results to Obsidian, grouped by score.
    - _Top Matches_ get prominent placement in `Dashboard.canvas`.
    - _Matches with Connections_ get highlighted.
