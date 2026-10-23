import csv
import json
from pathlib import Path

import httpx
import pytest

from context_memory import cli
from context_memory.api import HTTPClient
from context_memory.config import Config
from context_memory.core import Controller
from context_memory.errors import APIError, MemoryExperimentError, ResponseError
from context_memory.evaluation import dataset_identity, grade_result
from context_memory.mock import MockClient
from context_memory.personamem import BenchmarkError, export_personamem, load_inputs, score_choice


@pytest.fixture
def persona_data(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    columns = ["persona_id", "question_id", "question_type", "user_question_or_message", "correct_answer", "all_options", "shared_context_id", "end_index_in_shared_context"]
    with (source / "questions_32k.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for i in range(6):
            writer.writerow(dict(zip(columns, [str(i), f"q{i}", "track_full_preference_evolution", "PRIVATE_QUESTION Which choice?", "(b)", repr([f"({c}) option {c}" for c in "abcd"]), f"context{i}", 2])))
    with (source / "shared_contexts_32k.jsonl").open("w", encoding="utf-8") as handle:
        for i in range(6):
            handle.write(json.dumps({f"context{i}": [{"role": "system", "content": "Persona description"}, {"role": "user", "content": "I prefer blue now."}, {"role": "user", "content": "FUTURE_MESSAGE"}]}) + "\n")
    output = tmp_path / "dataset"
    export_personamem(source, output, "a" * 40)
    return output


def test_persona_preserves_native_prefix_without_future_or_reference(persona_data):
    rows = load_inputs(persona_data)
    assert len(rows) == 5
    assert all('FUTURE_MESSAGE' not in row['input'] and 'correct_answer' not in row for row in rows)
    assert all([m['content'] for m in map(json.loads, row['input'].splitlines())] == ['Persona description', 'I prefer blue now.'] for row in rows)
    assert all(row['choices'] == list('abcd') for row in rows)
    debug = load_inputs(persona_data, 'debug', 1)
    assert not {r['persona_id'] for r in debug} & {r['persona_id'] for r in rows}
    assert not {r['shared_context_id'] for r in debug} & {r['shared_context_id'] for r in rows}


def test_persona_input_loading_does_not_touch_targets(persona_data, monkeypatch):
    original = Path.open
    def guard(path, *a, **kw):
        assert not path.name.endswith('_targets.jsonl')
        return original(path, *a, **kw)
    monkeypatch.setattr(Path, 'open', guard)
    assert load_inputs(persona_data)


def test_persona_corrupt_exports_are_rejected(persona_data):
    with (persona_data / 'eval_inputs.jsonl').open('a') as handle:
        handle.write('{}\n')
    with pytest.raises(BenchmarkError, match='checksum'):
        load_inputs(persona_data)


def test_mock_can_execute_long_multiple_choice_questions(persona_data, tmp_path):
    output = tmp_path / 'long-choices'
    assert cli.main(['benchmark', '--dataset', 'personamem', '--data-dir', str(persona_data), '--limit', '1', '--mode', 'both', '--no-score', '--out', str(output)]) == 0
    result = json.loads((output / 'results.json').read_text())
    assert all(row['status'] == 'completed' for row in result['examples'])


@pytest.mark.parametrize(('answer', 'expected'), [('b', True), ('(B)', True), (' b. ', True), ('a or b', False), ('because b', False), ('', False), (None, False), ('(b', False), ('b)', False)])
def test_choice_scoring_is_strict(answer, expected):
    assert score_choice(answer, 'b') is expected
    assert not score_choice(answer, 'b', 'insufficient_data')


def test_no_score_then_offline_evaluation_has_no_model_call(persona_data, tmp_path, monkeypatch):
    calls = []
    class Selecting(MockClient):
        def complete(self, stage, messages, schema):
            calls.append((stage, json.loads(messages[-1]['content'])))
            if stage == 'answer':
                self.responses = iter([{'status': 'answer', 'answer': 'b', 'query': '', 'source_ids': []}])
            result = super().complete(stage, messages, schema)
            self.responses = None
            return result
    monkeypatch.setattr(cli, 'make_client', lambda args, cfg: Selecting(cfg))
    original = Path.open
    def guard(path, *a, **kw):
        assert not path.name.endswith('_targets.jsonl'), 'Targets opened during --no-score'
        return original(path, *a, **kw)
    run = tmp_path / 'run'
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', guard)
        assert cli.main(['benchmark', '--dataset', 'personamem', '--data-dir', str(persona_data), '--limit', '1', '--mode', 'both', '--no-score', '--out', str(run)]) == 0
    result = json.loads((run / 'results.json').read_text())
    assert result['evaluation']['method'] == 'not_scored'
    assert result['summary_by_mode']['summary']['accuracy'] is None
    assert result['presentation'] == 'question_later'
    assert all('PRIVATE_QUESTION' not in json.dumps(body) for stage, body in calls if stage != 'answer')
    assert all('target' not in body for _, body in calls)
    monkeypatch.setattr(cli, 'make_client', lambda *a: pytest.fail('Evaluator initialized a model'))
    assert cli.main(['evaluate', str(run), '--data-dir', str(persona_data)]) == 0
    scored = json.loads((run / 'evaluation' / 'results.json').read_text())
    assert scored['summary_by_mode']['summary']['accuracy'] == 1
    assert scored['evaluation']['judge_model'] is None
    assert json.loads((run / 'results.json').read_text()) == result


def test_evaluation_rejects_mismatched_dataset(persona_data):
    with pytest.raises(MemoryExperimentError, match='differs'):
        grade_result({'dataset_manifest_sha256': 'bad'}, persona_data)


def test_dry_run_needs_neither_model_nor_api_key(persona_data, tmp_path, monkeypatch):
    monkeypatch.setattr(cli, 'make_client', lambda *a: pytest.fail('dry-run created a model'))
    path = tmp_path / 'plan'
    assert cli.main(['benchmark', '--dataset', 'personamem', '--data-dir', str(persona_data), '--dry-run', '--provider', 'openrouter', '--limit', '1', '--out', str(path)]) == 0
    plan = json.loads((path / 'plan.json').read_text())
    assert plan['minimum_api_calls_estimate'] > 0
    assert plan['dataset_manifest_sha256'] == dataset_identity(persona_data)


def test_format_retry_is_bounded_logged_and_preserves_memory(tmp_path):
    cfg = Config(format_retries=1)
    client = MockClient(cfg)
    ctl = Controller(client, tmp_path / 'run', 'summary', cfg)
    ctl.start('Remember the current delivery date for Orion.')
    ctl.journal.append('Orion delivery date: Friday.')
    client.responses = iter([{'bad': 1}, {'memory': [{'text': 'Orion delivery date: Friday.', 'source_ids': ['c001']}]}])
    ctl.update(ctl.journal.chunks)
    assert len(client.records) == 3
    assert len((ctl.run_dir / 'api_calls.jsonl').read_text().splitlines()) == 3
    assert json.loads(client.records[-1]['request']['messages'][-1]['content'])['format_correction']
    before = list(ctl.memory)
    client.responses = iter([{'bad': 1}, {'bad': 2}])
    with pytest.raises(ResponseError):
        ctl.update([])
    assert ctl.memory == before
    assert len(client.records) == 5


def test_choice_constraint_and_source_count_bound(tmp_path):
    ctl = Controller(MockClient(Config()), tmp_path / 'run', 'summary')
    ctl.start('Goal')
    _, schema, _ = ctl._request('summary', {'new_sources': [{'chunk_id': 'c001', 'text': 'Fact'}]})
    assert schema['properties']['memory']['items']['properties']['source_ids']['maxItems'] == 1
    _, schema, _ = ctl._request('answer', {'choices': list('abcd')})
    assert schema['properties']['answer']['enum'] == ['', 'a', 'b', 'c', 'd']


def test_openai_compatible_server_supports_local_model_without_paid_flags():
    requests = []
    def handler(request):
        requests.append(request)
        if request.url.path == '/v1/models':
            return httpx.Response(200, json={'data': [{'id': 'Qwen/test'}]})
        return httpx.Response(200, json={'id': 'local-1', 'choices': [{'finish_reason': 'stop', 'message': {'content': '{"answer":"yes"}'}}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 4}})
    schema = {'type': 'object', 'properties': {'answer': {'type': 'string'}}, 'required': ['answer'], 'additionalProperties': False}
    client = HTTPClient('openai', 'Qwen/test', Config(), transport=httpx.MockTransport(handler), seed=7)
    assert client.complete('answer', [{'role': 'user', 'content': 'Question'}], schema) == {'answer': 'yes'}
    assert client.records[0]['cost_usd'] == 0
    payload = json.loads(requests[-1].content)
    assert payload['seed'] == 7 and 'plugins' not in payload and 'provider' not in payload
    assert client.attempts == 1


@pytest.mark.parametrize('kwargs', [{'seed': True}, {'timeout_s': 0}, {'local_context_tokens': 0}])
def test_invalid_runtime_options_fail_before_network(kwargs):
    with pytest.raises(APIError):
        HTTPClient('ollama', 'local', Config(), **kwargs)
