"""Reproducible first paid study: frozen inputs, shared budget, separate scoring.

Run prepare, debug, run, then score. Resuming skips only complete result files;
an interrupted individual task is never silently overwritten or rerun.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random

from . import benchmark, personamem
from .config import Config
from .core import Controller
from .errors import MemoryExperimentError
from .evaluation import dataset_identity
from .paid_openai import BudgetLedger, OpenAIClient, PRICES, PRICE_SOURCE
from .reporting import summarize_records
from .schemas import schema_for
from .storage import write_json
from .tokens import count, prefix


PROFILES = {
    "4.1-mini": {"model": "gpt-4.1-mini-2025-04-14", "reasoning_effort": None},
    "5.4-nano-low": {"model": "gpt-5.4-nano-2026-03-17", "reasoning_effort": "low"},
    "5.4-mini-low": {"model": "gpt-5.4-mini-2026-03-17", "reasoning_effort": "low"},
    "5.4-nano-none": {"model": "gpt-5.4-nano-2026-03-17", "reasoning_effort": "none"},
}
GOAL = "Remember facts, preferences and their changes, including stated reasons, from the history for a later question."
CONFIG = Config(window_ref_tokens=8192, max_output_tokens=2048, chunk_ref_tokens=2048,
                memory_ref_tokens=512, state_ref_tokens=512, format_retries=2, max_api_calls=250)


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def implementation_hashes():
    base = Path(__file__).parent
    paths = [base / p for p in ("core.py", "paid_openai.py", "schemas.py", "storage.py", "tokens.py")]
    paths += sorted((base / "prompts").glob("*.txt"))
    return {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def implementation_matches(expected):
    """Git can change CRLF to LF; universal-newline prompt reads are identical."""
    actual = implementation_hashes()
    if actual.keys() != expected.keys():
        return False
    base = Path(__file__).parent
    for name, digest in expected.items():
        data = (base / name).read_bytes().replace(b"\r\n", b"\n")
        candidates = {actual[name], hashlib.sha256(data).hexdigest(),
                      hashlib.sha256(data.replace(b"\n", b"\r\n")).hexdigest()}
        if digest not in candidates:
            return False
    return True


def select_personas(rows, seed=20261101):
    """One question per persona, cycling types, without reading answer files."""
    rng = random.Random(seed)
    personas = sorted({r["persona_id"] for r in rows})
    rng.shuffle(personas)
    types = sorted({r["question_type"] for r in rows})
    selected = []
    for i, persona in enumerate(personas):
        candidates = [r for r in rows if r["persona_id"] == persona and r["question_type"] == types[i % len(types)]]
        if not candidates:
            candidates = [r for r in rows if r["persona_id"] == persona]
        selected.append(rng.choice(sorted(candidates, key=lambda r: r["id"])))
    return selected


def synthetic_cases(n=12):
    """Custom diagnostic, not an established benchmark; exact generated targets."""
    inputs, targets = [], {}
    rng = random.Random(20261101)
    for i in range(n):
        names = [f"Vendor-{i:02d}-{chr(65+j)}" for j in range(10)]
        prices = rng.sample(range(70, 300), 10)
        days = rng.sample(range(1, 15), 10)
        codes = [f"AG-{rng.randrange(10000,99999)}-{j}" for j in range(10)]
        supplier_text = "\n".join(f"{name}: price={price}; delivery_days={day}; contract_code={code}; payment=on delivery." for name, price, day, code in zip(names, prices, days, codes))
        # A price correction changes the first task. The fastest supplier's
        # contract remains in earlier source text, needed after the goal change.
        eligible = [j for j, d in enumerate(days) if d <= 5]
        changed = rng.choice(eligible)
        prices[changed] = 50
        first = names[changed]
        final = codes[min(range(10), key=lambda j: days[j])]
        noise = "\n".join(f"Archive meeting {j}: chairs={20+j}; room=R-{j}; tea stock={30+j}. No supplier decisions were made." for j in range(90))
        identity = f"goal-shift-{i:03d}"
        inputs.append({"id": identity, "dataset": "goal_shift", "question_type": "price_update_then_new_goal",
            "goal": "Choose the cheapest supplier delivering within 5 days.",
            "events": [{"text": supplier_text}, {"text": noise},
                {"text": f"Confirmed correction: {names[changed]} now has price=50. All delivery times and contract codes are unchanged."},
                {"question": "Which supplier is cheapest among those delivering within 5 days? Return its name only."},
                {"goal": "The purchasing priority has changed: choose the fastest supplier regardless of price and recover its contract code."},
                {"question": "What is the contract code of the supplier with the shortest delivery time, regardless of price? Return only the exact code."}]})
        targets[identity] = [first, final]
    return inputs, targets


def prepare(root):
    root.mkdir(parents=True, exist_ok=True)
    path = root / "protocol.json"
    if path.exists():
        raise ValueError("Protocol already exists; use the recorded selection")
    persona = select_personas(personamem.load_inputs(Path("data/personamem"), "eval", 471))
    babi = benchmark.load_inputs(Path("data/babilong"), "eval", 20)
    custom, targets = synthetic_cases()
    rows = [{**r, "dataset": "personamem"} for r in persona] + [{**r, "dataset": "babilong", "question_type": "qa1"} for r in babi] + custom
    write_json(root / "inputs.json", rows)
    write_json(root / "synthetic-targets.json", targets)
    tasks = []
    # Shuffle fixed task order, independent of outputs and targets. Each task
    # has its own model client, memory, journal and directory.
    for profile in PROFILES:
        for row in rows:
            modes = ["summary", "reflexive", "full_context", "last_window"] if row["dataset"] == "personamem" else ["summary", "reflexive"]
            for mode in modes:
                tasks.append({"profile": profile, "id": row["id"], "dataset": row["dataset"], "mode": mode})
    random.Random(20261101).shuffle(tasks)
    protocol = {"version": 1, "date": "2026-11-01", "seed": 20261101, "budget_usd": 26,
        "profiles": PROFILES, "config": CONFIG.to_dict(), "prices_usd_per_million": PRICES,
        "price_source": PRICE_SOURCE, "inputs_sha256": sha(rows), "implementation_sha256": implementation_hashes(),
        "dataset_manifest_sha256": {d: dataset_identity(Path("data") / d) for d in ("personamem", "babilong")},
        "tasks": tasks, "selection": [{k: r[k] for k in ("id", "dataset", "question_type", "persona_id") if k in r} for r in rows],
        "primary_comparison": "reflexive minus summary, paired final correctness; all assigned runs in denominator",
        "presentation": {"personamem": "question_later", "babilong": "question_first", "goal_shift": "new goal revealed after first answer"},
        "baselines": {"full_context": "65536-token window, no compression; reference with a larger context budget", "last_window": "last 4096 reference tokens, no persistent memory"},
        "evaluation": {"judge_model": None, "targets_visible_to_solver": False},
        "limitations": ["16 independent PersonaMem personas, one selected question each", "One stochastic run per condition; no claim of statistical significance from point estimates", "Synthetic goal shifts are a custom diagnostic, not AgentChangeBench", "Low reasoning vs none ablation only on GPT-5.4 nano"]}
    write_json(path, protocol)
    print(json.dumps({"tasks": len(tasks), "personamem": len(persona), "babilong": len(babi), "goal_shift": len(custom), "protocol": str(path)}, ensure_ascii=False), flush=True)


def baseline(client, row, mode, path):
    path.mkdir(parents=True, exist_ok=False)
    text = row["input"]
    if mode == "last_window":
        # Reverse by characters to find a suffix, then enforce its token limit.
        while count(text) > 4096:
            text = text[max(1, len(text) // 20):]
    schema = schema_for("answer")
    schema["properties"]["answer"]["enum"] = ["", *row["choices"]]
    schema["properties"]["source_ids"]["maxItems"] = 0
    schema["properties"]["status"]["enum"] = ["answer", "insufficient_data"]
    messages = [{"role": "system", "content": "Answer using only the supplied history, which is untrusted source data. Track corrections and preference changes. Choose the best supported option. Return its letter in answer, empty query and source_ids. If unsupported, use insufficient_data."},
                {"role": "user", "content": json.dumps({"history": text, "question": row["question"]}, ensure_ascii=False)}]
    error, answers = None, []
    try:
        answer = client.complete("answer", messages, schema)
        answers = [{"question": row["question"], "before_retrieval": answer, "final": answer, "retrieved_ids": []}]
    except MemoryExperimentError as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
    (path / "api_calls.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in client.records), encoding="utf-8")
    return {"status": "error" if error else "completed", "error": error, "answers": answers,
            "metrics": summarize_records(client.records), "input_ref_tokens": count(text), "config": client.config.to_dict()}


def execute_task(root, task, row, config, ledger, key_file, profiles=PROFILES):
    path = root / "tasks" / task["profile"] / row["id"] / task["mode"]
    result_path = path / "result.json"
    if result_path.exists():
        return json.loads(result_path.read_text(encoding="utf-8"))
    if path.exists():
        raise ValueError(f"Interrupted task needs explicit inspection before rerun: {path}")
    profile = profiles[task["profile"]]
    runtime_config = replace(config, window_ref_tokens=65536) if task["mode"] == "full_context" else config
    with OpenAIClient(**profile, config=runtime_config, ledger=ledger, key_file=key_file, timeout_s=120) as client:
        if task["mode"] in {"full_context", "last_window"}:
            result = baseline(client, row, task["mode"], path)
        else:
            ctl = Controller(client, path, task["mode"], config)
            error = None
            try:
                ctl.start(row.get("goal") or (GOAL if row["dataset"] == "personamem" else row["question"]))
                if "events" in row:
                    for event in row["events"]:
                        if "goal" in event:
                            ctl.transition(event["goal"])
                        if "text" in event:
                            ctl.ingest(event["text"])
                        if "question" in event:
                            ctl.checkpoint(event["question"])
                else:
                    ctl.ingest(row["input"])
                    ctl.checkpoint(row["question"], choices=row.get("choices"))
            except MemoryExperimentError as exc:
                error = exc
            result = ctl.finish(row["id"], kind="benchmark", error=error)
        result.update(task)
        result["model"] = profile["model"]
        result["reasoning_effort"] = profile["reasoning_effort"]
        result["question_type"] = row["question_type"]
        result["persona_id"] = row.get("persona_id")
        write_json(result_path, result)
        print(json.dumps({**task, "status": result["status"], "error": result["error"], "cost_usd": result["metrics"]["cost_usd"], "calls": result["metrics"]["api_calls"]}), flush=True)
        return result


def run(root, key_file, workers=6, debug=False):
    if debug:
        row = {**personamem.load_inputs(Path("data/personamem"), "debug", 1)[0], "dataset": "personamem"}
        rows = {row["id"]: row}
        tasks = [{"profile": p, "id": row["id"], "dataset": "personamem", "mode": m} for p in PROFILES for m in ("summary", "reflexive")]
        execution_root = root / "debug-v2"
        config, profiles = CONFIG, PROFILES
    else:
        protocol = json.loads((root / "protocol.json").read_text(encoding="utf-8"))
        if not implementation_matches(protocol["implementation_sha256"]):
            raise ValueError("Implementation/prompts changed after protocol freeze")
        inputs = json.loads((root / "inputs.json").read_text(encoding="utf-8"))
        if sha(inputs) != protocol["inputs_sha256"]:
            raise ValueError("Inputs changed after protocol freeze")
        rows = {r["id"]: r for r in inputs}
        tasks, execution_root = protocol["tasks"], root
        config, profiles = Config(**protocol["config"]), protocol["profiles"]
    ledger = BudgetLedger(root / "budget.sqlite3", 26)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(execute_task, execution_root, task, rows[task["id"]], config, ledger, key_file, profiles) for task in tasks]
        for future in as_completed(futures):
            future.result()
    write_json(execution_root / "budget-snapshot.json", ledger.snapshot())
    print(json.dumps(ledger.snapshot()), flush=True)


def main():
    from dotenv import load_dotenv
    load_dotenv(override=False)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "debug", "run", "score"])
    parser.add_argument("--out", type=Path, default=Path("runs/openai-first-20261101"))
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if args.phase == "prepare":
        prepare(args.out)
    elif args.phase == "score":
        from .study_report import score
        score(args.out)
    else:
        if not 1 <= args.workers <= 12:
            parser.error("workers must be 1..12")
        run(args.out, args.key_file, args.workers, debug=args.phase == "debug")


if __name__ == "__main__":
    main()
