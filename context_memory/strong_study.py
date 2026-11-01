"""Extend the frozen first study with GPT-6 under the same USD 28 allocation."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import shutil

from .config import Config
from .paid_openai import BudgetLedger, PRICES, CACHE_WRITE_RATES
from .storage import write_json
from .study import execute_task, implementation_hashes, implementation_matches, sha
from .tokens import dumps

FIRST = Path('runs/openai-first-20261101')
ROOT = Path('runs/openai-strong-20261101')
PROFILES = {
    '6.1-sol-low': {'model':'gpt-6.1-sol','reasoning_effort':'low'},
    '6-astra-low': {'model':'gpt-6-astra','reasoning_effort':'low'},
}


def prepare(root=ROOT, first=FIRST):
    root.mkdir(parents=True,exist_ok=True)
    if (root/'protocol.json').exists():raise ValueError('Protocol already exists')
    parent=json.loads((first/'protocol.json').read_text(encoding='utf-8'))
    current=implementation_hashes()
    # Only provider/pricing code may differ. No retuning from earlier eval answers.
    if any(current[k]!=v for k,v in parent['implementation_sha256'].items() if k!='paid_openai.py'):
        raise ValueError('Memory implementation or prompts changed from the comparison study')
    for name in ['inputs.json','synthetic-targets.json']:
        shutil.copyfile(first/name,root/name)
    rows=json.loads((root/'inputs.json').read_text(encoding='utf-8'))
    tasks=[{**t,'profile':'6.1-sol-low'} for t in parent['tasks'] if t['profile']=='5.4-mini-low']
    queue=[r['id'] for dataset in ['goal_shift','babilong','personamem'] for r in sorted(rows,key=lambda x:x['id']) if r['dataset']==dataset]
    protocol={**parent,'version':2,'parent_study':str(first),'budget_usd':28,
        'ledger_path':str(first/'budget.sqlite3'),'prior_study_cost_usd':9.37739709,
        'profiles':PROFILES,'prices_usd_per_million':{k:PRICES[k] for k in ['gpt-6.1-sol','gpt-6-astra']},
        'cache_write_rates':CACHE_WRITE_RATES,'implementation_sha256':current,'tasks':tasks,
        'astra_queue':queue,'astra_admission_rule':'Fixed order: all goal shifts, then BABILong, then PersonaMem. Admit complete summary/reflexive pairs only when remaining allocation covers 1.5x replayed Sol token cost at Astra rates plus USD 0.15. No accuracy-based selection.',
        'astra_controls_rule':'After paired tests, try full_context then last_window on PersonaMem in sorted ID order. Single-call controls are admitted only if their full conservative request reservation fits the remaining allocation.',
        'limitations':parent['limitations']+['Follow-up on the same eval examples, not an independent new holdout','GPT-6 model IDs have no dated snapshots in official model metadata','Astra subset size depends on remaining budget, never on observed correctness']}
    write_json(root/'protocol.json',protocol)
    write_json(root/'admissions.json',[])
    print(json.dumps({'sol_tasks':len(tasks),'astra_candidate_pairs':len(queue),'budget_total':28}),flush=True)


def context(root):
    p=json.loads((root/'protocol.json').read_text(encoding='utf-8'))
    if not implementation_matches(p['implementation_sha256']):raise ValueError('Implementation changed after freeze')
    rows=json.loads((root/'inputs.json').read_text(encoding='utf-8'))
    if sha(rows)!=p['inputs_sha256']:raise ValueError('Input hash differs')
    return p,{r['id']:r for r in rows},Config(**p['config']),BudgetLedger(p['ledger_path'],28)


def run_sol(root,key_file,workers):
    p,rows,cfg,ledger=context(root)
    with ThreadPoolExecutor(workers) as pool:
        futures=[pool.submit(execute_task,root,t,rows[t['id']],cfg,ledger,key_file,p['profiles']) for t in p['tasks'] if t['profile']=='6.1-sol-low']
        for f in as_completed(futures):f.result()
    write_json(root/'budget-snapshot.json',ledger.snapshot())


def run_controls(root,key_file,medium=False):
    p,rows,cfg,ledger=context(root)
    profile='6.1-sol-medium-control' if medium else '6-astra-low'
    model='gpt-6.1-sol' if medium else 'gpt-6-astra'
    effort='medium' if medium else 'low'
    if profile not in p['profiles']:
        p['profiles'][profile]={'model':model,'reasoning_effort':effort}
        write_json(root/'protocol.json',p)
    admissions=json.loads((root/'admissions.json').read_text(encoding='utf-8'))
    for mode in ['full_context','last_window']:
        for row in sorted(rows.values(),key=lambda r:r['id']):
            if row['dataset']!='personamem':continue
            task={'profile':profile,'id':row['id'],'dataset':'personamem','mode':mode}
            if task in p['tasks']:
                execute_task(root,task,row,cfg,ledger,key_file,p['profiles'])
                continue
            source=root/'tasks'/'6.1-sol-low'/row['id']/mode/'api_calls.jsonl'
            record=json.loads(source.read_text(encoding='utf-8').splitlines()[0])
            payload={**record['request'],'model':model,'reasoning_effort':effort}
            reserve=((len(dumps(payload).encode('utf-8'))+1024)*CACHE_WRITE_RATES[model]+cfg.max_output_tokens*PRICES[model][2])/1e6
            remaining=28-ledger.snapshot()['accounted_usd']
            admissions.append({'id':row['id'],'profile':profile,'mode':mode,'remaining_usd':remaining,'full_reservation_usd':reserve,'admitted':remaining>=reserve})
            write_json(root/'admissions.json',admissions)
            if remaining<reserve:continue
            p['tasks'].append(task);write_json(root/'protocol.json',p)
            execute_task(root,task,row,cfg,ledger,key_file,p['profiles'])
    write_json(root/'budget-snapshot.json',ledger.snapshot())


def astra_forecast(root,identity):
    amount=0
    for mode in ['summary','reflexive']:
        path=root/'tasks'/'6.1-sol-low'/identity/mode/'api_calls.jsonl'
        for line in path.read_text(encoding='utf-8').splitlines():
            usage=json.loads(line)['usage']
            # Assume all input is newly written, ignoring any future cache benefit.
            amount+=(usage['prompt_tokens']*12.5+usage['completion_tokens']*50)/1e6
    return amount


def run_astra(root,key_file):
    p,rows,cfg,ledger=context(root)
    admissions=json.loads((root/'admissions.json').read_text(encoding='utf-8'))
    for index,identity in enumerate(p['astra_queue']):
        tasks=[{'profile':'6-astra-low','id':identity,'dataset':rows[identity]['dataset'],'mode':m} for m in ['summary','reflexive']]
        enrolled=any(t['profile']=='6-astra-low' and t['id']==identity for t in p['tasks'])
        if not enrolled:
            estimate=1.5*astra_forecast(root,identity)+.15
            remaining=28-ledger.snapshot()['accounted_usd']
            admission={'id':identity,'remaining_usd':remaining,'admission_estimate_usd':estimate,'admitted':remaining>=estimate}
            admissions.append(admission);write_json(root/'admissions.json',admissions)
            if remaining<estimate:
                print(json.dumps({'stopped_before_pair':identity,**admission}),flush=True)
                break
            p['tasks'].extend(tasks);write_json(root/'protocol.json',p)
        ordered=tasks if index%2==0 else tasks[::-1]
        with ThreadPoolExecutor(2) as pool:
            futures=[pool.submit(execute_task,root,t,rows[identity],cfg,ledger,key_file,p['profiles']) for t in ordered]
            for f in as_completed(futures):f.result()
        print(json.dumps({'budget':ledger.snapshot()}),flush=True)
    write_json(root/'budget-snapshot.json',ledger.snapshot())


def main():
    from dotenv import load_dotenv
    load_dotenv(override=False)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['prepare','sol','astra','controls','medium-controls'])
    parser.add_argument('--out',type=Path,default=ROOT)
    parser.add_argument('--key-file',type=Path)
    parser.add_argument('--workers',type=int,default=8)
    args=parser.parse_args()
    if not 1<=args.workers<=12:parser.error('workers must be 1..12')
    if args.phase=='prepare':prepare(args.out)
    elif args.phase=='sol':run_sol(args.out,args.key_file,args.workers)
    elif args.phase=='astra':run_astra(args.out,args.key_file)
    else:run_controls(args.out,args.key_file,medium=args.phase=='medium-controls')


if __name__=='__main__':main()
