# 🔍 Competitor Intelligence Bot

**Portfolio project — Product Marketing Manager**

Automated competitor tracking system that monitors messaging, pricing, and positioning changes weekly — no more manual scraping.

## What it does

- Tracks headline, CTA, and subheadline changes on competitor landing pages
- Monitors pricing changes across plans
- Detects high-severity positioning shifts automatically
- Generates weekly change reports with PMM-level analysis notes

## Live demo

> Deploy link (HuggingFace Spaces): _add after deploy_

## Tech stack

- **Python** — scraping pipeline (BeautifulSoup, Playwright)
- **SQLite** — snapshot storage with hash-based diff engine
- **Streamlit** — dashboard UI
- **GitHub Actions** — weekly automation scheduler

## Screenshots

### Overview Dashboard
Snapshot of all tracked competitors with rating, free tier status, and alert count.

### Changes Timeline
All detected changes with severity badges and PMM analysis notes.

### Competitor Detail
Week-by-week breakdown of every field tracked per competitor.

## How to run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Project structure

```
├── app.py                  # Streamlit dashboard
├── mock_data.json          # 4 weeks of demo data
├── competitor_intelligence.ipynb  # Colab pipeline notebook
└── requirements.txt
```

## Background

Built as part of a PMM portfolio to demonstrate:
- Systems thinking applied to competitive intelligence
- Workflow automation replacing manual research
- Product-led insights surfaced to marketing teams
