"""Markdown reports and memory snapshots."""

from __future__ import annotations

from collections import defaultdict
from html import escape
import json
import math
from pathlib import Path
import textwrap
from typing import Any, Iterable


def _known_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def _usage(row: dict[str, Any]) -> dict[str, Any]:
    usage = row.get("usage")
    return usage if isinstance(usage, dict) else {}


def _record_totals(records: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "api_calls": len(records),
        "attempts": len(records),
        "duration_s": round(sum(row["duration_s"] for row in records if _known_number(row.get("duration_s"))), 6),
        "api_errors": 0,
        "response_errors": 0,
    }
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        values = []
        for row in records:
            usage = _usage(row)
            value = usage.get(field)
            if field == "total_tokens" and value is None:
                prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
                if _known_number(prompt) and _known_number(completion):
                    value = prompt + completion
            values.append(value)
        known = sum(value for value in values if _known_number(value))
        result[f"known_{field}"] = known
        result[field] = known if all(_known_number(value) for value in values) else None
        result[f"unknown_{field}_calls"] = sum(not _known_number(value) for value in values)
    costs = [row.get("cost_usd", _usage(row).get("cost")) for row in records]
    result["known_cost_usd"] = round(sum(value for value in costs if _known_number(value)), 10)
    result["unknown_cost_calls"] = sum(not _known_number(value) for value in costs)
    result["cost_usd"] = result["known_cost_usd"] if not result["unknown_cost_calls"] else None
    for row in records:
        error = row.get("error")
        kind = row.get("error_type", "")
        if isinstance(error, dict):
            kind = error.get("type", kind)
        if error or kind:
            if "response" in str(kind).lower() or "validation" in str(kind).lower():
                result["response_errors"] += 1
            else:
                result["api_errors"] += 1
    return result


