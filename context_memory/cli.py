import argparse
import importlib.metadata
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from .config import Config
from .core import Controller, run_scenario
from .errors import MemoryExperimentError
from .mock import MockClient


def parser():
    parser = argparse.ArgumentParser(description="Compare summary and reflexive context memory")
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser("doctor", help="Check dependencies/configuration; never generates text")
    demo = commands.add_parser("demo", help="Run a small human-readable scenario")
    smoke = commands.add_parser("smoke", help="Check the complete pipeline on a short fact update before a large run")
    demo.add_argument("--name", choices=["correction", "supplier", "retrieval"], default="supplier")
    benchmark = commands.add_parser("benchmark", help="Compare modes on held-out BABILong rows")
    benchmark.add_argument("--data-dir", type=Path, default=Path("data/babilong"))
    benchmark.add_argument("--limit", type=int, default=5)
    benchmark.add_argument("--full-eval", action="store_true", help="Explicitly authorize all 20 evaluation examples")
    benchmark.add_argument("--dataset", choices=["babilong", "personamem"], default="babilong")
    benchmark.add_argument("--presentation", choices=["question_first", "question_later"])
    benchmark.add_argument("--dry-run", action="store_true", help="Save an experiment plan without any model calls")
    benchmark.add_argument("--no-score", action="store_true", help="Generate predictions without opening reference answers")
    benchmark.add_argument("--order", choices=["alternate", "summary_first", "reflexive_first"], default="alternate")
    benchmark.add_argument("--split", choices=["debug", "eval"], default="eval")
    fetch = commands.add_parser("fetch-benchmark", help="Download only BABILong 8k qa1")
    fetch.add_argument("--data-dir", type=Path, default=Path("data/babilong"))
    fetch.add_argument("--revision", default="main")
    fetch.add_argument("--dataset", choices=["babilong", "personamem"], default="babilong")
    evaluate = commands.add_parser("evaluate", help="Score saved predictions offline, without a model")
    evaluate.add_argument("run_dir", type=Path)
    evaluate.add_argument("--data-dir", type=Path, required=True)
    inspect = commands.add_parser("inspect", help="Read report and optionally render an actual memory snapshot")
    inspect.add_argument("run_dir", type=Path)
    inspect.add_argument("--snapshot", type=Path)
    inspect.add_argument("--event-index", type=int, default=-1, help="Index among memory_update events")
    for command in (doctor, demo, benchmark, smoke):
        command.add_argument("--provider", choices=["mock", "ollama", "openrouter", "openai"])
        command.add_argument("--model", help="Explicit local model; OpenRouter uses OPENROUTER_MODEL")
        command.add_argument("--live", action="store_true", help="Enable paid OpenRouter calls only with --budget-usd")
        command.add_argument("--budget-usd", type=float)
        command.add_argument("--ollama-url", default="http://127.0.0.1:11434")
        command.add_argument("--local-url", default="http://127.0.0.1:8000/v1", help="Local OpenAI-compatible server, e.g. vLLM through SSH forwarding")
        command.add_argument("--seed", type=int, default=42)
        command.add_argument("--timeout-s", type=float, default=60)
        command.add_argument("--local-context-tokens", type=int, default=8192)
    for command in (demo, benchmark, smoke):
        command.add_argument("--mode", choices=["summary", "reflexive", "both"], default="reflexive" if command is demo else "both")
        command.add_argument("--out", type=Path, help="New output folder, never overwritten")
        for field, value in Config().to_dict().items():
            command.add_argument("--" + field.replace("_", "-"), type=int, default=value)
    return parser


def make_client(args, config):
    provider = args.provider or ("openrouter" if args.live else "mock")
    if provider == "mock":
        if args.live:
            raise ValueError("--live requires provider openrouter")
        return MockClient(config)
    from .api import HTTPClient
    runtime = {"seed": args.seed, "timeout_s": args.timeout_s, "local_context_tokens": args.local_context_tokens}
    if provider in {"ollama", "openai"}:
        if args.live:
            raise ValueError("Local Ollama uses --provider ollama without --live")
        model = args.model or os.getenv("OLLAMA_MODEL" if provider == "ollama" else "LOCAL_MODEL")
        if not model:
            variable = "OLLAMA_MODEL" if provider == "ollama" else "LOCAL_MODEL"
            raise ValueError(f"Specify --model or {variable} for a local run")
        return HTTPClient(provider, model, config, base_url=args.ollama_url if provider == "ollama" else args.local_url, **runtime)
    if not args.live or args.budget_usd is None:
        raise ValueError("OpenRouter requires both --live and explicit --budget-usd")
    if args.model:
        raise ValueError("Set OPENROUTER_MODEL for OpenRouter; --model is for local Ollama")
    return HTTPClient("openrouter", os.getenv("OPENROUTER_MODEL"), config, budget_usd=args.budget_usd, **runtime)


