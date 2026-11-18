"""Offline checks of report scoring boundaries and frozen experiment results."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("research_report", ROOT / "tools/build_research_report.py")
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)


def fixture(answer, target="hallway", status="completed", answer_status="answer"):
    strict = bool(status == "completed" and answer_status == "answer" and answer and
                  REPORT.exact_text(answer) == REPORT.exact_text(target))
    return {"id": "fixture", "profile": "4.1-mini", "dataset": "babilong", "mode": "summary",
            "answer": answer, "target": target, "status": status,
            "answer_status": answer_status, "correct": strict}


class ResearchReportTests(unittest.TestCase):
    def test_only_one_leading_article_is_removed(self):
        cases = {" THE hallway. ": "hallway", "an office": "office", "a garden": "garden",
                 "theatre": "theatre", "in the hallway": "in the hallway", "the the hallway": "the hallway"}
        for answer, expected in cases.items():
            with self.subTest(answer=answer):
                self.assertEqual(REPORT.article_text(answer), expected)

    def test_matching_text_cannot_override_refusal_or_execution_failure(self):
        for status, answer_status, category in [
            ("completed", "insufficient_data", "insufficient_data"),
            ("error", "answer", "execution_error"),
            ("completed", "retrieve", "execution_error"),
        ]:
            r = REPORT.analyze_babilong([fixture("the hallway", status=status, answer_status=answer_status)])["rows"][0]
            self.assertFalse(r["article_correct"])
            self.assertEqual(r["category"], category)

    def test_content_and_complex_wording_are_not_conflated(self):
        for answer, expected in [("the kitchen", "other_location"),
                                 ("Daniel is in the office.", "other_mismatch"),
                                 ("hallway, then kitchen", "other_mismatch"),
                                 ("", "other_mismatch"), ("the hallway", "article_only")]:
            with self.subTest(answer=answer):
                self.assertEqual(REPORT.analyze_babilong([fixture(answer)])["rows"][0]["category"], expected)

    def test_duplicate_ids_and_changed_primary_scores_fail(self):
        r = fixture("the hallway")
        with self.assertRaises(ValueError):
            REPORT.analyze_babilong([r, r])
        r["correct"] = True
        with self.assertRaises(ValueError):
            REPORT.analyze_babilong([r])

    @classmethod
    def setUpClass(cls):
        cls.original = [json.loads((ROOT / "examples" / name / "results.json").read_text())
                        for name in ("openai-20261101", "openai-strong-20261101")]
        cls.rows = [r for d in cls.original for r in d["rows"]]

    def test_saved_results_partition_without_mutating_official_rows(self):
        before = copy.deepcopy(self.rows)
        analysis = REPORT.analyze_babilong(self.rows)
        self.assertEqual(self.rows, before)
        self.assertEqual((analysis["n_runs"], analysis["n_examples"]), (200, 20))
        self.assertEqual(analysis["category_counts"], {
            "strict_match": 117, "article_only": 42, "other_location": 18,
            "insufficient_data": 14, "other_mismatch": 9, "execution_error": 0})
        self.assertEqual(sum(analysis["category_counts"].values()), 200)
        for s in analysis["summaries"]:
            self.assertEqual(s["n"], 20)
            self.assertEqual(s["article_correct"], s["strict_correct"] + s["categories"]["article_only"])

    def test_known_paired_reasoning_results_under_both_metrics(self):
        analysis = REPORT.analyze_babilong(self.rows)
        comparisons = {c["first_mode"]: c for c in analysis["comparisons"] if c["kind"] == "reasoning"}
        for mode, strict, article in [("summary", .015625, .0703125), ("reflexive", .0390625, 1.0)]:
            self.assertEqual(comparisons[mode]["strict"]["mcnemar_exact_p_unadjusted"], strict)
            self.assertEqual(comparisons[mode]["article"]["mcnemar_exact_p_unadjusted"], article)
            self.assertEqual(comparisons[mode]["article"]["n"], 20)

    def test_goal_checkpoints_keep_their_original_denominators(self):
        summaries = [s for d in self.original for s in d["summaries"]]
        table = REPORT.goal_table(summaries)
        self.assertEqual(len(table), 12)
        sol = next(r for r in table if r[:2] == ["GPT-6.1 Sol · low", "Summary"])
        self.assertEqual(sol[2:5], ["12/12", "2/12", "12/12"])
        astra = next(r for r in table if r[:2] == ["GPT-6 Astra · low", "Reflexive"])
        self.assertEqual(astra[2:5], ["9/9", "2/9", "9/9"])


if __name__ == "__main__":
    unittest.main()
