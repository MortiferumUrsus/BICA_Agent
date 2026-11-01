"""Offline paired analysis; reference answers are opened only here."""
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import random
import re

from . import benchmark, personamem
from .evaluation import dataset_identity
from .paid_openai import BudgetLedger
from .storage import write_json
from .study import sha


def wilson(k, n):
    z = 1.959963984540054
    center = (k/n + z*z/(2*n))/(1+z*z/n)
    radius = z*math.sqrt(k/n*(1-k/n)/n+z*z/(4*n*n))/(1+z*z/n)
    return [max(0, center-radius), min(1, center+radius)]


def paired(rows, first="summary", second="reflexive"):
    groups = defaultdict(dict)
    for row in rows:
        groups[row["id"]][row["mode"]] = row
    pairs = [g for g in groups.values() if first in g and second in g]
    if not pairs:
        raise ValueError("No paired observations")
    diffs = [int(g[second]["correct"])-int(g[first]["correct"]) for g in pairs]
    wins, losses = diffs.count(1), diffs.count(-1)
    discordant = wins + losses
    p = min(1, 2*sum(math.comb(discordant,k) for k in range(min(wins,losses)+1))/2**discordant) if discordant else 1.0
    rng = random.Random(20261101)
    bootstrap = sorted(sum(rng.choices(diffs, k=len(diffs)))/len(diffs) for _ in range(10000))
    return {"n": len(pairs), "first": first, "second": second,
        "delta_accuracy": sum(diffs)/len(diffs), "second_only_correct": wins,
        "first_only_correct": losses, "ties": len(diffs)-discordant,
        "bootstrap_95_ci": [bootstrap[249], bootstrap[9749]],
        "mcnemar_exact_p_unadjusted": p}


def collect(root):
    protocol = json.loads((root / "protocol.json").read_text(encoding="utf-8"))
    inputs = json.loads((root / "inputs.json").read_text(encoding="utf-8"))
    if sha(inputs) != protocol["inputs_sha256"]:
        raise ValueError("Input integrity check failed")
    for dataset, digest in protocol["dataset_manifest_sha256"].items():
        if dataset_identity(Path("data")/dataset) != digest:
            raise ValueError("Evaluation dataset differs from protocol")
    targets = {"personamem": personamem.load_targets(Path("data/personamem"), "eval"),
               "babilong": benchmark.load_targets(Path("data/babilong"), "eval"),
               "goal_shift": json.loads((root/"synthetic-targets.json").read_text(encoding="utf-8"))}
    custom = [r for r in inputs if r.get("dataset") == "goal_shift"]
    if custom:
        if {r['id'] for r in custom} != set(targets['goal_shift']):
            raise ValueError("Synthetic target IDs differ from frozen inputs")
        for row in custom:
            facts = re.findall(r'(Vendor-\d+-[A-Z]): price=(\d+); delivery_days=(\d+); contract_code=([^;]+)', row['events'][0]['text'])
            change = re.search(r'(Vendor-\d+-[A-Z]) now has price=(\d+)', row['events'][2]['text'])
            eligible = [r for r in facts if int(r[2]) <= 5]
            cheapest = min(eligible, key=lambda r: int(change[2]) if r[0] == change[1] else int(r[1]))
            fastest = min(facts, key=lambda r: int(r[2]))
            if targets['goal_shift'][row['id']] != [cheapest[0], fastest[3]]:
                raise ValueError("Synthetic targets disagree with frozen source facts")
    expected = {(t["profile"],t["id"],t["mode"]) for t in protocol["tasks"]}
    if len(expected) != len(protocol["tasks"]):
        raise ValueError("Duplicate tasks in protocol")
    rows = []
    for task in protocol["tasks"]:
        path = root/"tasks"/task["profile"]/task["id"]/task["mode"]/"result.json"
        if not path.exists():
            raise ValueError(f"Incomplete experiment; missing {path}. Do not reduce the denominator.")
        result = json.loads(path.read_text(encoding="utf-8"))
        if any(result[k] != task[k] for k in task):
            raise ValueError("Task/result identity mismatch")
        target = targets[task["dataset"]][task["id"]]
        scorer = personamem.score_choice if task["dataset"] == "personamem" else benchmark.exact_match
        outcomes = result["answers"]
        outcome = outcomes[-1] if outcomes else {}
        final, before = outcome.get("final"), outcome.get("before_retrieval")
        expected_answer = target[-1] if isinstance(target, list) else target
        # Goal-shift tasks need both checkpoints; a first-only answer must never
        # be scored as the answer to the new goal.
        enough = len(outcomes) == 2 if task["dataset"] == "goal_shift" else len(outcomes) == 1
        correct = bool(result["status"] == "completed" and enough and final and scorer(final["answer"], expected_answer, final["status"]))
        before_correct = bool(enough and before and scorer(before["answer"], expected_answer, before["status"]))
        metrics = result["metrics"]
        calls = [json.loads(line) for line in (path.parent / "api_calls.jsonl").read_text(encoding="utf-8").splitlines()]
        reasoning_tokens = sum(((r.get("usage") or {}).get("completion_tokens_details") or {}).get("reasoning_tokens", 0) for r in calls)
        cached_tokens = sum(((r.get("usage") or {}).get("prompt_tokens_details") or {}).get("cached_tokens", 0) for r in calls)
        row = {**task, "model": result["model"], "reasoning_effort": result["reasoning_effort"],
            "question_type": result["question_type"], "persona_id": result["persona_id"],
            "status": result["status"], "error": result["error"], "correct": correct,
            "correct_before_retrieval": before_correct, "answer": final["answer"] if enough and final else None,
            "answer_status": final["status"] if enough and final else None, "target": expected_answer,
            "first_goal_correct": bool(outcomes and outcomes[0].get("final") and benchmark.exact_match(outcomes[0]["final"]["answer"], target[0], outcomes[0]["final"]["status"])) if isinstance(target,list) else None,
            "cost_usd": metrics["cost_usd"], "known_cost_usd": metrics["known_cost_usd"],
            "api_calls": metrics["api_calls"], "duration_s": metrics["duration_s"],
            "prompt_tokens": metrics["prompt_tokens"], "completion_tokens": metrics["completion_tokens"],
            "reasoning_tokens": reasoning_tokens, "cached_input_tokens": cached_tokens,
            "retrievals": metrics.get("retrievals",0), "path": str(path.relative_to(root)).replace("\\","/")}
        rows.append(row)
    actual = {(r["profile"],r["id"],r["mode"]) for r in rows}
    if actual != expected:
        raise ValueError("Unexpected prediction set")
    return protocol, rows


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[(row["dataset"],row["profile"],row["mode"])].append(row)
    summaries = []
    for (dataset,profile,mode), values in sorted(groups.items()):
        n, k = len(values), sum(r["correct"] for r in values)
        summaries.append({"dataset":dataset,"profile":profile,"mode":mode,"n":n,"correct":k,
            "accuracy":k/n,"wilson_95_ci":wilson(k,n),
            "errors":sum(r["status"]!="completed" for r in values),
            "correct_before_retrieval":sum(r["correct_before_retrieval"] for r in values),
            "cost_usd":sum(r["known_cost_usd"] for r in values),
            "api_calls":sum(r["api_calls"] for r in values),
            "duration_s":sum(r["duration_s"] for r in values),
            "reasoning_tokens":sum(r["reasoning_tokens"] for r in values),
            "cached_input_tokens":sum(r["cached_input_tokens"] for r in values),
            "first_goal_correct":sum(r["first_goal_correct"] is True for r in values) if dataset == "goal_shift" else None,
            "retrievals":sum(r["retrievals"] for r in values)})
    return summaries


