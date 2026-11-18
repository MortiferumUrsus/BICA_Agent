"""Build the offline research report from committed results. Standard library only."""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ["4.1-mini", "5.4-nano-none", "5.4-nano-low", "5.4-mini-low",
            "6.1-sol-low", "6-astra-low", "6.1-sol-medium-control"]
LABELS = {"4.1-mini": "GPT-4.1 mini", "5.4-nano-none": "GPT-5.4 nano · none",
          "5.4-nano-low": "GPT-5.4 nano · low", "5.4-mini-low": "GPT-5.4 mini · low",
          "6.1-sol-low": "GPT-6.1 Sol · low", "6-astra-low": "GPT-6 Astra · low",
          "6.1-sol-medium-control": "GPT-6.1 Sol · medium"}
DATASETS = {"personamem": "PersonaMem", "babilong": "BABILong", "goal_shift": "Смена цели"}
METHODS = {"summary": "Summary", "reflexive": "Reflexive",
           "full_context": "Полный контекст", "last_window": "Последнее окно"}
COLORS = {"summary": "#246f86", "reflexive": "#bc6646",
          "full_context": "#448267", "last_window": "#87919a"}
CATEGORY_LABELS = {
    "strict_match": "Строгое совпадение",
    "article_only": "Различие только в артикле",
    "other_location": "Указано другое место",
    "insufficient_data": "Недостаточно данных",
    "other_mismatch": "Требуется разбор фразы",
    "execution_error": "Ошибка выполнения / статуса",
}
LOCATIONS = frozenset({"bathroom", "bedroom", "garden", "hallway", "kitchen", "office"})
REPORT_FILES = {
    **dict.fromkeys(("README.md", "report.html", "report.pdf", "report.summary.pdf"), "final"),
    **dict.fromkeys(("accuracy.svg", "context.svg", "retrieval.svg", "cost.svg"), "figures"),
    "babilong_sensitivity.md": "analysis",
    **dict.fromkeys(("all_answers.csv", "all_answers.json", "example_contexts.json", "archived_answers.json",
                     "saved_stage_responses.json", "verification.json", "pdf_data.json",
                     "babilong_sensitivity.csv", "babilong_sensitivity.json"), "data"),
}


def report_links(text, section="final"):
    """Resolve report artifacts within the final/data/analysis/figures layout."""
    def href(url):
        path, marker, fragment = url.partition("#")
        if path in REPORT_FILES:
            path = Path(os.path.relpath(Path(REPORT_FILES[path]) / path, section)).as_posix()
        elif path.startswith("../../") and not path.startswith("../../../"):
            # Report subfolders need three parent steps to reach repository sources.
            path = "../" + path
        return path + marker + fragment

    text = re.sub(r'((?:href|src)=[\"\x27])([^\"\x27]+)([\"\x27])',
                  lambda m: m[1] + href(m[2]) + m[3], text)
    return re.sub(r'\]\(([^)]+)\)', lambda m: "](" + href(m[1]) + ")", text)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lines(path):
    return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]


def save_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def e(value):
    return html.escape(str(value), quote=True)


def money(value, digits=4):
    return "$" + f"{value:.{digits}f}"


def table(headers, rows, cls=""):
    return ('<div class="table-wrap"><table class="' + cls + '"><thead><tr>' +
            "".join(f"<th>{e(x)}</th>" for x in headers) + "</tr></thead><tbody>" +
            "".join("<tr>" + "".join(f"<td>{x}</td>" for x in row) + "</tr>" for row in rows) +
            "</tbody></table></div>")


def md_table(headers, rows):
    def cell(x):
        return str(x).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(map(cell, headers)) + " |",
                      "| " + " | ".join("---" for _ in headers) + " |"] +
                     ["| " + " | ".join(map(cell, row)) + " |" for row in rows])


def exact_text(value):
    """The frozen BABILong normalization; do not broaden the primary metric."""
    return (value or "").lower().strip().removesuffix(".")


def article_text(value):
    """Remove one leading article only, after the frozen normalization."""
    return re.sub(r"^(?:the|a|an)\s+", "", exact_text(value), count=1)


def exact_paired(first, second):
    ids = sorted(first.keys() & second.keys())
    if not ids:
        raise ValueError("No shared IDs for paired analysis")
    differences = [int(second[i]) - int(first[i]) for i in ids]
    wins, losses = differences.count(1), differences.count(-1)
    discordant = wins + losses
    p = min(1, 2 * sum(math.comb(discordant, k) for k in range(min(wins, losses) + 1)) / 2**discordant) if discordant else 1.0
    return {"n": len(ids), "first_correct": sum(first[i] for i in ids),
            "second_correct": sum(second[i] for i in ids),
            "delta_accuracy": sum(differences) / len(ids), "second_only_correct": wins,
            "first_only_correct": losses, "mcnemar_exact_p_unadjusted": p}


def analyze_babilong(rows):
    records, identities = [], set()
    for r in rows:
        if r["dataset"] != "babilong":
            continue
        identity = (r["profile"], r["mode"], r["id"])
        if identity in identities:
            raise ValueError(f"Duplicate BABILong run: {identity}")
        identities.add(identity)
        eligible = r["status"] == "completed" and r["answer_status"] == "answer"
        strict = bool(eligible and r["answer"] and exact_text(r["answer"]) == exact_text(r["target"]))
        normalized = bool(eligible and r["answer"] and article_text(r["answer"]) == article_text(r["target"]))
        if strict != r["correct"]:
            raise ValueError(f"Frozen score differs for {identity}")
        if r["status"] != "completed":
            category = "execution_error"
        elif r["answer_status"] == "insufficient_data":
            category = "insufficient_data"
        elif not eligible:
            category = "execution_error"
        elif strict:
            category = "strict_match"
        elif normalized:
            category = "article_only"
        elif article_text(r["answer"]) in LOCATIONS and article_text(r["target"]) in LOCATIONS:
            category = "other_location"
        else:
            category = "other_mismatch"
        records.append({"id": r["id"], "profile": r["profile"], "mode": r["mode"],
                        "answer": r["answer"], "target": r["target"], "status": r["status"],
                        "answer_status": r["answer_status"], "strict_correct": strict,
                        "article_correct": normalized, "category": category})
    summaries = []
    for profile in PROFILES:
        for mode in ("summary", "reflexive"):
            group = [r for r in records if r["profile"] == profile and r["mode"] == mode]
            if group:
                counts = collections.Counter(r["category"] for r in group)
                summaries.append({"profile": profile, "mode": mode, "n": len(group),
                                  "strict_correct": sum(r["strict_correct"] for r in group),
                                  "article_correct": sum(r["article_correct"] for r in group),
                                  "categories": {k: counts[k] for k in CATEGORY_LABELS}})
    specs = [("methods", profile, "summary", profile, "reflexive") for profile in PROFILES]
    specs += [("reasoning", "5.4-nano-none", mode, "5.4-nano-low", mode) for mode in ("summary", "reflexive")]
    specs += [("models", "5.4-mini-low", mode, "6.1-sol-low", mode) for mode in ("summary", "reflexive")]
    comparisons = []
    for kind, first_profile, first_mode, second_profile, second_mode in specs:
        first = {r["id"]: r for r in records if (r["profile"], r["mode"]) == (first_profile, first_mode)}
        second = {r["id"]: r for r in records if (r["profile"], r["mode"]) == (second_profile, second_mode)}
        if not first or not second:
            continue
        comparisons.append({"kind": kind, "first_profile": first_profile, "first_mode": first_mode,
                            "second_profile": second_profile, "second_mode": second_mode,
                            "strict": exact_paired({k: v["strict_correct"] for k, v in first.items()},
                                                   {k: v["strict_correct"] for k, v in second.items()}),
                            "article": exact_paired({k: v["article_correct"] for k, v in first.items()},
                                                    {k: v["article_correct"] for k, v in second.items()})})
    totals = collections.Counter(r["category"] for r in records)
    return {"analysis_date": "2026-11-18", "dataset": "babilong", "retrospective": True,
            "primary_metric_unchanged": True,
            "normalization": "Frozen lowercase/strip/one final period; then remove one initial the, a or an followed by whitespace from answer and target.",
            "category_rules": {**CATEGORY_LABELS,
                "other_location_rule": "Answer and target name different members of the fixed six-room vocabulary after article normalization.",
                "other_mismatch_rule": "Unresolved wording or content; no semantic correctness is assigned automatically."},
            "n_runs": len(records), "n_examples": len({r["id"] for r in records}),
            "category_counts": {k: totals[k] for k in CATEGORY_LABELS},
            "summaries": summaries, "comparisons": comparisons, "rows": records}


def sensitivity_table(analysis):
    result = []
    for profile in PROFILES:
        ss = [next((s for s in analysis["summaries"] if s["profile"] == profile and s["mode"] == m), None)
              for m in ("summary", "reflexive")]
        if all(ss):
            result.append([LABELS[profile]] + [f'{s[k]}/{s["n"]}' for s in ss for k in ("strict_correct", "article_correct")])
    return result


SENSITIVITY_HEADERS = ["Профиль", "Summary строго", "Summary без артикля", "Reflexive строго", "Reflexive без артикля"]
GOAL_HEADERS = ["Профиль", "Метод", "Первая цель", "Новая цель до поиска", "Новая цель итог", "Поиски"]
PAIR_HEADERS = ["Набор", "Профиль", "Пар", "Δ, п.п.", "95% интервал, п.п.", "p"]


def goal_table(summaries):
    return [[LABELS[p], METHODS[m], f'{s["first_goal_correct"]}/{s["n"]}',
             f'{s["correct_before_retrieval"]}/{s["n"]}', f'{s["correct"]}/{s["n"]}', s["retrievals"]]
            for p in PROFILES for m in ("summary", "reflexive") for s in summaries
            if s["dataset"] == "goal_shift" and s["profile"] == p and s["mode"] == m]


def pp_interval(c):
    return " … ".join(f"{100*v:+.2f}" for v in c["bootstrap_95_ci"])


def pair_table(comparisons):
    return [[DATASETS[c["dataset"]], LABELS[c["profile"]], c["n"], f'{100*c["delta_accuracy"]:+.2f}',
             pp_interval(c), f'{c["mcnemar_exact_p_unadjusted"]:.4f}'] for c in comparisons]


