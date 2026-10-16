"""Offline CLI integration: real controllers/files, deterministic model fixture."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import httpx
import pytest

from context_memory import cli
from context_memory.errors import APIError
from context_memory.mock import MockClient


TARGET_SENTINEL = "EVALUATOR_ONLY_TARGET_SENTINEL_93812"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.fixture(autouse=True)
def isolated_cli(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "load_dotenv", lambda **_: None)
    for key in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OLLAMA_MODEL"):
        monkeypatch.delenv(key, raising=False)

    def reject_http(*_, **__):
        pytest.fail("Offline CLI test attempted an HTTP request")

    monkeypatch.setattr(httpx.Client, "send", reject_http)


@pytest.fixture
def captured_client(monkeypatch):
    clients = []

    def create(args, config):
        assert not args.live and args.provider in {None, "mock"}
        result = MockClient(config)
        clients.append(result)
        return result

    monkeypatch.setattr(cli, "make_client", create)
    return clients


@pytest.fixture
def synthetic_benchmark(tmp_path):
    """Twenty valid exports, deliberately synthetic; no BABILong downloads."""
    directory = tmp_path / "synthetic-eval"
    directory.mkdir()
    inputs, targets = [], []
    for row in range(5, 25):
        identity = f"qa1-8k-{row:05d}"
        date = f"{row - 4} November 2026"
        inputs.append({
            "id": identity, "row": row,
            "input": f"Orion delivery date: {date}.\nSOURCE_ONLY_ROW_{row:05d}\n",
            "question": "What is the current delivery date for Orion?",
        })
        targets.append({"id": identity, "row": row,
                        "target": TARGET_SENTINEL if row == 5 else date})
    exports = {"rows": list(range(5, 25))}
    for kind, rows in (("inputs", inputs), ("targets", targets)):
        path = directory / f"eval_{kind}.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        exports[kind] = path.name
        exports[kind + "_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory / "manifest.json").write_text(
        json.dumps({"exports": {"eval": exports}}), encoding="utf-8")
    return directory


@pytest.mark.parametrize("options", [
    ["--provider", "openrouter"],
    ["--provider", "openrouter", "--budget-usd", "1"],
    ["--live"],
    ["--provider", "openrouter", "--live"],
])
def test_openrouter_requires_both_live_and_budget_before_any_traffic(tmp_path, capsys, options):
    output = tmp_path / "denied"
    assert cli.main(["demo", "--out", str(output), *options]) == 2
    assert "both --live and explicit --budget-usd" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("budget", ["0", "-1", "nan", "inf"])
def test_invalid_paid_budget_is_rejected_before_any_traffic(tmp_path, monkeypatch, capsys, budget):
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-cli-test-key")
    output = tmp_path / "denied"
    assert cli.main(["demo", "--live", "--budget-usd", budget, "--out", str(output)]) == 2
    error = capsys.readouterr().err
    assert "positive budget" in error and "fake-cli-test-key" not in error
    assert not output.exists()


def test_local_model_is_required_before_creating_output(tmp_path, capsys):
    output = tmp_path / "missing-model"
    assert cli.main(["demo", "--provider", "ollama", "--out", str(output)]) == 2
    assert "--model or OLLAMA_MODEL" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("provider", ["mock", "ollama"])
def test_live_flag_cannot_be_misapplied_to_mock_or_local(tmp_path, capsys, provider):
    assert cli.main(["demo", "--provider", provider, "--live", "--budget-usd", "1",
                     "--model", "test/model", "--out", str(tmp_path / "denied")]) == 2
    assert "--live" in capsys.readouterr().err


@pytest.mark.parametrize("limits", [
    ["--memory-ref-tokens", "0"],
    ["--state-ref-tokens", "-1"],
    ["--window-ref-tokens", "768"],
    ["--max-retrieval-rounds", "2"],
    ["--retrieval-top-k", "3"],
])
def test_invalid_limits_fail_before_client_or_output(tmp_path, monkeypatch, capsys, limits):
    monkeypatch.setattr(cli, "make_client", lambda *_: pytest.fail("Invalid config created a client"))
    output = tmp_path / "invalid"
    assert cli.main(["demo", "--out", str(output), *limits]) == 2
    assert "Error (ValueError)" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("limit", [6, 20])
def test_eval_over_five_requires_full_eval_without_generation(tmp_path, captured_client, capsys, limit):
    assert cli.main(["benchmark", "--limit", str(limit), "--out", str(tmp_path / "blocked")]) == 2
    assert "requires explicit --full-eval" in capsys.readouterr().err
    assert captured_client[0].records == []


@pytest.mark.parametrize("name", ["correction", "supplier", "retrieval"])
def test_successful_demo_writes_complete_reviewable_artifacts(tmp_path, capsys, name):
    output = tmp_path / name
    assert cli.main(["demo", "--name", name, "--mode", "both", "--out", str(output)]) == 0
    capsys.readouterr()
    for mode in ("summary", "reflexive"):
        directory = output / mode
        for filename in ("journal.jsonl", "state.json", "memory.json", "memory_versions.jsonl",
                         "trace.jsonl", "api_calls.jsonl", "report.md", "results.json"):
            assert (directory / filename).is_file(), filename
        result = read_json(directory / "results.json")
        assert result["status"] == "completed"
        assert result["provider"] == "mock"
        assert result["metrics"]["max_memory_ref_tokens"] <= result["config"]["memory_ref_tokens"]
        assert result["metrics"]["max_request_ref_tokens"] <= result["config"]["window_ref_tokens"]
        assert all(item["final"]["status"] == "answer" for item in result["answers"])
        assert "MOCK" in (directory / "report.md").read_text(encoding="utf-8")
        if name == "supplier":
            assert result["answers"][0]["final"]["answer"] == "Cedar"
            assert "CD-104" in result["answers"][1]["final"]["answer"]
        if name == "retrieval":
            final = result["answers"][-1]
            assert final["before_retrieval"]["status"] == "retrieve"
            assert final["final"]["answer"] == "RIVER-17"
            assert final["retrieved_ids"]


def test_benchmark_keeps_targets_out_of_requests_and_per_example_journals(
        tmp_path, monkeypatch, capsys, captured_client, synthetic_benchmark):
    target_read_call_counts = []
    original_open = Path.open

    def observe_target_reads(path, *args, **kwargs):
        if path.name == "eval_targets.jsonl":
            target_read_call_counts.append(len(captured_client[0].records))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", observe_target_reads)
    output = tmp_path / "comparison"
    assert cli.main(["benchmark", "--limit", "2", "--mode", "both",
                     "--data-dir", str(synthetic_benchmark), "--out", str(output)]) == 0
    capsys.readouterr()
    records = captured_client[0].records
    assert target_read_call_counts and all(n == len(records) for n in target_read_call_counts)
    assert TARGET_SENTINEL not in json.dumps(records)
    result = read_json(output / "results.json")
    assert result["presentation"] == "question_first" and len(result["examples"]) == 4
    for mode in ("summary", "reflexive"):
        summary = result["summary_by_mode"][mode]
        assert summary["requested"] == summary["processed"] == 2
        assert summary["infra_errors"] == 0 and summary["correct"] == 1
        assert summary["accuracy"] == .5
    for example in result["examples"]:
        row = example["row"]
        directory = output / example["id"] / example["mode"]
        journal = read_jsonl(directory / "journal.jsonl")
        text = "".join(chunk["text"] for chunk in journal)
        assert text == f"Orion delivery date: {row - 4} November 2026.\nSOURCE_ONLY_ROW_{row:05d}\n"
        assert journal[0]["chunk_id"] == "c001"
        assert TARGET_SENTINEL not in text
        calls = read_jsonl(directory / "api_calls.jsonl")
        assert TARGET_SENTINEL not in json.dumps(calls)
        other_row = 6 if row == 5 else 5
        assert f"SOURCE_ONLY_ROW_{other_row:05d}" not in json.dumps(calls)
        first_body = json.loads(calls[0]["request"]["messages"][-1]["content"])
        assert first_body["goal"] == "What is the current delivery date for Orion?"


def test_twenty_rows_run_only_with_explicit_gate(tmp_path, synthetic_benchmark, capsys):
    output = tmp_path / "full-synthetic"
    assert cli.main(["benchmark", "--limit", "20", "--full-eval", "--mode", "summary",
                     "--data-dir", str(synthetic_benchmark), "--out", str(output)]) == 0
    capsys.readouterr()
    result = read_json(output / "results.json")
    assert len(result["examples"]) == 20
    assert result["summary_by_mode"]["summary"]["processed"] == 20
    assert result["summary_by_mode"]["summary"]["correct"] == 19


def test_benchmark_infrastructure_failure_is_distinct_from_wrong_answer(
        tmp_path, synthetic_benchmark, monkeypatch, capsys):
    def failing_client(args, config):
        return MockClient(config, responses=[{"plan": ["Read"]}, APIError("Fixture transport failed")])

    monkeypatch.setattr(cli, "make_client", failing_client)
    output = tmp_path / "failure"
    assert cli.main(["benchmark", "--limit", "1", "--mode", "summary",
                     "--data-dir", str(synthetic_benchmark), "--out", str(output)]) == 1
    capsys.readouterr()
    result = read_json(output / "results.json")
    summary = result["summary_by_mode"]["summary"]
    assert summary["processed"] == 0 and summary["infra_errors"] == 1
    assert summary["correct"] == 0 and summary["api_errors"] == 1
    assert summary["completed_accuracy"] is None
    assert result["examples"][0]["correct"] is None
    assert read_json(output / "qa1-8k-00005" / "summary" / "memory.json") == []


def test_inspect_snapshot_renders_actual_saved_memory(tmp_path, capsys):
    output = tmp_path / "demo"
    assert cli.main(["demo", "--name", "correction", "--mode", "reflexive", "--out", str(output)]) == 0
    capsys.readouterr()
    directory = output / "reflexive"
    snapshot = tmp_path / "snapshot.svg"
    assert cli.main(["inspect", str(directory), "--snapshot", str(snapshot)]) == 0
    printed = capsys.readouterr().out
    assert "MOCK" in printed and "Snapshot:" in printed
    root = ET.parse(snapshot).getroot()
    texts = list(root.iter("{http://www.w3.org/2000/svg}text"))
    rendered = " ".join(element.text or "" for element in texts)
    event = [e for e in read_jsonl(directory / "trace.jsonl") if e["event"] == "memory_update"][-1]
    assert "Before compression" in rendered and "After compression" in rendered
    assert "mock / deterministic-demo-fixture" in rendered
    for entry in event["memory_after"]:
        assert entry["text"] in rendered


def test_existing_output_is_never_overwritten(tmp_path, capsys):
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("existing result", encoding="utf-8")
    assert cli.main(["demo", "--out", str(output)]) == 2
    assert "Error (FileExistsError)" in capsys.readouterr().err
    assert sentinel.read_text(encoding="utf-8") == "existing result"


def test_default_doctor_reports_presence_without_secrets_or_generation(monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "doctor-private-sentinel")
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    monkeypatch.setattr(cli, "make_client", lambda *_: pytest.fail("Default doctor created an API client"))
    assert cli.main(["doctor"]) == 0
    text = capsys.readouterr().out
    result = json.loads(text)
    assert result["generation_performed"] is False
    assert result["openrouter_key_present"] and result["openrouter_model_present"]
    assert "doctor-private-sentinel" not in text
