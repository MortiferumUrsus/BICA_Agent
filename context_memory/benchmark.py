"""Download a pinned BABILong shard and keep evaluator targets separate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .errors import MemoryExperimentError

DATASET = "RMT-team/babilong-1k-samples"
DATASET_FILE = "8k/qa1-00000-of-00001.parquet"
SPLIT_ROWS = {"debug": list(range(5)), "eval": list(range(5, 25))}


class BenchmarkError(MemoryExperimentError):
    """A missing dependency, corrupt export, or unexpected dataset schema."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def export_benchmark(
    parquet_path: Path,
    output_dir: Path,
    revision: str,
    *,
    requested_revision: str | None = None,
) -> dict[str, Any]:
    """Validate the actual schema before exporting the fixed 5/20 split.

    ``revision`` must be the resolved commit, not a moving branch. This public
    helper also allows offline validation against a small Parquet fixture.
    """
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise BenchmarkError('Install benchmark dependencies: pip install -e ".[bench]"') from exc
    if not re.fullmatch(r"[0-9a-fA-F]{40}", revision):
        raise BenchmarkError("The dataset revision must be an immutable 40-character commit SHA")
    parquet_path, output_dir = Path(parquet_path), Path(output_dir)
    parquet = pq.ParquetFile(parquet_path)
    schema = parquet.schema_arrow
    for name in ("input", "question", "target"):
        if schema.names.count(name) != 1:
            raise BenchmarkError(f"Dataset schema changed: expected exactly one {name!r} column")
        dtype = schema.field(name).type
        if not (pa.types.is_string(dtype) or pa.types.is_large_string(dtype)):
            raise BenchmarkError(f"Dataset schema changed: {name!r} must be a string, got {dtype}")
    if parquet.metadata.num_rows < 25:
        raise BenchmarkError("BABILong shard must contain at least 25 rows for the fixed debug/eval split")

    # Read only the required rows; do not display targets or hand them to a model.
    selected: list[dict[str, Any]] = []
    for batch in parquet.iter_batches(batch_size=25, columns=["input", "question", "target"]):
        selected.extend(batch.to_pylist())
        if len(selected) >= 25:
            selected = selected[:25]
            break
    for index, row in enumerate(selected):
        if not all(isinstance(row[name], str) for name in ("input", "question", "target")):
            raise BenchmarkError(f"Dataset schema changed: row {index} contains a null or non-string field")

    output_dir.mkdir(parents=True, exist_ok=True)
    exports: dict[str, Any] = {}
    for split, numbers in SPLIT_ROWS.items():
        inputs, targets = [], []
        for number in numbers:
            row = selected[number]
            identity = f"qa1-8k-{number:05d}"
            inputs.append({"id": identity, "row": number, "input": row["input"], "question": row["question"]})
            targets.append({"id": identity, "row": number, "target": row["target"]})
        inputs_path = output_dir / f"{split}_inputs.jsonl"
        targets_path = output_dir / f"{split}_targets.jsonl"
        _write_jsonl(inputs_path, inputs)
        _write_jsonl(targets_path, targets)
        exports[split] = {
            "rows": numbers,
            "inputs": inputs_path.name,
            "targets": targets_path.name,
            "inputs_sha256": _sha256(inputs_path),
            "targets_sha256": _sha256(targets_path),
        }
    manifest = {
        "dataset": DATASET,
        "configuration": "8k",
        "split": "qa1",
        "revision": revision.lower(),
        "requested_revision": requested_revision or revision,
        "path": DATASET_FILE,
        "local_source": str(parquet_path.resolve()),
        "sha256": _sha256(parquet_path),
        "total_rows": parquet.metadata.num_rows,
        "row_indexing": "zero_based",
        "selected_rows": SPLIT_ROWS,
        "presentation": "question_first",
        "exports": exports,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def fetch_benchmark(output_dir: Path = Path("data/babilong"), revision: str = "main") -> dict[str, Any]:
    """Resolve the dataset commit, then download exactly the requested shard."""
    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError as exc:
        raise BenchmarkError('Install benchmark dependencies: pip install -e ".[bench]"') from exc
    output_dir = Path(output_dir)
    try:
        resolved = HfApi().dataset_info(DATASET, revision=revision, token=False).sha
        if not resolved or not re.fullmatch(r"[0-9a-fA-F]{40}", resolved):
            raise BenchmarkError("Hugging Face did not return an immutable dataset revision")
        source = hf_hub_download(
            repo_id=DATASET,
            repo_type="dataset",
            filename=DATASET_FILE,
            revision=resolved,
            local_dir=output_dir / "source",
            token=False,
        )
        return export_benchmark(Path(source), output_dir, resolved, requested_revision=revision)
    except BenchmarkError:
        raise
    except Exception as exc:
        # Public data, with no credentials. Keep an actionable exception type.
        raise BenchmarkError(f"BABILong download/export failed ({type(exc).__name__}): {exc}") from exc


def _read_split(data_dir: Path, split: str, category: str) -> list[dict[str, Any]]:
    if split not in SPLIT_ROWS:
        raise BenchmarkError("Split must be 'debug' or 'eval'")
    data_dir = Path(data_dir)
    try:
        manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
        details = manifest["exports"][split]
        # Do not accept arbitrary paths from a manifest.
        path = data_dir / f"{split}_{category}.jsonl"
        if _sha256(path) != details[f"{category}_sha256"]:
            raise BenchmarkError(f"Export checksum mismatch: {path.name}; run fetch-benchmark again")
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except BenchmarkError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise BenchmarkError("Missing or invalid BABILong export; run fetch-benchmark first") from exc
    expected = {"id", "row", "input", "question"} if category == "inputs" else {"id", "row", "target"}
    if len(rows) != len(SPLIT_ROWS[split]):
        raise BenchmarkError(f"Invalid {split} row count")
    for row, number in zip(rows, SPLIT_ROWS[split]):
        if set(row) != expected or row["row"] != number or row["id"] != f"qa1-8k-{number:05d}":
            raise BenchmarkError(f"Invalid {split} export structure")
        if not all(isinstance(row[field], str) for field in expected - {"row"}):
            raise BenchmarkError(f"Invalid non-string value in {split} export")
    return rows


def load_inputs(data_dir: Path = Path("data/babilong"), split: str = "eval", limit: int = 5) -> list[dict[str, Any]]:
    """Load only the input file; this code never opens the targets export."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= len(SPLIT_ROWS.get(split, [])):
        raise BenchmarkError("Limit must be positive and fit the selected split (eval: 20, debug: 5)")
    return _read_split(data_dir, split, "inputs")[:limit]


def load_targets(data_dir: Path = Path("data/babilong"), split: str = "eval") -> dict[str, str]:
    """Evaluator-only entry point: do not pass its return value to a controller."""
    return {row["id"]: row["target"] for row in _read_split(data_dir, split, "targets")}


def normalize_answer(answer: str) -> str:
    """Apply exactly lower-case, edge whitespace removal, and one final dot."""
    return answer.lower().strip().removesuffix(".")


def exact_match(answer: str | None, target: str, status: str = "answer") -> bool:
    if status != "answer" or not isinstance(answer, str):
        return False
    normalized = normalize_answer(answer)
    return bool(normalized) and normalized == normalize_answer(target)