def load_data(root):
    first = read(root / "examples/openai-20261101/results.json")
    strong = read(root / "examples/openai-strong-20261101/results.json")
    rows = [{**r, "series": name} for name, data in [("Первая серия", first), ("Продолжение", strong)] for r in data["rows"]]
    rows.sort(key=lambda r: (list(DATASETS).index(r["dataset"]), r["id"],
                             PROFILES.index(r["profile"]), list(METHODS).index(r["mode"])))
    summaries = first["summaries"] + strong["summaries"]
    archived, stages, sources = [], [], []
    for p in sorted((root / "examples").rglob("results.json")):
        r = read(p)
        if "provider" not in r or "examples" in r or "mode" not in r:
            continue
        for index, outcome in enumerate(r.get("answers", []), 1):
            final = outcome.get("final")
            archived.append({
                "run": p.parent.relative_to(root).as_posix(), "provider": r["provider"],
                "model": r.get("model", ""), "mode": r["mode"], "checkpoint": index,
                "question": outcome["question"], "status": r["status"],
                "answer_status": final.get("status") if final else None,
                "answer": final.get("answer") if final else None,
                "before_retrieval": outcome.get("before_retrieval"),
                "retrieved_ids": outcome.get("retrieved_ids", []), "error": r.get("error")})
        if not r.get("answers"):
            archived.append({
                "run": p.parent.relative_to(root).as_posix(), "provider": r["provider"],
                "model": r.get("model", ""), "mode": r["mode"], "checkpoint": None,
                "question": r.get("state", {}).get("goal") if r.get("name", "").startswith("qa1-") else None,
                "status": r["status"], "answer_status": None, "answer": None,
                "before_retrieval": None, "retrieved_ids": [], "error": r.get("error")})
        raw_path = p.with_name("api_calls.jsonl")
        if raw_path.exists():
            for index, call in enumerate(lines(raw_path), 1):
                response = call.get("response")
                parsed = response
                if isinstance(response, dict):
                    content = None
                    if response.get("choices"):
                        content = response["choices"][0].get("message", {}).get("content")
                    elif isinstance(response.get("message"), dict):
                        content = response["message"].get("content")
                    if isinstance(content, str):
                        try:
                            parsed = json.loads(content)
                        except ValueError:
                            parsed = content
                stages.append({"run": p.parent.relative_to(root).as_posix(), "index": index,
                               "stage": call["stage"], "provider": r["provider"],
                               "model": call.get("model", r.get("model")), "payload": parsed,
                               "record": call})
    for name in ("openai-20261101", "openai-strong-20261101"):
        for filename in ("results.json", "predictions.csv", "receipts.csv", "protocol.json"):
            p = root / "examples" / name / filename
            sources.append({"path": p.relative_to(root).as_posix(),
                            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    return first, strong, rows, summaries, archived, stages, sources


def verify(root, first, strong, rows, summaries):
    assert len(rows) == 686
    assert len({(r["profile"], r["id"], r["mode"]) for r in rows}) == len(rows)
    for r in rows:
        a, t = r["answer"], r["target"]
        if r["dataset"] == "personamem":
            m = re.fullmatch(r"\s*(?:([a-dA-D])|\(([a-dA-D])\))[.]?\s*", a or "")
            answer = (m[1] or m[2]).lower() if m else None
            correct = answer == t
        else:
            normalize = lambda x: x.lower().strip().removesuffix(".")
            correct = bool(a) and normalize(a) == normalize(t)
        correct = bool(correct and r["status"] == "completed" and r["answer_status"] == "answer")
        assert correct == r["correct"], r
    for s in summaries:
        group = [r for r in rows if all(r[k] == s[k] for k in ("profile", "dataset", "mode"))]
        assert len(group) == s["n"]
        assert sum(r["correct"] for r in group) == s["correct"]
        assert abs(sum(r["known_cost_usd"] for r in group) - s["cost_usd"]) < 1e-7
    receipts = []
    for name, data in [("openai-20261101", first), ("openai-strong-20261101", strong)]:
        p = root / "examples" / name
        with (p / "receipts.csv").open(encoding="utf-8-sig", newline="") as f:
            receipts += list(csv.DictReader(f))
        protocol = read(p / "protocol.json")
        assert {(r["profile"], r["id"], r["mode"]) for r in data["rows"]} == {
            (r["profile"], r["id"], r["mode"]) for r in protocol["tasks"]}
    assert len(receipts) == 9683
    assert len({r["ledger_id"] for r in receipts}) == len(receipts)
    assert abs(sum(float(r["cost_usd"]) for r in receipts) - 27.87631429) < 1e-7


def example_contexts(root, rows, archived):
    """Attach only questions backed by saved traces, with explicit provenance."""
    contexts = {}
    for r in rows:
        c = contexts.setdefault(r["id"], {"id": r["id"], "dataset": r["dataset"],
            "target": r["target"], "question": None, "question_sources": [],
            "first_question": None, "source_excerpt": [], "trace_reports": []})
        if c["target"] != r["target"] or c["dataset"] != r["dataset"]:
            raise ValueError(f'Conflicting identity or target: {r["id"]}')
    local = read(root / "examples/babilong-manifest.json")
    paid = read(root / "examples/openai-20261101/babilong-manifest.json")
    same_babilong = all(local[k] == paid[k] for k in ("dataset", "revision", "sha256"))
    for r in archived:
        run = Path(r["run"])
        identity = run.parent.name
        if identity not in contexts or not r["question"]:
            continue
        c = contexts[identity]
        if c["dataset"] == "babilong" and not same_babilong:
            continue
        if c["dataset"] == "goal_shift" and r["checkpoint"] != 2:
            if r["checkpoint"] == 1:
                c["first_question"] = r["question"]
            continue
        if c["question"] is not None and c["question"] != r["question"]:
            raise ValueError(f"Conflicting saved questions: {identity}")
        c["question"] = r["question"]
        c["question_sources"].append((run / "results.json").as_posix())
        c["trace_reports"].append((run / "report.md").as_posix())
        if c["dataset"] == "goal_shift":
            for chunk in lines(root / run / "journal.jsonl"):
                for line in chunk["text"].splitlines():
                    if c["target"] in line:
                        item = {"source_id": chunk["chunk_id"], "text": line}
                        if item not in c["source_excerpt"]:
                            c["source_excerpt"].append(item)
    for c in contexts.values():
        c["question_sources"] = sorted(set(c["question_sources"]))
        c["trace_reports"] = sorted(set(c["trace_reports"]))
    return list(contexts.values())


def answer_note(r):
    if r["status"] != "completed":
        return "Прогон остановлен. Содержательный ответ не получен."
    if r["answer_status"] == "insufficient_data":
        return "Модель сообщила о нехватке данных."
    if r["correct"]:
        return "Засчитано исходной метрикой."
    if r["dataset"] == "babilong":
        if article_text(r["answer"]) == article_text(r["target"]):
            return "Расхождение только в начальном артикле. Строгая метрика не засчитала ответ."
        if article_text(r["answer"]) in LOCATIONS:
            return "Названо другое место."
        return "Строка не совпала с эталоном. Смысл фразы требует отдельного разбора."
    if r["dataset"] == "personamem":
        return "Не засчитано. Без вопроса и вариантов нельзя объяснить содержательную причину."
    return "Ответ не совпал с точным кодом договора."


def example_cards(contexts, rows):
    out = ['<section class="sheet" id="examples"><h2>Разбор отдельных примеров</h2>',
           '<p>Выберите ID, чтобы сопоставить ответы на одну задачу. Вопросы приведены дословно из сохранённых журналов. Вопросы BABILong связаны с платной серией по ID и совпадающим ревизии и SHA-256 датасета.</p>']
    for c in contexts:
        group = [r for r in rows if r["id"] == c["id"]]
        availability = "вопрос сохранён" if c["question"] else "текст вопроса отсутствует"
        out.append(f'<details class="example-card" id="example-{e(c["id"])}"><summary><strong>{e(c["id"])}</strong> · {DATASETS[c["dataset"]]} · {availability}</summary>')
        if c["first_question"]:
            out.append(f'<p><strong>Первая цель:</strong> {e(c["first_question"])}</p>')
        out.append(f'<p><strong>Вопрос:</strong> {e(c["question"]) if c["question"] else "Точная формулировка не сохранена в доступном архиве."}</p>')
        if c["dataset"] == "personamem":
            out.append('<p class="caption">Варианты a–d также отсутствуют. Буквы ответа и эталона позволяют проверить оценку, но не содержание выбора.</p>')
        out.append(f'<p><strong>Эталон:</strong> <code>{e(c["target"])}</code>. Источник эталона — сводные результаты платных серий.</p>')
        for item in c["source_excerpt"]:
            out.append(f'<p><strong>Фрагмент {e(item["source_id"])}:</strong> {e(item["text"])}</p>')
        out.append(table(["Модель", "Метод", "Ответ → эталон", "Как понимать оценку"], [
            [e(LABELS[r["profile"]]), METHODS[r["mode"]],
             f'<code>{e(r["answer"] or "∅")} → {e(r["target"])}</code>', e(answer_note(r))] for r in group]))
        links = [f'<a href="../../{e(p)}">{e(p)}</a>' for p in c["question_sources"]]
        links += [f'<a href="../../{e(p)}">Разбор {e(Path(p).parent.name)}</a>' for p in c["trace_reports"]]
        if links:
            out.append('<p class="caption">Источники вопроса и трассы: ' + " · ".join(links) + '</p>')
        out.append('</details>')
    return "".join(out) + '</section>'


def svg_start(width, height, title):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{e(title)}">',
            '<rect width="100%" height="100%" fill="white"/>',
            '<g font-family="Arial, DejaVu Sans, sans-serif" fill="#20343e">']


def label(x, y, text, size=13, anchor="start", fill=None, weight=None):
    return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}"' + (
        f' fill="{fill}"' if fill else "") + (f' font-weight="{weight}"' if weight else "") + f'>{e(text)}</text>'


def accuracy_chart(summaries):
    out = svg_start(1050, 540, "Точность методов по моделям и наборам")
    out += [label(22, 27, "Правильные ответы", 19, weight="bold"),
            label(22, 49, "Числитель — верные ответы, знаменатель — число примеров. Линии — 95% интервалы Wilson.", 12)]
    for index, dataset in enumerate(DATASETS):
        x = 160 + index * 295
        out.append(label(x + 118, 88, DATASETS[dataset], 17, anchor="middle", weight="bold"))
        for tick in (0, .5, 1):
            xx = x + 235 * tick
            out.append(label(xx, 110, f"{tick:.0%}", 10, anchor="middle", fill="#62737c"))
            out.append(f'<line x1="{xx}" y1="122" x2="{xx}" y2="473" stroke="#e6ebed"/>')
        for i, profile in enumerate(PROFILES[:6]):
            y = 145 + i * 56
            if index == 0:
                out.append(label(145, y + 8, LABELS[profile].replace("GPT-", "").replace(" · ", " / "), 12, anchor="end"))
            for j, mode in enumerate(("summary", "reflexive")):
                row = next((s for s in summaries if s["profile"] == profile and s["dataset"] == dataset and s["mode"] == mode), None)
                if row is None:
                    if j == 0:
                        out.append(label(x+115, y+8, "нет прогона", 12, anchor="middle", fill="#87919a"))
                    continue
                yy = y - 8 + j * 20
                out.append(f'<rect x="{x}" y="{yy-8}" width="{row["accuracy"]*235}" height="13" rx="2" fill="{COLORS[mode]}"/>')
                lo, hi = [x + 235 * v for v in row["wilson_95_ci"]]
                out.append(f'<line x1="{lo}" y1="{yy-2}" x2="{hi}" y2="{yy-2}" stroke="#20343e" stroke-width="1.2"/>')
                for xx in (lo, hi):
                    out.append(f'<line x1="{xx}" y1="{yy-5}" x2="{xx}" y2="{yy+1}" stroke="#20343e"/>')
                out.append(label(x+241, yy+2, f'{row["correct"]}/{row["n"]}', 11))
    out += [label(160, 510, "Summary", 13, fill=COLORS["summary"], weight="bold"),
            label(260, 510, "Reflexive", 13, fill=COLORS["reflexive"], weight="bold"),
            label(22, 533, "Astra: девять смен цели. Остальные модели: 16 PersonaMem, 20 BABILong и 12 смен цели.", 12)]
    return "".join(out) + "</g></svg>"


def context_chart(summaries):
    out = svg_start(1050, 360, "PersonaMem — память и полный контекст")
    out += [label(22, 28, "PersonaMem: сколько информации оставить модели", 19, weight="bold"),
            label(22, 51, "16 персон, один итоговый вопрос. Полный контекст использует большее окно.", 12)]
    for i, profile in enumerate(PROFILES[:5]):
        x = 35+i*205
        out.append(label(x+87, 85, LABELS[profile].replace("GPT-", ""), 12, anchor="middle"))
        for j, mode in enumerate(("last_window", "summary", "reflexive", "full_context")):
            row = next(s for s in summaries if s["profile"] == profile and s["dataset"] == "personamem" and s["mode"] == mode)
            hh, xx = row["accuracy"]*174, x+j*40
            out.append(f'<rect x="{xx}" y="{287-hh}" width="29" height="{hh}" rx="2" fill="{COLORS[mode]}"/>')
            out.append(label(xx+14.5, 279-hh, str(row["correct"]), 12, anchor="middle"))
        out.append(f'<line x1="{x-5}" y1="287" x2="{x+162}" y2="287" stroke="#9babb2"/>')
    for i, mode in enumerate(("last_window", "summary", "reflexive", "full_context")):
        out.append(label(35+i*250, 329, METHODS[mode], 13, fill=COLORS[mode], weight="bold"))
    out.append(label(22, 353, "Подписи — верные ответы из 16. Память Summary и Reflexive одинакова: 512 токенов.", 12))
    return "".join(out) + "</g></svg>"


