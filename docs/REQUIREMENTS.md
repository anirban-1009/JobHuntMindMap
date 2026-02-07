 # Project Requirements: Job Hunt Mind Mapper

## Overview
A tool to visualize job opportunities and professional network connections within Obsidian, creating an interactive "mind map" of the job search process.

## Core Features

### 1. Job Discovery & Matching
- **Input Experience**: Ability to parse a user's resume (PDF/text) or LinkedIn profile to understand skills and experience.
- **Job Search**: Automated search for relevant job postings based on the user's profile.
  - *Source*: Primarily LinkedIn, potentially other boards (Indeed, Glassdoor).
  - *Filters*: Location, Remote/Hybrid, Salary, Company Size.
- **Relevance Scoring**: AI-based scoring of how well a job matches the user's experience.

### 2. Network Integration (LinkedIn)
- **Connection Import**: Import user's LinkedIn connections.
- **Company Matching**: Identify which connections work at companies with open relevant positions.
- **Connection Strength**: (Optional) Categorize connections by closeness or relevance to the target role.

### 3. Obsidian Integration (The "Mind Map")
- **Vault Structure**: Automatically generate a structured Obsidian Vault.
  - `Jobs/`: Individual notes for each job posting.
  - `Companies/`: Notes for companies, linking to their jobs and your connections there.
  - `People/`: Notes for connections, linking to their current companies.
- **Graph Visualization**: Leverage Obsidian's Graph View to show clusters of opportunities.
- **Canvas Generation**: Programmatically create Obsidian Canvas files to visualize specific search, e.g., "Top 10 Remote Roles".
- **Status Tracking**: Use Obsidian properties (YAML frontmatter) to track application status (`To Apply`, `Applied`, `Interviewing`, `Offer`).

### 4. Email Notifications
- **Daily Digest**: Send a summary email of new high-match job opportunities.
- **Content**: Include Job Title, Company, Match Score, Connection highlights, and direct Application Links.
- **Configuration**: User can configure email settings (SMTP server or local client integration).

### 5. User Workflow
1.  **Configure**: Set up resume/profile and search criteria.
2.  **Fetch**: Run the tool to scrape/fetch jobs and connections.
3.  **Generate**: Tool creates/updates the Obsidian Vault.
4.  **Explore**: User opens Obsidian to visually explore opportunities and see "who do I know at Google?".
5.  **Track**: User updates status in Obsidian; tool respects these manual updates on next run.

### 5. Cost Constraint (Strict)
- **Free to Use**: The tool must rely entirely on free tools and strictly avoid any paid APIs or services.
- **Local/Free AI**: Any AI/ML features (like resume parsing or relevance scoring) must use:
  - **Local Models**: Open-source models (e.g., Ollama, spacy).
  - **Gemini API**: The free tier of Google's Gemini API for advanced reasoning without cost.

### 6. Technical Constraints & Considerations
- **LinkedIn Access**: Direct API access is typically paid. We will use:
  - **Browser Automation**: (Selenium/Playwright) to "scrape" data as a logged-in user.
  - **Data Exports**: Parse the official GDPR data export (CSV/HTML) provided by LinkedIn.
- **Privacy**: Data stored locally in Markdown files.
- **Extensibility**: Modular design to add more job boards later.
