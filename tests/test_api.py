import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest

from context_memory.api import HTTPClient
from context_memory.config import Config
from context_memory.errors import APIError, LimitError, ResponseError
from context_memory.tokens import dumps


SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}},
          "required": ["answer"], "additionalProperties": False}
MESSAGES = [{"role": "user", "content": "Return a short JSON answer."}]


def envelope(content='{"answer":"yes"}', cost=0.01, finish="stop"):
    return {"id": "gen-1", "choices": [{"message": {"content": content},
                                        "finish_reason": finish}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 5,
                      "total_tokens": 105, "cost": cost}}


def local_envelope(content='{"answer":"yes"}', finish="stop"):
    return {"message": {"content": content}, "done": True, "done_reason": finish,
            "prompt_eval_count": 21, "eval_count": 4}


def transport_for(handler, metadata=None):
    def wrapped(request):
        if request.url.path == "/api/v1/models":
            return httpx.Response(200, json=metadata if metadata is not None else {"data": [{
                "id": "test/model", "supported_parameters": ["response_format", "structured_outputs"],
                "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]}}]})
        if request.url.path == "/api/show":
            return httpx.Response(200, json=metadata if metadata is not None else {
                "capabilities": ["completion"]})
        return handler(request)
    return httpx.MockTransport(wrapped)


def client(handler, provider="openrouter", config=None, metadata=None, **kwargs):
    return HTTPClient(provider, "test/model", config or Config(),
                      transport=transport_for(handler, metadata),
                      **({"api_key": "private-test-key", "budget_usd": 1} | kwargs
                         if provider == "openrouter" else kwargs))


def test_openrouter_body_matches_counted_payload_and_logs_usage():
    sent = []
    def respond(request):
        sent.append(request)
        return httpx.Response(200, json=envelope())
    api = client(respond)
    expected = api.build_payload(MESSAGES, SCHEMA)
    assert api.complete("compress", MESSAGES, SCHEMA) == {"answer": "yes"}
    assert sent[0].content.decode() == dumps(expected)
    assert sent[0].extensions["timeout"]["read"] == 60
    assert expected["plugins"] == [{"id": "context-compression", "enabled": False}]
    assert expected["provider"] == {"require_parameters": True}
    assert expected["response_format"]["json_schema"]["strict"] is True
    assert api.records[0]["usage"]["total_tokens"] == 105
    assert api.records[0]["cost_usd"] == .01
    assert api.records[0]["response_id"] == "gen-1"
    assert "private-test-key" not in dumps(api.records)


@pytest.mark.parametrize("budget", [None, 0, -1, True, float("nan"), float("inf")])
def test_paid_api_requires_explicit_positive_budget(budget):
    with pytest.raises(APIError, match="budget"):
        HTTPClient("openrouter", "test/model", Config(), api_key="secret", budget_usd=budget)


def test_key_model_and_provider_are_required(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(APIError, match="API_KEY"):
        HTTPClient("openrouter", "test/model", Config(), budget_usd=1)
    with pytest.raises(APIError, match="model"):
        HTTPClient("ollama", " ", Config())
    with pytest.raises(APIError, match="Provider"):
        HTTPClient("other", "test/model", Config())


def test_env_key_fallback(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "env-private-key")
    seen = []
    def respond(request):
        seen.append(request.headers["Authorization"])
        return httpx.Response(200, json=envelope())
    api = HTTPClient("openrouter", "test/model", Config(), budget_usd=1,
                     transport=transport_for(respond))
    api.complete("answer", MESSAGES, SCHEMA)
    assert seen == ["Bearer env-private-key"]
    assert "env-private-key" not in dumps(api.records)


@pytest.mark.parametrize("metadata", [{"data": []}, {"data": [{"id": "test/model",
                         "supported_parameters": ["response_format"]}]}, {"data": [
                         {"id": "test/model", "supported_parameters": ["response_format",
                          "structured_outputs"], "architecture": {"output_modalities": ["image"]}}]}])
def test_incompatible_model_stops_before_generation(metadata):
    def forbidden(_):
        pytest.fail("No generation may occur")
    api = client(forbidden, metadata=metadata)
    with pytest.raises(APIError):
        api.complete("plan", MESSAGES, SCHEMA)
    assert api.attempts == 0 and not api.records


def test_preflight_does_not_generate():
    api = client(lambda _: pytest.fail("No generation may occur"))
    assert api.preflight()["generation_performed"] is False
    assert api.records == [] and api.attempts == 0


def test_local_payload_usage_and_cost():
    seen = []
    def respond(request):
        seen.append(request)
        return httpx.Response(200, json=local_envelope())
    api = client(respond, provider="ollama")
    assert api.complete("plan", MESSAGES, SCHEMA) == {"answer": "yes"}
    payload = json.loads(seen[0].content)
    assert payload["format"] == SCHEMA and not payload["stream"]
    assert payload["options"] == {"temperature": 0, "num_predict": 768, "num_ctx": 8192, "seed": 42}
    assert "authorization" not in seen[0].headers
    record = api.records[0]
    assert record["usage"]["total_tokens"] == 25
    assert record["cost_usd"] == 0 and "compute excluded" in record["cost_basis"]


@pytest.mark.parametrize("url", ["https://ollama.com", "http://192.168.1.1:11434",
                                 "http://localhost:11434/api", "http://user:pass@localhost",
                                 "http://localhost?token=secret", "file://localhost",
                                 "http://localhost:99999"])
def test_local_provider_rejects_nonlocal_or_ambiguous_endpoint(url):
    with pytest.raises(APIError, match="loopback"):
        HTTPClient("ollama", "test/model", Config(), base_url=url)


@pytest.mark.parametrize("model", ["model:cloud", "model:12b-cloud", "cloud/model"])
def test_local_provider_rejects_cloud_name(model):
    with pytest.raises(APIError, match="cloud"):
        HTTPClient("ollama", model, Config())


def test_local_provider_rejects_remote_alias():
    api = client(lambda _: pytest.fail("No generation may occur"), provider="ollama",
                 metadata={"capabilities": ["completion"], "remote_host": "https://ollama.com"})
    with pytest.raises(APIError, match="remote"):
        api.complete("plan", MESSAGES, SCHEMA)


def test_local_provider_does_not_follow_redirects():
    api = client(lambda _: httpx.Response(307, headers={"Location": "https://ollama.com"}),
                 provider="ollama")
    with pytest.raises(APIError, match="307"):
        api.complete("answer", MESSAGES, SCHEMA)
    assert api.attempts == 1


@pytest.mark.parametrize("content,finish", [("", "stop"), ("  ", "stop"),
                                          ('{"answer":', "stop"), ('{"answer":12}', "stop"),
                                          ('{"answer":"yes"}', "length"),
                                          ('{"answer":NaN}', "stop"), ("[]", "stop")])
def test_invalid_model_answer_keeps_telemetry_without_retry(content, finish):
    api = client(lambda _: httpx.Response(200, json=envelope(content=content, finish=finish)))
    with pytest.raises(ResponseError):
        api.complete("verify", MESSAGES, SCHEMA)
    assert api.attempts == 1 and len(api.records) == 1
    assert api.records[0]["error"] and api.spent_usd == .01
    assert api.records[0]["error_type"] == "ResponseError"
    assert api.records[0]["usage"]["total_tokens"] == 105


def test_unknown_cost_is_not_zero_and_blocks_next_generation():
    api = client(lambda _: httpx.Response(200, json=envelope(cost=None)))
    assert api.complete("answer", MESSAGES, SCHEMA)["answer"] == "yes"
    assert api.records[0]["cost_usd"] is None
    with pytest.raises(LimitError, match="unknown"):
        api.complete("answer", MESSAGES, SCHEMA)
    assert api.attempts == 1


def test_unknown_transport_cost_stops_paid_retry():
    def fail(request):
        raise httpx.ReadTimeout("private-test-key", request=request)
    api = client(fail, sleep=lambda _: pytest.fail("Unknown cost must stop retries"))
    with pytest.raises(LimitError, match="unknown"):
        api.complete("answer", MESSAGES, SCHEMA)
    assert api.records[0]["cost_usd"] is None
    assert "private-test-key" not in dumps(api.records)


def test_budget_stops_before_next_generation():
    api = client(lambda _: httpx.Response(200, json=envelope(cost=.04)), budget_usd=.04)
    api.complete("plan", MESSAGES, SCHEMA)
    with pytest.raises(LimitError, match="budget"):
        api.complete("answer", MESSAGES, SCHEMA)
    assert api.attempts == 1


def test_retries_preserve_usage_cost_and_retry_after():
    waits = []
    responses = iter([httpx.Response(429, json={"usage": {"cost": 0, "total_tokens": 0}},
                                    headers={"Retry-After": "3"}),
                      httpx.Response(503, json={"usage": {"cost": .01, "total_tokens": 10}}),
                      httpx.Response(200, json=envelope())])
    api = client(lambda _: next(responses), sleep=waits.append)
    assert api.complete("compress", MESSAGES, SCHEMA)["answer"] == "yes"
    assert waits == [3, 2]
    assert [r["attempt"] for r in api.records] == [1, 2, 3]
    assert sum(r["usage"]["total_tokens"] for r in api.records) == 115
    assert api.spent_usd == .02


def test_retry_after_http_date():
    future = datetime.now(timezone.utc) + timedelta(seconds=30)
    response = httpx.Response(429, headers={"Retry-After": format_datetime(future)})
    assert 28 <= HTTPClient._retry_delay(response, 1) <= 31


def test_local_retries_at_most_twice():
    api = client(lambda _: httpx.Response(503, json={"error": "temporarily unavailable"}),
                 provider="ollama", sleep=lambda _: None)
    with pytest.raises(APIError, match="503"):
        api.complete("plan", MESSAGES, SCHEMA)
    assert api.attempts == 3 and len(api.records) == 3


def test_temporary_local_transport_error_retries():
    seen = []
    def respond(request):
        seen.append(1)
        if len(seen) < 3:
            raise httpx.ConnectError("unreachable", request=request)
        return httpx.Response(200, json=local_envelope())
    api = client(respond, provider="ollama", sleep=lambda _: None)
    assert api.complete("plan", MESSAGES, SCHEMA)["answer"] == "yes"
    assert api.attempts == 3


@pytest.mark.parametrize("status", [400, 401, 402, 403])
def test_non_temporary_http_errors_do_not_retry_or_leak_keys(status):
    api = client(lambda _: httpx.Response(status, json={"error": {
        "message": "Authorization: Bearer private-test-key", "api_key": "private-test-key"}}))
    with pytest.raises(APIError, match=str(status)) as error:
        api.complete("plan", MESSAGES, SCHEMA)
    assert api.attempts == 1
    assert api.records[0]["error_type"] == "APIError"
    assert "private-test-key" not in str(error.value) + dumps(api.records)


@pytest.mark.parametrize("status", [401, 402])
def test_authentication_and_credit_failure_stop_client(status):
    api = client(lambda _: httpx.Response(status, json={"usage": {"cost": 0}}))
    for _ in range(2):
        with pytest.raises(APIError, match=str(status)):
            api.complete("plan", MESSAGES, SCHEMA)
    assert api.attempts == 1


def test_api_limit_counts_retries_and_calls_globally():
    api = client(lambda _: httpx.Response(503, json={}), provider="ollama",
                 config=replace(Config(), max_api_calls=2), sleep=lambda _: None)
    with pytest.raises(LimitError, match="attempts"):
        api.complete("plan", MESSAGES, SCHEMA)
    assert api.attempts == 2
    with pytest.raises(LimitError):
        api.complete("compress", MESSAGES, SCHEMA)
    assert api.attempts == 2


def test_whole_request_limit_checked_before_preflight():
    api = client(lambda _: pytest.fail("No network calls"),
                 config=replace(Config(), window_ref_tokens=800))
    with pytest.raises(LimitError, match="window"):
        api.complete("plan", MESSAGES, SCHEMA)
    assert api.attempts == 0 and not api.records


def test_non_json_envelope_is_logged_and_cost_stays_unknown():
    api = client(lambda _: httpx.Response(200, text="not JSON private-test-key"))
    with pytest.raises(ResponseError):
        api.complete("verify", MESSAGES, SCHEMA)
    assert api.records[0]["cost_usd"] is None
    assert "private-test-key" not in dumps(api.records)


def test_local_client_never_logs_openrouter_environment_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "another-client-private-key")
    api = client(lambda _: httpx.Response(200, json=local_envelope(
        '{"answer":"another-client-private-key"}')), provider="ollama")
    api.complete("answer", MESSAGES, SCHEMA)
    assert "another-client-private-key" not in dumps(api.records)