def new_output(args):
    stamp = datetime.now(timezone(timedelta(hours=3))).strftime("%Y%m%d-%H%M%S")
    path = args.out or Path("runs") / f"{stamp}-{args.command}-{uuid4().hex[:6]}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def print_result(result, path):
    print(f"{result['provider']} / {result.get('model', '')}: {path.resolve()}")
    for outcome in result.get("answers", []):
        decision = outcome["final"]
        if decision is None:
            print("  No final answer: execution stopped after the initial decision")
            continue
        print(f"  {decision['status']}: {decision['answer']}")
    if result.get("error"):
        print(f"  ERROR {result['error']['type']}: {result['error']['message']}")


def run_demo(args, client, config, output):
    from .reporting import write_report
    scenario = json.loads((Path(__file__).parent / "scenarios" / f"{args.name}.json").read_text(encoding="utf-8"))
    modes = ["summary", "reflexive"] if args.mode == "both" else [args.mode]
    results = []
    for mode in modes:
        path = output / mode
        result = run_scenario(client, scenario, path, mode, config)
        results.append(result)
        print_result(result, path)
    if len(results) > 1:
        write_report(output, {"kind": "demo", "name": args.name, "provider": client.provider, "model": client.model,
                              "config": config.to_dict(), "examples": results})
    return int(any(r["status"] == "error" for r in results))


