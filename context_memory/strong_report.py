"""Offline follow-up report, with like-for-like comparisons on shared IDs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from .paid_openai import BudgetLedger
from .storage import write_json
from .study_report import collect, paired, summarize


def matched_comparison(rows, old_rows, profile, previous, dataset, mode):
    new={r['id']:r for r in rows if r['profile']==profile and r['dataset']==dataset and r['mode']==mode}
    old={r['id']:r for r in old_rows if r['profile']==previous and r['dataset']==dataset and r['mode']==mode}
    ids=sorted(new.keys() & old.keys())
    if not ids:return None
    pair_rows=[{**source[identity],'mode':label} for identity in ids for source,label in [(old,previous),(new,profile)]]
    return {'dataset':dataset,'mode':mode,'ids':ids,'old_correct':sum(old[i]['correct'] for i in ids),
            'new_correct':sum(new[i]['correct'] for i in ids),**paired(pair_rows,previous,profile)}


def score(root):
    protocol,rows=collect(root)
    first=Path(protocol['parent_study'])
    old=json.loads((first/'analysis/results.json').read_text(encoding='utf-8'))['rows']
    output=root/'analysis';output.mkdir(exist_ok=True)
    summaries=summarize(rows)
    comparisons=[];method_comparisons=[]
    for profile in protocol['profiles']:
        for dataset in ['personamem','babilong','goal_shift']:
            subset=[r for r in rows if r['profile']==profile and r['dataset']==dataset and r['mode'] in {'summary','reflexive'}]
            if subset:method_comparisons.append({'profile':profile,'dataset':dataset,**paired(subset)})
            for mode in ['summary','reflexive','full_context','last_window']:
                previous='5.4-mini-low' if profile=='6.1-sol-low' else '6.1-sol-low'
                comparison=matched_comparison(rows,old if previous=='5.4-mini-low' else rows,profile,previous,dataset,mode)
                if comparison:comparisons.append(comparison)
    closing=root/'budget-snapshot.json'
    ledger=json.loads(closing.read_text(encoding='utf-8')) if closing.exists() else BudgetLedger.open_existing(protocol['ledger_path']).snapshot()
    if ledger['by_state'].get('pending',{}).get('calls',0):
        raise ValueError('Cannot score a study with pending requests')
    total=ledger['accounted_usd'];prior=protocol['prior_study_cost_usd']
    result={'summaries':summaries,'rows':rows,'matched_model_comparisons':comparisons,
        'paired_method_comparisons':method_comparisons,'budget':ledger,
        'followup_cost_usd':total-prior,'original_cost_usd':prior,'remaining_usd':28-total,
        'evaluation':{'method':'reference_only','judge_model':None,'denominator':'all enrolled tasks; failures incorrect'},
        'combined_summaries':summarize(old+rows)}
    write_json(output/'results.json',result)
    with (output/'predictions.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    receipt_rows=[]
    for path in sorted(root.rglob('api_calls.jsonl')):
        for line in path.read_text(encoding='utf-8').splitlines():
            record=json.loads(line);usage=record['usage'];details=usage.get('prompt_tokens_details') or {}
            receipt_rows.append({'ledger_id':record['ledger_id'],'model':record['model'],'stage':record['stage'],
                'response_id':record['response_id'],'prompt_tokens':usage.get('prompt_tokens'),
                'cached_tokens':details.get('cached_tokens',0),'cache_write_tokens':details.get('cache_write_tokens',0),
                'completion_tokens':usage.get('completion_tokens'),'reasoning_tokens':(usage.get('completion_tokens_details') or {}).get('reasoning_tokens',0),
                'cost_usd':record['cost_usd'],'reserved_usd':record['reserved_usd'],
                'request_sha256':hashlib.sha256(json.dumps(record['request'],sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                'path':str(path.relative_to(root)).replace('\\','/')})
    with (output/'receipts.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(receipt_rows[0]));writer.writeheader();writer.writerows(receipt_rows)
    assert abs(sum(r['cost_usd'] if r['cost_usd'] is not None else r['reserved_usd'] for r in receipt_rows)-(total-prior))<1e-7
    lines=['# Продолжение эксперимента: GPT-6', '',
        f"Завершено {len(rows)} назначенных прогонов. Расход продолжения с отладкой: ${total-prior:.6f}; суммарно две серии: ${total:.6f} из $28. Не использовано ${28-total:.6f}.", '',
        'Основные модели: GPT-6.1 Sol и GPT-6 Astra, reasoning low. Sol получает всю прежнюю выборку: 16 PersonaMem, 20 BABILong и 12 смен цели. Astra получает фиксированную очередь пар до исчерпания доступного бюджета; затем одношаговые контроли, если помещается полный резерв стоимости. Последний остаток используется на одношаговые контроли Sol medium. Размер дополнительных выборок зависит только от бюджета, не от точности.', '',
        'Промпты, порядок раскрытия вопроса, память 512, состояние 512, окно 8192, фрагмент 2048 и лимит выхода 2048 сохранены. Проверка — кодом, без модели-судьи. Для полного контекста окно 65536. Модели GPT-6 публикуются под недатированными ID; ответ сервера сохранён в трассах.', '',
        '| Набор | Модель | Метод | Верно | 95% Wilson | Ошибки | USD | Вызовы |',
        '|---|---|---|---:|---|---:|---:|---:|']
    for s in summaries:
        lo,hi=s['wilson_95_ci']
        lines.append(f"| {s['dataset']} | {s['profile']} | {s['mode']} | {s['correct']}/{s['n']} | {lo:.1%}–{hi:.1%} | {s['errors']} | {s['cost_usd']:.4f} | {s['api_calls']} |")
    lines+=['','## Сравнение моделей на одинаковых примерах','',
            'Для каждого сравнения используется пересечение ID. Неполную выборку Astra нельзя сравнивать с полной выборкой другой модели без этого выравнивания. p — точный парный McNemar без поправок; анализ разведочный.','',
            '| Набор | Метод | Сравнение | n | Верно раньше → сейчас | Разница, п.п. | p |',
            '|---|---|---|---:|---:|---:|---:|']
    for c in comparisons:
        lines.append(f"| {c['dataset']} | {c['mode']} | {c['first']} → {c['second']} | {c['n']} | {c['old_correct']} → {c['new_correct']} | {100*c['delta_accuracy']:+.1f} | {c['mcnemar_exact_p_unadjusted']:.4f} |")
    lines+=['','## Reflexive − summary','',
            '| Набор | Модель | n | Разница, п.п. | 95% bootstrap | p |','|---|---|---:|---:|---|---:|']
    for c in method_comparisons:
        lo,hi=c['bootstrap_95_ci']
        lines.append(f"| {c['dataset']} | {c['profile']} | {c['n']} | {100*c['delta_accuracy']:+.1f} | {100*lo:+.1f}…{100*hi:+.1f} | {c['mcnemar_exact_p_unadjusted']:.4f} |")
    lines+=['','## Повторное чтение','', '| Набор | Модель | Метод | Верно до → после | Поиски |','|---|---|---|---:|---:|']
    for s in summaries:
        if s['mode'] in {'summary','reflexive'}:
            lines.append(f"| {s['dataset']} | {s['profile']} | {s['mode']} | {s['correct_before_retrieval']} → {s['correct']} | {s['retrievals']} |")
    lines+=['','## Учёт расходов и ограничения','',
        'Использован прежний SQLite-журнал: ранее потраченные $9.37739709 не обнулялись. Разрешение пользователя потратить остаток зафиксировано как изменение общего лимита с $26 на $28. Перед запросом резервируется полная верхняя оценка; оплачиваемые cache writes GPT-6 учтены по отдельному тарифу 1.25× входа, а не как дополнительная двойная плата. Reasoning включён в выходные токены.', '',
        'Стоимость рассчитана по usage и [официальным тарифам](https://developers.openai.com/api/docs/pricing), а не прочитана из баланса аккаунта. Допуск заданий и остановка записаны в admissions.json. Остаток не расходуется на заведомо незавершаемые пары или бессодержательные запросы.', '',
        'Это продолжение на тех же примерах, а не новый независимый holdout. На каждую комбинацию выполнен один прогон. После просмотра результатов первой серии промпты и методы памяти не перенастраивались. Небольшие выборки и множественные сравнения ограничивают выводы. Смена цели — собственный диагностический набор, не стандартный AgentChangeBench.', '']
    (output/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'tasks':len(rows),'additional_cost':total-prior,'total_cost':total,'remaining':28-total}),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);score(p.parse_args().root)
