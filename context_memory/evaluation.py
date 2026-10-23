"""Reference-based scoring. This module never calls a language model."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from . import benchmark, personamem
from .errors import MemoryExperimentError


def dataset_module(name):
    if name == "babilong":
        return benchmark
    if name == "personamem":
        return personamem
    raise ValueError("Unknown dataset")


def dataset_identity(data_dir):
    path = Path(data_dir) / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    # Moving results between the GPU server and laptop must not change dataset identity.
    canonical = {k: v for k, v in manifest.items() if k not in {"local_source", "requested_revision"}}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def grade_result(result, data_dir):
    """Read targets only after inference; return a new result without modifying answers."""
    if result.get("dataset_manifest_sha256") != dataset_identity(data_dir):
        raise MemoryExperimentError("Evaluation dataset differs from the inference dataset manifest")
    result = deepcopy(result)
    name, split = result["dataset"], result["split"]
    module = dataset_module(name)
    targets = module.load_targets(Path(data_dir), split)
    scorer = module.score_choice if name == "personamem" else module.exact_match
    seen = set()
    for example in result["examples"]:
        identity = (example["id"], example["mode"])
        if identity in seen or example["id"] not in targets:
            raise MemoryExperimentError("Unknown/duplicate prediction ID")
        seen.add(identity)
        outcome = example["answers"][-1] if example["answers"] else {}
        for key, source in (("correct", "final"), ("correct_before_retrieval", "before_retrieval")):
            answer = outcome.get(source)
            example[key] = scorer(answer["answer"], targets[example["id"]], answer["status"]) if answer and example["status"] == "completed" else None
    expected = {(identity, mode) for identity in result["requested_ids"] for mode in result["requested_modes"]}
    if seen != expected:
        raise MemoryExperimentError("Incomplete prediction set; cannot silently change the accuracy denominator")
    for mode, summary in result["summary_by_mode"].items():
        rows = [r for r in result["examples"] if r["mode"] == mode]
        if not rows or summary["requested"] != len(rows):
            raise MemoryExperimentError("Prediction count differs from the recorded protocol")
        correct = sum(r["correct"] is True for r in rows)
        summary.update(correct=correct, accuracy=correct / len(rows),
                       completed_accuracy=correct / summary["processed"] if summary["processed"] else None,
                       correct_before_retrieval=sum(r["correct_before_retrieval"] is True for r in rows))
        summary["by_question_type"] = {}
        for question_type in sorted({r.get("question_type", "qa1") for r in rows}):
            category = [r for r in rows if r.get("question_type", "qa1") == question_type]
            correct_category = sum(r["correct"] is True for r in category)
            summary["by_question_type"][question_type] = {"requested": len(category), "correct": correct_category,
                "processed": sum(r["status"] == "completed" for r in category), "accuracy": correct_category / len(category)}
    result["evaluation"] = {"method": "strict_choice_label" if name == "personamem" else "exact_match",
                            "judge_model": None, "targets_visible_to_solver": False,
                            "accuracy_denominator": "all_requested_examples"}
    return result
