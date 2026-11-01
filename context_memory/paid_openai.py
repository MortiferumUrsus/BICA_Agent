"""Direct OpenAI API, with durable reservations shared by all experiment workers."""
import copy
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

import httpx
from jsonschema import Draft202012Validator

from .api import HTTPClient
from .errors import APIError, LimitError, ResponseError
from .tokens import count, dumps


# Standard tier USD / million tokens, checked 2026-11-01 against official pricing.
# Tuple: uncached input, cached input, output (including reasoning).
PRICES = {
    "gpt-4.1-mini-2025-04-14": (0.40, 0.10, 1.60),
    "gpt-5.4-nano-2026-03-17": (0.20, 0.02, 1.25),
    "gpt-5.4-mini-2026-03-17": (0.75, 0.075, 4.50),
}
PRICE_SOURCE = "https://developers.openai.com/api/docs/pricing"


def read_api_key(path=None):
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        path = path or os.getenv("OPENAI_API_KEY_FILE")
        if path:
            contents = Path(path).read_text(encoding="utf-8-sig").strip()
            if re.fullmatch(r"sk-[A-Za-z0-9_-]+", contents):
                key = contents
    if not key or not key.strip():
        raise APIError("Set OPENAI_API_KEY or an OPENAI_API_KEY_FILE containing only the key")
    return key.strip()


class BudgetLedger:
    """SQLite transactions prevent concurrent jobs or restarts from resetting spend.

    Pending/ambiguous requests continue to count at their full reservation. The
    user account may have other charges; this ledger covers this experiment only.
    """
    def __init__(self, path, limit_usd):
        if isinstance(limit_usd, bool) or not isinstance(limit_usd, (int, float)) or not math.isfinite(limit_usd) or limit_usd <= 0:
            raise ValueError("A positive finite budget is required")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, cap REAL NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS calls (id TEXT PRIMARY KEY, model TEXT, stage TEXT, reserved REAL, charged REAL, state TEXT, response_id TEXT, usage TEXT)")
            db.execute("INSERT OR IGNORE INTO settings VALUES (1, ?)", (limit_usd,))
            if db.execute("SELECT cap FROM settings WHERE id=1").fetchone()[0] != limit_usd:
                raise ValueError("Ledger budget differs from requested budget; do not reset an active experiment")

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def snapshot(self):
        with self.connect() as db:
            cap = db.execute("SELECT cap FROM settings WHERE id=1").fetchone()[0]
            rows = db.execute("SELECT state, COUNT(*), SUM(charged), SUM(reserved) FROM calls GROUP BY state").fetchall()
        return {"limit_usd": cap, "accounted_usd": sum(r[2] for r in rows),
                "by_state": {r[0]: {"calls": r[1], "charged_usd": r[2], "reserved_usd": r[3]} for r in rows}}

    def reserve(self, model, stage, amount):
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("Invalid reservation")
        identity = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            cap = db.execute("SELECT cap FROM settings WHERE id=1").fetchone()[0]
            used = db.execute("SELECT COALESCE(SUM(charged),0) FROM calls").fetchone()[0]
            if used + amount > cap:
                raise LimitError("Shared OpenAI budget cannot cover the next request")
            db.execute("INSERT INTO calls VALUES (?,?,?,?,?,?,?,?)", (identity, model, stage, amount, amount, "pending", None, None))
        return identity

    def settle(self, identity, cost, response_id=None, usage=None):
        if cost is not None and (not math.isfinite(cost) or cost < 0):
            raise ValueError("Invalid settled cost")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT reserved, state FROM calls WHERE id=?", (identity,)).fetchone()
            if not row or row[1] != "pending":
                raise ValueError("Unknown or already settled request")
            db.execute("UPDATE calls SET charged=?, state=?, response_id=?, usage=? WHERE id=?",
                       (row[0] if cost is None else cost, "unknown" if cost is None else "settled", response_id, json.dumps(usage), identity))
        if cost is not None and cost > row[0] + 1e-9:
            raise LimitError("Actual charge exceeded conservative reservation; stop and inspect pricing")


def wire_schema(schema):
    """OpenAI's schema subset omits uniqueness; enforce original schema locally."""
    if isinstance(schema, dict):
        return {k: wire_schema(v) for k, v in schema.items() if k != "uniqueItems"}
    if isinstance(schema, list):
        return [wire_schema(v) for v in schema]
    return schema


