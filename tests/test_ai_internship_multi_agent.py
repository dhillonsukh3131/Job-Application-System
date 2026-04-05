import tempfile
import unittest
from pathlib import Path

from ai_internship_multi_agent import (
    CandidateProfile,
    Internship,
    TrackerAgent,
    _build_keywords,
    _is_ai_internship_match,
)


class InternshipAgentTests(unittest.TestCase):
    def test_keyword_builder_adds_and_excludes(self):
        ai, roles, intern = _build_keywords(
            extra_keywords=["ai platform intern"],
            exclude_keywords=["data science"],
        )
        self.assertIn("ai platform intern", ai)
        self.assertIn("ai platform intern", roles)
        self.assertNotIn("data science", ai)
        self.assertGreater(len(intern), 0)

    def test_variant_match_for_non_standard_title(self):
        ai, roles, intern = _build_keywords(extra_keywords=[], exclude_keywords=[])
        profile = CandidateProfile(
            full_name="Tester",
            skills=["Python"],
            preferred_regions=["Remote"],
            ai_keywords=ai,
            role_variants=roles,
            internship_terms=intern,
        )
        text = "We are hiring an AI Automation Engineer Intern for remote teams"
        self.assertTrue(_is_ai_internship_match(text, profile))

    def test_tracker_upsert(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tracker.csv"
            tracker = TrackerAgent(str(path))
            role = Internship(
                title="ML Intern",
                company="Acme",
                location="Remote",
                url="https://example.com/ml-intern",
                source="demo",
                description="Machine learning internship",
            )
            rows = tracker.update([role])
            self.assertEqual(len(rows), 1)
            self.assertTrue(path.exists())
            content = path.read_text(encoding="utf-8")
            self.assertIn("matched_keywords", content)
            self.assertIn("https://example.com/ml-intern", content)


if __name__ == "__main__":
    unittest.main()
