import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from context_memory.config import Config
from context_memory.errors import APIError, LimitError, ResponseError
from context_memory.paid_openai import BudgetLedger, OpenAIClient

MODEL = "gpt-5.4-nano-2026-03-17"
SCHEMA = {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"], "additionalProperties": False}


def client(tmp_path, response, **kwargs):
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"id": MODEL})
        return response(request)
    return OpenAIClient(MODEL, Config(), BudgetLedger(tmp_path / "budget.sqlite3", 1),
                        reasoning_effort="low", api_key="sk-private", sleep=lambda _: None,
                        transport=httpx.MockTransport(handler), **kwargs)


def test_reservations_are_atomic_and_survive_restart(tmp_path):
    path = tmp_path / "ledger.sqlite3"
    ledger = BudgetLedger(path, 1)
    def reserve(_):
        try:
            return ledger.reserve(MODEL, "answer", .3)
        except LimitError:
            return None
    with ThreadPoolExecutor(8) as pool:
        ids = list(filter(None, pool.map(reserve, range(20))))
    assert len(ids) == 3
    assert BudgetLedger(path, 1).snapshot()["accounted_usd"] == pytest.approx(.9)
    ledger.settle(ids[0], .01)
    assert ledger.snapshot()["accounted_usd"] == pytest.approx(.61)
    with pytest.raises(ValueError):
        BudgetLedger(path, 2)


def test_cost_includes_reasoning_and_cached_tokens(tmp_path):
    def response(request):
        body = json.loads(request.content)
        assert body["reasoning_effort"] == "low"
        assert body["max_completion_tokens"] == 768
        assert body["store"] is False and body["service_tier"] == "default"
        return httpx.Response(200, json={"id": "test", "choices": [{"finish_reason": "stop", "message": {"content": '{"answer":"yes"}'}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 200,
                      "prompt_tokens_details": {"cached_tokens": 50}, "completion_tokens_details": {"reasoning_tokens": 180}}})
    api = client(tmp_path, response)
    assert api.complete("answer", [{"role": "user", "content": "test"}], SCHEMA) == {"answer": "yes"}
    assert api.spent_usd == pytest.approx((50*.2+50*.02+200*1.25)/1e6)
    assert api.ledger.snapshot()["accounted_usd"] == api.spent_usd
    assert "sk-private" not in json.dumps(api.records)


def test_ambiguous_transport_keeps_full_reservation(tmp_path):
    def response(request):
        raise httpx.ReadTimeout("secret", request=request)
    api = client(tmp_path, response)
    with pytest.raises(APIError):
        api.complete("answer", [], SCHEMA)
    snapshot = api.ledger.snapshot()
    assert snapshot["by_state"]["unknown"]["calls"] == 1
    assert snapshot["accounted_usd"] > 0
    assert api.records[0]["cost_usd"] is None


def test_budget_blocks_before_post(tmp_path):
    api = client(tmp_path, lambda _: pytest.fail("No generation expected"))
    api.ledger.reserve(MODEL, "other", .999999)
    with pytest.raises(LimitError):
        api.complete("answer", [], SCHEMA)


def test_original_schema_checked_after_wire_normalization(tmp_path):
    schema = {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "string"}, "uniqueItems": True}}, "required": ["items"], "additionalProperties": False}
    def response(request):
        assert "uniqueItems" not in request.content.decode()
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": '{"items":["a","a"]}'}}], "usage": {"prompt_tokens": 100, "completion_tokens": 10}})
    api = client(tmp_path, response)
    with pytest.raises(ResponseError):
        api.complete("answer", [], schema)
    assert api.records[0]["cost_usd"] > 0


def test_quota_failure_is_not_retried(tmp_path):
    api = client(tmp_path, lambda _: httpx.Response(429, json={"error": {"code": "insufficient_quota"}}))
    with pytest.raises(APIError):
        api.complete("answer", [], SCHEMA)
    assert api.attempts == 1 and api.ledger.snapshot()["accounted_usd"] == 0
