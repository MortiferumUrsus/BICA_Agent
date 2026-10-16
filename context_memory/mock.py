"""Deterministic responses for demos and offline tests."""
import json
import re
from copy import deepcopy

from .errors import LimitError
from .tokens import count


class MockClient:
    provider = "mock"
    model = "deterministic-demo-fixture"

    def __init__(self, config, responses=None):
        self.config, self.records = config, []
        self.responses = iter(responses) if responses is not None else None

    def build_payload(self, messages, schema):
        return {"model": self.model, "messages": messages, "response_format": {"type": "json_schema", "schema": schema},
                "max_tokens": self.config.max_output_tokens, "stream": False}

    def complete(self, stage, messages, schema):
        if len(self.records) >= self.config.max_api_calls:
            raise LimitError("max_api_calls reached")
        body = json.loads(messages[-1]["content"])
        response = next(self.responses) if self.responses is not None else self.respond(stage, body)
        self.records.append({"stage": stage, "attempt": 1, "request": self.build_payload(messages, schema),
            "response": deepcopy(response), "response_id": f"mock-{len(self.records) + 1}",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "cost_usd": 0.0, "duration_s": 0.0, "error": None})
        if isinstance(response, Exception):
            self.records[-1]["response"] = None
            self.records[-1]["error"] = type(response).__name__
            raise response
        return response

    def _memory(self, body):
        goal = body.get("goal", "").lower()
        memory = deepcopy(body.get("old_memory", []))
        for source in body.get("new_sources", []):
            for line in source["text"].splitlines():
                if line.strip():
                    memory.append({"text": line.strip(), "source_ids": [source["chunk_id"]]})
        if "supplier" in goal or "order" in goal:
            memory = [m for m in memory if m["text"].startswith("Supplier ")]
        elif "access code" in goal:
            memory = [m for m in memory if "access code:" in m["text"].lower()]
        elif "delivery date" in goal:
            memory = [m for m in memory if "delivery date:" in m["text"].lower()][-1:]
        else:
            # Only the demo scenarios have scripted responses.
            memory = []
        unique = {m["text"].split(":", 1)[0]: m for m in memory}
        memory = list(unique.values())[-8:]
        while memory and count(memory) > body.get("memory_ref_tokens", self.config.memory_ref_tokens):
            memory.pop(0)
        return memory

    def respond(self, stage, body):
        if stage == "plan":
            return {"plan": ["Read relevant evidence", "Answer the current question"]}
        if stage == "assess":
            return {"current_stage": "Read evidence", "remaining_steps": ["Answer the current question"],
                    "missing_data": [], "selected_facts": self._memory(body)}
        if stage in ("summary", "compress"):
            return {"memory": self._memory(body)}
        if stage == "verify":
            memory = deepcopy(body["candidate_memory"])
            missing = [fact for fact in body["selected_facts"] if fact not in memory]
            return {"issues": ["Selected fact missing"] if missing else [], "memory": memory + missing}
        if stage == "answer":
            question = body["question"].lower()
            facts = body["memory"]
            answer, ids = "", []
            for fact in facts:
                text = fact["text"]
                if "delivery date" in question and "delivery date:" in text.lower():
                    answer = re.split(r"delivery date:\s*", text, flags=re.I)[1].split(".", 1)[0].strip()
                    ids = fact["source_ids"]
                elif "access code" in question and "access code:" in text.lower():
                    answer, ids = text.split(":", 1)[1].strip().rstrip("."), fact["source_ids"]
            offers = []
            for fact in facts:
                match = re.search(r"Supplier (\w+): price=(\d+); delivery_days=(\d+); payment=([^;]+); contract=([\w-]+)", fact["text"])
                if match:
                    offers.append((match, fact["source_ids"]))
            if "choose" in question and offers:
                eligible = [(m, sid) for m, sid in offers if int(m[3]) <= 5]
                if eligible:
                    match, ids = min(eligible, key=lambda item: int(item[0][2]))
                    answer = match[1]
            elif "order" in question:
                chosen = body["state"]["last_result"]
                for match, sid in offers:
                    if match[1] == chosen:
                        answer = f"{match[1]}: payment {match[4]}, contract {match[5]}"
                        ids = sid
            if answer:
                return {"status": "answer", "answer": answer, "query": "", "source_ids": ids}
            allowed = body["retrieval_allowed"]
            query = "Archive access code" if "access code" in question else body["question"]
            return {"status": "retrieve" if allowed else "insufficient_data", "answer": "", "query": query if allowed else "", "source_ids": []}
        raise ValueError(stage)
