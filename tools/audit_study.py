"""Offline audit of source preservation, limits and paid request accounting."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

from context_memory.paid_openai import PRICES
from context_memory.storage import write_json
from context_memory.study import implementation_matches, sha
from context_memory.tokens import count


def audit(root):
    protocol=json.loads((root/'protocol.json').read_text(encoding='utf-8'))
    inputs=json.loads((root/'inputs.json').read_text(encoding='utf-8'))
    assert sha(inputs)==protocol['inputs_sha256'], 'Input hash differs'
    assert implementation_matches(protocol['implementation_sha256']), 'Implementation changed'
    lookup={r['id']:r for r in inputs}
    task_count, source_checks, max_memory, max_window, response_models = 0,0,0,0,Counter()
    for task in protocol['tasks']:
        path=root/'tasks'/task['profile']/task['id']/task['mode']
        result=json.loads((path/'result.json').read_text(encoding='utf-8'))
        task_count+=1
        row=lookup[task['id']]
        if task['mode'] in {'summary','reflexive'}:
            journal=[json.loads(line) for line in (path/'journal.jsonl').read_text(encoding='utf-8').splitlines()]
            if result['status']=='completed':
                expected=row['input'] if 'input' in row else ''.join(e.get('text','') for e in row['events'])
                assert ''.join(c['text'] for c in journal)==expected, f'Source text lost: {path}'
                assert len(result['answers'])==(2 if task['dataset']=='goal_shift' else 1), f'Missing checkpoint: {path}'
                source_checks+=1
            versions=path/'memory_versions.jsonl'
            for line in versions.read_text(encoding='utf-8').splitlines() if versions.exists() else []:
                version=json.loads(line)
                size=count(version['memory']);max_memory=max(max_memory,size)
                assert size<=protocol['config']['memory_ref_tokens'], f'Memory overflow: {path}'
            if result['state']:
                assert count(result['state'])<=protocol['config']['state_ref_tokens']
        for line in (path/'api_calls.jsonl').read_text(encoding='utf-8').splitlines():
            record=json.loads(line)
            size=count(record['request'])
            assert size==record['request_ref_tokens'], f'Payload count differs: {path}'
            window=size+record['request']['max_completion_tokens']
            cap=65536 if task['mode']=='full_context' else protocol['config']['window_ref_tokens']
            assert window<=cap, f'Window overflow: {path}'
            if task['mode'] in {'summary','reflexive'}:max_window=max(max_window,window)
            body=record.get('response') or {}
            if 'model' in body:
                response_models[body['model']]+=1
                assert body['model']==record['model'], f'Model changed: {path}'
    calls=[]
    for path in root.rglob('api_calls.jsonl'):
        calls.extend(json.loads(line) for line in path.read_text(encoding='utf-8').splitlines())
    identities=[r['ledger_id'] for r in calls]
    assert len(identities)==len(set(identities)), 'Duplicate physical requests in logs'
    with sqlite3.connect(root/'budget.sqlite3') as db:
        ledger=db.execute('SELECT id,charged,state FROM calls').fetchall()
    assert {r[0] for r in ledger}==set(identities), 'Missing or unaccounted physical request'
    assert not any(r[2]=='pending' for r in ledger), 'A request is still pending'
    for record in calls:
        if record['cost_usd'] is not None and record.get('http_status')==200:
            usage=record['usage'];rates=PRICES[record['model']]
            cached=(usage.get('prompt_tokens_details') or {}).get('cached_tokens',0)
            expected=((usage['prompt_tokens']-cached)*rates[0]+cached*rates[1]+usage['completion_tokens']*rates[2])/1e6
            assert abs(record['cost_usd']-expected)<1e-9
    charged=sum(r[1] for r in ledger)
    assert charged<=protocol['budget_usd']
    result={'passed':True,'tasks':task_count,'complete_source_checks':source_checks,
        'physical_requests_including_debug':len(calls),'max_memory_ref_tokens':max_memory,
        'max_memory_method_request_including_output_reserve':max_window,
        'served_models':dict(response_models),'accounted_usd':charged,
        'unknown_requests':sum(r[2]=='unknown' for r in ledger),
        'checks':['frozen implementation and inputs','all requested tasks present',
            'complete source reconstruction for completed memory tasks','memory/state/window limits',
            'requested and served model snapshots match','every ledger request has one physical trace',
            'usage prices include cached input and all output tokens','total within shared budget']}
    write_json(root/'analysis'/'audit.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    audit(parser.parse_args().root)