class OpenAIClient(HTTPClient):
    def __init__(self, model, config, ledger, reasoning_effort=None, api_key=None,
                 key_file=None, timeout_s=120, transport=None, sleep=time.sleep):
        if model not in PRICES:
            raise APIError("Model needs an explicit verified price in paid_openai.PRICES")
        if model.startswith("gpt-4.1"):
            if reasoning_effort not in {None, "none"}:
                raise APIError("GPT-4.1 does not support reasoning effort")
            reasoning_effort = None
        elif reasoning_effort not in {"none", "low", "medium", "high", "xhigh"}:
            raise APIError("Specify reasoning effort for GPT-5.4")
        key = api_key or read_api_key(key_file)
        self.provider, self.model, self.config = "openai-api", model, config
        self.ledger, self.reasoning_effort = ledger, reasoning_effort
        self.records, self.attempts, self.spent_usd = [], 0, 0.0
        self._ready, self._fatal_error, self._sleep = False, None, sleep
        self._secrets = (key,)
        self.base_url = "https://api.openai.com/v1"
        self._http = httpx.Client(headers={"Authorization": "Bearer " + key,
            "Content-Type": "application/json"}, timeout=timeout_s, transport=transport,
            follow_redirects=False, trust_env=False)

    def preflight(self):
        model = self._metadata("GET", "/models/" + self.model)
        if model.get("id") != self.model:
            raise APIError("Requested model snapshot not available")
        self.model_metadata, self._ready = self._sanitize(model), True
        return {"provider": self.provider, "model": self.model, "ready": True, "generation_performed": False}

    def build_payload(self, messages, schema):
        payload = {"model": self.model, "messages": copy.deepcopy(messages),
            "max_completion_tokens": self.config.max_output_tokens, "stream": False,
            "store": False, "service_tier": "default",
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "memory_response", "strict": True, "schema": wire_schema(schema)}}}
        if self.reasoning_effort is not None:
            payload["reasoning_effort"] = self.reasoning_effort
        else:
            payload["temperature"] = 0
        return payload

    def _parse(self, response, schema):
        # Reuse the Chat Completions parser without identifying this as a free
        # local provider anywhere in accounting or exported artifacts.
        if not isinstance(response, dict):
            raise ResponseError("API response is not an object")
        try:
            choice = response["choices"][0]
            if choice["finish_reason"] != "stop":
                raise ResponseError("Output truncated (reasoning and visible tokens share the cap)")
            content = choice["message"]["content"]
            value = json.loads(content)
            Draft202012Validator(schema).validate(value)
            return value
        except ResponseError:
            raise
        except Exception as exc:
            raise ResponseError("Invalid structured output: " + type(exc).__name__) from None

    def complete(self, stage, messages, schema):
        Draft202012Validator.check_schema(schema)
        payload = self.build_payload(messages, schema)
        if count(payload) + self.config.max_output_tokens > self.config.window_ref_tokens:
            raise LimitError("Request plus output reserve exceeds application window")
        if self._fatal_error:
            raise APIError(self._fatal_error)
        if not self._ready:
            self.preflight()
        rates = PRICES[self.model]
        # Bytes upper-bound byte-BPE input tokens, with additional framing margin.
        reservation = ((len(dumps(payload).encode("utf-8")) + 1024) * rates[0]
                       + self.config.max_output_tokens * rates[2]) / 1e6
        for attempt in range(1, 4):
            if self.attempts >= self.config.max_api_calls:
                raise LimitError("Maximum API attempts reached")
            identity = self.ledger.reserve(self.model, stage, reservation)
            self.attempts += 1
            started = time.perf_counter()
            body, status, cost, usage, error = None, None, None, {}, None
            try:
                response = self._http.post(self.base_url + "/chat/completions", content=dumps(payload).encode("utf-8"))
                status = response.status_code
                try:
                    body = response.json()
                except ValueError:
                    body = {"error": "Non-JSON HTTP response"}
                if not response.is_success:
                    error = f"OpenAI HTTP {status}"
                    if 400 <= status < 500:
                        cost = 0.0
                    if status in {401, 402, 403} or (isinstance(body, dict) and body.get("error", {}).get("code") == "insufficient_quota"):
                        self._fatal_error = error
                else:
                    usage = body.get("usage", {})
                    inp, out = usage.get("prompt_tokens"), usage.get("completion_tokens")
                    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
                    if all(type(v) is int and v >= 0 for v in (inp, out, cached)) and cached <= inp:
                        cost = ((inp - cached) * rates[0] + cached * rates[1] + out * rates[2]) / 1e6
                    else:
                        error = "OpenAI usage missing; conservative charge retained"
                        self._fatal_error = error
            except httpx.TransportError as exc:
                error = "OpenAI transport failure: " + type(exc).__name__
            finally:
                response_id = body.get("id") if isinstance(body, dict) else None
                self.ledger.settle(identity, cost, response_id, usage)
                self.spent_usd += cost if cost is not None else reservation
                record = self._sanitize({"stage": stage, "provider": self.provider, "model": self.model,
                    "reasoning_effort": self.reasoning_effort, "request": payload, "response": body,
                    "response_id": response_id, "ledger_id": identity, "usage": usage,
                    "cost_usd": cost, "reserved_usd": reservation,
                    "cost_basis": "OpenAI reported usage x standard price; reasoning included",
                    "duration_s": time.perf_counter() - started, "attempt": attempt,
                    "http_status": status, "error": error, "error_type": "APIError" if error else None,
                    "request_ref_tokens": count(payload)})
                self.records.append(record)
            if error:
                if status == 429 and not self._fatal_error and attempt < 3:
                    self._sleep(min(60, max(1, self._retry_delay(response, attempt))))
                    continue
                raise APIError(error)
            try:
                return self._parse(body, schema)
            except ResponseError as exc:
                record.update(error=str(exc), error_type="ResponseError")
                raise
        raise APIError("OpenAI retry limit reached")
