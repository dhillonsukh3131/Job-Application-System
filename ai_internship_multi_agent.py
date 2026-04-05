#!/usr/bin/env python3
"""Multi-agent system to discover and track AI internships globally."""

from __future__ import annotations

import argparse
import asyncio
import csv
import dataclasses
import datetime as dt
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_AI_KEYWORDS = [
    "artificial intelligence",
    "ai",
    "machine learning",
    "ml",
    "deep learning",
    "nlp",
    "llm",
    "generative ai",
    "computer vision",
    "data science",
    "ai automation",
    "ai agent",
    "autonomous systems",
]

ROLE_VARIANTS = [
    "ai intern",
    "machine learning intern",
    "ml intern",
    "ai engineer intern",
    "machine learning engineer intern",
    "ai automation engineer",
    "ai automation intern",
    "data science intern",
    "nlp intern",
    "llm intern",
    "genai intern",
    "research intern ai",
    "applied scientist intern",
    "ai research assistant",
]

INTERNSHIP_TERMS = [
    "intern",
    "internship",
    "graduate internship",
    "summer internship",
    "off-cycle internship",
]


@dataclasses.dataclass
class CandidateProfile:
    full_name: str
    skills: list[str]
    preferred_regions: list[str]
    ai_keywords: list[str]
    role_variants: list[str]
    internship_terms: list[str]
    visa_required: bool = False
    remote_ok: bool = True
    max_results: int = 50


@dataclasses.dataclass
class Internship:
    title: str
    company: str
    location: str
    url: str
    source: str
    description: str = ""
    deadline: str = "Unknown"
    posted_at: str | None = None
    score: float = 0.0
    reasons: list[str] = dataclasses.field(default_factory=list)
    matched_keywords: list[str] = dataclasses.field(default_factory=list)