def summarize_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Sum physical request attempts, preserving unknown usage and cost."""
    records = list(records)
    result = _record_totals(records)
    stages: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        stages[str(row.get("stage", "unknown"))].append(row)
    result["stage_totals"] = {stage: _record_totals(rows) for stage, rows in sorted(stages.items())}
    return result


def _cell(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return str(value).replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def _decision(value: Any) -> str:
    if not isinstance(value, dict):
        return _cell(value)
    status = value.get("status", "unknown")
    if status == "retrieve":
        return _cell(f"retrieve: {value.get('query', '')}; IDs: {value.get('source_ids', [])}")
    return _cell(f"{status}: {value.get('answer', '')}")


def _metrics_table(metrics: dict[str, Any]) -> list[str]:
    names = {
        "max_memory_ref_tokens": "Maximum working memory (reference tokens)",
        "max_request_ref_tokens": "Maximum request incl. output reserve (reference tokens)",
        "input_ref_tokens": "Original input (reference tokens)",
        "compressions": "Compressions",
        "retrievals": "Retrieval rounds",
        "reread_ref_tokens": "Re-read text (reference tokens)",
        "api_calls": "API calls / recorded attempts",
        "attempts": "HTTP / mock attempts",
        "prompt_tokens": "Provider prompt tokens",
        "completion_tokens": "Provider completion tokens",
        "total_tokens": "Provider total tokens",
        "cost_usd": "Total provider cost (USD)",
        "known_cost_usd": "Known cost subtotal (USD)",
        "unknown_cost_calls": "Calls with unknown cost",
        "duration_s": "Sum of request duration (seconds)",
        "api_errors": "API / transport errors",
        "response_errors": "Invalid model output errors",
    }
    lines = ["| Metric | Value |", "| --- | ---: |"]
    for key, name in names.items():
        if key in metrics:
            lines.append(f"| {name} | {_cell(metrics[key])} |")
    for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
        if metrics.get(field) is None and f"known_{field}" in metrics:
            lines.append(f"| Known {field.replace('_', ' ')} subtotal | {_cell(metrics[f'known_{field}'])} |")
    return lines


def _stages_table(metrics: dict[str, Any]) -> list[str]:
    stages = metrics.get("stage_totals", {})
    if not stages:
        return []
    lines = [
        "", "### Usage by stage", "",
        "| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for stage, row in stages.items():
        fields = [stage] + [row.get(key) for key in (
            "api_calls", "attempts", "prompt_tokens", "completion_tokens", "cost_usd",
            "known_cost_usd", "duration_s", "api_errors", "response_errors",
        )]
        lines.append("| " + " | ".join(_cell(value) for value in fields) + " |")
    return lines


def write_report(run_dir: Path, result: dict[str, Any]) -> Path:
    """Save results.json and report.md."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    provider = result.get("provider", "unknown")
    provider_note = {
        "mock": "MOCK: scripted responses.",
        "local_ollama": "LOCAL MODEL (Ollama). API cost excludes local compute.",
        "ollama": "LOCAL MODEL (Ollama). API cost excludes local compute.",
        "openrouter": "OPENROUTER. Missing usage or cost is reported as unknown.",
    }.get(provider, f"Provider: {_cell(provider)}.")
    lines = [
        f"# Context memory — {_cell(result.get('kind', 'run'))}", "", provider_note, "",
        f"Model: `{_cell(result.get('model', 'unknown'))}`. Provider: `{_cell(provider)}`.", "",
        f"Presentation: `{_cell(result.get('presentation', 'not specified'))}`. "
        "Reference tokens measure application limits; provider usage measures actual model requests.", "",
        "## Configuration", "", "```json", json.dumps(result.get("config", {}), ensure_ascii=False, indent=2), "```", "",
    ]
    metrics = result.get("metrics", {})
    lines.extend(["## Measured totals", ""] + _metrics_table(metrics))
    if "elapsed_s" in result:
        lines.extend(["", f"Wall time: {_cell(result['elapsed_s'])} seconds."])
    lines.extend(_stages_table(metrics))
    comparison = result.get("summary_by_mode", {})
    if comparison:
        lines.extend([
            "", "## Comparison", "",
            "| Mode | Requested | Processed | Correct | Wrong answers | Failed examples | API errors | Model output errors | Limit errors | Accuracy |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for mode, summary in comparison.items():
            wrong = summary.get("wrong_answers")
            if wrong is None and all(isinstance(summary.get(key), int) for key in ("processed", "correct")):
                wrong = summary["processed"] - summary["correct"]
            values = [mode, summary.get("requested"), summary.get("processed"), summary.get("correct"), wrong]
            values.extend(summary.get(key) for key in ("failed_examples", "infra_errors", "model_output_errors", "limit_errors", "accuracy"))
            lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
        lines.extend([
            "", "| Mode | Max memory | Compressions | Retrievals | Re-read tokens | Calls | Tokens | Cost USD | Seconds |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for mode, summary in comparison.items():
            values = [mode] + [summary.get(key) for key in (
                "max_memory_ref_tokens", "compressions", "retrievals", "reread_ref_tokens",
                "api_calls", "total_tokens", "cost_usd", "duration_s",
            )]
            lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
        lines.extend([
            "", "Accuracy is exact match divided by all requested examples, including failed runs in the denominator. "
            "Wrong answers, API failures, invalid model output and limit failures are listed separately; processed counts include only completed examples. "
            "Empty and insufficient_data answers are wrong.",
        ])
    examples = result.get("examples")
    if examples is None:
        examples = [result]
    lines.extend(["", "## Answers and failures", ""])
    for example in examples:
        identity = example.get("id", example.get("name", "example"))
        lines.extend([f"### {_cell(identity)} · {_cell(example.get('mode', 'unknown'))}", ""])
        status_text = f"Status: {_cell(example.get('status', 'unknown'))}."
        if "correct" in example:
            status_text += f" Exact match: {_cell(example['correct'])}."
        lines.extend([status_text, ""])
        error = example.get("error")
        if error:
            lines.extend([f"Recorded error: {_cell(error)}", ""])
        for answer in example.get("answers", []):
            lines.extend([
                f"Question: {_cell(answer.get('question', ''))}", "",
                "| Decision before retrieval | Final decision | Retrieved chunk IDs |",
                "| --- | --- | --- |",
                f"| {_decision(answer.get('before_retrieval'))} | {_decision(answer.get('final'))} | {_cell(answer.get('retrieved_ids', []))} |", "",
            ])
        if example.get("metrics") and example is not result:
            lines.extend(_metrics_table(example["metrics"]))
            lines.append("")
    trace_path = run_dir / "trace.jsonl"
    if trace_path.exists():
        updates = [event for event in (json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines())
                   if event.get("event") == "memory_update"]
        samples = [event for event in updates if event.get("reason") == "transition"]
        if not samples and updates:
            samples = [next((event for event in updates if event.get("memory_before") and event["memory_before"] != event["memory_after"]), updates[-1])]
        for event in samples:
            lines.extend(["", "## Actual memory snapshot", "",
                          f"Reason: {_cell(event.get('reason'))}. Stage: {_cell(event.get('current_stage'))}.", "",
                          "| Before compression | After compression |", "| --- | --- |",
                          f"| {_cell(event['memory_before'])} | {_cell(event['memory_after'])} |", ""])
    lines.extend([
        "## Files", "",
        "Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. "
        "Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.", "",
    ])
    path = run_dir / "report.md"
    path.write_text("\n".join(line.rstrip() for line in lines), encoding="utf-8")
    return path


def render_snapshot(before: Any, after: Any, output: Path, label: str) -> Path:
    """Render only supplied trace values, with escaped, wrapped SVG text."""
    def content(value: Any) -> list[str]:
        if isinstance(value, list):
            paragraphs = [json.dumps(row, ensure_ascii=False) if isinstance(row, dict) else str(row) for row in value]
        else:
            paragraphs = [json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value]
        lines = []
        for paragraph in paragraphs:
            lines.extend(textwrap.wrap(paragraph, width=57, break_long_words=True, break_on_hyphens=False) or [""])
            lines.append("")
        return lines or ["(empty)"]

    left, right = content(before), content(after)
    title = textwrap.wrap(str(label), width=108, break_long_words=True) or [""]
    title_height = 36 + 23 * len(title)
    body_y = title_height + 64
    height = body_y + 24 * max(len(left), len(right), 2) + 36
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}">',
        '<rect width="1200" height="100%" fill="#f5f6f7"/>',
        '<g font-family="Segoe UI, Arial, sans-serif" fill="#16283b">',
    ]
    for index, text in enumerate(title):
        svg.append(f'<text x="32" y="{36 + index * 23}" font-size="20" font-weight="600">{escape(text)}</text>')
    for x, heading, rows in ((24, "Before compression", left), (612, "After compression", right)):
        svg.append(f'<rect x="{x}" y="{title_height}" width="564" height="{height-title_height-24}" rx="12" fill="#fff" stroke="#bdcbd6"/>')
        svg.append(f'<text x="{x+20}" y="{title_height+32}" font-size="20" font-weight="600">{heading}</text>')
        for index, text in enumerate(rows):
            svg.append(f'<text x="{x+20}" y="{body_y+index*24}" font-size="15" xml:space="preserve">{escape(text)}</text>')
    svg.extend(["</g>", "</svg>"])
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(svg) + "\n", encoding="utf-8")
    return output
