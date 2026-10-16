import json
from copy import deepcopy
from pathlib import Path

import pytest

from context_memory.config import Config
from context_memory.core import Controller, run_scenario
from context_memory.errors import APIError, LimitError, ResponseError
from context_memory.mock import MockClient
from context_memory.storage import Journal
from context_memory.tokens import count, dumps, prefix, split_text


SCENARIOS = Path(__file__).parents[1] / "context_memory" / "scenarios"


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def bodies(client, stage=None):
    return [json.loads(r["request"]["messages"][-1]["content"])
            for r in client.records if stage is None or r["stage"] == stage]


def controller(tmp_path, mode="reflexive", config=None, client_class=MockClient):
    config = config or Config()
    client = client_class(config)
    ctl = Controller(client, tmp_path / "run", mode, config)
    ctl.start("Remember the current delivery date for Orion.")
    return ctl, client


@pytest.mark.parametrize("limit", [5, 11, 32])
def test_unicode_splitting_preserves_every_character_and_whitespace(limit):
    original = "  Привет 👩🏽‍🔬!\r\n漢字 café e\u0301\n\n<|endoftext|> \t" * 17
    parts = list(split_text(original, limit))
    assert len(parts) > 1
    assert "".join(parts) == original
    assert all(0 < count(part) <= limit for part in parts)
    assert all("\ufffd" not in part for part in parts)
    assert prefix(original, limit) == parts[0]


def test_unrepresentable_single_character_is_not_replaced_or_dropped():
    with pytest.raises(ValueError, match="one character"):
        list(split_text("😀", 1))


def test_journal_is_append_only_and_readers_cannot_mutate_it(tmp_path):
    journal = Journal(tmp_path / "journal.jsonl")
    first = journal.append("Первая строка\r\n  ")
    first_bytes = journal.path.read_bytes()
    first["text"] = "changed outside journal"
    view = journal.chunks
    view[0]["text"] = "also changed outside journal"
    journal.append("第二行 😀\n")
    assert journal.path.read_bytes().startswith(first_bytes)
    assert journal.chunks == [
        {"chunk_id": "c001", "order": 0, "text": "Первая строка\r\n  "},
        {"chunk_id": "c002", "order": 1, "text": "第二行 😀\n"},
    ]
    assert read_jsonl(journal.path) == journal.chunks
    with pytest.raises(ValueError, match="overwrite or reuse"):
        Journal(journal.path)


def test_search_cannot_read_future_or_another_examples_sources(tmp_path):
    left = Journal(tmp_path / "left.jsonl")
    right = Journal(tmp_path / "right.jsonl")
    left.append("Mary is in the kitchen.")
    right.append("Mary is in the garden. Secret: RIGHT-ONLY.")
    assert left.retrieve("RIGHT-ONLY") == []
    assert left.retrieve(source_ids=["c001"])[0]["text"] == "Mary is in the kitchen."
    with pytest.raises(ResponseError, match="unread"):
        left.retrieve(source_ids=["c002"])
    left.append("Mary moved to the hallway.")
    assert [r["chunk_id"] for r in left.retrieve("Mary")] == ["c002", "c001"]
    left.append("Mary moved to the office.")
    assert len(left.retrieve("Mary", top_k=9)) == 2
    assert len(left.retrieve(source_ids=["c001", "c002", "c003"], top_k=9)) == 2


@pytest.mark.parametrize("mode", ["summary", "reflexive"])
def test_every_sent_request_and_source_chunk_obey_limits(tmp_path, mode):
    config = Config(window_ref_tokens=1800, max_output_tokens=256,
                    memory_ref_tokens=128, chunk_ref_tokens=4096)
    ctl, client = controller(tmp_path, mode, config)
    text = "  The irrelevant meeting discussed packaging and chairs. Привет 😀.\n" * 140
    assert count(text) > config.window_ref_tokens
    ctl.ingest(text)
    assert "".join(c["text"] for c in ctl.journal.chunks) == text
    assert [c["order"] for c in ctl.journal.chunks] == list(range(len(ctl.journal.chunks)))
    assert len(ctl.journal.chunks) > 1
    assert all(count(c["text"]) <= config.chunk_ref_tokens for c in ctl.journal.chunks)
    assert all(count(r["request"]) + config.max_output_tokens <= config.window_ref_tokens
               for r in client.records)
    assert all(v["ref_tokens"] <= config.memory_ref_tokens
               for v in read_jsonl(ctl.run_dir / "memory_versions.jsonl"))
    assert count(ctl.state) <= config.state_ref_tokens