class ScoutAgent:
    def __init__(self, profile: CandidateProfile) -> None:
        self.profile = profile

    async def run(self) -> list[Internship]:
        tasks = [self._search_with_serpapi(), self._search_with_remotive()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        internships: list[Internship] = []
        for result in results:
            if isinstance(result, Exception):
                continue
            internships.extend(result)
        return internships

    async def _search_with_serpapi(self) -> list[Internship]:
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key:
            return []

        role_query = " OR ".join(f'"{k}"' for k in self.profile.role_variants[:8])
        ai_query = " OR ".join(f'"{k}"' for k in self.profile.ai_keywords[:8])
        query = (
            f"({role_query}) OR (({ai_query}) AND (intern OR internship)) "
            "site:greenhouse.io OR site:lever.co OR site:workdayjobs.com"
        )
        params = {"engine": "google", "q": query, "api_key": api_key, "num": 70}
        url = "https://serpapi.com/search?" + urllib.parse.urlencode(params)
        data = await asyncio.to_thread(_fetch_json, url)

        items: list[Internship] = []
        for row in data.get("organic_results", []):
            title = row.get("title", "Unknown role")
            link = row.get("link", "")
            snippet = row.get("snippet", "")
            if not link:
                continue

            combined = f"{title} {snippet}"
            if not _is_ai_internship_match(combined, self.profile):
                continue

            items.append(
                Internship(
                    title=title,
                    company=_extract_company(title),
                    location=_extract_location(snippet),
                    url=link,
                    source="serpapi",
                    description=snippet,
                    deadline=_extract_deadline(snippet),
                    matched_keywords=_collect_keyword_hits(combined, self.profile),
                )
            )
        return items

    async def _search_with_remotive(self) -> list[Internship]:
        data = await asyncio.to_thread(_fetch_json, "https://remotive.com/api/remote-jobs")

        internships: list[Internship] = []
        for row in data.get("jobs", []):
            title = row.get("title", "")
            desc_html = row.get("description", "")
            combined = f"{title} {desc_html}"

            if not _is_ai_internship_match(combined, self.profile):
                continue

            desc = _strip_html(desc_html)
            internships.append(
                Internship(
                    title=title,
                    company=row.get("company_name", "Unknown company"),
                    location=row.get("candidate_required_location", "Worldwide/Remote"),
                    url=row.get("url", ""),
                    source="remotive",
                    description=desc[:500],
                    deadline=_extract_deadline(desc),
                    posted_at=row.get("publication_date"),
                    matched_keywords=_collect_keyword_hits(combined, self.profile),
                )
            )
        return internships


class AnalystAgent:
    def __init__(self, profile: CandidateProfile) -> None:
        self.profile = profile

    def run(self, internships: list[Internship]) -> list[Internship]:
        for role in internships:
            self._score(role)
        return internships

    def _score(self, role: Internship) -> None:
        text = f"{role.title} {role.description} {role.location}".lower()
        score = 0.0
        reasons: list[str] = []

        ai_hits = sum(1 for k in self.profile.ai_keywords if k.lower() in text)
        role_hits = sum(1 for k in self.profile.role_variants if k.lower() in text)
        internship_hits = sum(1 for k in self.profile.internship_terms if k.lower() in text)

        if ai_hits:
            score += min(40, ai_hits * 8)
            reasons.append(f"AI keyword hits: {ai_hits}")

        if role_hits:
            score += min(30, role_hits * 10)
            reasons.append(f"Role variant hits: {role_hits}")

        if internship_hits:
            score += min(20, internship_hits * 8)
            reasons.append(f"Internship-term hits: {internship_hits}")

        skill_hits = sum(1 for skill in self.profile.skills if skill.lower() in text)
        if skill_hits:
            score += skill_hits * 10
            reasons.append(f"Skill matches: {skill_hits}")

        if self.profile.remote_ok and "remote" in text:
            score += 10
            reasons.append("Remote-friendly")

        if any(region.lower() in text for region in self.profile.preferred_regions):
            score += 10
            reasons.append("Preferred region match")

        if self.profile.visa_required and any(k in text for k in ["visa", "sponsorship", "relocation"]):
            score += 8
            reasons.append("Potential visa support")

        if role.posted_at:
            freshness_bonus = _freshness_bonus(role.posted_at)
            if freshness_bonus:
                score += freshness_bonus
                reasons.append(f"Recent posting (+{freshness_bonus})")

        if role.deadline != "Unknown":
            score += 5
            reasons.append("Deadline found")

        role.score = round(score, 2)
        role.reasons = reasons


class CuratorAgent:
    def __init__(self, profile: CandidateProfile) -> None:
        self.profile = profile

    def run(self, internships: list[Internship]) -> list[Internship]:
        deduped: dict[str, Internship] = {}
        for role in internships:
            key = _normalize_key(role)
            existing = deduped.get(key)
            if existing is None or role.score > existing.score:
                deduped[key] = role

        sorted_roles = sorted(deduped.values(), key=lambda x: x.score, reverse=True)
        return sorted_roles[: self.profile.max_results]


class TrackerAgent:
    FIELDNAMES = [
        "company",
        "title",
        "location",
        "deadline",
        "description",
        "url",
        "source",
        "posted_at",
        "score",
        "matched_keywords",
        "reasons",
        "first_seen_utc",
        "last_seen_utc",
        "status",
    ]

    def __init__(self, tracker_path: str) -> None:
        self.tracker_path = Path(tracker_path)

    def update(self, internships: list[Internship]) -> list[dict[str, str]]:
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        current = self._load_existing()
        seen_urls = {i.url for i in internships if i.url}

        for role in internships:
            if not role.url:
                continue
            row = current.get(role.url)
            if row is None:
                row = self._new_row(role, now)
            else:
                row.update(self._role_to_row(role))
                row["last_seen_utc"] = now
                row["status"] = "active"
            current[role.url] = row

        for url, row in current.items():
            if url not in seen_urls:
                row["status"] = "not_seen_this_run"

        self._write_all(current)
        return list(current.values())

    def _new_row(self, role: Internship, now: str) -> dict[str, str]:
        row = self._role_to_row(role)
        row["first_seen_utc"] = now
        row["last_seen_utc"] = now
        row["status"] = "active"
        return row

    def _role_to_row(self, role: Internship) -> dict[str, str]:
        return {
            "company": role.company,
            "title": role.title,
            "location": role.location,
            "deadline": role.deadline,
            "description": role.description,
            "url": role.url,
            "source": role.source,
            "posted_at": role.posted_at or "",
            "score": str(role.score),
            "matched_keywords": ", ".join(role.matched_keywords),
            "reasons": "; ".join(role.reasons),
        }

    def _load_existing(self) -> dict[str, dict[str, str]]:
        if not self.tracker_path.exists():
            return {}

        rows: dict[str, dict[str, str]] = {}
        with self.tracker_path.open("r", newline="", encoding="utf-8") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                url = row.get("url", "")
                if url:
                    rows[url] = row
        return rows

    def _write_all(self, rows: dict[str, dict[str, str]]) -> None:
        self.tracker_path.parent.mkdir(parents=True, exist_ok=True)
        sorted_rows = sorted(rows.values(), key=lambda r: float(r.get("score", "0") or 0), reverse=True)

        with self.tracker_path.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=self.FIELDNAMES)
            writer.writeheader()
            for row in sorted_rows:
                writer.writerow({k: row.get(k, "") for k in self.FIELDNAMES})


