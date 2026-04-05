# Job-Application-System

A lightweight **multi-agent AI internship finder** that searches globally and ranks internship opportunities based on your skills and preferences.

## What this project now includes

- **Scout Agent**: discovers internships from multiple sources (Remotive + optional SerpAPI Google results).
- **Analyst Agent**: scores opportunities for AI relevance, internship fit, skill overlap, location/remote preference, visa hints, and freshness.
- **Curator Agent**: de-duplicates and returns the top opportunities.
- **Outreach Agent**: generates a reusable message template for roles you like.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### Run the global AI internship search

```bash
python ai_internship_multi_agent.py \
  --name "Your Name" \
  --skills "Python,Machine Learning,LLMs,PyTorch" \
  --regions "United States,Europe,Asia,Remote" \
  --visa-required \
  --max-results 20 \
  --save-json internship_results.json
```

## How it works

1. **ScoutAgent** fetches job posts asynchronously from public job sources.
2. **AnalystAgent** scores each post:
   - AI keywords (AI/ML/NLP/LLM/Data Science)
   - internship-level signal (intern/internship/graduate)
   - your skills
   - region match and remote support
   - visa/sponsorship hints
   - posting freshness
3. **CuratorAgent** removes duplicates and keeps top `N` matches.

## Recommended next upgrades

- Add additional providers (LinkedIn Jobs API alternatives, Greenhouse/Lever board harvesters).
- Add LLM-powered extraction of required skills and responsibilities from each listing.
- Add automated application package generation (tailored resume bullets + cover letters).
- Add scheduling/cron to refresh results daily.

## Notes

- `SERPAPI_API_KEY` is optional but strongly recommended for wider global coverage.
- Without a SerpAPI key, the script still runs using Remotive data.