def score(root):
    protocol, rows = collect(root)
    output = root/"analysis"
    output.mkdir(exist_ok=True)
    summaries = summarize(rows)
    comparisons = []
    for dataset in sorted({r["dataset"] for r in rows}):
        for profile in protocol["profiles"]:
            subset = [r for r in rows if r["dataset"]==dataset and r["profile"]==profile]
            comparisons.append({"dataset":dataset,"profile":profile,**paired(subset)})
    reasoning_comparisons = []
    for dataset in sorted({r["dataset"] for r in rows}):
        for mode in sorted({r["mode"] for r in rows if r["dataset"] == dataset}):
            subset = [{**r, "mode": r["profile"]} for r in rows if r["dataset"] == dataset and r["mode"] == mode and r["profile"] in {"5.4-nano-none", "5.4-nano-low"}]
            reasoning_comparisons.append({"dataset": dataset, "mode": mode, **paired(subset, "5.4-nano-none", "5.4-nano-low")})
    # A later authorized study can share the ledger. Historical reports retain
    # their own closing balance instead of including future charges.
    closing = root/"budget-snapshot.json"
    budget = json.loads(closing.read_text(encoding="utf-8")) if closing.exists() else BudgetLedger.open_existing(root/"budget.sqlite3").snapshot()
    report = {"evaluation":{"judge_model":None,"method":"reference_only","denominator":"all protocol tasks, failures counted incorrect"},
              "summaries":summaries,"paired_comparisons":comparisons,"reasoning_comparisons":reasoning_comparisons,"budget":budget,"rows":rows}
    write_json(output/"results.json",report)
    with (output/"predictions.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=["# Первый эксперимент с OpenAI", "", "Дата протокола: 1 ноября 2026. Оценка ответов — кодом по эталонам, без LLM-судьи.", "",
           f"Всего запусков: {len(rows)}. Расход с отладкой: ${budget['accounted_usd']:.4f}; программный лимит $26 из выделенных $28.", "",
           "Память 512, состояние 512, окно 8192, блок 2048 токенов cl100k_base. До 2048 выходных токенов API, включая размышления. Не более двух повторов при нарушении формата/размера. Все модели и методы получают одинаковые выбранные примеры.", "",
           "PersonaMem: 16 разных персон, по одному вопросу на персону; вопрос раскрывается после чтения. BABILong: 20 ранее выделенных eval-примеров, вопрос известен заранее. Goal shift: 12 наших сценариев с исправлением цены и последующей сменой цели. Последняя группа не является стандартным бенчмарком.", "",
           "full_context получает всё исходное сообщение и окно 65536; это контроль с большим бюджетом контекста. last_window получает только последние 4096 токенов. Сравнивать ограничения full_context с памятью 512 как равные нельзя.", "",
           "| Набор | Модель / reasoning | Метод | Верно | Точность | 95% интервал Wilson | Ошибки запуска | USD | Вызовы |",
           "|---|---|---|---:|---:|---|---:|---:|---:|"]
    for s in summaries:
        lo,hi=s['wilson_95_ci']
        lines.append(f"| {s['dataset']} | {s['profile']} | {s['mode']} | {s['correct']}/{s['n']} | {s['accuracy']:.1%} | {lo:.1%}–{hi:.1%} | {s['errors']} | {s['cost_usd']:.4f} | {s['api_calls']} |")
    lines += ["", "## Парное сравнение reflexive − summary", "", "Положительная разница — в пользу reflexive. Интервалы получены парным bootstrap (10 000 повторов); p — точный McNemar без поправки на множественные сравнения. Анализ разведочный.", "",
              "| Набор | Модель | Разница, п.п. | 95% bootstrap | Только reflexive верно | Только summary верно | p |",
              "|---|---|---:|---|---:|---:|---:|"]
    for c in comparisons:
        lo,hi=c['bootstrap_95_ci']
        lines.append(f"| {c['dataset']} | {c['profile']} | {100*c['delta_accuracy']:+.1f} | {100*lo:+.1f}…{100*hi:+.1f} | {c['second_only_correct']} | {c['first_only_correct']} | {c['mcnemar_exact_p_unadjusted']:.4f} |")
    lines += ["", "## Влияние размышлений: nano low − none", "", "| Набор | Метод | Разница, п.п. | 95% bootstrap | p |", "|---|---|---:|---|---:|"]
    for c in reasoning_comparisons:
        lo, hi = c['bootstrap_95_ci']
        lines.append(f"| {c['dataset']} | {c['mode']} | {100*c['delta_accuracy']:+.1f} | {100*lo:+.1f}…{100*hi:+.1f} | {c['mcnemar_exact_p_unadjusted']:.4f} |")
    lines += ["", "## Повторное чтение", "", "| Набор | Модель | Метод | Верно до → после | Запросов повторного чтения |", "|---|---|---|---:|---:|"]
    for s in summaries:
        if s['mode'] in {'summary','reflexive'}:
            lines.append(f"| {s['dataset']} | {s['profile']} | {s['mode']} | {s['correct_before_retrieval']} → {s['correct']} | {s['retrievals']} |")
    lines += ["", "## Два этапа смены цели", "", "| Модель | Метод | Первая цель | Новая цель |", "|---|---|---:|---:|"]
    for s in summaries:
        if s['dataset'] == 'goal_shift':
            lines.append(f"| {s['profile']} | {s['mode']} | {s['first_goal_correct']}/{s['n']} | {s['correct']}/{s['n']} |")
    lines += ["", "## Токены размышлений и время", "", "Время — сумма длительности HTTP-запросов на пример; параллельное выполнение и сеть влияют на эти значения.", "", "| Набор | Модель | Метод | Reasoning tokens | Cached input tokens | Среднее время запросов, с |", "|---|---|---|---:|---:|---:|"]
    for s in summaries:
        lines.append(f"| {s['dataset']} | {s['profile']} | {s['mode']} | {s['reasoning_tokens']} | {s['cached_input_tokens']} | {s['duration_s']/s['n']:.1f} |")
    lines += ["", "## Ограничения", "", "Выборка небольшая, на каждую комбинацию выполнен один прогон. Несколько вопросов и наборов проверяют разные навыки; их точности не объединяются в один рейтинг. Различия могут быть связаны с дополнительными вызовами и инструкциями reflexive. Перед/после retrieval — наблюдение в одном прогоне, а не отдельная рандомизированная проверка. Внешний оценщик не использовался; внутренний verify — часть метода сжатия.", "",
              "Стоимость рассчитана по usage OpenAI и стандартным тарифам с учётом cache и reasoning. Это учёт запросов данного эксперимента, а не выгрузка баланса аккаунта. Неопределённые запросы удерживают полную предварительную оценку. Настройки, версии моделей, цены и хеши находятся в protocol.json; полные локальные журналы — в tasks/.", ""]
    (output/"report.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps({"runs":len(rows),"cost_usd":budget['accounted_usd'],"report":str(output/'report.md')}),flush=True)
    return report
