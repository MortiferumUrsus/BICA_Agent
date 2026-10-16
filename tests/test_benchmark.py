import hashlib
import json
from pathlib import Path

import pytest

from context_memory.benchmark import (
    BenchmarkError, DATASET, DATASET_FILE, exact_match, export_benchmark,
    fetch_benchmark, load_inputs, load_targets,
)
from context_memory.reporting import render_snapshot, summarize_records, write_report

SHA = "a" * 40


@pytest.fixture
def parquet(tmp_path):
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    source = tmp_path / "tiny.parquet"
    pq.write_table(pa.table({
        "input": [f"source {i}" for i in range(26)],
        "question": [f"question {i}?" for i in range(26)],
        "target": [f"secret {i}" for i in range(26)],
    }), source)
    return source


def test_export_fixed_disjoint_rows_and_separate_targets(parquet, tmp_path):
    directory = tmp_path / "export"
    manifest = export_benchmark(parquet, directory, SHA)
    assert manifest["selected_rows"] == {"debug": list(range(5)), "eval": list(range(5, 25))}
    assert manifest["sha256"] == hashlib.sha256(parquet.read_bytes()).hexdigest()
    assert manifest["revision"] == SHA
    inputs = load_inputs(directory)
    assert len(inputs) == 5
    assert inputs[0]["row"] == 5 and inputs[-1]["row"] == 9
    assert len(load_inputs(directory, limit=20)) == 20
    for split in ("debug", "eval"):
        input_text = (directory / f"{split}_inputs.jsonl").read_text(encoding="utf-8")
        assert '"target"' not in input_text and "secret" not in input_text
    targets = load_targets(directory)
    assert targets[inputs[0]["id"]] == "secret 5"
    assert len(targets) == 20


def test_input_loader_never_reads_target_file(parquet, tmp_path, monkeypatch):
    directory = tmp_path / "export"
    export_benchmark(parquet, directory, SHA)
    original = Path.open

    def guarded_open(path, *args, **kwargs):
        assert not path.name.endswith("_targets.jsonl")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    assert len(load_inputs(directory)) == 5


def test_download_pins_commit_and_only_requests_one_shard(parquet, tmp_path, monkeypatch):
    hub = pytest.importorskip("huggingface_hub")
    calls = []

    class FakeApi:
        def dataset_info(self, repo, **kwargs):
            calls.append((repo, kwargs))
            return type("Info", (), {"sha": SHA})()

    def fake_download(**kwargs):
        calls.append(kwargs)
        return str(parquet)

    monkeypatch.setattr(hub, "HfApi", FakeApi)
    monkeypatch.setattr(hub, "hf_hub_download", fake_download)
    manifest = fetch_benchmark(tmp_path / "export")
    assert len(calls) == 2
    assert calls[0] == (DATASET, {"revision": "main", "token": False})
    assert calls[1]["filename"] == DATASET_FILE
    assert calls[1]["revision"] == SHA
    assert calls[1]["repo_type"] == "dataset"
    assert manifest["requested_revision"] == "main"


@pytest.mark.parametrize("problem", ["missing", "type", "null", "short"])
def test_schema_changes_are_not_guessed(tmp_path, problem):
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    size = 24 if problem == "short" else 25
    data = {"input": ["text"] * size, "question": ["question"] * size, "target": ["target"] * size}
    if problem == "missing":
        data["answer"] = data.pop("target")
    elif problem == "type":
        data["target"] = [1] * size
    elif problem == "null":
        data["target"][4] = None
    source = tmp_path / "invalid.parquet"
    pq.write_table(pa.table(data), source)
    with pytest.raises(BenchmarkError):
        export_benchmark(source, tmp_path / "export", SHA)
    assert not (tmp_path / "export" / "manifest.json").exists()


def test_modified_inputs_are_rejected(parquet, tmp_path):
    directory = tmp_path / "export"
    export_benchmark(parquet, directory, SHA)
    with (directory / "eval_inputs.jsonl").open("a", encoding="utf-8") as stream:
        stream.write("{}\n")
    with pytest.raises(BenchmarkError, match="checksum"):
        load_inputs(directory)