def retrieval_chart(summaries):
    out = svg_start(1050, 460, "Ответы до и после поиска при смене цели")
    out += [label(22, 28, "Смена цели: ответы до и после поиска", 19, weight="bold"),
            label(22, 51, "Каждый отрезок — один метод на одной модели. Отдельного контроля без поиска нет.", 12)]
    for i, profile in enumerate(PROFILES[:6]):
        y = 105+i*51
        out.append(label(205, y+4, LABELS[profile].replace("GPT-", ""), 13, anchor="end"))
        for j, mode in enumerate(("summary", "reflexive")):
            s = next(s for s in summaries if s["dataset"] == "goal_shift" and s["profile"] == profile and s["mode"] == mode)
            base = 270+j*380
            a, z = base+230*s["correct_before_retrieval"]/s["n"], base+230*s["correct"]/s["n"]
            out.append(f'<line x1="{base}" y1="{y}" x2="{base+230}" y2="{y}" stroke="#e0e7ea"/>')
            out.append(f'<line x1="{a}" y1="{y}" x2="{z}" y2="{y}" stroke="{COLORS[mode]}" stroke-width="4"/>')
            out.append(f'<circle cx="{a}" cy="{y}" r="5" fill="white" stroke="{COLORS[mode]}" stroke-width="2"/>')
            out.append(f'<circle cx="{z}" cy="{y}" r="5" fill="{COLORS[mode]}"/>')
            out.append(label(base+244, y+4, f'{s["correct_before_retrieval"]} → {s["correct"]} / {s["n"]}', 12))
    out += [label(382, 78, "Summary", 14, anchor="middle", fill=COLORS["summary"], weight="bold"),
            label(762, 78, "Reflexive", 14, anchor="middle", fill=COLORS["reflexive"], weight="bold"),
            label(22, 440, "Пустая точка — до поиска, закрашенная — итог. При одинаковом результате точки совпадают.", 12)]
    for base in (270, 650):
        for tick in (0, .5, 1):
            out.append(label(base + 230*tick, 94, f"{tick:.0%}", 10, anchor="middle", fill="#62737c"))
    return "".join(out) + "</g></svg>"


def cost_chart(summaries):
    out = svg_start(1050, 550, "Средняя стоимость одного примера по моделям и наборам")
    out += [label(22, 28, "Стоимость одного примера", 19, weight="bold"),
            label(22, 51, "USD по сохранённому usage, с попытками внутри основных прогонов. Отладка показана отдельно.", 12)]
    for index, dataset in enumerate(DATASETS):
        x = 160+index*295
        values = [s for s in summaries if s["dataset"] == dataset and s["mode"] in ("summary", "reflexive")]
        top = max(s["cost_usd"]/s["n"] for s in values)*1.18
        out.append(label(x+118, 88, DATASETS[dataset], 17, anchor="middle", weight="bold"))
        for tick in (0, .5, 1):
            xx = x+235*tick
            out.append(f'<line x1="{xx}" y1="122" x2="{xx}" y2="473" stroke="#e6ebed"/>')
            out.append(label(xx, 110, money(top*tick, 3), 10, anchor="middle", fill="#62737c"))
        for i, profile in enumerate(PROFILES[:6]):
            y = 145+i*56
            if index == 0:
                out.append(label(145, y+8, LABELS[profile].replace("GPT-", ""), 12, anchor="end"))
            if not any(s["profile"] == profile for s in values):
                out.append(label(x+118, y+8, "нет прогона", 12, anchor="middle", fill="#87919a"))
            for j, mode in enumerate(("summary", "reflexive")):
                s = next((s for s in values if s["profile"] == profile and s["mode"] == mode), None)
                if s:
                    width = (s["cost_usd"]/s["n"])/top*235
                    out.append(f'<rect x="{x}" y="{y-16+j*20}" width="{width}" height="13" rx="2" fill="{COLORS[mode]}"/>')
    out += [label(160, 510, "Summary", 13, fill=COLORS["summary"], weight="bold"),
            label(270, 510, "Reflexive", 13, fill=COLORS["reflexive"], weight="bold"),
            label(22, 536, "Средняя стоимость, USD. Шкалы панелей различаются. Префикс GPT в названиях опущен.", 12)]
    return "".join(out) + "</g></svg>"


def result_grid(summaries):
    rows = []
    for profile in PROFILES[:6]:
        cells = [e(LABELS[profile])]
        for dataset in DATASETS:
            ss = [next((s for s in summaries if s["profile"] == profile and s["dataset"] == dataset and s["mode"] == mode), None)
                  for mode in ("summary", "reflexive")]
            cells.append(" / ".join(f'{s["correct"]}/{s["n"]}' if s else "—" for s in ss))
        rows.append(cells)
    return table(["Модель и режим", "PersonaMem", "BABILong", "Смена цели"], rows)


def profile_costs(rows):
    result = []
    for profile in PROFILES:
        group = [r for r in rows if r["profile"] == profile]
        result.append([LABELS[profile], len(group), sum(r["api_calls"] for r in group),
                       f'{sum(r["known_cost_usd"] for r in group):.6f}'])
    return result


def analysis_sections(analysis, summaries, comparisons):
    reasoning = [c for c in analysis["comparisons"] if c["kind"] == "reasoning"]
    p_rows = [[METHODS[c["first_mode"]], f'{100*c["strict"]["delta_accuracy"]:+.1f}',
               f'{c["strict"]["mcnemar_exact_p_unadjusted"]:.4f}',
               f'{100*c["article"]["delta_accuracy"]:+.1f}',
               f'{c["article"]["mcnemar_exact_p_unadjusted"]:.4f}'] for c in reasoning]
    counts = analysis["category_counts"]
    return [
        ("metric", "Как форма ответа влияет на оценку",
         '<h2>Почему правильное место могло не засчитаться</h2>'
         '<p>Числа выше получены по правилам, установленным до эксперимента. Для BABILong ответ приводится к нижнему регистру, из него убираются пробелы по краям и одна конечная точка. После этого требуется точное совпадение с эталоном. Поэтому the hallway и hallway получают разные оценки, хотя оба ответа называют коридор.</p>'
         '<p>Чтобы понять, насколько результат зависит от этой особенности, выполнен дополнительный пересчёт. Из ответа и эталона после прежней обработки убирается один начальный английский артикль the, a или an с пробелом. Пересчёт сделан после просмотра результатов и показан отдельно. Исходные оценки сохранены.</p>' +
         table(SENSITIVITY_HEADERS, sensitivity_table(analysis)) +
         '<p>У nano none результат Summary меняется с 2 до 12 верных ответов из 20. Значит, десять ответов не были засчитаны только из-за артикля. По одной строгой оценке нельзя заключить, что модель во всех этих случаях забыла нужный факт.</p>'
         '<h2>Как это меняет сравнение настроек nano</h2>'
         '<p>В таблице ниже из точности nano low вычтена точность nano none на тех же 20 задачах. Положительная разница означает преимущество low. Значение p получено точным парным тестом Мак-Немара, который учитывает задачи с различающимися исходами. Правила чтения этого показателя объяснены в разделе о неопределённости.</p>' +
         table(["Метод", "Δ строго, п.п.", "p строго", "Δ без артикля, п.п.", "p без артикля"], p_rows) +
         '<p>После удаления артикля оба значения p выше 0,05. Убедительность сравнения меняется вместе с правилом оценки. Поэтому исходное различие нельзя целиком объяснить качеством сохранения памяти.</p>'
         '<p class="caption">Подробные правила и все спорные фразы доступны в <a href="babilong_sensitivity.md">дополнительном разборе</a>. Индивидуальные результаты сохранены в <a href="babilong_sensitivity.csv">CSV</a> и <a href="babilong_sensitivity.json">JSON</a>. Astra на BABILong не запускалась.</p>'),
        ("errors", "Какие ответы не засчитаны",
         '<h2>Ошибки содержания и различия формулировки</h2>'
         '<p>Для проверки этого объяснения все 200 ответов BABILong разделены по причине полученной оценки. Это ответы пяти профилей с двумя методами на одних и тех же 20 задачах. Повторение задач не увеличивает число независимых примеров до 200.</p>' +
         table(["Категория", "Ответов"], [[v, counts[k]] for k, v in CATEGORY_LABELS.items()]) +
         '<p>Категория «Указано другое место» применяется, когда ответ и эталон называют разные места из фиксированного словаря bathroom, bedroom, garden, hallway, kitchen и office. Сообщение модели о нехватке данных, сохранённое как insufficient_data, учитывается отдельно. Такой ответ не приносит балла, но отличается от уверенного указания неверного места.</p>'
         '<p>Девять более сложных фраз требуют отдельного разбора. Два ответа, Daniel is in the office. и Mary is in the hallway., явно содержат эталонное место. Даже дополнительное удаление артикля их не засчитывает, поскольку оно не оценивает смысл целого предложения.</p>' +
         table(["Ответ", "Эталон", "Как понимать различие"], [
             ["the hallway", "hallway", "Разница только в начальном артикле"],
             ["Daniel is in the office.", "office", "Нужное место названо внутри предложения"],
             ["hallway, then kitchen", "kitchen", "Названы два места, нужен отдельный разбор"]]) +
         '<p>Такое разделение помогает увидеть границы оценки. Строгое несовпадение может означать потерю факта, отказ отвечать или неподходящую форму ответа. Эти причины нельзя считать одним и тем же сбоем памяти.</p>'),
        ("goals", "Что происходит при смене цели",
         '<h2>От выбора поставщика к поиску кода договора</h2>'
         '<p>Сценарий с поставщиками проверяет, сохранится ли информация, которая сначала была второстепенной. Вначале модель выбирает самого дешёвого поставщика с доставкой до пяти дней. После первого ответа цена перестаёт быть главным условием. Теперь нужно назвать код договора самого быстрого поставщика независимо от цены.</p>'
         '<p>Первая оценка показывает, справилась ли модель с исходным выбором. Вторая относится к новой цели до обращения к источнику. Третья показывает итог после разрешённого повторного чтения. В каждой ячейке указано число верных ответов из числа сценариев.</p>' +
         table(GOAL_HEADERS, goal_table(summaries)) +
         '<p>Например, Sol с Summary решил исходную задачу во всех 12 сценариях. На новый вопрос до поиска он ответил правильно только в двух. Итоговый результат составил 12 из 12. Поэтому высокая итоговая точность ещё не означает, что все нужные сведения сохранялись в короткой памяти.</p>'
         '<p class="caption">Столбец «Поиски» считает обращения к источникам за весь прогон, включая первую цель. Astra проверена на девяти сценариях. Отдельное условие с отключённым поиском не запускалось.</p>'),
        ("paired", "Насколько убедительны различия",
         '<h2>Как читать разницу точности</h2>'
         '<p>Методы сравниваются попарно на одних и тех же задачах. Из точности Reflexive вычитается точность Summary. Эта разница обозначена Δ и измеряется в процентных пунктах, сокращённо п.п. Например, рост с 50% до 60% составляет 10 процентных пунктов. Положительная Δ означает преимущество Reflexive.</p>'
         '<p>При малом числе задач разница может заметно меняться от состава выборки. Для оценки этой неустойчивости в сохранённом анализе 10 000 раз собирались новые выборки из имеющихся пар с возвращением. Такой способ называется парным bootstrap. Полученный 95% интервал показывает диапазон оценок разницы при этом пересчёте. Он не охватывает все источники неопределённости, в частности вариативность новых запусков модели.</p>'
         '<p>Дополнительно приведено p точного теста Мак-Немара. При предположении, что у методов одинаковы шансы выигрывать на задачах с разными исходами, p показывает вероятность получить столь же сильный или более сильный перекос. В исследовании использован обычный порог 0,05. Значение выше порога означает нехватку оснований заявить различие, но не доказывает равенство методов.</p>' +
         table(PAIR_HEADERS, pair_table(comparisons)) +
         '<p>У Sol на PersonaMem разница равна −6,25 п.п., а интервал простирается от −25 до +12,5 п.п. Наблюдения совместимы с изменениями в обе стороны. Ни одно из показанных сравнений методов не имеет p ниже 0,05.</p>'
         '<p>Интервал и p рассчитаны разными способами, поэтому на малой выборке могут давать неодинаковые ориентиры. Все значения p приведены без поправки на число сравнений. При множественных проверках случайное обнаружение различия становится вероятнее. Нулевой интервал при одинаково верных ответах описывает только наблюдаемую выборку и не доказывает равенство на новых задачах.</p>'),
    ]


