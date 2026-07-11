# 🔍 Competitor Intelligence Bot
### Automated Competitive Positioning Tracker for Product Analytics Tools

> *Built as a PMM portfolio project — replacing 4 hours of manual research with a fully automated weekly intelligence pipeline.*

---

## 🎯 Problem Statement

Product Marketing Managers spend 3–5 hours every week manually tracking competitor websites, pricing pages, and review platforms — screenshot by screenshot, tab by tab. By the time insights reach the team, they're already outdated.

This project automates the entire workflow: from data collection to scoring to actionable A/B test variants — running every week without human intervention.

---

## 🚀 Live Demo

**👉 [View the app](https://your-app-link.streamlit.app)** ← replace after deploy

---

## 💡 What It Does

### 1. Real-time Data Collection (4 sources)
Automatically scrapes 5 Product Analytics competitors every week:

| Source | What it collects |
|---|---|
| Landing page | Headline, subheadline, CTA |
| Pricing page | Plan names, prices, GTM model (PLG vs Sales-led) |
| G2 reviews | Rating, review count |
| Meta Ad Library | Active ad count, ad themes |

**Competitors tracked:** Amplitude · Mixpanel · PostHog · Heap · Pendo

### 2. Automated Change Detection
Hash-based diff engine compares this week's snapshot vs last week. Detects changes in:
- Messaging (headline, CTA pivots)
- Pricing (plan changes, price increases)
- Ad volume (budget signal)

### 3. Scoring Engine — 6 PMM Criteria
Every competitor is automatically scored 0–10 across:

| Criteria | What it measures |
|---|---|
| **Clarity** | Does the headline explain what the product does? |
| **Value Prop** | Specific benefits vs generic feature claims |
| **CTA Strength** | Action-oriented language, free trial signal |
| **Social Proof** | G2 rating + review volume |
| **Pricing Transparency** | Public pricing vs "contact sales" |
| **Audience Clarity** | PM/Growth-specific language in copy |

### 4. A/B Test Generator
Based on competitive analysis, generates 2 landing page variants:
- **Variant A (Follow the Leader):** Adapts the top-scoring competitor's messaging structure to your product
- **Variant B (Contrarian):** Identifies overused category words → generates opposing positioning

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│  Layer 1 — Collection (Google Colab)                │
│  landing.py · pricing.py · reviews.py · ads.py      │
└──────────────────┬──────────────────────────────────┘
                   │ real-time scrape
┌──────────────────▼──────────────────────────────────┐
│  Layer 2 — Storage                                  │
│  SQLite · hash engine · change history log          │
└──────────────────┬──────────────────────────────────┘
                   │ diff detection
┌──────────────────▼──────────────────────────────────┐
│  Layer 3 — Analysis                                 │
│  scoring engine · messaging diff · ad intelligence  │
└──────────────────┬──────────────────────────────────┘
                   │ export live_data.json
┌──────────────────▼──────────────────────────────────┐
│  Layer 4 — Output (Streamlit · HuggingFace)         │
│  Overview · Leaderboard · Timeline · A/B Generator  │
└─────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Tools |
|---|---|
| Data collection | Python · requests · BeautifulSoup |
| Storage | SQLite · hashlib (MD5 diff engine) |
| Analysis | Pandas · rule-based scoring |
| Pipeline | Google Colab · Google Drive |
| Frontend | Streamlit |
| Deploy | Streamlit Community Cloud |

---

## 📁 Project Structure

```
competitor-intelligence/
├── app.py                        # Streamlit dashboard (5 pages)
├── competitor_intel_v2.ipynb     # Google Colab pipeline (13 cells)
├── mock_data.json                # Fallback demo data (4 weeks)
├── live_data.json                # Real-time data from Colab (auto-updated)
├── requirements.txt
└── README.md
```

---

## 🔄 How the Automation Works

```
Every Monday 8am
      │
      ▼
Open Colab → Run Cell 10 (pipeline)
      │
      ├── Scrape 5 competitors × 4 sources = 20 data points
      ├── Compare with last week's hashes
      ├── Score each competitor across 6 criteria
      └── Generate A/B variants
      │
      ▼
Run Cell 13 → Export live_data.json
      │
      ▼
Upload to GitHub → Streamlit auto-reloads
```

**Time investment after setup: ~5 minutes/week** (vs 3–5 hours manual)

---

## 📊 App Pages

| Page | What you see |
|---|---|
| **Overview** | Snapshot of all competitors: score, rating, GTM model, active ads |
| **Score Leaderboard** | Ranked by total score · breakdown per criteria |
| **Changes Timeline** | All detected changes with severity badges and PMM analysis notes |
| **Competitor Detail** | Deep dive per competitor: positioning history, score breakdown |
| **A/B Generator** | Input your product → get 2 ready-to-test landing page variants |

---

## 🏃 Run Locally

```bash
git clone https://github.com/your-username/competitor-intelligence
cd competitor-intelligence
pip install -r requirements.txt
streamlit run app.py
```

---

## 🗓️ Roadmap

- [x] Real-time scraping pipeline (4 sources)
- [x] Hash-based change detection
- [x] 6-criteria scoring engine
- [x] A/B variant generator (rule-based)
- [ ] Anthropic Claude API integration for smarter variant generation
- [ ] Meta Ad Library deeper analysis
- [ ] Slack/email alert when high-severity change detected
- [ ] Add custom competitor URL input (Version 2)
- [ ] GitHub Actions for fully automated weekly run

---

## 👤 About This Project

Built by a Product Owner / PMM with background in:
- B2B SaaS product marketing
- Go-to-market strategy
- Competitive intelligence
- Workflow automation

This project demonstrates the intersection of **PMM domain knowledge** and **automation thinking** — not just knowing what to track, but building systems that track it automatically.

---

## 📬 Contact

- LinkedIn: [your-linkedin]
- Portfolio: [your-portfolio]