class SheetsSyncAgent:
    def __init__(self, webhook_url: str = "") -> None:
        self.webhook_url = webhook_url.strip()

    def run(self, rows: list[dict[str, str]]) -> bool:
        if not self.webhook_url:
            return False

        payload = json.dumps({"rows": rows}).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30):
                return True
        except urllib.error.URLError:
            return False


class InternshipMultiAgentSystem:
    def __init__(self, profile: CandidateProfile, tracker_csv: str, sheets_webhook_url: str = "") -> None:
        self.scout = ScoutAgent(profile)
        self.analyst = AnalystAgent(profile)
        self.curator = CuratorAgent(profile)
        self.tracker = TrackerAgent(tracker_csv)
        self.sheet_sync = SheetsSyncAgent(sheets_webhook_url)

    async def run_once(self) -> tuple[list[Internship], list[dict[str, str]], bool]:
        found = await self.scout.run()
        return self.process_and_store(found)

    def process_and_store(self, found: list[Internship]) -> tuple[list[Internship], list[dict[str, str]], bool]:
        scored = self.analyst.run(found)
        top_roles = self.curator.run(scored)
        tracker_rows = self.tracker.update(top_roles)
        pushed = self.sheet_sync.run(tracker_rows)
        return top_roles, tracker_rows, pushed


def _fetch_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 internship-finder/3.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return {}


def _strip_html(raw: str) -> str:
    return re.sub(r"<[^>]+>", " ", raw).replace("\n", " ").strip()


def _extract_location(text: str) -> str:
    m = re.search(r"(Remote|[A-Za-z .'-]+,\s*[A-Za-z]{2,})", text)
    return m.group(1).strip() if m else "Unknown"


def _extract_company(title: str) -> str:
    if " at " in title.lower():
        return title.split(" at ")[-1].strip()
    if " - " in title:
        return title.split(" - ")[0].strip()
    return "Unknown company"


