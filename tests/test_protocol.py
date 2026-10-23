import json
from pathlib import Path

import pytest

from context_memory import cli
from context_memory.config import Config
from context_memory.evaluation import dataset_identity, grade_result
from context_memory.mock import MockClient
from context_memory.errors import ResponseError


def test_mock_smoke_checks_both_modes_against_reference(tmp_path):
    path = tmp_path / 'smoke'
    assert cli.main(['smoke', '--out', str(path)]) == 0
    result = json.loads((path / 'smoke.json').read_text())
    assert result['passed'] and result['provider'] == 'mock'
    assert {c['mode'] for c in result['checks']} == {'summary', 'reflexive'}


def test_smoke_is_not_success_when_model_fails(tmp_path, monkeypatch):
    class BadAnswer(MockClient):
        def respond(self, stage, body):
            if stage == 'answer':
                return {'status': 'insufficient_data', 'answer': '', 'query': '', 'source_ids': []}
            return super().respond(stage, body)
    monkeypatch.setattr(cli, 'make_client', lambda args, config: BadAnswer(config))
    output = tmp_path / 'bad'
    assert cli.main(['smoke', '--out', str(output)]) == 1
    assert not json.loads((output / 'smoke.json').read_text())['passed']


def test_dataset_identity_survives_moving_between_machines(tmp_path):
    manifest = {'dataset': 'test', 'revision': 'a' * 40, 'exports': {'sha': 'unchanged'}, 'local_source': 'C:/data', 'requested_revision': 'main'}
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest))
    before = dataset_identity(tmp_path)
    manifest.update(local_source='/server/data', requested_revision='a' * 40)
    path.write_text(json.dumps(manifest))
    assert dataset_identity(tmp_path) == before
    manifest['exports']['sha'] = 'modified'
    path.write_text(json.dumps(manifest))
    assert dataset_identity(tmp_path) != before


@pytest.mark.parametrize('value', [-1, 3, True, 0.5])
def test_format_retry_range_is_explicit(value):
    with pytest.raises(ValueError, match='format_retries'):
        Config(format_retries=value)


def test_bool_not_accepted_as_token_limit():
    with pytest.raises(ValueError):
        Config(memory_ref_tokens=True)


def test_provider_failure_telemetry_is_saved_before_finish(tmp_path):
    from context_memory.core import Controller
    from context_memory.errors import APIError
    client = MockClient(Config(), responses=[APIError('fixture failure')])
    ctl = Controller(client, tmp_path / 'run')
    with pytest.raises(APIError):
        ctl.start('Goal')
    record = json.loads((ctl.run_dir / 'api_calls.jsonl').read_text())
    assert record['stage'] == 'plan' and record['error'] == 'APIError'