@pytest.mark.parametrize("mode", ["summary", "reflexive"])
@pytest.mark.parametrize("name", ["correction", "supplier", "retrieval"])
def test_all_demo_paths_and_phase_disclosure(tmp_path, mode, name):
    scenario = json.loads((SCENARIOS / f"{name}.json").read_text(encoding="utf-8"))
    config = Config()
    client = MockClient(config)
    run_dir = tmp_path / "run"
    result = run_scenario(client, scenario, run_dir, mode, config)
    assert result["status"] == "completed", result["error"]
    assert result["provider"] == "mock"
    assert result["metrics"]["compressions"] >= 3
    assert all(a["final"]["status"] == "answer" for a in result["answers"])
    if name == "correction":
        answer = result["answers"][0]["final"]
        assert "19 November 2026" in answer["answer"]
        assert "12 November" not in dumps(result["memory"])
        assert "c003" in answer["source_ids"]
    elif name == "supplier":
        assert result["answers"][0]["final"]["answer"] == "Cedar"
        assert "30% advance" in result["answers"][1]["final"]["answer"]
        assert "CD-104" in result["answers"][1]["final"]["answer"]
        assert result["state"]["completed_results"][0] == "Cedar"
        first_answer = next(i for i, r in enumerate(client.records) if r["stage"] == "answer")
        hidden_goal = next(e["goal"] for e in scenario["events"] if "goal" in e)
        assert all(hidden_goal not in dumps(r["request"]) for r in client.records[:first_answer + 1])
        transitions = [r for r in read_jsonl(run_dir / "trace.jsonl") if r["event"] == "transition"]
        assert len(transitions) == 1
        assert transitions[0]["state_after"]["last_result"] == "Cedar"
        assert any(v["reason"] == "transition" for v in read_jsonl(run_dir / "memory_versions.jsonl"))
    else:
        answer = result["answers"][-1]
        assert answer["before_retrieval"]["status"] == "retrieve"
        assert answer["retrieved_ids"] == ["c001"]
        assert answer["final"]["answer"] == "RIVER-17"
        assert result["metrics"]["retrievals"] == 1
        assert result["metrics"]["reread_ref_tokens"] > 0
    stages = [r["stage"] for r in client.records]
    assert ("assess" in stages) is (mode == "reflexive")
    assert ("verify" in stages) is (mode == "reflexive")


def test_verification_restores_an_intentionally_lost_selected_fact(tmp_path):
    class LosingCompressor(MockClient):
        def respond(self, stage, body):
            if stage == "compress":
                return {"memory": []}
            return super().respond(stage, body)

    ctl, client = controller(tmp_path, client_class=LosingCompressor)
    ctl.ingest("Orion delivery date: Thursday.\n")
    assert ctl.memory == [{"text": "Orion delivery date: Thursday.", "source_ids": ["c001"]}]
    assert bodies(client, "verify")[0]["candidate_memory"] == []
    events = read_jsonl(ctl.run_dir / "trace.jsonl")
    update = next(e for e in events if e["event"] == "memory_update")
    assert update["verification"]["issues"] == ["Selected fact missing"]
    assert [r["stage"] for r in client.records].count("verify") == 1


def test_repeated_retrieve_decision_stops_after_one_round(tmp_path):
    class AlwaysRetrieve(MockClient):
        def respond(self, stage, body):
            if stage == "answer":
                return {"status": "retrieve", "answer": "", "query": "delivery", "source_ids": []}
            return super().respond(stage, body)

    ctl, client = controller(tmp_path, client_class=AlwaysRetrieve)
    ctl.ingest("Orion delivery date: Thursday.\n")
    outcome = ctl.checkpoint("What is the delivery date?")
    assert outcome["before_retrieval"]["status"] == "retrieve"
    assert outcome["final"]["status"] == "insufficient_data"
    assert outcome["final"]["answer"] == ""
    assert [b["retrieval_allowed"] for b in bodies(client, "answer")] == [True, False]
    assert ctl.metrics["retrievals"] == 1
    assert len(ctl.journal.chunks) == 1  # Rereading does not duplicate original evidence.


@pytest.mark.parametrize("failure", [
    {"unexpected": "schema violation"},
    APIError("temporary network failure"),
    ResponseError("invalid JSON"),
    {"memory": [{"text": "fabricated", "source_ids": ["c999"]}]},
])
def test_bad_response_or_api_error_preserves_last_committed_memory(tmp_path, failure):
    ctl, client = controller(tmp_path, mode="summary")
    ctl.ingest("Orion delivery date: Monday.\n")
    before = deepcopy(ctl.memory)
    disk_before = (ctl.run_dir / "memory.json").read_bytes()
    versions_before = (ctl.run_dir / "memory_versions.jsonl").read_bytes()
    client.responses = iter([failure])
    with pytest.raises((APIError, ResponseError)):
        ctl.ingest("Orion delivery date: Thursday.\n")
    assert ctl.memory == before
    assert (ctl.run_dir / "memory.json").read_bytes() == disk_before
    assert (ctl.run_dir / "memory_versions.jsonl").read_bytes() == versions_before
    assert ctl.version == 1
    assert len(ctl.journal.chunks) == 2  # Original new evidence survives the failed step.
    assert read_jsonl(ctl.run_dir / "trace.jsonl")[-1]["event"] == "step_error"


