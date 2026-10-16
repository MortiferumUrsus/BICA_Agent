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
    demo.add_argument("--name", choices=["correction", "supplier", "retrieval"], default="supplier")
    benchmark = commands.add_parser("benchmark", help="Compare modes on held-out BABILong rows")
    benchmark.add_argument("--data-dir", type=Path, default=Path("data/babilong"))
    benchmark.add_argument("--limit", type=int, default=5)
    benchmark.add_argument("--full-eval", action="store_true", help="Explicitly authorize all 20 evaluation examples")
    benchmark.add_argument("--split", choices=["debug", "eval"], default="eval")
    fetch = commands.add_parser("fetch-benchmark", help="Download only BABILong 8k qa1")
    fetch.add_argument("--data-dir", type=Path, default=Path("data/babilong"))
    fetch.add_argument("--revision", default="main")
    inspect = commands.add_parser("inspect", help="Read report and optionally render an actual memory snapshot")
    inspect.add_argument("run_dir", type=Path)
    inspect.add_argument("--snapshot", type=Path)
    inspect.add_argument("--event-index", type=int, default=-1, help="Index among memory_update events")
    for command in (doctor, demo, benchmark):
        command.add_argument("--provider", choices=["mock", "ollama", "openrouter"])
        command.add_argument("--model", help="Explicit local model; OpenRouter uses OPENROUTER_MODEL")
        command.add_argument("--live", action="store_true", help="Enable paid OpenRouter calls only with --budget-usd")
        command.add_argument("--budget-usd", type=float)
        command.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    for command in (demo, benchmark):
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
    if provider == "ollama":
        if args.live:
            raise ValueError("Local Ollama uses --provider ollama without --live")
        model = args.model or os.getenv("OLLAMA_MODEL")
        if not model:
            raise ValueError("Specify --model or OLLAMA_MODEL for a local run")
        return HTTPClient("ollama", model, config, base_url=args.ollama_url)
    if not args.live or args.budget_usd is None:
        raise ValueError("OpenRouter requires both --live and explicit --budget-usd")
    if args.model:
        raise ValueError("Set OPENROUTER_MODEL for OpenRouter; --model is for local Ollama")
    return HTTPClient("openrouter", os.getenv("OPENROUTER_MODEL"), config, budget_usd=args.budget_usd)


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
    from .benchmark import exact_match, load_inputs, load_targets
    from .reporting import summarize_records, write_report
    if args.limit not in range(1, 21):
        raise ValueError("--limit must be between 1 and 20")
    if args.split == "eval" and args.limit > 5 and not args.full_eval:
        raise ValueError("More than 5 evaluation examples requires explicit --full-eval")
    if args.split == "debug" and args.limit > 5:
        raise ValueError("Only 5 debug examples are available")
    inputs = load_inputs(args.data_dir, args.split, args.limit)
    modes = ["summary", "reflexive"] if args.mode == "both" else [args.mode]
    examples = []
    records_by_mode = {mode: [] for mode in modes}
    for row in inputs:
        for mode in modes:
            path = output / row["id"] / mode
            controller = Controller(client, path, mode, config)
            record_start = len(client.records)
            error = None
            try:
                controller.start(row["question"])
                controller.ingest(row["input"])
                controller.checkpoint(row["question"])
            except MemoryExperimentError as exc:
                error = exc
            result = controller.finish(row["id"], kind="benchmark", error=error)
            records_by_mode[mode].extend(client.records[record_start:])
            result["id"] = row["id"]
            result["row"] = row["row"]
            examples.append(result)
            print_result(result, path)
    # Reference data enters only this evaluator after inference has finished.
    targets = load_targets(args.data_dir, args.split)
    summaries = {}
    for result in examples:
        final = result["answers"][-1]["final"] if result["answers"] else None
        result["correct"] = exact_match(final["answer"], targets[result["id"]], final["status"]) if final and result["status"] == "completed" else None
        write_report(output / result["id"] / result["mode"], result)
    for mode in modes:
        rows = [r for r in examples if r["mode"] == mode]
        processed = sum(r["status"] == "completed" for r in rows)
        correct = sum(r["correct"] is True for r in rows)
        summaries[mode] = {"requested": len(rows), "processed": processed, "correct": correct,
            "infra_errors": sum(bool(r["error"] and r["error"]["type"] == "APIError") for r in rows),
            "failed_examples": sum(r["status"] == "error" for r in rows),
            "model_output_errors": sum(bool(r["error"] and r["error"]["type"] == "ResponseError") for r in rows),
            "limit_errors": sum(bool(r["error"] and r["error"]["type"] == "LimitError") for r in rows),
            "accuracy": correct / len(rows), "completed_accuracy": correct / processed if processed else None,
            "max_memory_ref_tokens": max(r["metrics"]["max_memory_ref_tokens"] for r in rows),
            "max_request_ref_tokens": max(r["metrics"]["max_request_ref_tokens"] for r in rows)}
        summaries[mode].update(summarize_records(records_by_mode[mode]))
        for key in ("compressions", "retrievals", "reread_ref_tokens", "api_calls", "known_cost_usd", "known_total_tokens", "api_errors", "response_errors"):
            summaries[mode][key] = sum(r["metrics"].get(key, 0) for r in rows)
    report = {"kind": "benchmark", "provider": client.provider, "model": client.model, "config": config.to_dict(),
        "presentation": "question_first", "split": args.split, "examples": examples,
        "metrics": summarize_records(client.records), "summary_by_mode": summaries,
        "notes": ["Accuracy denominator includes all requested examples; failures are separately counted.",
                  "Responses are scripted." if client.provider == "mock" else "Evaluation uses five examples by default."]}
    write_report(output, report)
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    print(f"Report: {(output / 'report.md').resolve()}")
    return int(any(r["status"] == "error" for r in examples))


def main(argv=None):
    load_dotenv(override=False)
    args = parser().parse_args(argv)
    client = None
    try:
        if args.command == "fetch-benchmark":
            from .benchmark import fetch_benchmark
            manifest = fetch_benchmark(args.data_dir, args.revision)
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
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
            if args.provider == "ollama" or args.live:
                client = make_client(args, Config())
                result["provider_check"] = client.preflight()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        config = Config(**{field: getattr(args, field) for field in Config().to_dict()})
        client = make_client(args, config)
        output = new_output(args)
        (output / "command.json").write_text(json.dumps({
            "argv": list(argv) if argv is not None else sys.argv[1:],
            "python": sys.version.split()[0], "cwd": str(Path.cwd()),
            "started_at": datetime.now(timezone(timedelta(hours=3))).isoformat(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        if args.command == "demo":
            return run_demo(args, client, config, output)
        return run_benchmark(args, client, config, output)
    except (MemoryExperimentError, ValueError, OSError, ImportError, KeyError, IndexError) as exc:
        print(f"Error ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 2
    finally:
        if client is not None and hasattr(client, "close"):
            client.close()
