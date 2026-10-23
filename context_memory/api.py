"""Synchronous OpenRouter and Ollama clients with usage accounting."""

import copy
import ipaddress
import json
import math
import os
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx
from jsonschema import Draft202012Validator, SchemaError, ValidationError

from .errors import APIError, LimitError, ResponseError
from .tokens import count, dumps


class HTTPClient:
    """One explicitly selected model and one cumulative generation budget."""

    def __init__(self, provider, model, config, budget_usd=None, api_key=None,
                 base_url=None, transport=None, sleep=time.sleep, seed=42,
                 timeout_s=60, local_context_tokens=8192):
        if provider not in {"openrouter", "ollama", "openai"}:
            raise APIError("Provider must be openrouter, ollama or openai")
        if type(seed) is not int or type(local_context_tokens) is not int or local_context_tokens <= 0:
            raise APIError("Invalid local runtime options")
        if not isinstance(timeout_s, (int, float)) or not math.isfinite(timeout_s) or timeout_s <= 0:
            raise APIError("timeout_s must be positive")
        self.seed, self.local_context_tokens = seed, local_context_tokens
        if not isinstance(model, str) or not model.strip():
            raise APIError("An explicit model identifier is required")
        self.provider, self.model, self.config = provider, model.strip(), config
        self.records = []
        self.budget_usd = budget_usd
        self.spent_usd = 0.0
        self.attempts = 0
        self._unknown_cost = False
        self._fatal_error = None
        self._ready = False
        self._sleep = sleep
        self._api_key = None
        self._secrets = tuple(value for value in
                              (api_key, os.getenv("OPENROUTER_API_KEY")) if value)
        if provider == "openrouter":
            if (isinstance(budget_usd, bool) or not isinstance(budget_usd, (int, float))
                    or not math.isfinite(budget_usd) or budget_usd <= 0):
                raise APIError("OpenRouter requires an explicit positive budget_usd")
            self._api_key = api_key or os.getenv("OPENROUTER_API_KEY")
            if not self._api_key or not self._api_key.strip():
                raise APIError("OPENROUTER_API_KEY is required")
            self.base_url = (base_url or "https://openrouter.ai/api/v1").rstrip("/")
            if self.base_url != "https://openrouter.ai/api/v1":
                raise APIError("OpenRouter base URL must be https://openrouter.ai/api/v1")
        else:
            self.base_url = (base_url or ("http://127.0.0.1:11434" if provider == "ollama" else "http://127.0.0.1:8000/v1")).rstrip("/")
            self._validate_local_url()
            if re.search(r"(?:^|[/:_-])cloud(?:$|[/:_-])", self.model, re.I):
                raise APIError("Ollama cloud model identifiers are not allowed")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = "Bearer " + self._api_key
        self._http = httpx.Client(headers=headers, timeout=timeout_s, transport=transport,
                                  follow_redirects=False, trust_env=False)

    def _validate_local_url(self):
        try:
            parsed = urlsplit(self.base_url)
            loopback = (parsed.hostname == "localhost"
                        or ipaddress.ip_address(parsed.hostname or "").is_loopback)
            parsed.port  # Validate malformed/out-of-range ports before any request.
        except ValueError:
            raise APIError("Ollama requires a valid loopback HTTP(S) base URL") from None
        if (not loopback or parsed.scheme not in {"http", "https"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ({"", "/"} if self.provider == "ollama" else {"/v1"})):
            raise APIError("Ollama requires a loopback HTTP(S) base URL without a path")

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _sanitize(self, value):
        """Keep body telemetry, never credentials or raw exception messages."""
        if isinstance(value, dict):
            return {self._sanitize(str(key)): (
                "[REDACTED]" if str(key).lower() in {
                    "authorization", "api_key", "apikey", "access_token", "token"
                } else self._sanitize(item)) for key, item in value.items()}
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        if isinstance(value, str):
            for secret in self._secrets:
                value = value.replace(secret, "[REDACTED]")
            value = re.sub(r"Bearer\s+[^\s\"'<>]+", "Bearer [REDACTED]", value,
                           flags=re.I)
            return re.sub(r"sk-or-v1-[A-Za-z0-9_-]+", "[REDACTED]", value)
        return value

    def build_payload(self, messages, schema):
        """The complete POST body; no hidden schema or prompt is added later."""
        if self.provider in {"openrouter", "openai"}:
            payload = {
                "model": self.model, "messages": messages, "stream": False,
                "temperature": 0, "max_tokens": self.config.max_output_tokens,
                "response_format": {"type": "json_schema", "json_schema": {
                    "name": "memory_response", "strict": True, "schema": schema}},
                "provider": {"require_parameters": True},
                "plugins": [{"id": "context-compression", "enabled": False}],
            }
            if self.provider == "openai":
                payload.pop("plugins")
                payload.pop("provider")
                payload["seed"] = self.seed
        else:
            payload = {
                "model": self.model, "messages": messages, "stream": False,
                "format": schema, "options": {"temperature": 0,
                    "num_predict": self.config.max_output_tokens, "num_ctx": self.local_context_tokens, "seed": self.seed},
            }
        return copy.deepcopy(payload)

    def _metadata(self, method, path, payload=None):
        try:
            response = self._http.request(method, self.base_url + path,
                                          content=dumps(payload) if payload else None)
        except httpx.TransportError as exc:
            raise APIError("Provider metadata request failed: " + type(exc).__name__) from None
        if not response.is_success:
            raise APIError(f"Provider metadata returned HTTP {response.status_code}")
        try:
            data = response.json()
        except (ValueError, UnicodeError):
            raise APIError("Provider metadata is not valid JSON") from None
        if not isinstance(data, dict):
            raise APIError("Provider metadata must be a JSON object")
        return data

    def preflight(self):
        """Validate availability without generation, downloads, or paid calls."""
        if self.provider == "openrouter":
            data = self._metadata("GET", "/models")
            models = data.get("data", [])
            if not isinstance(models, list):
                raise APIError("OpenRouter model metadata has an unexpected format")
            model = next((item for item in models if isinstance(item, dict)
                          and item.get("id") == self.model), None)
            if model is None:
                raise APIError("Selected model is absent from OpenRouter model metadata")
            supported = model.get("supported_parameters") or []
            if (not isinstance(supported, list)
                    or not {"response_format", "structured_outputs"}.issubset(supported)):
                raise APIError("Selected model does not advertise response_format and structured_outputs")
            architecture = model.get("architecture") or {}
            if (not isinstance(architecture, dict)
                    or "text" not in architecture.get("input_modalities", [])
                    or "text" not in architecture.get("output_modalities", [])):
                raise APIError("Selected model does not advertise text input and output")
        elif self.provider == "openai":
            models = self._metadata("GET", "/models").get("data", [])
            model = next((m for m in models if isinstance(m, dict) and m.get("id") == self.model), None) if isinstance(models, list) else None
            if model is None:
                raise APIError("Selected model is absent from local server /models")
        else:
            model = self._metadata("POST", "/api/show", {"model": self.model})
            if model.get("remote_host") or model.get("remote_model"):
                raise APIError("Selected Ollama model is remote; a local model is required")
            if "completion" not in (model.get("capabilities") or []):
                raise APIError("Selected Ollama model does not advertise text completion")
        self._ready = True
        self.model_metadata = self._sanitize(model)
        return {"provider": self.provider, "model": self.model,
                "ready": True, "generation_performed": False}

    def _check_limits(self):
        if self._fatal_error:
            raise APIError(self._fatal_error)
        if self.attempts >= self.config.max_api_calls:
            raise LimitError("Maximum API generation attempts reached")
        if self.provider == "openrouter":
            if self._unknown_cost:
                raise LimitError("Previous OpenRouter cost is unknown; further requests stopped")
            if self.spent_usd >= self.budget_usd:
                raise LimitError("OpenRouter budget reached; further requests stopped")

    def _record(self, stage, payload, response, attempt, duration, error, status=None):
        usage, response_id = {}, None
        if isinstance(response, dict):
            response_id = response.get("id")
            if self.provider in {"openrouter", "openai"}:
                usage = response.get("usage") or {}
                if not isinstance(usage, dict):
                    usage = {}
            else:
                usage = {"prompt_tokens": response.get("prompt_eval_count"),
                         "completion_tokens": response.get("eval_count")}
                if all(isinstance(v, int) for v in usage.values()):
                    usage["total_tokens"] = sum(usage.values())
        cost = usage.get("cost") if self.provider == "openrouter" else 0.0
        if (isinstance(cost, bool) or not isinstance(cost, (int, float))
                or not math.isfinite(cost) or cost < 0):
            cost = None
        if cost is None and self.provider == "openrouter":
            self._unknown_cost = True
        elif cost is not None:
            self.spent_usd += cost
        record = self._sanitize({
            "stage": stage, "provider": self.provider, "model": self.model,
            "request": payload, "response": response, "response_id": response_id,
            "usage": usage, "cost_usd": cost, "duration_s": duration,
            "attempt": attempt, "error": error, "http_status": status,
            "error_type": "APIError" if error else None,
            "request_ref_tokens": count(payload),
            "cost_basis": ("local API charge; local compute excluded"
                           if self.provider != "openrouter" else "OpenRouter usage.cost"),
        })
        self.records.append(record)
        return record

    @staticmethod
    def _retry_delay(response, attempt):
        raw = response.headers.get("Retry-After") if response is not None else None
        if raw:
            try:
                seconds = float(raw)
                if math.isfinite(seconds) and seconds >= 0:
                    return seconds
            except ValueError:
                try:
                    deadline = parsedate_to_datetime(raw)
                    if deadline.tzinfo is None:
                        deadline = deadline.replace(tzinfo=timezone.utc)
                    return max(0.0, (deadline - datetime.now(timezone.utc)).total_seconds())
                except (ValueError, TypeError, OverflowError):
                    pass
        return float(2 ** (attempt - 1))

    @staticmethod
    def _bad_constant(_):
        raise ValueError("Non-finite JSON constant")

    def _parse(self, response, schema):
        if not isinstance(response, dict):
            raise ResponseError("API response is not a JSON object")
        if response.get("error"):
            raise APIError("Provider returned an error object")
        try:
            if self.provider in {"openrouter", "openai"}:
                choice = response["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise ResponseError("Model response was truncated or did not finish normally")
                content = choice["message"]["content"]
            else:
                if response.get("done") is not True or response.get("done_reason") != "stop":
                    raise ResponseError("Local model response was truncated or did not finish normally")
                content = response["message"]["content"]
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ResponseError("API response is missing the model answer") from None
        if not isinstance(content, str) or not content.strip():
            raise ResponseError("Model returned an empty answer")
        try:
            parsed = json.loads(content, parse_constant=self._bad_constant)
        except (ValueError, TypeError):
            raise ResponseError("Model answer is not valid JSON") from None
        if not isinstance(parsed, dict):
            raise ResponseError("Model answer must be a JSON object")
        try:
            Draft202012Validator(schema).validate(parsed)
        except ValidationError as exc:
            path = "/".join(map(str, exc.absolute_path))
            raise ResponseError(f"Model answer violates JSON schema: {exc.validator} at {path}") from None
        return parsed

    def complete(self, stage, messages, schema):
        """Generate once, with at most two retries for temporary HTTP failures."""
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError:
            raise ResponseError("Invalid response JSON schema") from None
        payload = self.build_payload(messages, schema)
        if count(payload) + self.config.max_output_tokens > self.config.window_ref_tokens:
            raise LimitError("Request including response reserve exceeds the application window")
        self._check_limits()
        if not self._ready:
            self.preflight()
        path = "/api/chat" if self.provider == "ollama" else "/chat/completions"
        for attempt in range(1, 4):
            self._check_limits()
            self.attempts += 1
            started = time.perf_counter()
            try:
                # The same serialization is used by tokens.count(payload).
                response = self._http.post(self.base_url + path,
                                           content=dumps(payload).encode("utf-8"))
            except httpx.TransportError as exc:
                error = "Provider transport failure: " + type(exc).__name__
                self._record(stage, payload, None, attempt,
                             time.perf_counter() - started, error)
                temporary = isinstance(exc, (httpx.TimeoutException, httpx.NetworkError,
                                              httpx.RemoteProtocolError))
                if temporary and attempt < 3:
                    self._check_limits()
                    self._sleep(self._retry_delay(None, attempt))
                    continue
                raise APIError(error) from None
            duration = time.perf_counter() - started
            try:
                body = response.json()
            except (ValueError, UnicodeError):
                body = response.text
            record = self._record(stage, payload, body, attempt, duration, None,
                                  response.status_code)
            if not response.is_success:
                error = f"Provider returned HTTP {response.status_code}"
                record["error"] = error
                record["error_type"] = "APIError"
                if response.status_code in {401, 402}:
                    self._fatal_error = error + "; client stopped"
                if (response.status_code == 429 or 500 <= response.status_code < 600) and attempt < 3:
                    self._check_limits()
                    self._sleep(self._retry_delay(response, attempt))
                    continue
                raise APIError(error)
            try:
                return self._parse(body, schema)
            except (APIError, ResponseError) as exc:
                record["error"] = str(exc)
                record["error_type"] = type(exc).__name__
                raise
        raise APIError("Retry limit reached")