def test_failed_verification_does_not_commit_candidate(tmp_path):
    class FailingVerifier(MockClient):
        fail = False

        def respond(self, stage, body):
            if stage == "verify" and self.fail:
                raise APIError("verification unavailable")
            return super().respond(stage, body)

    ctl, client = controller(tmp_path, client_class=FailingVerifier)
    ctl.ingest("Orion delivery date: Monday.\n")
    before = deepcopy(ctl.memory)
    client.fail = True
    with pytest.raises(APIError):
        ctl.ingest("Orion delivery date: Thursday.\n")
    assert ctl.memory == before
    assert json.loads((ctl.run_dir / "memory.json").read_text(encoding="utf-8")) == before
    assert ctl.version == 1


def test_oversized_repair_fails_without_expanding_memory(tmp_path):
    class OversizedRepair(MockClient):
        inflate = False

        def respond(self, stage, body):
            answer = super().respond(stage, body)
            if stage == "verify" and self.inflate:
                answer["memory"] = [{"text": " x" * 180,
                                     "source_ids": body["candidate_memory"][0]["source_ids"]}]
            return answer

    config = Config(memory_ref_tokens=128)
    ctl, client = controller(tmp_path, config=config, client_class=OversizedRepair)
    ctl.ingest("Orion delivery date: Monday.\n")
    before = deepcopy(ctl.memory)
    client.inflate = True
    with pytest.raises(LimitError, match="Memory exceeds"):
        ctl.ingest("Orion delivery date: Thursday.\n")
    assert ctl.memory == before
    assert ctl.config.memory_ref_tokens == 128
    assert ctl.version == 1


def test_call_limit_stops_before_next_model_action(tmp_path):
    config = Config(max_api_calls=2)
    ctl, client = controller(tmp_path, mode="summary", config=config)
    ctl.ingest("Orion delivery date: Monday.\n")
    with pytest.raises(LimitError, match="max_api_calls"):
        ctl.ingest("Orion delivery date: Thursday.\n")
    assert len(client.records) == 2
    assert ctl.version == 1
    assert "Monday" in ctl.memory[0]["text"]


def test_oversized_request_is_rejected_before_any_client_call(tmp_path):
    config = Config(window_ref_tokens=1000, max_output_tokens=256)
    client = MockClient(config)
    ctl = Controller(client, tmp_path / "run", config=config)
    with pytest.raises(LimitError, match="exceeds window"):
        ctl.start("word " * 3000)
    assert not client.records
    assert not ctl.state


def test_state_overflow_preserves_previous_state(tmp_path):
    ctl, _ = controller(tmp_path)
    before = deepcopy(ctl.state)
    disk_before = (ctl.run_dir / "state.json").read_bytes()
    with pytest.raises(LimitError, match="state_ref_tokens"):
        ctl._save_state({**ctl.state, "completed_results": ["word " * 3000]})
    assert ctl.state == before
    assert (ctl.run_dir / "state.json").read_bytes() == disk_before


def test_trace_and_previous_assessment_are_not_hidden_memory(tmp_path):
    class MarkedAssessment(MockClient):
        def respond(self, stage, body):
            response = super().respond(stage, body)
            if stage == "assess":
                response["missing_data"] = ["TEMPORARY_ASSESSMENT_MARKER"]
            return response

    ctl, client = controller(tmp_path, client_class=MarkedAssessment)
    ctl.trace("debug", payload="TRACE_ONLY_MARKER")
    ctl.ingest("Orion delivery date: Monday.\n")
    first_cycle_end = len(client.records)
    ctl.ingest("The meeting concerned chair colours.\n")
    assert all("TRACE_ONLY_MARKER" not in dumps(r["request"]) for r in client.records)
    next_assessment = client.records[first_cycle_end]
    assert next_assessment["stage"] == "assess"
    assert "TEMPORARY_ASSESSMENT_MARKER" not in dumps(next_assessment["request"])
    assert all(len(r["request"]["messages"]) == 2 for r in client.records)
    assert all("assessment" not in b for b in bodies(client, "verify"))
    assert "TEMPORARY_ASSESSMENT_MARKER" not in dumps(ctl.state)


