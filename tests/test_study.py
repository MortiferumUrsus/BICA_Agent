import json
import re

import pytest

from context_memory.config import Config
from context_memory.core import Controller
from context_memory.mock import MockClient
from context_memory.study import select_personas, synthetic_cases
from context_memory.study_report import paired, wilson


def test_freeze_accepts_only_line_ending_changes():
    import hashlib
    from pathlib import Path
    from context_memory import study
    expected = study.implementation_hashes()
    for name in expected:
        data = (Path(study.__file__).parent/name).read_bytes().replace(b'\r\n',b'\n')
        expected[name] = hashlib.sha256(data).hexdigest()
    assert study.implementation_matches(expected)
    expected['core.py'] = '0'*64
    assert not study.implementation_matches(expected)


def test_persona_selection_is_blind_deterministic_and_disjoint():
    rows = [{"id": f"{p}-{q}", "persona_id": str(p), "question_type": str(q)} for p in range(16) for q in range(7)]
    selected = select_personas(rows)
    assert selected == select_personas(list(reversed(rows)))
    assert len(selected) == len({r['persona_id'] for r in selected}) == 16
    assert len({r['question_type'] for r in selected}) == 7


def test_synthetic_targets_follow_source_not_labels():
    rows, targets = synthetic_cases()
    for row in rows:
        facts = re.findall(r'(Vendor-\d+-[A-Z]): price=(\d+); delivery_days=(\d+); contract_code=([^;]+)', row['events'][0]['text'])
        fastest = min(facts, key=lambda r:int(r[2]))
        changed = re.search(r'(Vendor-\d+-[A-Z]) now has price=50', row['events'][2]['text'])[1]
        assert targets[row['id']] == [changed, fastest[3]]
        assert int(next(r[2] for r in facts if r[0] == changed)) <= 5
        assert 'target' not in json.dumps(row)


def test_paired_statistics_known_discordance():
    rows=[]
    for i in range(10):
        rows.extend([{'id':str(i),'mode':'summary','correct':False},{'id':str(i),'mode':'reflexive','correct':True}])
    result=paired(rows)
    assert result['delta_accuracy']==1
    assert result['bootstrap_95_ci']==[1,1]
    assert result['mcnemar_exact_p_unadjusted']==pytest.approx(2/1024)
    assert wilson(10,10)[1] == pytest.approx(1)


def test_memory_limit_repair_uses_same_sources_and_preserves_budget(tmp_path):
    cfg=Config(memory_ref_tokens=128,format_retries=1)
    client=MockClient(cfg)
    ctl=Controller(client,tmp_path/'task','summary',cfg)
    ctl.start('Remember Orion delivery date.')
    ctl.journal.append('Orion delivery date: Friday.')
    client.responses=iter([{'memory':[{'text':' x'*180,'source_ids':['c001']}]}, {'memory':[{'text':'Orion: Friday','source_ids':['c001']}]}])
    ctl.update(ctl.journal.chunks)
    assert len(client.records)==3
    before=json.loads(client.records[-2]['request']['messages'][-1]['content'])
    after=json.loads(client.records[-1]['request']['messages'][-1]['content'])
    assert before['new_sources']==after['new_sources']
    assert after['memory_ref_tokens']==128
    assert 'format_correction' in after


def test_offline_scoring_requires_every_task_and_second_goal(tmp_path, monkeypatch):
    from context_memory import study_report as report
    from context_memory.study import sha
    inputs=[]
    task={'profile':'test','id':'case','mode':'summary','dataset':'goal_shift'}
    protocol={'inputs_sha256':sha(inputs),'dataset_manifest_sha256':{},'tasks':[task]}
    (tmp_path/'protocol.json').write_text(json.dumps(protocol))
    (tmp_path/'inputs.json').write_text(json.dumps(inputs))
    (tmp_path/'synthetic-targets.json').write_text(json.dumps({'case':['same','same']}))
    monkeypatch.setattr(report.personamem,'load_targets',lambda *a:{})
    monkeypatch.setattr(report.benchmark,'load_targets',lambda *a:{})
    with pytest.raises(ValueError,match='Incomplete experiment'):
        report.collect(tmp_path)
    path=tmp_path/'tasks'/'test'/'case'/'summary';path.mkdir(parents=True)
    answer={'answer':'same','status':'answer'}
    result={**task,'model':'test','reasoning_effort':None,'question_type':'goal_shift','persona_id':None,
            'status':'completed','error':None,'answers':[{'final':answer,'before_retrieval':answer}],
            'metrics':{'cost_usd':0,'known_cost_usd':0,'api_calls':0,'duration_s':0,'prompt_tokens':0,'completion_tokens':0}}
    (path/'result.json').write_text(json.dumps(result));(path/'api_calls.jsonl').write_text('')
    _,rows=report.collect(tmp_path)
    assert rows[0]['first_goal_correct'] is True
    assert rows[0]['correct'] is False and rows[0]['answer'] is None