def narrative_sections(rows, summaries, analysis, comparisons):
    sections = [
        ("overview", "Задача исследования",
         """<p class="eyebrow">BICA Agent · Эксперименты 9 октября — 1 ноября 2026 года</p>
         <h1>Сжатие контекстной памяти языковых моделей</h1>
         <p class="subtitle">Как сохранить полезные сведения, если история длинная, а задача меняется</p>
         <p class="lead">На изученной выборке дополнительная проверка короткой памяти не дала устойчивого выигрыша в точности и увеличила расходы. После смены задачи успешный ответ часто сопровождался повторным чтением исходных записей.</p>
         <div class="facts"><div><strong>48</strong><span>основных примеров</span></div><div><strong>686</strong><span>прогонов моделей</span></div><div><strong>5</strong><span>моделей</span></div><div><strong>$27,88</strong><span>расход с отладкой</span></div></div>
         <h2>Почему короткую память нужно проверять</h2>
         <p>Языковая модель отвечает по тексту, который получает в текущем запросе. Этот доступный ей текст называется контекстом. Если переписка или история событий становится длинной, её можно читать частями и сохранять краткую запись важных фактов. В этом проекте такая запись называется рабочей памятью.</p>
         <p>При сжатии приходится решать, какие сведения оставить. Для выбора дешёвого поставщика важна цена, а код его договора может казаться второстепенным. Если позднее понадобится именно код, в короткой записи его уже может не быть. Поэтому мы проверяем, помогает ли дополнительная проверка памяти точнее отвечать после смены цели и оправдывает ли она расходы.</p>
         <p>Для ответа сравниваются два способа обновления памяти. Summary создаёт новую краткую запись за один запрос к модели. Reflexive сначала отбирает факты, затем сжимает их и отдельным запросом проверяет результат. Оба способа получают одинаковый объём памяти и одинаковые задачи.</p>
         <p>Сначала в отчёте объясняются методы, задания и условия эксперимента. Затем рассматриваются точность, влияние формы ответа, смена цели и стоимость. Разбор отдельных случаев связывает эти числа с поведением модели, а заключительная часть определяет границы выводов.</p>"""),
        ("methods", "Как устроен эксперимент",
         """<h2>Что модель читает и что сохраняет</h2>
         <p>История поступает по частям. Исходные фрагменты остаются в отдельном журнале, к которому можно обратиться позднее. После каждого фрагмента модель обновляет короткую рабочую память. Цель, план и последние результаты хранятся в отдельной короткой записи, называемой состоянием. Полная переписка предыдущих запросов автоматически в новый запрос не переносится.</p>
         <p>В Summary модель получает прежнюю память и новый текст, после чего сразу пишет обновлённую память. В Reflexive работа разделена на три последовательных запроса. Сначала модель выбирает факты, затем составляет краткую запись, а затем проверяет, сохранились ли выбранные факты в этой записи.</p>""" +
         table(["Метод", "Обновление после каждого фрагмента", "Запросов"],
               [["Summary", "Прежняя память и новый текст превращаются в новую память", "1"],
                ["Reflexive", "Отбор фактов, сжатие и проверка выбранного", "3"]]) +
         """<p>У проверки есть важная граница. Она видит уже отобранные факты и составленную память. Если нужное сведение не попало в первоначальный отбор, проверка не гарантирует его восстановления. В памяти также хранятся идентификаторы исходных фрагментов. Наличие такой ссылки позволяет найти источник, но само по себе не доказывает правильность записанного утверждения.</p>
         <p>Когда поступает вопрос, модель может ответить по памяти, сообщить о нехватке данных или запросить повторное чтение. Разрешён один раунд такого обращения с чтением не более двух известных фрагментов. Прочитанный текст снова проходит через тот же способ обновления памяти. Поэтому итог зависит и от сохранённых сведений, и от решения вовремя вернуться к источнику.</p>
         <h2>Какие задачи использованы</h2>
         <p>В исследовании 48 основных примеров из трёх наборов. PersonaMem содержит истории общения о пользователях, их предпочтениях и изменениях этих предпочтений. BABILong проверяет извлечение нужного факта среди длинного отвлекающего текста. Третий набор создан в проекте и проверяет смену задачи на историях о поставщиках.</p>""" +
         table(["Набор", "Выборка", "Когда известен вопрос", "Что засчитывается"],
               [["PersonaMem 32k", "16 персон, по одному вопросу", "После чтения истории", "Правильный вариант a–d"],
                ["BABILong qa1/8k", "20 примеров, строки 5–24", "До чтения истории", "Совпадение короткого ответа с эталоном"],
                ["Смена цели", "12 сценариев с поставщиками", "Новая цель после первого ответа", "Для новой цели нужен точный код договора"]]) +
         """<p>В PersonaMem модель заранее не знает, о чём её спросят. В BABILong она знает вопрос ещё до чтения. В сценарии с поставщиками вопрос меняется после первого ответа. Эти различия важны для отбора фактов, поэтому точности трёх наборов рассматриваются отдельно.</p>
         <p>Для PersonaMem дополнительно проверены два способа ответа без последовательного сжатия. «Полный контекст» передаёт всю доступную историю одним запросом. «Последнее окно» передаёт только её конец. Эти варианты помогают понять, даёт ли сжатая память пользу по сравнению с прямым чтением истории.</p>"""),
        ("protocol", "Условия и объём проверки",
         """<h2>Что означает одинаковый размер памяти</h2>
         <p>Размер текста измеряется токенами, то есть небольшими частями текста, на которые его разбивает программа. Токен не равен слову. Рабочая память обоих методов ограничена 512 токенами. Короткая запись состояния получает ещё 512 токенов. Таким образом, сравнивается работа при одинаковом объёме сохраняемой информации, а затраты на запросы измеряются отдельно.</p>""" +
         table(["Параметр", "Лимит в эксперименте"],
               [["Рабочая память", "512 токенов"], ["Состояние с целью и планом", "512 токенов"],
                ["Текущий запрос с резервом для ответа", "8192 токена"], ["Новый фрагмент истории", "2048 токенов"],
                ["Выход одного запроса к модели", "2048 токенов"], ["Дополнительные попытки исправить формат", "До двух"]]) +
         """<p>Внутри приложения длина текста для всех моделей считается одним измерителем cl100k_base. Для денежного расчёта используется фактическое число токенов, которое сообщил сервис модели. Выходной лимит включает внутреннее рассуждение, если выбранный режим модели его использует. Если ответ нарушает требуемый формат, допускается до двух дополнительных попыток.</p>
         <p>У полного контекста PersonaMem отдельный лимит в 65 536 токенов. Последнее окно содержит до 4096 токенов конца истории. Эти способы имеют другие условия доступа к информации, поэтому их результат нельзя считать сравнением при равном размере текущего контекста.</p>
         <h2>Что здесь называется платной серией</h2>
         <p>Платная серия — это группа заранее назначенных запусков через API, программный интерфейс внешнего сервиса языковых моделей. Сервис получает запросы программы и возвращает ответы, а расход рассчитывается по числу обработанных токенов и тарифам эксперимента. Это название отличает такие запуски от локальных проверок и демонстраций с заранее заданными ответами.</p>
         <p>Один прогон означает выполнение одной задачи выбранной моделью с одним способом работы с памятью. Он может включать много запросов к сервису, поскольку история читается частями. Поэтому 686 прогонов и 9 683 оплаченных запроса описывают разные величины. Последнее число также включает отладку, то есть предварительные запуски для проверки работоспособности.</p>
         <p>Первая серия от 1 ноября 2026 года содержит 512 прогонов. В ней использованы GPT-4.1 mini, GPT-5.4 mini и GPT-5.4 nano с двумя настройками. Продолжение содержит 174 прогона на Sol и Astra. Всего проверено пять моделей, а некоторые из них запускались с разными настройками.</p>
         <p>Сочетание модели и её настройки далее называется профилем. Метки none, low и medium обозначают выбранный режим внутреннего рассуждения. Они не меняют лимит памяти. В продолжении Sol low прошёл 128 прогонов на прежней выборке, Astra low — 28 прогонов на её части, а Sol medium — 18 дополнительных проверок без цикла обновления памяти.</p>
         <p>Для Astra бюджет позволил проверить девять сценариев смены цели обоими методами и десять вопросов PersonaMem только с последним окном. В режиме Sol medium проверены 16 последних окон и два полных контекста. Размеры этих дополнительных выборок определялись бюджетом. Их нельзя сравнивать с полной выборкой другой модели без отбора одинаковых примеров.</p>
         <p>Правильные ответы, называемые эталонами, отделены от входных данных и не передаются агенту. Оценку выполняет программа без дополнительной модели-судьи. В PersonaMem персонажи для отладки и итоговой оценки разделены. Продолжение использует те же примеры итоговой оценки, поэтому оно расширяет сравнение моделей, но не является проверкой на новом независимом наборе.</p>"""),
        ("accuracy", "Какие результаты получены",
         """<h2>Усложнение памяти не дало устойчивого выигрыша</h2>
         <p>Сначала рассмотрим итоговые ответы по исходным правилам оценки. В первой серии Reflexive на одних сочетаниях модели и набора давал больше верных ответов, а на других меньше. В продолжении Sol решил все задачи BABILong и все сценарии смены цели обоими методами. На PersonaMem Reflexive у Sol дал на один верный ответ меньше.</p>
         <figure>__ACCURACY__<figcaption>Рисунок 1. Точность по исходным правилам оценки. Подписи показывают число верных ответов из числа задач. Линии около столбцов — 95% интервалы Wilson, оценка неопределённости доли верных ответов при малой выборке. Это не интервалы разницы методов. Astra проверена на меньшем наборе.</figcaption></figure>
         <p>В каждой ячейке таблицы слева указан Summary, справа Reflexive. Например, 8/16 и 7/16 означают восемь и семь верных ответов на одних и тех же 16 задачах. Прочерк означает, что такого прогона не было.</p>""" + result_grid(summaries) +
         """<p>Более сильная модель заметно улучшила оба способа памяти. Для сравнения Sol и GPT-5.4 mini на BABILong с Reflexive точное парное p равно 0,0078 по исходной оценке. Однако часть различий связана с формой ответа. Далее разберём эту особенность, прежде чем оценивать убедительность сравнения.</p>"""),
        ("context", "Нужна ли память для одного вопроса",
         """<h2>Что даёт прямое чтение всей истории</h2>
         <p>Предыдущие разделы сравнивали два способа сжатия. Дополнительные проверки PersonaMem позволяют поставить другой вопрос. Нужно ли вообще сжимать историю, если она помещается в один запрос и в конце требуется ответить только на один вопрос?</p>
         <p>Полный контекст дал больше верных ответов, чем Summary, у всех пяти основных профилей. По сравнению с Reflexive исключением оказался nano none. У него полный контекст дал 6 верных ответов из 16, а Reflexive — 8. Пять профилей здесь включают две настройки одной модели nano.</p>
         <figure>__CONTEXT__<figcaption>Рисунок 2. Число верных ответов на 16 одинаковых задачах PersonaMem. Последнее окно содержит только конец истории, а полный контекст получает всю историю с большим лимитом запроса.</figcaption></figure>
         <p>На примере Sol можно сопоставить точность с затратами. Таблица относится к одним и тем же 16 вопросам. Денежные суммы указаны в долларах США, а число запросов включает обработку фрагментов и получение ответа.</p>""" +
         table(["Sol low на PersonaMem", "Верно", "USD за 16 задач", "Запросы"],
               [["Последнее окно", "5/16", "0,1860", "16"], ["Summary", "10/16", "2,5664", "270"],
                ["Reflexive", "9/16", "6,1878", "751"], ["Полный контекст", "13/16", "1,0564", "16"]]) +
         """<p>Полный контекст оказался и точнее, и дешевле обоих способов сжатия в этом условии. Причина, согласующаяся с устройством программы, состоит в повторной обработке текста. При сжатии инструкции, память и новые фрагменты отправляются много раз. Малый размер одного запроса поэтому не гарантирует малого суммарного расхода.</p>
         <p>Этот результат относится к историям данного размера и одному итоговому вопросу. Он не показывает, что произойдёт при множестве последующих вопросов или при окне, в которое вся история не помещается. Такие условия отдельно не проверялись.</p>"""),
        ("retrieval", "Как помогает возврат к источнику",
         """<h2>Почему итоговый ответ не описывает одну лишь память</h2>
         <p>При смене цели Sol до поиска правильно отвечал в 2 из 12 сценариев с Summary и в 3 из 12 с Reflexive. После разрешённого повторного чтения оба метода дали 12 из 12. У Astra на девяти общих сценариях результат изменился с 2 до 9 верных ответов в обоих режимах.</p>
         <figure>__RETRIEVAL__<figcaption>Рисунок 3. Результат на новой цели до поиска и в конце прогона. Пустая точка показывает оценку до поиска, закрашенная — итог. Подпись справа показывает переход и число сценариев. При равных результатах точки совпадают.</figcaption></figure>
         <p>Это наблюдение поддерживает предположение о пользе возврата к исходным записям. Однако решение искать принимала сама модель, а полученный текст затем снова проходил через обновление памяти. Отдельного условия с принудительно отключённым поиском нет. Поэтому весь прирост нельзя приписать только одному компоненту системы.</p>
         <p>Некоторые менее сильные модели отвечали без необходимых сведений и не обращались к источнику. Это указывает на ещё один возможный источник ошибки. Недостаточно сохранить ссылку на запись, нужно также распознать нехватку данных и решить ею воспользоваться. Ниже это показано на конкретном прогоне.</p>"""),
        ("cost", "Сколько стоила проверка",
         """<h2>Дополнительные запросы увеличили расходы</h2>
         <p>У Reflexive три запроса на обновление каждого фрагмента вместо одного у Summary. В первой серии его суммарная стоимость была выше в 2,2–3,3 раза, а у Sol — в 2,3–3,1 раза. Соотношение отличается от трёх, поскольку меняются длины запросов, ответов и число дополнительных действий.</p>
         <p>На девяти одинаковых сценариях смены цели Astra обошлась примерно в пять раз дороже Sol при одинаковой итоговой точности. Это сравнение относится только к этим сценариям.</p>
         <figure>__COST__<figcaption>Рисунок 4. Средняя стоимость одной задачи в долларах США. Шкалы трёх панелей различаются. Выборка Astra меньше, поэтому сопоставление моделей требует одинакового состава задач.</figcaption></figure>
         <p>Таблица показывает затраты основных прогонов по профилям. Отладка в неё не входит и учтена отдельно в общем расходе.</p>""" +
         table(["Профиль", "Прогоны", "Запросы", "USD, основные прогоны"],
               [[e(x) for x in row] for row in profile_costs(rows)]) +
         """<p>Основные прогоны стоили $26,44097159, отладка — $1,43534270. Общий расход составил <strong>$27,87631429 при бюджете $28</strong>. Осталось $0,12368571. Учтены 9 683 оплаченных запроса. Суммы рассчитаны по сохранённым сведениям об использовании токенов и тарифам эксперимента от 1 ноября 2026 года.</p>
         <p>Заранее установленного порога, при котором прирост точности считался бы оправданием расходов, не было. На этой выборке Reflexive стоил дороже без устойчивого общего выигрыша. Это основание для осторожного практического вывода в условиях эксперимента, но не универсальная оценка окупаемости.</p>"""),
        ("cases", "Как возникают ошибки",
         """<h2>Нужный факт не попал в сохранённую память</h2>
         <p>Сводные числа не объясняют каждую ошибку. Для подробного разбора доступны четыре полных журнала, по два метода на двух сценариях. Они показывают исходные запросы, ответы и изменения памяти. В каждой группе выбран первый по идентификатору случай, в котором методы дали разные результаты. Такой выбор помогает показать механизм, но не оценить его частоту.</p>
         <p>В сценарии goal-shift-000 у nano low после смены цели требовался код AG-10894-7 для поставщика Vendor-00-H. Summary запросил исходные фрагменты и вернул этот код. Reflexive сохранил сроки доставки, но отбросил коды договоров. Затем он ответил именем поставщика и не запросил повторное чтение.</p>""" +
         table(["Метод", "Действие", "Ответ", "Оценка"],
               [["Summary", "Перечитал фрагменты c001 и c004", "AG-10894-7", "Верно"],
                ["Reflexive", "Ответил без поиска", "Vendor-00-H", "Нужен был код договора"]]) +
         """<p>В этом случае проверяющая стадия не вернула сведения, отсутствующие в первоначальном отборе. Технический формат ответа и лимиты были соблюдены. Ошибка связана с содержанием памяти и последующим решением ответить без поиска.</p>
         <h2>Сохранённая альтернатива помогла изменить выбор</h2>
         <p>В сценарии goal-shift-001 у mini low первая цель привела оба метода к Vendor-01-D. После смены приоритета требовался более быстрый Vendor-01-B с кодом AG-88779-1. Summary ошибочно счёл прежнего поставщика самым быстрым. Reflexive сохранил сведения об альтернативе и вернул правильный код без поиска.</p>""" +
         table(["Метод", "Ответ", "Эталон", "Оценка"],
               [["Summary", "AG-68601-3", "AG-88779-1", "Неверно"],
                ["Reflexive", "AG-88779-1", "AG-88779-1", "Верно"]]) +
         """<p>Два случая объясняют, почему дополнительная проверка может и не помочь, и оказаться полезной. Результат зависит от того, какие факты были отобраны до сжатия и что понадобится для следующей задачи. Полные записи этих четырёх прогонов находятся в examples/openai-20261101/cases/.</p>"""),
        ("limits", "Что можно заключить",
         """<h2>Вывод в пределах проведённой проверки</h2>
         <p>На этой выборке трёхстадийное обновление памяти не показало устойчивого преимущества перед одношаговым, хотя требовало больше расходов. Переход к более сильной модели улучшил оба метода. После смены цели успешный ответ часто сопровождался возвратом к исходным записям. Для одного вопроса PersonaMem прямое чтение всей истории оказалось конкурентным по точности и стоимости.</p>
         <p>Эти результаты получены на небольших наборах из 16, 20 и 12 задач. Для каждой комбинации выполнен только один прогон, поэтому вариативность повторных запусков не измерена. Astra прошла часть заданий, а продолжение использовало прежние примеры. Проверка на новом независимом наборе ещё нужна.</p>
         <p>Сравнение меняет весь способ работы с памятью, включая инструкции и число запросов. Оно не выделяет отдельный вклад проверяющей стадии. Нет и отдельного условия с отключённым поиском. Собственные сценарии смены цели остаются короткими текстовыми задачами о поставщиках. Поведение в среде с реальными действиями здесь не исследовалось.</p>
         <p>У BABILong оценка зависит от формулировки ответа. Дополнительный пересчёт с удалением артикля введён после просмотра результатов и не заменяет исходную оценку. Он также не оценивает смысл сложных фраз. Эти ограничения нужно учитывать при объяснении различий между моделями.</p>
         <h2>Откуда взяты результаты и что можно проверить</h2>
         <p>Отчёт собран из сохранённых протоколов, итоговых ответов, таблиц расходов и доступных журналов запросов. При сборке сверены состав задач, все 686 итоговых ответов с сохранёнными эталонами, сводные числа и денежные суммы. Контрольные суммы SHA-256 в файле verification.json позволяют установить, какие версии исходных файлов использованы.</p>
         <p>Полные исходные истории и журналы большинства обращений к внешним моделям в репозитории отсутствуют. Поэтому можно проверить опубликованные сводки и доступные записи, но нельзя независимо восстановить все промежуточные стадии или заново проверить извлечение всех эталонов. Дословные вопросы доступны для пяти примеров BABILong и двух сценариев смены цели. Остальные вопросы и варианты ответов по догадке не восстанавливались.</p>
         <p>Источниками наборов служат bowen-upenn/PersonaMem в варианте 32k и RMT-team/babilong-1k-samples в варианте qa1/8k. Их версии и контрольные суммы записаны в файлах manifest. Идентификаторы Sol и Astra не привязаны к дате выпуска, поэтому точные веса моделей для будущего повторения не зафиксированы.</p>
         <h2>Какой эксперимент нужен дальше</h2>
         <p>Следующая проверка должна использовать новые, более сложные смены цели и несколько повторов каждого условия. Сравнение с отключённым поиском поможет отделить качество сохранения памяти от способности вовремя перечитать источник. Отдельное изменение проверяющей стадии позволит оценить именно её вклад. Пока такие эксперименты не проведены, вывод остаётся ограниченным описанными условиями.</p>
"""),
    ]
    additions = analysis_sections(analysis, summaries, comparisons)
    position = next(i for i, section in enumerate(sections) if section[0] == "context")
    sections[position:position] = additions[:2] + additions[3:]
    position = next(i for i, section in enumerate(sections) if section[0] == "retrieval")
    sections.insert(position, additions[2])
    return sections