@pytest.mark.parametrize("stage", ["summary", "assess", "compress", "verify", "answer"])
def test_request_schema_allows_only_source_ids_visible_to_this_stage(tmp_path, stage):
    ctl, _ = controller(tmp_path)
    hidden = ctl.journal.append("Hidden evidence from a previous step.")
    visible = ctl.journal.append("Current evidence.")
    fact = {"text": visible["text"], "source_ids": [visible["chunk_id"]]}
    if stage == "verify":
        body = {"selected_facts": [fact], "candidate_memory": [fact], "memory_ref_tokens": 512}
    elif stage == "answer":
        body = {"goal": ctl.state["goal"], "question": "What is known?", "state": ctl.state,
                "memory": [fact], "retrieval_allowed": True}
    else:
        body = ctl._body([visible])
    messages, schema, _ = ctl._request(stage, body)
    assert hidden["text"] not in dumps(messages)

    source_fields = []

    def visit(value):
        if isinstance(value, dict):
            if "source_ids" in value:
                source_fields.append(value["source_ids"])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    assert source_fields
    assert all(field["items"]["enum"] == ["c002"] for field in source_fields)


@pytest.mark.parametrize("invented_id", ["c001", "c999"])
def test_local_validation_rejects_hidden_and_future_source_ids(tmp_path, invented_id):
    ctl, client = controller(tmp_path, mode="summary")
    ctl.journal.append("Hidden historical evidence.")
    visible = ctl.journal.append("Orion delivery date: Thursday.")
    client.responses = iter([{"memory": [{"text": "Thursday", "source_ids": [invented_id]}]}])
    with pytest.raises(ResponseError, match="JSON schema"):
        ctl._call("summary", ctl._body([visible]))
    assert ctl.memory == []
    assert ctl.version == 0


def test_no_visible_sources_requires_empty_source_ids(tmp_path):
    ctl, client = controller(tmp_path)
    ctl.journal.append("Known to the journal only.")
    body = {"goal": ctl.state["goal"], "question": "Where?", "state": ctl.state,
            "memory": [], "retrieval_allowed": True}
    _, schema, _ = ctl._request("answer", body)
    assert schema["properties"]["source_ids"]["maxItems"] == 0
    client.responses = iter([{"status": "retrieve", "answer": "", "query": "Where?", "source_ids": ["c001"]}])
    with pytest.raises(ResponseError, match="JSON schema"):
        ctl._call("answer", body)


def test_fit_part_reserves_nested_json_escaping_for_quoted_assessment(tmp_path):
    config = Config()
    client = MockClient(config)
    ctl = Controller(client, tmp_path / "run", "reflexive", config)
    ctl.start("Retain exact punctuation. " + "x " * 80)
    source = ctl.journal.append('"' * 450)
    ctl.memory = [{"text": source["text"], "source_ids": [source["chunk_id"]]}]
    assessment = {"current_stage": "Read evidence", "remaining_steps": ["Answer"],
                  "missing_data": [], "selected_facts": deepcopy(ctl.memory)}
    assert count(assessment) <= config.memory_ref_tokens
    text = "New evidence text. " * 1500
    large_part = prefix(text, config.chunk_ref_tokens)
    large_body = ctl._body([{"chunk_id": "c002", "order": 1, "text": large_part}])
    base_size = ctl._request("compress", {**large_body, "assessment": {}})[2]
    # The former one-budget reserve undercounted quote escaping in user.content.
    old_estimate = base_size + config.memory_ref_tokens + 16 + config.max_output_tokens
    actual_large = ctl._request("compress", {**large_body, "assessment": assessment})[2] + config.max_output_tokens
    assert old_estimate <= config.window_ref_tokens < actual_large

    part = ctl._fit_part(text, "c002", 1)
    assert text.startswith(part)
    assert count(part) < count(large_part)
    current = ctl.journal.append(part)
    body = {**ctl._body([current]), "assessment": assessment}
    actual_size = ctl._request("compress", body)[2] + config.max_output_tokens
    assert actual_size <= config.window_ref_tokens
    client.responses = iter([{"memory": deepcopy(ctl.memory)}])
    assert ctl._call("compress", body)["memory"] == ctl.memory

def test_failed_retrieval_preserves_initial_decision_for_report(tmp_path):
    from context_memory.core import Controller
    from context_memory.errors import APIError
    from context_memory.mock import MockClient
    from context_memory.config import Config

    class FailingReread(MockClient):
        def respond(self, stage, body):
            if stage == "summary" and body.get("new_sources"):
                raise APIError("Retrieval fixture failure")
            return super().respond(stage, body)

    config = Config()
    ctl = Controller(FailingReread(config), tmp_path / "failed-reread", "summary", config)
    ctl.start("Find the archive access code.")
    ctl.journal.append("Archive access code: RIVER-17.")
    with pytest.raises(APIError):
        ctl.checkpoint("What is the archive access code?")
    assert ctl.memory == []
    assert ctl.answers[0]["before_retrieval"]["status"] == "retrieve"
    assert ctl.answers[0]["retrieved_ids"] == ["c001"]
    assert ctl.answers[0]["final"] is None
