"""PersonaMem 32k: pinned source files, context-disjoint splits, strict MCQ scoring."""
import ast
import csv
import json
import re
from pathlib import Path

from .benchmark import BenchmarkError, _sha256, _write_jsonl

DATASET = "bowen-upenn/PersonaMem"
FILES = ("questions_32k.csv", "shared_contexts_32k.jsonl")


def option_label(value):
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(?:([a-dA-D])|\(([a-dA-D])\))[.]?\s*", value)
    return (match[1] or match[2]).lower() if match else None


def score_choice(answer, target, status="answer"):
    return status == "answer" and option_label(answer) is not None and option_label(answer) == target


def export_personamem(source_dir, output_dir, revision):
    source_dir, output_dir = Path(source_dir), Path(output_dir)
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise BenchmarkError("PersonaMem requires an immutable commit SHA")
    with (source_dir / FILES[0]).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"persona_id", "question_id", "question_type", "user_question_or_message", "correct_answer", "all_options", "shared_context_id", "end_index_in_shared_context"}
        if not required.issubset(reader.fieldnames or []):
            raise BenchmarkError("PersonaMem question schema changed")
        questions = list(reader)
    contexts = {}
    for line in (source_dir / FILES[1]).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if not isinstance(row, dict) or len(row) != 1 or set(row) & contexts.keys():
            raise BenchmarkError("Invalid or duplicate PersonaMem context")
        contexts.update(row)
    # Split by persona, not by questions sharing the same history/profile.
    personas = sorted({row["persona_id"] for row in questions})
    if len(personas) < 2:
        raise BenchmarkError("PersonaMem needs at least two personas for a disjoint split")
    debug_personas = set(personas[:max(1, len(personas) // 5)])
    exports = {}
    output_dir.mkdir(parents=True, exist_ok=True)
    context_owners = {}
    for row in questions:
        owner = context_owners.setdefault(row["shared_context_id"], row["persona_id"])
        if owner != row["persona_id"]:
            raise BenchmarkError("A context is shared by multiple personas; cannot split safely")
    for split in ("debug", "eval"):
        inputs, targets = [], []
        for index, row in enumerate(questions):
            if (row["persona_id"] in debug_personas) != (split == "debug"):
                continue
            try:
                options = ast.literal_eval(row["all_options"])
                if not isinstance(options, list) or len(options) != 4 or any(not isinstance(o, str) or not o.startswith(f"({label}) ") for o, label in zip(options, "abcd")):
                    raise ValueError("Invalid options")
                history = contexts[row["shared_context_id"]]
                stop = int(row["end_index_in_shared_context"])
                if not isinstance(history, list) or not 0 < stop <= len(history):
                    raise ValueError("Invalid history boundary")
                messages = history[:stop]
                if any(not isinstance(m, dict) or set(m) != {"role", "content"} or m["role"] not in {"system", "user", "assistant"} or not isinstance(m["content"], str) for m in messages):
                    raise ValueError("Invalid messages")
                label = option_label(row["correct_answer"])
                if label is None:
                    raise ValueError("Invalid answer label")
            except (ValueError, KeyError, TypeError, SyntaxError) as exc:
                raise BenchmarkError(f"Invalid PersonaMem row {index}: {type(exc).__name__}") from exc
            identity = f"personamem-32k-{index:05d}"
            # Preserve every original message, including the system persona, as SOURCE DATA.
            text = "".join(json.dumps(m, ensure_ascii=False, separators=(",", ":")) + "\n" for m in messages)
            question = row["user_question_or_message"] + "\n" + "\n".join(options) + "\nReturn only the letter a, b, c or d in answer."
            inputs.append({"id": identity, "row": index, "input": text, "question": question,
                           "choices": list("abcd"), "question_type": row["question_type"],
                           "persona_id": row["persona_id"], "shared_context_id": row["shared_context_id"]})
            targets.append({"id": identity, "row": index, "target": label})
        for category, records in (("inputs", inputs), ("targets", targets)):
            _write_jsonl(output_dir / f"{split}_{category}.jsonl", records)
        exports[split] = {"count": len(inputs), "rows": [r["row"] for r in inputs],
                          **{f"{c}_sha256": _sha256(output_dir / f"{split}_{c}.jsonl") for c in ("inputs", "targets")}}
    manifest = {"dataset": DATASET, "configuration": "32k", "revision": revision,
                "sources": {name: _sha256(source_dir / name) for name in FILES}, "exports": exports,
                "split_policy": "sorted persona_id: first 20% debug, remaining eval",
                "adaptation": "Native message prefix, system persona retained as source, strict single-label MCQ, question_later by default"}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def fetch_personamem(output_dir=Path("data/personamem"), revision="main"):
    from huggingface_hub import HfApi, hf_hub_download
    output_dir = Path(output_dir)
    try:
        sha = HfApi().dataset_info(DATASET, revision=revision, token=False).sha
        for name in FILES:
            hf_hub_download(repo_id=DATASET, repo_type="dataset", filename=name, revision=sha,
                            local_dir=output_dir / "source", token=False)
        return export_personamem(output_dir / "source", output_dir, sha)
    except BenchmarkError:
        raise
    except Exception as exc:
        raise BenchmarkError(f"PersonaMem download/export failed: {type(exc).__name__}") from exc


def _load(data_dir, split, category):
    if split not in {"debug", "eval"}:
        raise BenchmarkError("Unknown PersonaMem split")
    data_dir = Path(data_dir)
    try:
        manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
        info = manifest["exports"][split]
        path = data_dir / f"{split}_{category}.jsonl"
        if _sha256(path) != info[f"{category}_sha256"] or manifest["dataset"] != DATASET:
            raise BenchmarkError("PersonaMem export checksum/dataset mismatch")
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if len(rows) != info["count"] or [r["row"] for r in rows] != info["rows"] or len({r["id"] for r in rows}) != len(rows):
            raise BenchmarkError("Invalid PersonaMem row sequence")
        keys = {"id", "row", "target"} if category == "targets" else {"id", "row", "input", "question", "choices", "question_type", "persona_id", "shared_context_id"}
        for row in rows:
            if set(row) != keys or row["id"] != f"personamem-32k-{row['row']:05d}":
                raise BenchmarkError("Invalid PersonaMem export schema")
            if category == "targets" and row["target"] not in list("abcd"):
                raise BenchmarkError("Invalid target label")
            if category == "inputs" and (row["choices"] != list("abcd") or any(not isinstance(row[k], str) for k in keys - {"row", "choices"})):
                raise BenchmarkError("Invalid PersonaMem input values")
        return rows
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise BenchmarkError("Missing/invalid PersonaMem export; run fetch-benchmark --dataset personamem") from exc


def load_inputs(data_dir=Path("data/personamem"), split="eval", limit=5):
    rows = _load(data_dir, split, "inputs")
    if type(limit) is not int or not 1 <= limit <= len(rows):
        raise BenchmarkError("Limit exceeds available PersonaMem examples")
    return rows[:limit]


def load_targets(data_dir=Path("data/personamem"), split="eval"):
    return {r["id"]: r["target"] for r in _load(data_dir, split, "targets")}