def brief_sections(sections, summaries, analysis):
    """Keep the summary self-contained while leaving exhaustive evidence in the full report."""
    full = {key: (key, title, body) for key, title, body in sections}
    methods = ('<h2>Как сравниваются способы памяти</h2>'
        '<p>История читается частями. Summary сразу создаёт новую краткую память, а Reflexive отдельно отбирает факты, сжимает их и проверяет сохранение выбранного. Проверка не гарантирует, что в первоначальный отбор попало всё нужное. Оба метода могут один раз запросить повторное чтение не более двух исходных фрагментов.</p>' +
        table(["Метод", "Обновление памяти", "Запросов на фрагмент"], [
            ["Summary", "Сразу новая краткая запись", "1"],
            ["Reflexive", "Отбор, сжатие и проверка выбранных фактов", "3"]]) +
        '<p>Рабочая память ограничена 512 токенами, небольшими частями текста. Цель и план получают ещё 512 токенов. Текущий запрос с резервом для ответа ограничен 8192 токенами, новый фрагмент и выход модели — 2048 токенами каждый. Разрешены до двух дополнительных попыток исправить формат. Лимиты одинаковы у двух методов, число запросов и стоимость различаются.</p>'
        '<p>PersonaMem проверяет знания о пользователе по истории общения. Использованы 16 персон и по одному вопросу с выбором ответа. BABILong проверяет извлечение факта из длинного текста на 20 примерах. Собственный набор содержит 12 смен цели в задачах о поставщиках. В PersonaMem вопрос известен после истории, в BABILong до неё. Правильные ответы отделены от входов, оценку выполняет программа.</p>'
        '<h2>Откуда взялись 686 прогонов</h2>'
        '<p>Платными сериями здесь названы группы запусков через API, программный интерфейс внешнего сервиса моделей. Расход считается по обработанным токенам. Один прогон решает одну задачу выбранным способом, но может включать много запросов. Первая серия содержит 512 прогонов на GPT-4.1 mini, GPT-5.4 mini и двух настройках GPT-5.4 nano. Продолжение добавляет 174 прогона на Sol и Astra.</p>'
        '<p>Профиль означает модель с выбранной настройкой. Метки none, low и medium обозначают режим внутреннего рассуждения. Sol low прошёл 128 прогонов, Astra low — 28, Sol medium — 18 дополнительных проверок без цикла памяти. Astra проверена только на девяти сменах цели обоими методами и десяти последних окнах PersonaMem. Продолжение использует прежние примеры и не является новой независимой выборкой.</p>')
    accuracy = full["accuracy"][2] + (
        '<p>Ни одно парное сравнение Summary и Reflexive не дало p ниже 0,05. Точный тест Мак-Немара оценивает перекос между задачами, на которых выигрывает один или другой метод. Большое p означает нехватку оснований заявить различие, но не доказывает равенство. Полные разницы и интервалы неопределённости приведены в подробной версии. Поправка на число сравнений не применялась.</p>')
    metric = ('<h2>Как формулировка меняет оценку</h2>'
        '<p>В BABILong исходное правило требует точного совпадения после удаления крайних пробелов, одной конечной точки и приведения к нижнему регистру. Поэтому the hallway не совпадает с hallway, хотя оба ответа называют коридор. Дополнительный пересчёт убирает один начальный артикль the, a или an. Он выполнен после просмотра результатов и показан отдельно от исходной оценки.</p>' +
        table(SENSITIVITY_HEADERS, sensitivity_table(analysis)) +
        '<p>Из 200 ответов на 20 повторяющихся задачах 117 совпали строго, ещё 42 отличались только артиклем. В 18 ответах указано другое место, в 14 модель сообщила о нехватке данных. Девять фраз требуют отдельного разбора. Две из них явно содержат эталонное место, но не засчитываются даже после удаления артикля. Таким образом, несовпадение строки нельзя автоматически считать потерей факта.</p>'
        '<p>После удаления артикля сравнения nano low и none имеют p выше 0,05. У Sol против GPT-5.4 mini с Reflexive значение p меняется с 0,0078 до 0,03125. Эти показатели приведены без поправок на число сравнений и показывают зависимость вывода от правила оценки.</p>')
    goals = full["goals"][2] + (
        '<p>У Sol итог составил 12/12 в обоих методах, хотя до поиска результат был только 2/12 и 3/12. У Astra он изменился с 2/9 до 9/9. Итоговая точность поэтому характеризует и память, и обращение к источнику. Без отдельного условия с отключённым поиском причинный вклад повторного чтения не установлен.</p>')
    context = full["context"][2] + (
        '<h2>Цена дополнительных стадий</h2><p>Reflexive стоил дороже Summary в 2,2–3,3 раза в первой серии и в 2,3–3,1 раза у Sol. Общий расход с отладкой составил $27,87631429 при бюджете $28. Учтены 9 683 оплаченных запроса. Это расчёт по сохранённому числу токенов и тарифам эксперимента от 1 ноября 2026 года.</p>')
    cases = full["cases"][2] + (
        '<h2>Границы вывода</h2><p>Выборки малы, для каждой комбинации выполнен один прогон. Сравниваются целые процессы, поэтому отдельный эффект проверяющей стадии не выделен. Полный контекст имеет большее окно. Не исследованы ни множество последующих вопросов, ни работа с реальными действиями во внешней среде.</p>'
        '<p>Подробная версия содержит все 686 итоговых ответов, статистические сравнения и сохранённые вопросы. Большинство полных журналов и исходные истории в репозитории отсутствуют. Проверить можно сводки и доступные записи, но восстановить все промежуточные стадии нельзя. Следующая проверка требует новых сценариев, повторных запусков и отдельного сравнения с отключённым поиском.</p>')
    return [full["overview"], ("methods", "Методы и условия", methods), ("accuracy", "Результаты", accuracy),
            ("metric", "Как читать оценки", metric), ("goals", "Смена цели и поиск", goals),
            ("context", "Полная история и расходы", context), ("cases", "Разбор случаев и ограничения", cases)]


