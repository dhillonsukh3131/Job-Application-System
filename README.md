# Job-Application-System

This project automates AI internship discovery, ranking, and tracking so you do not manually search and maintain spreadsheets.

## What this can do

- Search AI internships globally.
- Catch **keyword variants** (not just “AI internship”) such as:
  - machine learning intern
  - AI automation engineer
  - applied scientist intern
  - NLP/LLM/data science internships
- Score and prioritize internships using your skills and location preferences.
- Track each job in CSV with company, deadline, location, description, link, score, and timestamps.
- Optionally sync all rows to Google Sheets.
- Run continuously on a schedule.

## 1) How keyword coverage works

The tool uses three keyword groups:

1. `ai_keywords` (AI domain terms)
2. `role_variants` (job-title variants)
3. `internship_terms` (intern/internship style terms)

You can add or remove terms at runtime:

```bash
python ai_internship_multi_agent.py \
  --name "Your Name" \
  --skills "Python,Machine Learning" \
  --extra-keywords "ai platform intern,ai solutions engineer,mlops intern" \
  --exclude-keywords "data science"
```

Preview active keywords:

```bash
python ai_internship_multi_agent.py \
  --name "Your Name" \
  --skills "Python" \
  --print-keywords
```

## 2) How to run and test (step-by-step)

### Step A — run once

```bash
python ai_internship_multi_agent.py \
  --name "Your Name" \
  --skills "Python,Machine Learning,LLMs,PyTorch" \
  --regions "United States,Europe,Asia,Remote" \
  --max-results 50 \
  --tracker-csv data/ai_internships_tracker.csv
```

### Step B — verify output

- Check terminal output for ranked matches.
- Open `data/ai_internships_tracker.csv` in Excel.
- Confirm columns include `company`, `title`, `location`, `deadline`, `description`, `url`, `score`, and `matched_keywords`.

### Step C — continuous updates (automation)

```bash
python ai_internship_multi_agent.py \
  --name "Your Name" \
  --skills "Python,Machine Learning,LLMs,PyTorch" \
  --interval-minutes 60 \
  --cycles 24 \
  --tracker-csv data/ai_internships_tracker.csv
```

That runs every 60 minutes for 24 cycles.

## 3) Google Sheets sync (optional)

1. Open Google Sheets → Extensions → Apps Script.
2. Paste `scripts/google_sheets_webhook.gs`.
3. Deploy it as a web app.
4. Set webhook URL:

```bash
export GOOGLE_SHEETS_WEBHOOK_URL="https://script.google.com/macros/s/your-id/exec"
```

5. Run script with the same `--tracker-csv`; it will also push to Sheets.

## 4) Optional broader coverage

For broader web discovery (Greenhouse/Lever/Workday pages), set:

```bash
cp .env.example .env
```

and add your `SERPAPI_API_KEY`.

## Notes

- Deadline extraction is heuristic and depends on listing text.
- You can keep extending `--extra-keywords` over time as you discover new role names.
