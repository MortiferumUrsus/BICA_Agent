import json
import hashlib
import time
from copy import deepcopy
from pathlib import Path

import jsonschema

from .config import Config
from .errors import LimitError, MemoryExperimentError, ResponseError
from .schemas import schema_for
from .storage import Journal, append_jsonl, write_json
from .tokens import count, dumps, prefix


class Controller:
    def __init__(self, client, run_dir, mode="reflexive", config=None):
        if mode not in ("summary", "reflexive"):
            raise ValueError("Unknown memory mode")
        self.client, self.mode = client, mode
        self.config = config or Config()
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=False)
        self.journal = Journal(self.run_dir / "journal.jsonl")
        self.memory = []
        self.state = {}
        self.answers = []
        self.version = 0
        self.record_start = len(client.records)
        self.started = time.perf_counter()
        self.metrics = {"max_memory_ref_tokens": 0, "max_request_ref_tokens": 0,
                        "compressions": 0, "retrievals": 0, "reread_ref_tokens": 0, "input_ref_tokens": 0}

    def trace(self, event, **data):
        append_jsonl(self.run_dir / "trace.jsonl", {"event": event, "mode": self.mode, **data})

    def _request(self, stage, body):
        prompt = (Path(__file__).parent / "prompts" / f"{stage}.txt").read_text(encoding="utf-8")
        messages = [{"role": "system", "content": prompt}, {"role": "user", "content": dumps(body)}]
        schema = schema_for(stage)
        # Allow only source IDs present in this request.
        ids = set()
        def collect(value):
            if isinstance(value, dict):
                if "chunk_id" in value:
                    ids.add(value["chunk_id"])
                ids.update(value.get("source_ids", []))
                for child in value.values():
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)
        collect(body)
        def constrain(value):
            if isinstance(value, dict):
                if "source_ids" in value:
                    field = value["source_ids"]
                    if ids:
                        field["items"]["enum"] = sorted(ids)
                    else:
                        field["maxItems"] = 0
                for child in value.values():
                    constrain(child)
            elif isinstance(value, list):
                for child in value:
                    constrain(child)
        constrain(schema)
        return messages, schema, count(self.client.build_payload(messages, schema))

    def _call(self, stage, body):
        messages, schema, size = self._request(stage, body)
        total = size + self.config.max_output_tokens
        if total > self.config.window_ref_tokens:
            raise LimitError(f"{stage} request {size} + output reserve {self.config.max_output_tokens} exceeds window {self.config.window_ref_tokens}")
        self.metrics["max_request_ref_tokens"] = max(self.metrics["max_request_ref_tokens"], total)
        self.trace("call", stage=stage, input_ref_tokens=size, reserved_output_ref_tokens=self.config.max_output_tokens)
        response = self.client.complete(stage, messages, schema)
        try:
            jsonschema.validate(response, schema)
        except jsonschema.ValidationError as exc:
            raise ResponseError(f"{stage}: response violates JSON schema at {list(exc.absolute_path)}") from exc
        if count(response) > self.config.max_output_tokens:
            raise LimitError(f"{stage} response exceeds reference output reserve")
        return response

    def _save_state(self, state):
        if count(state) > self.config.state_ref_tokens:
            raise LimitError("Task state exceeds state_ref_tokens; last saved state is preserved")
        self.state = deepcopy(state)
        write_json(self.run_dir / "state.json", self.state)

    def start(self, goal):
        plan = self._call("plan", {"goal": goal})["plan"]
        self._save_state({"goal": goal, "plan": plan, "current_step": plan[0], "last_result": "", "completed_results": []})
        write_json(self.run_dir / "memory.json", [])
        self.trace("start", state=self.state)

    def transition(self, goal):
        before = deepcopy(self.state)
        plan = self._call("plan", {"goal": goal, "last_result": self.state["last_result"]})["plan"]
        self._save_state({**self.state, "goal": goal, "plan": plan, "current_step": plan[0]})
        self.trace("transition", state_before=before, state_after=self.state, memory_before=self.memory)
        self.update([], reason="transition")

    def _body(self, sources):
        common = {"goal": self.state["goal"], "old_memory": self.memory, "new_sources": sources,
                  "memory_ref_tokens": self.config.memory_ref_tokens}
        if self.mode == "reflexive":
            common["state"] = self.state
            common["assessment_ref_tokens"] = self.config.memory_ref_tokens
        return common

    def _fit_part(self, text, chunk_id, order):
        limit = self.config.chunk_ref_tokens
        while limit:
            part = prefix(text, limit)
            if not part:
                break
            body = self._body([{"chunk_id": chunk_id, "order": order, "text": part}])
            stage = "summary" if self.mode == "summary" else "assess"
            size = self._request(stage, body)[2]
            if self.mode == "reflexive":
                # Reserve the *entire* assessment for the next compression request.
                # JSON is nested in user.content: reserve escaped content too.
                compressed_size = self._request("compress", {**body, "assessment": {}})[2] + 2 * self.config.memory_ref_tokens + 64
                size = max(size, compressed_size)
            if size + self.config.max_output_tokens <= self.config.window_ref_tokens:
                return part
            limit //= 2
        raise LimitError("No source character fits beside the existing memory/state; nothing is silently dropped")

    def ingest(self, text):
        while text:
            index = len(self.journal.chunks)
            part = self._fit_part(text, f"c{index + 1:03d}", index)
            chunk = self.journal.append(part)
            self.metrics["input_ref_tokens"] += count(part)
            self.trace("read", chunk=chunk)
            self.update([chunk], reason="read")
            text = text[len(part):]

    def _validate_memory(self, memory):
        if count(memory) > self.config.memory_ref_tokens:
            raise LimitError("Memory exceeds memory_ref_tokens; last valid memory is preserved")
        for fact in memory:
            self.journal.validate_ids(fact["source_ids"])

    def update(self, sources, reason="read"):
        before = deepcopy(self.memory)
        body = self._body(sources)
        assessment = None
        verification = None
        try:
            if self.mode == "summary":
                candidate = self._call("summary", body)["memory"]
            else:
                assessment = self._call("assess", body)
                if count(assessment) > self.config.memory_ref_tokens:
                    raise LimitError("Assessment exceeds its explicit temporary budget")
                self._validate_memory(assessment["selected_facts"])
                self.trace("assessment", assessment=assessment, sources=sources)
                candidate = self._call("compress", {**body, "assessment": assessment})["memory"]
                # Candidate is never committed before a successful verification.
                self._validate_memory(candidate)
                verification = self._call("verify", {"selected_facts": assessment["selected_facts"],
                    "candidate_memory": candidate, "memory_ref_tokens": self.config.memory_ref_tokens})
                candidate = verification["memory"]
            self._validate_memory(candidate)
        except MemoryExperimentError as exc:
            self.trace("step_error", reason=reason, error_type=type(exc).__name__, error=str(exc), memory_before=before)
            raise
        self.memory = deepcopy(candidate)
        self.version += 1
        self.metrics["compressions"] += 1
        self.metrics["max_memory_ref_tokens"] = max(self.metrics["max_memory_ref_tokens"], count(candidate))
        version = {"version": self.version, "reason": reason, "memory": self.memory, "ref_tokens": count(self.memory)}
        append_jsonl(self.run_dir / "memory_versions.jsonl", version)
        write_json(self.run_dir / "memory.json", self.memory)
        self.trace("memory_update", reason=reason, current_stage=self.state["current_step"], sources=sources,
                   selected_facts=assessment["selected_facts"] if assessment else None,
                   memory_before=before, memory_after=self.memory, verification=verification)

    def _decision(self, question, retrieval_allowed):
        result = self._call("answer", {"goal": self.state["goal"], "question": question,
                         "state": self.state, "memory": self.memory, "retrieval_allowed": retrieval_allowed})
        self.journal.validate_ids(result["source_ids"])
        if result["status"] == "answer" and not result["answer"].strip():
            result = {"status": "insufficient_data", "answer": "", "query": "", "source_ids": []}
        if result["status"] == "retrieve" and not retrieval_allowed:
            result = {"status": "insufficient_data", "answer": "", "query": "", "source_ids": []}
        return result

    def checkpoint(self, question):
        first = self._decision(question, True)
        outcome = {"question": question, "before_retrieval": first, "final": None, "retrieved_ids": []}
        self.answers.append(outcome)
        self.trace("decision_before_retrieval", question=question, decision=first)
        final = first
        retrieved = []
        if first["status"] == "retrieve":
            self.metrics["retrievals"] += 1
            chunks = self.journal.retrieve(first["query"], first["source_ids"], self.config.retrieval_top_k)
            retrieved = [c["chunk_id"] for c in chunks]
            outcome["retrieved_ids"] = retrieved
            self.trace("retrieve", query=first["query"], requested_ids=first["source_ids"], found_ids=retrieved)
            for chunk in chunks:
                text = chunk["text"]
                while text:
                    part = self._fit_part(text, chunk["chunk_id"], chunk["order"])
                    self.metrics["reread_ref_tokens"] += count(part)
                    self.update([{**chunk, "text": part}], reason="retrieval")
                    text = text[len(part):]
            final = self._decision(question, False)
        outcome["final"] = final
        self.trace("checkpoint", **outcome)
        if final["status"] == "answer":
            completed = (self.state["completed_results"] + [final["answer"]])[-2:]
            self._save_state({**self.state, "last_result": final["answer"], "completed_results": completed})
        return outcome

    def finish(self, name, kind="demo", error=None):
        from .reporting import summarize_records, write_report
        records = self.client.records[self.record_start:]
        with (self.run_dir / "api_calls.jsonl").open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        metrics = {**self.metrics, **summarize_records(records)}
        if error and isinstance(error, ResponseError) and not metrics.get("response_errors"):
            metrics["response_errors"] = 1
        result = {"kind": kind, "name": name, "mode": self.mode, "provider": self.client.provider,
                  "model": self.client.model, "config": self.config.to_dict(), "presentation": "question_first",
                  "status": "error" if error else "completed", "error": {"type": type(error).__name__, "message": str(error)} if error else None,
                  "answers": self.answers, "state": self.state, "memory": self.memory,
                  "metrics": metrics, "elapsed_s": round(time.perf_counter() - self.started, 3)}
        result["prompt_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sorted((Path(__file__).parent / "prompts").glob("*.txt"))}
        write_report(self.run_dir, result)
        return result


def run_scenario(client, scenario, run_dir, mode, config):
    controller = Controller(client, run_dir, mode, config)
    error = None
    try:
        controller.start(scenario["goal"])
        for event in scenario["events"]:
            if "goal" in event:
                controller.transition(event["goal"])
            if "text" in event:
                controller.ingest(event["text"])
            if "question" in event:
                controller.checkpoint(event["question"])
    except MemoryExperimentError as exc:
        error = exc
    return controller.finish(scenario["name"], error=error)