def markdown_report(sections):
    """Use the same narrative for Markdown, HTML and the full PDF."""
    parts = []
    for key, title, body in sections:
        body = re.sub(r'<div class="facts">.*?</div></div>', '', body, flags=re.S)
        def convert_table(match):
            records = []
            for row in re.findall(r'<tr[^>]*>(.*?)</tr>', match[0], flags=re.S):
                records.append([html.unescape(re.sub(r'<[^>]+>', '', cell))
                                for cell in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row, flags=re.S)])
            return "\n\n" + md_table(records[0], records[1:]) + "\n\n"
        body = re.sub(r'<table[^>]*>.*?</table>', convert_table, body, flags=re.S)
        body = re.sub(r'<figure>.*?<figcaption>(.*?)</figcaption></figure>',
                      lambda m: f'\n\n![{title}]({key}.svg)\n\n{m[1]}\n\n', body, flags=re.S)
        body = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\n\n# \1\n\n', body, flags=re.S)
        body = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n\n## \1\n\n', body, flags=re.S)
        body = re.sub(r'<a href="([^"]+)">(.*?)</a>', r'[\2](\1)', body, flags=re.S)
        body = re.sub(r'</p>', '\n\n', body)
        body = html.unescape(re.sub(r'<[^>]+>', '', body))
        parts.append(re.sub(r'\n[ \t]+', '\n', body).strip())
    links = ('[HTML с каталогом ответов](report.html) · [Краткий PDF](report.summary.pdf) · '
             '[Полный PDF](report.pdf) · [Все ответы CSV](all_answers.csv)')
    # Put navigation below the title without interrupting the opening explanation.
    text = "\n\n".join(parts)
    title_end = text.index('\n\n', text.index('# '))
    text = text[:title_end] + "\n\n" + links + text[title_end:]
    return re.sub(r'\n{3,}', '\n\n', text) + "\n\nРедакция от 18 ноября 2026 года. Подготовлено по сохранённым материалам без новых запросов к моделям.\n"


CSS = """
:root{--ink:#20343e;--muted:#61717b;--line:#dbe3e7;--blue:#246f86;--rust:#bc6646}
*{box-sizing:border-box}body{margin:0;color:var(--ink);background:#eef2f3;font:16px/1.65 Arial,sans-serif}
a{color:#185f77;text-underline-offset:3px}button,input,select{font:inherit}
.layout{max-width:1510px;margin:auto;display:grid;grid-template-columns:218px minmax(0,1fr);gap:26px;padding:28px}
nav{position:sticky;top:24px;align-self:start;padding:8px 10px 20px;max-height:95vh;overflow:auto}
nav .brand{font:22px Georgia,serif;margin:0 0 16px}nav a{display:block;text-decoration:none;font-size:13px;padding:7px 0;color:#526975}
main{min-width:0}.sheet{background:white;padding:42px 46px;margin:0 0 24px;border:1px solid var(--line);scroll-margin-top:20px}
.eyebrow{font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
h1{font:43px/1.13 Georgia,serif;letter-spacing:-.02em;margin:22px 0 18px;color:#153d4d}
h2{font:26px/1.25 Georgia,serif;margin:24px 0 14px;color:#153d4d}
.subtitle{font-size:20px;line-height:1.4;color:var(--muted)}.lead{font-size:18px;line-height:1.65;margin-top:28px}
p{margin:12px 0 18px}.facts{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:20px 0;margin:28px 0}
.facts strong{display:block;font-size:29px;font-weight:550;color:#18556b}.facts span{display:block;font-size:12px;color:var(--muted)}
.caption,figcaption{color:var(--muted);font-size:12px;line-height:1.55;margin:10px 0 20px}
figure{margin:22px 0}figure svg{display:block;width:100%;height:auto}
.table-wrap{overflow-x:auto;margin:18px 0 24px}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.45}
th{font-weight:600;text-align:left;background:#e9f0f3;color:#254858;padding:12px 10px;border-bottom:2px solid #bacdd5}
td{padding:11px 10px;border-bottom:1px solid #e1e7ea;vertical-align:top}tbody tr:nth-child(even){background:#f8fafb}
.badge{display:inline-block;font-size:11px;font-weight:600;border-radius:3px;padding:2px 6px;white-space:nowrap}
.ok{color:#285f4e;background:#eaf3ee}.bad{color:#93482d;background:#fbefe9}.absent{color:#6b727a;background:#eef0f2}
.filters{display:grid;grid-template-columns:1.5fr 1fr 1fr;gap:12px;margin:22px 0 14px}
label.filter{font-size:12px;color:var(--muted)}label.filter input,label.filter select{display:block;width:100%;padding:10px 9px;border:1px solid #bdccd3;border-radius:3px;background:white;color:var(--ink);margin-top:5px;font-size:13px}
.filter-count{font-size:13px;color:var(--muted)}.download{display:flex;gap:18px;font-size:13px;flex-wrap:wrap}
.answer-table{font-size:12px}.answer-table th{position:sticky;top:0;z-index:1}.answer-table td:nth-child(1){width:160px}
.answer{font-family:ui-monospace,Menlo,monospace;overflow-wrap:anywhere;max-width:170px}
.example-card{scroll-margin-top:20px}.example-card:target{border:1px solid #8eabb7;padding:12px}.example-card table{font-size:13px}
.sub{display:block;color:var(--muted);font-size:10px;margin-top:3px}
details{margin:8px 0;border-bottom:1px solid var(--line);padding:8px 0}summary{cursor:pointer;font-size:13px}
pre{font:12px/1.5 ui-monospace,Menlo,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f7f8;padding:16px}
.raw-list{max-height:650px;overflow:auto;padding:0 8px}.source-list{font-size:12px;word-break:break-word}
footer{font-size:12px;color:var(--muted);padding:12px 0 25px}
@media(max-width:1100px){.layout{grid-template-columns:170px minmax(0,1fr);gap:14px;padding:16px}.sheet{padding:30px 24px}.filters{grid-template-columns:repeat(2,1fr)}}
@media(max-width:760px){.layout{display:block;padding:12px}nav{position:static;max-height:none;display:flex;gap:12px;overflow-x:auto;padding:0 0 12px}nav a{white-space:nowrap}nav .brand{display:none}.sheet{padding:26px 20px}h1{font-size:34px}.facts{grid-template-columns:repeat(2,1fr)}.filters{grid-template-columns:1fr}}
@media print{@page{size:A4;margin:17mm 15mm}body{background:white;font-size:10pt;line-height:1.45}.layout{display:block;padding:0}nav,.filters,.download,.raw-section,footer{display:none!important}.sheet{padding:0;margin:0;border:0;break-before:page}#overview{break-before:auto}h1{font-size:30pt}h2{font-size:18pt}table{font-size:8pt}.answer-table{font-size:7pt}td,th{padding:5pt}figure,tr{break-inside:avoid}thead{display:table-header-group}th{position:static!important}.answer-row[hidden]{display:table-row!important}.filter-count{display:none}}
"""

JS = """
const state={q:'',profile:'',dataset:'',mode:'',result:''};
const norm=x=>String(x||'').toLowerCase();
function revealExample(id){if(!id.startsWith('example-'))return;const card=document.getElementById(id);if(card){card.open=true;card.scrollIntoView({block:'start'})}}
function openExample(){revealExample(decodeURIComponent(location.hash.slice(1)))}
window.addEventListener('hashchange',openExample);openExample();
document.querySelectorAll('a[href^="#example-"]').forEach(el=>el.addEventListener('click',()=>revealExample(el.getAttribute('href').slice(1))));
function filterAnswers(){let shown=0;document.querySelectorAll('.answer-row').forEach(row=>{
const ok=(!state.profile||row.dataset.profile===state.profile)&&(!state.dataset||row.dataset.dataset===state.dataset)&&(!state.mode||row.dataset.mode===state.mode)&&(!state.result||row.dataset.result===state.result)&&(!state.q||norm(row.dataset.question+' '+row.textContent).includes(state.q));
row.hidden=!ok;if(ok)shown++});document.querySelector('#shown').textContent=shown}
document.querySelectorAll('[data-filter]').forEach(el=>el.addEventListener('input',()=>{state[el.dataset.filter]=norm(el.value);filterAnswers()}));
document.querySelector('#raw-query').addEventListener('input',event=>{const q=norm(event.target.value);let shown=0;document.querySelectorAll('.raw-record').forEach(el=>{el.hidden=!!q&&!norm(el.textContent).includes(q);if(!el.hidden)shown++});document.querySelector('#raw-shown').textContent=shown});
document.querySelector('#download-filtered').addEventListener('click',()=>{const cell=x=>'"'+String(x??'').replaceAll('"','""')+'"';const out=[['id','profile','dataset','mode','answer','target','correct','answer_status','cost_usd','question','question_sources','answer_note']];
document.querySelectorAll('.answer-row:not([hidden])').forEach(el=>out.push(JSON.parse(el.dataset.export)));
const blob=new Blob(['\\ufeff'+out.map(r=>r.map(cell).join(',')).join('\\r\\n')],{type:'text/csv;charset=utf-8'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='filtered_answers.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)});
"""


def answer_catalog(rows):
    out = ['<section class="sheet" id="answers"><p class="eyebrow">Приложение A</p><h2>Все 686 итоговых ответов</h2>',
           '<p>Каждая строка — основной прогон. Ответы и эталоны перенесены без перефразирования. Пустой ответ показан явно. При смене цели приведён ответ на второй, итоговый вопрос.</p>',
           '<p class="caption">Нажмите на ID: откроется карточка задачи с доступным вопросом, эталоном, ответами моделей и пояснениями оценки. PersonaMem: ответ и эталон — буквы отсутствующих вариантов. Нет данных означает статус insufficient_data. Стоимость строк округлена; точные значения и доступные вопросы есть в CSV. Правильность первого этапа смены цели сохранена в CSV.</p>',
           '<div class="download"><a href="all_answers.csv" download>Все ответы CSV</a><a href="all_answers.json" download>Все ответы JSON</a><a href="verification.json">Происхождение и проверки</a></div>',
           '<div class="filters"><label class="filter">Поиск<input data-filter="q" placeholder="ID, вопрос, ответ, эталон, модель"></label>']
    for key, title, values in [
        ("profile", "Модель", [(p, LABELS[p]) for p in PROFILES]),
        ("dataset", "Набор", list(DATASETS.items())), ("mode", "Метод", list(METHODS.items())),
        ("result", "Результат", [("correct", "Верно"), ("wrong", "Неверный ответ"), ("insufficient", "Недостаточно данных")])]:
        out.append(f'<label class="filter">{title}<select data-filter="{key}"><option value="">Все</option>' +
                   "".join(f'<option value="{e(k)}">{e(v)}</option>' for k, v in values) + "</select></label>")
    out += ['</div><p class="filter-count">Показано <strong id="shown">686</strong> из 686. <button id="download-filtered" type="button">Скачать выбранные строки</button></p>',
            '<div class="table-wrap"><table class="answer-table"><thead><tr><th>Пример и модель</th><th>Метод</th><th>Ответ</th><th>Эталон</th><th>Результат</th><th>USD</th></tr></thead><tbody>']
    for r in rows:
        category = "correct" if r["correct"] else ("insufficient" if r["answer_status"] == "insufficient_data" else "wrong")
        badge, cls = ("Верно", "ok") if r["correct"] else (("Нет данных", "absent") if category == "insufficient" else ("Неверно", "bad"))
        export = [r[k] for k in ("id", "profile", "dataset", "mode", "answer", "target", "correct", "answer_status", "cost_usd", "question", "question_sources", "answer_note")]
        out.append(f'<tr class="answer-row" data-question="{e(r["question"] or "")}" data-profile="{e(r["profile"])}" data-dataset="{r["dataset"]}" data-mode="{r["mode"]}" data-result="{category}" data-export="{e(json.dumps(export, ensure_ascii=False))}">' +
                   f'<td><a href="#example-{e(r["id"])}">{e(r["id"])}</a><span class="sub">{e(LABELS[r["profile"]])}</span><span class="sub">{DATASETS[r["dataset"]]}</span></td>' +
                   f'<td>{METHODS[r["mode"]]}</td><td class="answer">{e(r["answer"]) if r["answer"] else "∅ (пусто)"}</td><td class="answer">{e(r["target"])}</td>' +
                   f'<td><span class="badge {cls}">{badge}</span><span class="sub">{e(r["answer_note"])}</span></td><td>{r["cost_usd"]:.5f}</td></tr>')
    return "".join(out) + "</tbody></table></div></section>"


