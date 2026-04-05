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

### Step A.1 — no-network verification (recommended first)

```bash
python ai_internship_multi_agent.py \
  --name "Your Name" \
  --skills "Python,Machine Learning,LLMs,PyTorch" \
  --tracker-csv data/ai_internships_tracker.csv \
  --demo-mode
```

This runs against built-in demo internships so you can verify scoring and CSV updates even if APIs are unavailable.

### Step B — verify output

- Check terminal output for ranked matches.
- Open `data/ai_internships_tracker.csv` in Excel.
- Confirm columns include `company`, `title`, `location`, `deadline`, `description`, `url`, `score`, and `matched_keywords`.

### Step B.1 — run automated tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

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

### Quick verification for Google Sheets sync

```bash
python ai_internship_multi_agent.py \
  --name "Your Name" \
  --skills "Python,Machine Learning,LLMs,PyTorch" \
  --tracker-csv data/ai_internships_tracker.csv \
  --demo-mode \
  --sheets-webhook-url "https://script.google.com/macros/s/your-id/exec"
```

If webhook deployment is correct, your Google Sheet should receive/update rows.

## 4) Optional broader coverage

For broader web discovery (Greenhouse/Lever/Workday pages), set:

```bash
cp .env.example .env
```

and add your `SERPAPI_API_KEY`.

## Notes

- Deadline extraction is heuristic and depends on listing text.
- You can keep extending `--extra-keywords` over time as you discover new role names.

## 5) Run 24/7 on an always-on VM (recommended)

If you want this to run while you sleep, deploy on a machine that stays online.

### Option A: `systemd` timer (recommended on Linux VM)

Files provided:
- `deploy/systemd/ai-internships.service`
- `deploy/systemd/ai-internships.timer`
- `scripts/run_ai_tracker.sh`

Commands:

```bash
sudo cp deploy/systemd/ai-internships.service /etc/systemd/system/
sudo cp deploy/systemd/ai-internships.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ai-internships.timer
sudo systemctl status ai-internships.timer
```

Check latest run logs:

```bash
journalctl -u ai-internships.service -n 100 --no-pager
```

### Option B: cron (simple alternative)

Use the provided example in `deploy/cron/ai_internships_cron.txt`:

```bash
crontab -e
```

Paste the line from that file and save.
