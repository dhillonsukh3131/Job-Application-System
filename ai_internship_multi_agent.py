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
            location = _extract_location(snippet)
            company = _extract_company(title)
            items.append(
                Internship(
                    title=title,
                    company=company,
                    location=location,
                    url=link,
                    source="serpapi",
                    snippet=snippet,
                )
            )
        return items

    async def _search_with_remotive(self) -> list[Internship]:
        """Search remote opportunities from Remotive public jobs API."""
        data = await asyncio.to_thread(_fetch_json, "https://remotive.com/api/remote-jobs")

        internships: list[Internship] = []
        ai_pattern = re.compile(r"\b(ai|ml|machine learning|data science|nlp|llm)\b", re.I)
        internship_pattern = re.compile(r"\b(intern|internship|graduate)\b", re.I)

        for row in data.get("jobs", []):
            title = row.get("title", "")
            desc = row.get("description", "")
            if not internship_pattern.search(title + " " + desc):
                continue
            if not ai_pattern.search(title + " " + desc):
                continue
            internships.append(
                Internship(
                    title=title,
                    company=row.get("company_name", "Unknown company"),
                    location=row.get("candidate_required_location", "Worldwide/Remote"),
                    url=row.get("url", ""),
                    source="remotive",
                    snippet=_strip_html(desc)[:280],
                    posted_at=row.get("publication_date"),
                )
            )
        return internships


class AnalystAgent:
    """Scores each internship based on profile fit and priority signals."""

    def __init__(self, profile: CandidateProfile) -> None:
        self.profile = profile

    def run(self, internships: list[Internship]) -> list[Internship]:
        for role in internships:
            self._score(role)
        return internships

    def _score(self, role: Internship) -> None:
        text = f"{role.title} {role.snippet} {role.location}".lower()
        score = 0.0
        reasons: list[str] = []

        # Core requirement: AI relevance.
        if any(k in text for k in ["ai", "machine learning", "ml", "llm", "data science", "nlp"]):
            score += 30
            reasons.append("AI-focused role")

        # Internship signal.
        if any(k in text for k in ["intern", "internship", "graduate"]):
            score += 20
            reasons.append("Internship-level opening")

        # Skill matching.
        skill_hits = 0
        for skill in self.profile.skills:
            if skill.lower() in text:
                skill_hits += 1
        score += skill_hits * 10
        if skill_hits:
            reasons.append(f"{skill_hits} skill match(es)")

        # Location + remote preferences.
        if self.profile.remote_ok and "remote" in text:
            score += 15
            reasons.append("Remote-friendly")

        if any(region.lower() in text for region in self.profile.preferred_regions):
            score += 10
            reasons.append("Preferred region match")

        if self.profile.visa_required and any(k in text for k in ["visa", "sponsorship", "relocation"]):
            score += 8
            reasons.append("Possible visa support")

        # Freshness bonus.
        if role.posted_at:
            freshness_bonus = _freshness_bonus(role.posted_at)
            if freshness_bonus:
                score += freshness_bonus
                reasons.append(f"Recent posting (+{freshness_bonus})")

        role.score = round(score, 2)
        role.reasons = reasons


class CuratorAgent:
    """Deduplicates and returns the best opportunities."""

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


class OutreachAgent:
    """Creates copy-paste outreach messages for top-ranked roles."""

    def __init__(self, profile: CandidateProfile) -> None:
        self.profile = profile

    def run(self, role: Internship) -> str:
        top_skills = ", ".join(self.profile.skills[:4])
        return (
            f"Hello {role.company} recruiting team,\\n\\n"
            f"I am {self.profile.full_name}, and I am interested in the {role.title} role. "
            f"My background includes {top_skills}, and I would love to contribute to your AI projects.\\n\\n"
            f"Role link: {role.url}\\n"
            "Thank you for your consideration."
        )


class InternshipMultiAgentSystem:
    def __init__(self, profile: CandidateProfile) -> None:
        self.scout = ScoutAgent(profile)
        self.analyst = AnalystAgent(profile)
        self.curator = CuratorAgent(profile)
        self.outreach = OutreachAgent(profile)

    async def find(self) -> list[Internship]:
        found = await self.scout.run()
        scored = self.analyst.run(found)
        return self.curator.run(scored)


def _fetch_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 internship-finder/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        return {}


def _strip_html(raw: str) -> str:
    return re.sub(r"<[^>]+>", " ", raw).replace("\n", " ").strip()


def _extract_location(snippet: str) -> str:
    m = re.search(r"(Remote|[A-Za-z ]+, [A-Za-z]{2,})", snippet)
    return m.group(1) if m else "Unknown"


def _extract_company(title: str) -> str:
    # Common patterns: "AI Intern at Company" or "Company - AI Internship"
    if " at " in title.lower():
        return title.split(" at ")[-1].strip()
    if " - " in title:
        return title.split(" - ")[0].strip()
    return "Unknown company"


def _normalize_key(role: Internship) -> str:
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


def _print_results(roles: list[Internship], profile: CandidateProfile) -> None:
    print(f"\nTop {len(roles)} AI internship matches for {profile.full_name}:\n")
    for i, role in enumerate(roles, start=1):
        print(f"{i}. {role.title} — {role.company}")
        print(f"   Location: {role.location}")
        print(f"   Score: {role.score}")
        print(f"   Why: {', '.join(role.reasons) if role.reasons else 'General match'}")
        print(f"   Link: {role.url}")
        print(f"   Source: {role.source}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find AI internships globally using a multi-agent pipeline.")
    parser.add_argument("--name", required=True, help="Your full name")
    parser.add_argument("--skills", required=True, help="Comma-separated skills")
    parser.add_argument(
        "--regions",
        default="United States,Europe,Asia,Remote",
        help="Comma-separated preferred regions/countries",
    )
    parser.add_argument("--visa-required", action="store_true", help="Boost roles mentioning visa sponsorship")
    parser.add_argument("--remote-ok", action="store_true", default=True, help="Prefer remote roles")
    parser.add_argument("--max-results", type=int, default=25)
    parser.add_argument("--save-json", default="", help="Optional path to save results JSON")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    profile = CandidateProfile(
        full_name=args.name,
        skills=[s.strip() for s in args.skills.split(",") if s.strip()],
        preferred_regions=[r.strip() for r in args.regions.split(",") if r.strip()],
        visa_required=args.visa_required,
        remote_ok=args.remote_ok,
        max_results=args.max_results,
    )

    system = InternshipMultiAgentSystem(profile)
    roles = await system.find()
    _print_results(roles, profile)

    if args.save_json:
        payload = [dataclasses.asdict(r) for r in roles]
        with open(args.save_json, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2)
        print(f"Saved {len(roles)} records to {args.save_json}")


if __name__ == "__main__":
    asyncio.run(main())