def archive_catalog(archived, stages):
    non_paid = [r for r in archived if "/cases/" not in r["run"]]
    out = ['<section class="sheet" id="archive"><p class="eyebrow">Приложение B</p><h2>Локальные и демонстрационные прогоны</h2>',
           '<p>Эти записи не входят в 686 основных платных прогонов. Mock — заданные ответы для проверки программы. У Llama показаны и завершённые контрольные точки, и остановки без ответа.</p>',
           '<div class="download"><a href="archived_answers.json">Контрольные точки JSON</a><a href="saved_stage_responses.json">Ответы стадий JSON</a></div>']
    out.append(table(["Прогон", "Метод / этап", "Вопрос", "Ответ / остановка"], [
        [f'<a href="../../{e(r["run"])}/report.md">{e(r["run"].replace("examples/", ""))}</a>', f'{e(r["mode"])} / {r["checkpoint"] or "—"}',
         e(r["question"] or "Остановка до вопроса"),
         e(r["answer"] or ("Недостаточно данных" if r["answer_status"] == "insufficient_data" else
            (r["error"] or {}).get("message", "Ответ отсутствует")))]
        for r in non_paid]))
    out += ['</section><section class="sheet raw-section" id="stages"><p class="eyebrow">Приложение C · электронная версия</p><h2>Доступные промежуточные ответы</h2>',
            f'<p>Собрано <strong>{len(stages)}</strong> записей вызовов из локальных, mock и четырёх показательных платных прогонов. Это часть экспериментов, а не все 9 683 платных запроса. В раскрывающейся записи показан ответ модели. Исходный запрос и полная запись ответа доступны в JSON.</p>',
            f'<label class="filter">Поиск<input id="raw-query" placeholder="Например: verify, AG-10894-7, Sandra"></label><p class="filter-count">Записей: <span id="raw-shown">{len(stages)}</span></p><div class="raw-list">']
    for r in stages:
        out.append(f'<details class="raw-record"><summary>{e(r["run"])} · {r["index"]} · <strong>{e(r["stage"])}</strong></summary><pre>{e(json.dumps(r["payload"], ensure_ascii=False, indent=2))}</pre></details>')
    return "".join(out) + "</div></section>"


def rewrite_run_reports(root):
    """Refresh 29 derived Markdown reports without changing raw records."""
    for path in sorted((root / "examples").rglob("report.md")):
        r = read(path.with_name("results.json"))
        if "rows" in r:
            title = "Первая серия сравнения моделей" if "openai-20261101" in path.parts else "Продолжение на Sol и Astra"
            text = f"# {title}\n\n"
            text += ("Трёхстадийное обновление памяти не показало устойчивого преимущества перед одношаговым на этой выборке. "
                     "Платная серия означает группу запусков через программный интерфейс внешнего сервиса моделей. "
                     "Один прогон решает одну задачу выбранной моделью и может включать много запросов. "
                     "Summary обновляет память одним запросом, Reflexive использует отбор, сжатие и проверку. "
                     "Профиль задаёт модель и режим внутреннего рассуждения. Ниже приведены все группы серии. [Общий отчёт с графиками и каталогом ответов](../../docs/reports/final/report.html).\n\n")
            text += md_table(["Набор", "Модель", "Метод", "Верно", "Точность", "95% Wilson", "USD", "Вызовы"], [
                [DATASETS[s["dataset"]], LABELS[s["profile"]], METHODS[s["mode"]], f'{s["correct"]}/{s["n"]}',
                 f'{s["accuracy"]:.1%}', f'{100*s["wilson_95_ci"][0]:.1f}–{100*s["wilson_95_ci"][1]:.1f}%',
                 money(s["cost_usd"]), s["api_calls"]] for s in r["summaries"]])
            comparisons = r.get("paired_comparisons", r.get("paired_method_comparisons", []))
            text += "\n\n## Парное сравнение методов\n\nПоложительная разница — в пользу Reflexive. Интервал — сохранённый парный bootstrap (10 000 повторов). Значение p — точный McNemar без поправки на множественные сравнения. Используется исходная строгая метрика.\n\n"
            text += md_table(PAIR_HEADERS + ["Только Reflexive", "Только Summary"], [
                row + [c["second_only_correct"], c["first_only_correct"]]
                for row, c in zip(pair_table(comparisons), comparisons)])
            text += "\n\n## Два этапа смены цели\n\n" + md_table(GOAL_HEADERS, goal_table(r["summaries"]))
            text += "\n\nПервая цель — дешёвый поставщик с доставкой до пяти дней. Новая цель — код договора самого быстрого. Поиски учитываются за весь прогон, включая первую цель. До/после поиска — наблюдение внутри одного запуска, а не отдельный контроль без поиска.\n"
            text += "\n\n## До и после повторного чтения\n\n" + md_table(
                ["Набор", "Профиль", "Метод", "Верно до → после", "Поиски"], [
                    [DATASETS[s["dataset"]], LABELS[s["profile"]], METHODS[s["mode"]],
                     f'{s["correct_before_retrieval"]} → {s["correct"]} из {s["n"]}', s["retrievals"]]
                    for s in r["summaries"] if s["mode"] in ("summary", "reflexive")])
            if "reasoning_comparisons" in r:
                text += "\n\n## Reasoning low и none у nano\n\n" + md_table(["Набор", "Метод", "Разница low − none, п.п.", "95% интервал, п.п.", "p"], [
                    [DATASETS[c["dataset"]], METHODS[c["mode"]], f'{100*c["delta_accuracy"]:+.2f}',
                     pp_interval(c), f'{c["mcnemar_exact_p_unadjusted"]:.4f}'] for c in r["reasoning_comparisons"]])
            if "matched_model_comparisons" in r:
                text += "\n\n## Модели на общих примерах\n\n" + md_table(
                    ["Набор", "Метод", "Сравнение", "Общих ID", "Верно раньше → сейчас", "Δ, п.п.", "95% интервал, п.п.", "p"], [
                        [DATASETS[c["dataset"]], METHODS[c["mode"]], f'{LABELS[c["first"]]} → {LABELS[c["second"]]}',
                         c["n"], f'{c["old_correct"]} → {c["new_correct"]}', f'{100*c["delta_accuracy"]:+.2f}',
                         pp_interval(c), f'{c["mcnemar_exact_p_unadjusted"]:.4f}']
                        for c in r["matched_model_comparisons"]])
            analysis = analyze_babilong(r["rows"])
            text += "\n\n## Как форма ответа влияет на оценку BABILong\n\n"
            text += ("Исходные оценки не изменены. Дополнительно после прежней нормализации удалён один начальный артикль the, a или an с пробелом. "
                     "Пересчёт выполнен после просмотра результатов. Сложные фразы автоматически не переоцениваются.\n\n")
            text += md_table(SENSITIVITY_HEADERS, sensitivity_table(analysis))
            text += "\n\n" + md_table(["Категория", "Ответов"], [[v, analysis["category_counts"][k]] for k, v in CATEGORY_LABELS.items()])
            text += "\n\n[Правила, сложные фразы и парные сравнения обеих серий](../../docs/reports/analysis/babilong_sensitivity.md).\n"
            text += ("\n\n## Как читать результаты\n\nОдин прогон на комбинацию. Ошибки остаются в знаменателе. "
                     "Точности разных наборов не объединяются: они проверяют разные задачи. Полный контекст использует большее окно. "
                     "Небольшие выборки и несколько сравнений ограничивают выводы. До/после поиска — наблюдение в одном прогоне, не отдельный контроль без поиска.\n\n"
                     "Индивидуальные ответы: [CSV](predictions.csv) и [JSON](results.json). "
                     "Условия: [protocol.json](protocol.json). Расходы с отладкой: [receipts.csv](receipts.csv). "
                     "Большинство полных платных журналов в этом клоне отсутствуют.\n")
            path.write_text(text, encoding="utf-8")
            continue
        examples = r.get("examples", [r])
        provider = r.get("provider", examples[0].get("provider", ""))
        title = "Проверка программы с заданными ответами" if provider == "mock" else (
            "Локальная проверка Llama 3.2 1B" if provider == "ollama" else "Разбор сохранённого платного прогона")
        text = f"# {title}\n\n"
        if provider == "mock":
            text += "Ответы заданы программно. Пример проверяет обновление памяти, поиск и сохранение результатов. Качество языковой модели здесь не измеряется.\n\n"
        elif provider == "ollama":
            text += "Исторический запуск от 9 октября 2026 года. Завершение программы означает выполнение протокола. Оно не означает правильный ответ.\n\n"
        else:
            text += "Показательный случай первой серии. Он объясняет поведение метода, но не заменяет оценку всей выборки.\n\n"
        def identity(ex):
            return ex.get("id") or ex.get("name") or path.parent.name

        def run_link(ex, filename="report.md"):
            if "examples" not in r:
                target = path.with_name("results.json" if filename == "report.md" else filename)
            else:
                base = path.parent / identity(ex) if ex.get("kind") == "benchmark" else path.parent
                target = base / ex["mode"] / filename
            label = identity(ex)
            return f'[{label}]({Path(os.path.relpath(target, path.parent)).as_posix()})' if target.exists() else label

        answer_rows = []
        for ex in examples:
            for i, a in enumerate(ex.get("answers", []), 1):
                final = a.get("final")
                answer = final.get("answer", "") if final else ""
                status = final.get("status", "нет решения") if final else "нет решения"
                answer_rows.append([run_link(ex), METHODS.get(ex.get("mode"), ex.get("mode", "—")), i, a["question"], answer or "∅", status,
                                    ", ".join(a.get("retrieved_ids", [])) or "—"])
            if not ex.get("answers"):
                answer_rows.append([run_link(ex), METHODS.get(ex.get("mode"), ex.get("mode", "—")), "—", ex.get("state", {}).get("goal") or "Вопрос не сохранён", "∅",
                                    (ex.get("error") or {}).get("type", ex.get("status", "—")), "—"])
        text += "## Ответы\n\nID ведёт к материалам конкретного прогона. Этап — номер контрольного вопроса. Прочерк означает остановку до ответа.\n\n"
        text += md_table(["ID примера", "Метод", "Этап", "Вопрос", "Ответ", "Статус", "Перечитаны"], answer_rows)
        config = r.get("config", {})
        if config:
            text += "\n\n## Условия\n\n" + md_table(["Параметр", "Значение"], [
                ["Модель", r.get("model", "—")], ["Окно с резервом", config.get("window_ref_tokens", "—")],
                ["Память", config.get("memory_ref_tokens", "—")], ["Состояние", config.get("state_ref_tokens", "—")],
                ["Фрагмент", config.get("chunk_ref_tokens", "—")], ["Резерв ответа", config.get("max_output_tokens", "—")]])
        text += "\n\n## Работа программы\n\n" + md_table(["ID примера", "Метод", "Завершение", "Вызовы", "Сжатия", "Поиски", "USD"], [
            [run_link(x), METHODS.get(x.get("mode"), x.get("mode", "—")), x.get("status", "—"), x.get("metrics", {}).get("api_calls", "—"),
             x.get("metrics", {}).get("compressions", "—"), x.get("metrics", {}).get("retrievals", "—"),
             x.get("metrics", {}).get("cost_usd", "—")] for x in examples])
        errors = collections.defaultdict(list)
        for ex in examples:
            if ex.get("error"):
                errors[(ex["error"]["type"], ex["error"]["message"])].append(ex)
        if errors:
            text += "\n\n## Причины остановки\n\nОдинаковые ошибки объединены. Остановка по формату отличается от ответа insufficient_data: в первом случае протокол прерван, во втором модель явно сообщает о нехватке данных.\n\n"
            text += md_table(["Ошибка", "Что произошло", "Прогонов", "Какие прогоны"], [
                [kind, "Модель нарушила требуемую JSON-схему." if kind == "ResponseError" and "JSON schema" in message else message,
                 len(group), "; ".join(f'{run_link(ex)} / {METHODS.get(ex["mode"], ex["mode"])}' for ex in group)]
                for (kind, message), group in errors.items()])
        if r.get("summary_by_mode"):
            text += "\n\n## Оценка BABILong\n\n" + md_table(["Метод", "Запрошено", "Завершено", "Верно", "Ошибки формата"], [
                [mode, s["requested"], s["processed"], s["correct"], s["model_output_errors"]]
                for mode, s in r["summary_by_mode"].items()])
        trace = path.with_name("trace.jsonl")
        if trace.exists():
            updates = [x for x in lines(trace) if x.get("event") == "memory_update"]
            event = next((x for x in updates if x.get("reason") == "transition"), None)
            if event is None and updates:
                event = next((x for x in updates if x.get("memory_before") and x["memory_before"] != x["memory_after"]), updates[-1])
            if event:
                facts = [[when, fact["text"], ", ".join(fact.get("source_ids", []))]
                         for when, key in [("До", "memory_before"), ("После", "memory_after")]
                         for fact in event.get(key, [])]
                text += "\n\n## Пример изменения памяти\n\nЭто фактические записи модели. Наличие записи не подтверждает её истинность.\n\n<details>\n<summary>Показать записи до и после обновления</summary>\n\n"
                text += md_table(["Момент", "Запись", "Источники"], facts or [["До / после", "Пустая память", "—"]])
                text += "\n\n</details>"
        text += "\n\n## Исходные материалы\n\n[Результаты JSON](results.json)"
        for name, title in [("journal.jsonl", "Журнал текста"), ("memory_versions.jsonl", "Версии памяти"),
                            ("trace.jsonl", "Трасса"), ("api_calls.jsonl", "Запросы и ответы")]:
            if path.with_name(name).exists():
                text += f" · [{title}]({name})"
        path.write_text(text + "\n", encoding="utf-8")