def _extract_deadline(text: str) -> str:
    patterns = [
        r"(?i)(?:apply by|deadline|applications close|closing date)[:\s]+([A-Za-z]+\s+\d{1,2},\s*\d{4})",
        r"(?i)(?:apply by|deadline|applications close|closing date)[:\s]+(\d{4}-\d{2}-\d{2})",
        r"(?i)(?:apply by|deadline|applications close|closing date)[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return "Unknown"


def _normalize_key(role: Internship) -> str:
    if role.url:
        return role.url.strip().lower()
    return re.sub(r"\W+", "", f"{role.company}-{role.title}-{role.location}".lower())


def _freshness_bonus(iso_date: str) -> float:
    try:
        posted = dt.datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        days = (dt.datetime.now(dt.timezone.utc) - posted).days
    except ValueError:
        return 0.0

    if days <= 7:
        return 12.0
    if days <= 30:
        return 6.0
    return 0.0


def _is_ai_internship_match(text: str, profile: CandidateProfile) -> bool:
    lowered = text.lower()
    has_ai = any(k.lower() in lowered for k in profile.ai_keywords)
    has_role_variant = any(k.lower() in lowered for k in profile.role_variants)
    has_internship = any(k.lower() in lowered for k in profile.internship_terms)
    return has_role_variant or (has_ai and has_internship)


def _collect_keyword_hits(text: str, profile: CandidateProfile) -> list[str]:
    lowered = text.lower()
    combined = profile.ai_keywords + profile.role_variants + profile.internship_terms
    return sorted({k for k in combined if k.lower() in lowered})


def _demo_internships() -> list[Internship]:
    return [
        Internship(
            title="Machine Learning Engineer Intern",
            company="VisionLabs",
            location="Berlin, Germany",
            url="https://example.com/jobs/ml-intern-visionlabs",
            source="demo",
            description="Work on computer vision and deep learning models for production systems. Apply by June 30, 2026.",
            deadline="June 30, 2026",
            posted_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            matched_keywords=["machine learning", "machine learning engineer intern", "intern"],
        ),
        Internship(
            title="AI Automation Engineer Intern",
            company="FlowOps AI",
            location="Remote",
            url="https://example.com/jobs/ai-automation-intern-flowops",
            source="demo",
            description="Build AI automation workflows and LLM agents for enterprise teams.",
            deadline="Unknown",
            posted_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            matched_keywords=["ai automation", "ai automation engineer", "intern"],
        ),
    ]


def _print_results(roles: list[Internship], tracker_path: str, pushed: bool) -> None:
    print(f"\nTop {len(roles)} AI internship matches in this run:\n")
    for i, role in enumerate(roles, start=1):
        print(f"{i}. {role.title} — {role.company}")
        print(f"   Location: {role.location}")
        print(f"   Deadline: {role.deadline}")
        print(f"   Score: {role.score}")
        print(f"   Matched keywords: {', '.join(role.matched_keywords[:8]) or 'None'}")
        print(f"   Why: {', '.join(role.reasons) if role.reasons else 'General match'}")
        print(f"   Link: {role.url}\n")

    print(f"Tracker updated: {tracker_path}")
    print(f"Google Sheets sync: {'done' if pushed else 'skipped/failed'}")


def _parse_csv_keywords(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _build_keywords(extra_keywords: list[str], exclude_keywords: list[str]) -> tuple[list[str], list[str], list[str]]:
    ai_keywords = sorted(set(DEFAULT_AI_KEYWORDS + extra_keywords))
    role_variants = sorted(set(ROLE_VARIANTS + extra_keywords))
    internship_terms = sorted(set(INTERNSHIP_TERMS))

    if exclude_keywords:
        excluded = {e.lower() for e in exclude_keywords}
        ai_keywords = [k for k in ai_keywords if k.lower() not in excluded]
        role_variants = [k for k in role_variants if k.lower() not in excluded]
        internship_terms = [k for k in internship_terms if k.lower() not in excluded]

    return ai_keywords, role_variants, internship_terms


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find AI internships globally and keep an auto-updating tracker.")
    parser.add_argument("--name", required=True, help="Your full name")
    parser.add_argument("--skills", required=True, help="Comma-separated skills")
    parser.add_argument("--regions", default="United States,Europe,Asia,Remote", help="Comma-separated preferred regions")
    parser.add_argument("--extra-keywords", default="", help="Extra AI/role keywords to include (comma-separated)")
    parser.add_argument("--exclude-keywords", default="", help="Keywords to exclude (comma-separated)")
    parser.add_argument("--print-keywords", action="store_true", help="Print active keyword sets and exit")
    parser.add_argument("--demo-mode", action="store_true", help="Run with built-in demo internships (no network needed)")
    parser.add_argument("--visa-required", action="store_true", help="Boost roles mentioning visa sponsorship")
    parser.add_argument("--remote-ok", action="store_true", default=True, help="Prefer remote roles")
    parser.add_argument("--max-results", type=int, default=50, help="Max roles per run")
    parser.add_argument("--tracker-csv", default="data/ai_internships_tracker.csv", help="CSV tracker path")
    parser.add_argument("--save-json", default="", help="Optional JSON dump path for current run")
    parser.add_argument("--interval-minutes", type=int, default=0, help="Repeat search every N minutes (0 = run once)")
    parser.add_argument("--cycles", type=int, default=1, help="Number of cycles when interval > 0")
    parser.add_argument(
        "--sheets-webhook-url",
        default=os.getenv("GOOGLE_SHEETS_WEBHOOK_URL", ""),
        help="Optional Google Sheets Apps Script webhook URL",
    )
    return parser.parse_args()


async def run_loop(args: argparse.Namespace) -> None:
    extra_keywords = _parse_csv_keywords(args.extra_keywords)
    exclude_keywords = _parse_csv_keywords(args.exclude_keywords)
    ai_keywords, role_variants, internship_terms = _build_keywords(extra_keywords, exclude_keywords)

    if args.print_keywords:
        print("AI Keywords:", ", ".join(ai_keywords))
        print("Role Variants:", ", ".join(role_variants))
        print("Internship Terms:", ", ".join(internship_terms))
        return

    profile = CandidateProfile(
        full_name=args.name,
        skills=[s.strip() for s in args.skills.split(",") if s.strip()],
        preferred_regions=[r.strip() for r in args.regions.split(",") if r.strip()],
        ai_keywords=ai_keywords,
        role_variants=role_variants,
        internship_terms=internship_terms,
        visa_required=args.visa_required,
        remote_ok=args.remote_ok,
        max_results=args.max_results,
    )

    system = InternshipMultiAgentSystem(profile, args.tracker_csv, args.sheets_webhook_url)

    cycles = args.cycles if args.interval_minutes > 0 else 1
    for idx in range(cycles):
        if args.demo_mode:
            roles, tracker_rows, pushed = system.process_and_store(_demo_internships())
        else:
            roles, tracker_rows, pushed = await system.run_once()
        _print_results(roles, args.tracker_csv, pushed)

        if args.save_json:
            payload = [dataclasses.asdict(r) for r in roles]
            with open(args.save_json, "w", encoding="utf-8") as fp:
                json.dump(payload, fp, indent=2)
            print(f"Saved {len(roles)} records to {args.save_json}")

        if idx < cycles - 1 and args.interval_minutes > 0:
            print(f"Sleeping for {args.interval_minutes} minute(s) before next run...")
            await asyncio.sleep(args.interval_minutes * 60)

        print(f"Tracker rows currently stored: {len(tracker_rows)}")


if __name__ == "__main__":
    asyncio.run(run_loop(parse_args()))