def run_benchmark(args, client, config, output):
    from .evaluation import dataset_module, dataset_identity, grade_result
    from .reporting import summarize_records, write_report
    if args.limit not in range(1, 21):
        raise ValueError("--limit must be between 1 and 20")
    if args.split == "eval" and args.limit > 5 and not args.full_eval:
        raise ValueError("More than 5 evaluation examples requires explicit --full-eval")
    if args.split == "debug" and args.limit > 5:
        raise ValueError("Only 5 debug examples are available")
    module = dataset_module(args.dataset)
    inputs = module.load_inputs(args.data_dir, args.split, args.limit)
    presentation = args.presentation or ("question_later" if args.dataset == "personamem" else "question_first")
    identity = dataset_identity(args.data_dir)
    protocol = experiment_plan(args, config, inputs)
    (output / "protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    modes = ["summary", "reflexive"] if args.mode == "both" else [args.mode]
    examples = []
    records_by_mode = {mode: [] for mode in modes}
    for index, row in enumerate(inputs):
        reverse = args.order == "reflexive_first" or (args.order == "alternate" and index % 2 == 1)
        row_modes = list(reversed(modes)) if reverse else modes
        for mode in row_modes:
            path = output / row["id"] / mode
            controller = Controller(client, path, mode, config)
            record_start = len(client.records)
            error = None
            try:
                goal = row["question"] if presentation == "question_first" else "Remember facts, preferences and their changes, including stated reasons, from the history for a later question."
                # Options belong only to the checkpoint, not the bounded task state.
                if row.get("choices") and presentation == "question_first":
                    goal = row["question"].split("\n", 1)[0]
                controller.start(goal)
                controller.ingest(row["input"])
                controller.checkpoint(row["question"], choices=row.get("choices"))
            except MemoryExperimentError as exc:
                error = exc
            result = controller.finish(row["id"], kind="benchmark", error=error)
            records_by_mode[mode].extend(client.records[record_start:])
            result["id"] = row["id"]
            result["row"] = row["row"]
            result["presentation"] = presentation
            result["question_type"] = row.get("question_type", "qa1")
            result["correct"] = None
            examples.append(result)
            print_result(result, path)
    summaries = {}
    for mode in modes:
        rows = [r for r in examples if r["mode"] == mode]
        processed = sum(r["status"] == "completed" for r in rows)
        summaries[mode] = {"requested": len(rows), "processed": processed, "correct": None,
            "infra_errors": sum(bool(r["error"] and r["error"]["type"] == "APIError") for r in rows),
            "failed_examples": sum(r["status"] == "error" for r in rows),
            "model_output_errors": sum(bool(r["error"] and r["error"]["type"] == "ResponseError") for r in rows),
            "limit_errors": sum(bool(r["error"] and r["error"]["type"] == "LimitError") for r in rows),
            "accuracy": None, "completed_accuracy": None,
            "max_memory_ref_tokens": max(r["metrics"]["max_memory_ref_tokens"] for r in rows),
            "max_request_ref_tokens": max(r["metrics"]["max_request_ref_tokens"] for r in rows)}
        summaries[mode].update(summarize_records(records_by_mode[mode]))
        for key in ("compressions", "retrievals", "reread_ref_tokens", "api_calls", "known_cost_usd", "known_total_tokens", "api_errors", "response_errors"):
            summaries[mode][key] = sum(r["metrics"].get(key, 0) for r in rows)
    report = {"kind": "benchmark", "provider": client.provider, "model": client.model, "config": config.to_dict(),
        "dataset": args.dataset, "dataset_manifest_sha256": identity,
        "requested_ids": protocol["ids"], "requested_modes": modes,
        "presentation": presentation, "split": args.split, "examples": examples,
        "metrics": summarize_records(client.records), "summary_by_mode": summaries,
        "notes": ["Accuracy denominator includes all requested examples; failures are separately counted.",
                  "Responses are scripted." if client.provider == "mock" else "Evaluation uses five examples by default."]}
    report["evaluation"] = {"method": "not_scored", "judge_model": None, "targets_visible_to_solver": False}
    if not args.no_score:
        report = grade_result(report, args.data_dir)
    for result in report["examples"]:
        write_report(output / result["id"] / result["mode"], result)
    with (output / "predictions.jsonl").open("w", encoding="utf-8") as handle:
        for row in report["examples"]:
            handle.write(json.dumps({k: row[k] for k in ("id", "mode", "status", "answers")}, ensure_ascii=False) + "\n")
    write_report(output, report)
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    print(f"Report: {(output / 'report.md').resolve()}")
    return int(any(r["status"] == "error" for r in examples))


def experiment_plan(args, config, inputs=None):
    import hashlib
    from .evaluation import dataset_identity, dataset_module
    from .tokens import count
    rows = inputs if inputs is not None else dataset_module(args.dataset).load_inputs(args.data_dir, args.split, args.limit)
    if not 1 <= args.limit <= 20 or (args.limit > 5 and not args.full_eval):
        raise ValueError("Use --limit 1..5, or --full-eval for 6..20")
    chunks = [max(1, (count(row["input"]) + config.chunk_ref_tokens - 1) // config.chunk_ref_tokens) for row in rows]
    modes = ["summary", "reflexive"] if args.mode == "both" else [args.mode]
    minimum_calls = sum((2 + chunks_i * (3 if mode == "reflexive" else 1)) for chunks_i in chunks for mode in modes)
    return {"dataset": args.dataset, "split": args.split, "dataset_manifest_sha256": dataset_identity(args.data_dir),
            "ids": [r["id"] for r in rows], "modes": modes, "config": config.to_dict(),
            "presentation": args.presentation or ("question_later" if args.dataset == "personamem" else "question_first"),
            "input_ref_tokens": [count(r["input"]) for r in rows], "minimum_api_calls_estimate": minimum_calls,
            "call_limit_below_estimate": config.max_api_calls < minimum_calls,
            "estimate_note": "Excludes retrieval, format retries and extra adaptive chunks; actual calls can be higher.",
            "provider": args.provider or ("openrouter" if args.live else "mock"),
            "model": args.model or os.getenv("OPENROUTER_MODEL" if args.live else "OLLAMA_MODEL"),
            "seed": args.seed, "seed_scope": "local providers", "timeout_s": args.timeout_s, "local_context_tokens": args.local_context_tokens, "mode_order": args.order,
            "evaluation": {"method": "strict_choice_label" if args.dataset == "personamem" else "exact_match", "judge_model": None},
            "prompt_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).parent / "prompts").glob("*.txt")}}


def main(argv=None):
    load_dotenv(override=False)
    args = parser().parse_args(argv)
    if getattr(args, "dataset", None) == "personamem" and args.data_dir == Path("data/babilong"):
        args.data_dir = Path("data/personamem")
    client = None
    try:
        if args.command == "fetch-benchmark":
            from .benchmark import fetch_benchmark
            from .personamem import fetch_personamem
            fetcher = fetch_personamem if args.dataset == "personamem" else fetch_benchmark
            manifest = fetcher(args.data_dir, args.revision)
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0
        if args.command == "evaluate":
            from .evaluation import grade_result
            from .reporting import write_report
            result = json.loads((args.run_dir / "results.json").read_text(encoding="utf-8"))
            scored = grade_result(result, args.data_dir)
            destination = args.run_dir / "evaluation"
            write_report(destination, scored)
            print(json.dumps(scored["summary_by_mode"], indent=2))
            print(f"Report: {(destination / 'report.md').resolve()}")
            return 0
        if args.command == "inspect":
            from .reporting import render_snapshot
            report = args.run_dir / "report.md"
            print(report.read_text(encoding="utf-8"))
            if args.snapshot:
                events = [json.loads(line) for line in (args.run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
                event = [e for e in events if e["event"] == "memory_update"][args.event_index]
                result = json.loads((args.run_dir / "results.json").read_text(encoding="utf-8"))
                render_snapshot(event["memory_before"], event["memory_after"], args.snapshot, f"{result['provider']} / {result['model']}")
                print(f"Snapshot: {args.snapshot.resolve()}")
            return 0
        if args.command == "doctor":
            dependencies = {}
            for package in ("httpx", "jsonschema", "tiktoken", "python-dotenv", "huggingface-hub", "pyarrow", "pytest"):
                try:
                    dependencies[package] = importlib.metadata.version(package)
                except importlib.metadata.PackageNotFoundError:
                    dependencies[package] = "not installed"
            result = {"python": sys.version.split()[0], "dependencies": dependencies,
                      "openrouter_key_present": bool(os.getenv("OPENROUTER_API_KEY")),
                      "openrouter_model_present": bool(os.getenv("OPENROUTER_MODEL")), "generation_performed": False}
            if args.provider in {"ollama", "openai"} or args.live:
                client = make_client(args, Config())
                result["provider_check"] = client.preflight()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        config = Config(**{field: getattr(args, field) for field in Config().to_dict()})
        if args.command == "benchmark" and args.dry_run:
            plan = experiment_plan(args, config)
            output = new_output(args)
            (output / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
            print(json.dumps(plan, indent=2))
            print(f"Plan: {(output / 'plan.json').resolve()}")
            return 0
        client = make_client(args, config)
        output = new_output(args)
        (output / "command.json").write_text(json.dumps({
            "argv": list(argv) if argv is not None else sys.argv[1:],
            "python": sys.version.split()[0], "cwd": str(Path.cwd()),
            "started_at": datetime.now(timezone(timedelta(hours=3))).isoformat(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.command == "demo":
            return run_demo(args, client, config, output)
        if args.command == "smoke":
            from .benchmark import exact_match
            from .reporting import write_report
            args.name = "correction"
            code = run_demo(args, client, config, output)
            modes = ["summary", "reflexive"] if args.mode == "both" else [args.mode]
            checks = []
            for mode in modes:
                result = json.loads((output / mode / "results.json").read_text(encoding="utf-8"))
                final = result["answers"][-1]["final"] if result["answers"] else None
                passed = bool(final and result["status"] == "completed" and exact_match(final["answer"], "19 November 2026", final["status"]))
                checks.append({"mode": mode, "pipeline_completed": result["status"] == "completed", "answer_correct": passed})
            (output / "smoke.json").write_text(json.dumps({"checks": checks, "passed": all(c["answer_correct"] for c in checks), "evaluator": "exact_match_code", "provider": client.provider, "model": client.model}, indent=2), encoding="utf-8")
            print(json.dumps(checks, indent=2))
            return 0 if not code and all(c["answer_correct"] for c in checks) else 1
        return run_benchmark(args, client, config, output)
    except (MemoryExperimentError, ValueError, OSError, ImportError, KeyError, IndexError) as exc:
        print(f"Error ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 2
    finally:
        if client is not None and hasattr(client, "close"):
            client.close()