def write_sensitivity(output, analysis, analysis_output):
    save_json(output / "babilong_sensitivity.json", analysis)
    with (output / "babilong_sensitivity.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(analysis["rows"][0]))
        writer.writeheader()
        writer.writerows(analysis["rows"])
    md = ("# Как форма ответа влияет на оценку BABILong\n\n"
          "Ретроспективный анализ от 18 ноября 2026 года. Исходная метрика и оценки сохранены. "
          "200 прогонов используют одни и те же 20 примеров. Это не 200 независимых задач. Новых запросов к моделям нет.\n\n"
          "## Правило дополнительного пересчёта\n\n"
          "Сначала применяется исходное приведение к нижнему регистру, удаление пробелов по краям и одной конечной точки. "
          "Затем из ответа и эталона удаляется один начальный артикль the, a или an с пробелом. "
          "Ответ засчитывается только при status=completed и answer_status=answer. Отказы и ошибки остаются в знаменателе. "
          "Числа не подменяют результаты замороженного протокола.\n\n")
    md += md_table(SENSITIVITY_HEADERS, sensitivity_table(analysis))
    md += "\n\n## Категории ответов\n\n" + md_table(["Категория", "Ответов"], [[v, analysis["category_counts"][k]] for k, v in CATEGORY_LABELS.items()])
    md += ("\n\n«Другое место» означает несовпадение разных элементов словаря bathroom, bedroom, garden, hallway, kitchen, office "
           "после нормализации артикля. Остальные фразы требуют разбора. Они не объявляются автоматически содержательными ошибками.\n\n"
           "## Все сложные несовпадения\n\n")
    md += md_table(["ID", "Профиль", "Метод", "Ответ", "Эталон"], [
        [r["id"], LABELS[r["profile"]], METHODS[r["mode"]], r["answer"], r["target"]]
        for r in analysis["rows"] if r["category"] == "other_mismatch"])
    md += ("\n\nНапример, Daniel is in the office. и Mary is in the hallway. называют эталонное место, "
           "но не засчитываются даже после удаления артикля. Это ограничение данного пересчёта. Семантическая оценка не добавлялась.\n\n"
           "## Парные сравнения\n\nΔ — второе условие минус первое. Все сравнения используют одинаковые идентификаторы задач. "
           "p — точный парный McNemar без поправки на множественные проверки. Анализ после просмотра результатов, без новой независимой выборки.\n\n")
    md += md_table(["Первое условие", "Второе условие", "Пар", "Δ строго, п.п.", "p строго", "Δ без артикля, п.п.", "p без артикля"], [
        [f'{LABELS[c["first_profile"]]} / {METHODS[c["first_mode"]]}',
         f'{LABELS[c["second_profile"]]} / {METHODS[c["second_mode"]]}', c["strict"]["n"],
         f'{100*c["strict"]["delta_accuracy"]:+.2f}', f'{c["strict"]["mcnemar_exact_p_unadjusted"]:.5f}',
         f'{100*c["article"]["delta_accuracy"]:+.2f}', f'{c["article"]["mcnemar_exact_p_unadjusted"]:.5f}']
        for c in analysis["comparisons"]])
    md += ("\n\n## Файлы и ограничения\n\n[Индивидуальные ответы CSV](babilong_sensitivity.csv) · "
           "[Результаты, правила и контрольные суммы источников JSON](babilong_sensitivity.json) · [Общий отчёт](report.html#metric).\n\n"
           "Исходные вопросы и полные истории большинства платных прогонов отсутствуют. Правильность сверяется с сохранёнными эталонами. "
           "Их извлечение из датасета заново не проверялось. Уменьшение p не является доказательством практической пользы, "
           "а p выше 0,05 не доказывает равенство. Первичные результаты и расходы не редактировались.\n")
    (analysis_output / "babilong_sensitivity.md").write_text(report_links(md, "analysis"), encoding="utf-8")


def build(root=ROOT, output=None, rewrite=False):
    output = output or root / "docs/reports"
    final, data_output, figures, analysis_output = (output / name for name in ("final", "data", "figures", "analysis"))
    for directory in (final, data_output, figures, analysis_output):
        directory.mkdir(parents=True, exist_ok=True)
    first, strong, rows, summaries, archived, stages, sources = load_data(root)
    verify(root, first, strong, rows, summaries)
    contexts = example_contexts(root, rows, archived)
    by_id = {c["id"]: c for c in contexts}
    for r in rows:
        c = by_id[r["id"]]
        r.update(question=c["question"], question_sources="; ".join(c["question_sources"]), answer_note=answer_note(r))
    context_sources = {"examples/babilong-manifest.json", "examples/openai-20261101/babilong-manifest.json"}
    context_sources.update(p for c in contexts for p in c["question_sources"])
    context_sources.update(str(Path(p).with_name("journal.jsonl")) for c in contexts if c["source_excerpt"] for p in c["question_sources"])
    for name in sorted(context_sources):
        sources.append({"path": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()})
    analysis = analyze_babilong(rows)
    analysis["sources"] = sources
    write_sensitivity(data_output, analysis, analysis_output)
    comparisons = first["paired_comparisons"] + strong["paired_method_comparisons"]
    charts = {"ACCURACY": accuracy_chart(summaries), "CONTEXT": context_chart(summaries),
              "RETRIEVAL": retrieval_chart(summaries), "COST": cost_chart(summaries)}
    for name, svg in charts.items():
        (figures / f"{name.lower()}.svg").write_text(svg, encoding="utf-8")
    for filename, data in [("all_answers.json", rows), ("example_contexts.json", contexts), ("archived_answers.json", archived), ("saved_stage_responses.json", stages)]:
        save_json(data_output / filename, data)
    with (data_output / "all_answers.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    verification = {
        "source_commit": "60aa0c4", "experiment_date": "2026-11-01", "editorial_revision": "2026-11-18",
        "main_runs": len(rows), "unique_main_examples": len({r["id"] for r in rows}),
        "summary_groups": len(summaries), "paid_receipts": 9683, "recorded_total_usd": 27.87631429,
        "archive_records": len(archived), "available_stage_records": len(stages), "sources": sources,
        "saved_questions": {"examples": sum(bool(c["question"]) for c in contexts),
                            "runs": sum(bool(r["question"]) for r in rows),
                            "file": "example_contexts.json"},
        "secondary_analysis": {"file": "babilong_sensitivity.json", "retrospective": True,
                               "primary_metric_unchanged": True, "runs": analysis["n_runs"],
                               "categories": analysis["category_counts"]},
        "checks": ["Task IDs match protocols", "No duplicate main run IDs", "Answers rescored against saved targets",
                   "Summary counts and costs match rows", "9683 unique receipt IDs", "Receipt total matches recorded total"],
        "limits": ["Dataset exports and most paid traces are absent", "Historical unit tests and full audits were not rerun",
                   "No model calls or external source verification"]}
    save_json(data_output / "verification.json", verification)
    sections = narrative_sections(rows, summaries, analysis, comparisons)
    for i, (key, title, body) in enumerate(sections):
        for name, svg in charts.items():
            body = body.replace(f"__{name}__", svg)
        sections[i] = (key, title, body)
    nav = [(key, title) for key, title, _ in sections] + [
        ("answers", "Все ответы"), ("examples", "Разбор примеров"), ("archive", "Локальные проверки"), ("stages", "Промежуточные ответы"), ("sources", "Источники")]
    doc = '<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Сжатие контекстной памяти — исследовательский отчёт</title><style>' + CSS + '</style></head><body><div class="layout"><nav aria-label="Содержание"><p class="brand">BICA Agent</p>' + "".join(f'<a href="#{key}">{e(title)}</a>' for key, title in nav) + '</nav><main>'
    for key, title, body in sections:
        doc += f'<section class="sheet" id="{key}">{body}</section>'
    doc += answer_catalog(rows) + example_cards(contexts, rows) + archive_catalog(archived, stages)
    doc += '<section class="sheet" id="sources"><h2>Исходные файлы</h2><p>SHA-256 фиксирует использованные версии данных. В переносимой HTML-копии внешние файлы могут быть недоступны. Ответы и графики встроены.</p><ul class="source-list">'
    doc += "".join(f'<li><a href="../../{e(s["path"])}">{e(s["path"])}</a><br>{s["sha256"]}</li>' for s in sources)
    doc += '</ul></section><footer>Редакция 18 ноября 2026 года. Новые эксперименты не проводились. Исходные ответы, эталоны и журналы не изменены.</footer></main></div><script>' + JS + "</script></body></html>"
    (final / "report.html").write_text(report_links(doc), encoding="utf-8")
    md = markdown_report(sections)
    (final / "README.md").write_text(report_links(md), encoding="utf-8")
    save_json(data_output / "pdf_data.json", {
        "sections": [{"id": k, "title": t, "html": report_links(re.sub(r"<svg.*?</svg>", "", body, flags=re.S))} for k, t, body in sections],
        "brief_sections": [{"id": k, "title": t, "html": report_links(re.sub(r"<svg.*?</svg>", "", body, flags=re.S))}
                           for k, t, body in brief_sections(sections, summaries, analysis)],
        "rows": rows, "summaries": summaries, "archived": archived, "contexts": contexts, "stage_count": len(stages),
        "labels": LABELS, "datasets": DATASETS, "methods": METHODS})
    if rewrite:
        rewrite_run_reports(root)
    print(json.dumps({"output": str(output), "main_runs": len(rows), "archived_records": len(archived),
                      "stage_records": len(stages), "verified": True}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, help="Report base directory; creates final/, data/, analysis/ and figures/")
    parser.add_argument("--rewrite-run-reports", action="store_true")
    args = parser.parse_args()
    build(args.root.resolve(), args.out.resolve() if args.out else None, args.rewrite_run_reports)
