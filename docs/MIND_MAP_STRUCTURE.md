# Obsidian Vault Structure: The Job Hunt Mind Map

This document outlines the specific file structure and linking strategy to create a powerful, interconnected "mind map" of your job search within Obsidian.

## Core Entities & Relationships

The power of the mind map comes from the links between these three core entities:

1.  **Jobs** (`Jobs/`)
    - _Links to_: `[[Company Name]]`, `[[Skill]]`
    - _Tags_: `#job`, `#status/to_apply`, `#remote`, `#high_priority`
    - _Properties_: `Salary`, `Applied Date`, `Source URL`

2.  **Companies** (`Companies/`)
    - _Links to_: `[[Industry]]`, `[[Location]]`
    - _Backlinks from_: Jobs at this company, People working here.
    - _Tags_: `#company`, `#target_company`, `#action_cluster`, `#domain_cluster`
    - _Properties_: `Score`, `Action Cluster`, `Domain Cluster`, `Target Tier`, `Job Count`, `Connection Count`

    Company notes are now **enriched with an evaluation dossier** (see [Data Processing](DATA_PROCESSING.md)):
    - **Score** (0-100): Composite of Job Fit (45%), Company Domain Fit (35%), and Network Leverage (20%).
    - **Action Cluster**: `Warm Outreach`, `Direct Apply`, `Network Nurture`, or `Watchlist` — determines the action checklist rendered in the note.
    - **Domain Cluster**: e.g. `Generative AI & LLMs`, `Core ML & Computer Vision`, `Enterprise AI & Cloud Platforms`, `FinTech & E-Commerce AI`, `Healthcare & BioTech AI`, or `General Tech & Services`.
    - **Score Breakdown**: Individual sub-scores for each weighted component.
    - **Action Checklist**: A concrete next-step checklist generated from the action cluster.
    - **Open Opportunities**: Each listed job now includes its match score and direct apply link.
    - **Network & Referral Contacts**: Connections are tagged by role type — `[TALENT]` (recruiters/sourcers), `[ENGINEERING_LEAD]` (managers/directors/CTOs), `[PEER_ENGINEER]` (AI/ML/software engineers) — with the highest-leverage contacts listed first.

- _Links to_: `[[Current Company]]`, `[[Target Role]]` (if they are in a similar role)
- _Tags_: `#connection`, `#network/strong`, `#recruiter`
- _Properties_: `Last_Contacted`, `Latest_Update`

## Folder Hierarchy

```
MindMap_Vault/
├── 00_Dashboard.canvas      # Visual overview of top opportunities
├── Jobs/                    # Individual job postings
│   ├── Senior Python Dev at Spotify.md
│   └── ML Engineer at Netflix.md
├── Companies/               # Company profiles
│   ├── 00_Company_Clusters.md  # Hub: all companies grouped by action tier
│   ├── Spotify.md
│   └── Netflix.md
├── People/                  # Your network
│   ├── Jane Doe.md          # Works at Spotify
│   └── Recruiter Mike.md    # Recruiter at Netflix
├── Assets/                  # Resume versions, cover letters
│   └── Resume_2024.pdf
├── Analysis/                # Skill gaps & Retrospectives
│   ├── Missing_Skills.md
│   └── Rejected_Applications.md
└── Templates/               # Templates for new notes
    ├── Job_Template.md
    └── Meeting_Note.md
```

### Company Clusters Hub (`Companies/00_Company_Clusters.md`)

Generated during `sync` (after `evaluate-companies` has populated the database), this hub organizes every evaluated company into the four strategic action tiers:

- **🔥 Warm Outreach (Referral Priority)** — strong role fit **and** verified connections. Request an internal referral before applying.
- **⚡ Direct Apply & Cold Outreach** — high job fit but no direct internal network. Apply directly and cold-message the team.
- **🌱 Network Nurture** — connections exist, but no urgent high-matching role open right now. Keep in touch.
- **📋 Watchlist** — lower match or exploratory companies to monitor periodically.

Each tier is a table with company score, job counts (high-match in parentheses), connection counts (key contacts in parentheses), domain cluster, and the recommended action.

## Graph Visualization Strategy

### 1. The "Opportunity Cluster"

When filtering the graph for `#job` and `#status/to_apply`, you will see clusters around specific companies.

- **Visual**: A large node for `[[Spotify]]` connected to 3 job nodes and 2 person nodes (`[[Jane Doe]]`).
- **Insight**: "I have 2 connections at Spotify where there are 3 open roles. This is a high-priority target."

### 2. The "Skill Gap" Analysis

Create notes for skills (`Skills/Python.md`, `Skills/React.md`).

- Link jobs to required skills.
- **Visual**: See which skill nodes have the most connections to high-value jobs.
- **Insight**: "React is required by 80% of the jobs I'm interested in, but I don't have it on my resume."

## Automated Canvas Generation

The tool can generate `.canvas` files for specific views:

- **"Warm Leads" Canvas**: Automatically places `[[Company]]` cards in the center, surrounded by `[[Job]]` cards on one side and `[[Person]]` cards on the other, for companies where you have connections.
- **"Application Pipeline" Canvas**: Columns for `To Apply`, `Applied`, `Interviewing`, `Offer`—moving job cards between columns updates their status property.

## Note Templates

### Job Note Template

```markdown
---
tags:
  - job
  - status/to_apply
company: "[[Spotify]]"
location: "Remote"
salary: "$150k - $180k"
posted_date: 2023-10-27
url: "https://..."
match_score: 85
---

# Senior Python Developer at [[Spotify]]

**Connections at Company:**

- [[Jane Doe]] (Engineering Manager)
- [[John Smith]] (Alumni)

## Description

...

## My Fit

- ✅ Python API Development
- ❌ GraphQL experience (Need to brush up)

## Action Items

- [ ] Message [[Jane Doe]] about the role
- [ ] Tailor resume
- [ ] Apply
```