@pytest.mark.parametrize(("answer", "target", "status", "expected"), [
    ("  KITCHEN.  ", "kitchen", "answer", True),
    ("kitchen", "Kitchen.", "answer", True),
    ("The kitchen", "kitchen", "answer", False),
    ("kitchen..", "kitchen", "answer", False),
    ("kitchen!", "kitchen", "answer", False),
    ("  ", "", "answer", False),
    (".", "", "answer", False),
    (None, "kitchen", "answer", False),
    ("kitchen", "kitchen", "insufficient_data", False),
    ("kitchen", "kitchen", "retrieve", False),
])
def test_exact_match_is_not_substring_scoring(answer, target, status, expected):
    assert exact_match(answer, target, status) is expected


def test_metrics_include_failed_attempts_unknown_cost_and_stages():
    records = [
        {"stage": "reflect", "attempt": 1, "duration_s": 0.4, "usage": {"prompt_tokens": 10, "completion_tokens": 3}, "cost_usd": 0.01},
        {"stage": "compress", "attempt": 1, "duration_s": 0.2, "error": {"type": "APIError"}, "usage": None},
        {"stage": "compress", "attempt": 2, "duration_s": 0.7, "usage": {"prompt_tokens": 12, "completion_tokens": 5}, "cost_usd": 0.02},
        {"stage": "verify", "attempt": 1, "duration_s": 0.6, "usage": {"prompt_tokens": 8, "completion_tokens": 2}, "cost_usd": 0.01, "error": {"type": "ResponseError"}},
    ]
    metrics = summarize_records(records)
    assert metrics["api_calls"] == metrics["attempts"] == 4
    assert metrics["api_errors"] == metrics["response_errors"] == 1
    assert metrics["duration_s"] == 1.9
    assert metrics["cost_usd"] is None
    assert metrics["known_cost_usd"] == 0.04
    assert metrics["unknown_cost_calls"] == 1
    assert metrics["prompt_tokens"] is None
    assert metrics["known_prompt_tokens"] == 30
    assert metrics["known_total_tokens"] == 40
    assert metrics["stage_totals"]["compress"]["api_calls"] == 2


def test_malformed_usage_stays_unknown():
    metrics = summarize_records([{"usage": ["invalid"], "duration_s": "bad", "cost_usd": float("nan")}])
    assert metrics["cost_usd"] is None and metrics["total_tokens"] is None
    assert metrics["known_cost_usd"] == 0


def test_report_preserves_decisions_and_provider_label(tmp_path):
    result = {
        "kind": "demo", "provider": "ollama", "model": "tiny", "mode": "reflexive",
        "status": "completed", "presentation": "question_first", "config": {"memory_ref_tokens": 32},
        "answers": [{"question": "Where?", "before_retrieval": {"status": "retrieve", "query": "room", "source_ids": []},
                     "final": {"status": "answer", "answer": "kitchen"}, "retrieved_ids": ["c001"]}],
        "metrics": summarize_records([]),
    }
    path = write_report(tmp_path, result)
    text = path.read_text(encoding="utf-8")
    assert "LOCAL MODEL (Ollama)" in text and "question_first" in text
    assert "retrieve: room" in text and "answer: kitchen" in text
    assert "c001" in text and "memory_ref_tokens" in text
    assert json.loads((tmp_path / "results.json").read_text(encoding="utf-8")) == result


def test_snapshot_escapes_xml_and_wraps_long_text(tmp_path):
    import xml.etree.ElementTree as ET
    output = render_snapshot([{"text": "<script> & " + "word " * 80, "source_ids": ["c001"]}], [], tmp_path / "snapshot.svg", "MOCK <trace>")
    tree = ET.parse(output)
    assert tree.getroot().tag.endswith("svg")
    assert "&lt;script&gt;" in output.read_text(encoding="utf-8")
    assert len(list(tree.getroot().iter("{http://www.w3.org/2000/svg}text"))) > 8


def test_comparison_distinguishes_failure_types_and_accuracy_denominator(tmp_path):
    result = {
        "kind": "benchmark", "provider": "mock", "examples": [],
        "summary_by_mode": {"summary": {
            "requested": 5, "processed": 2, "correct": 1,
            "failed_examples": 3, "infra_errors": 1, "model_output_errors": 1, "limit_errors": 1,
            "accuracy": 0.2,
        }},
    }
    text = write_report(tmp_path, result).read_text(encoding="utf-8")
    assert "| summary | 5 | 2 | 1 | 1 | 3 | 1 | 1 | 1 | 0.2 |" in text
    assert "divided by all requested examples" in text
    assert "Model output errors" in text and "Limit errors" in text
