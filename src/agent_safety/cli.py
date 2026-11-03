"""Command-line entry point. Actual model calls require an explicit API key in the environment."""
from __future__ import annotations

import argparse
import json
import os
import platform
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .adapters import SYSTEM, AnthropicAdapter, FixtureAdapter
from .cases import load_cases
from .engine import VARIANTS, run_episode
from .scoring import summarize


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(args: argparse.Namespace, fixture: bool) -> int:
    cases, digest = load_cases()
    if args.max_turns < 1 or (not fixture and (args.max_tokens < 1 or (args.temperature is not None and not 0 <= args.temperature <= 1))):
        print("--max-turns and --max-tokens must be positive; --temperature must be 0 through 1.", file=sys.stderr)
        return 2
    if not fixture and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is required for model experiments.", file=sys.stderr)
        return 2
    if not fixture and not args.model:
        print("--model must name an exact Claude model ID.", file=sys.stderr)
        return 2
    variants = args.variants.split(",")
    if not variants or len(set(variants)) != len(variants) or any(v not in VARIANTS for v in variants):
        print(f"--variants must be a comma-separated subset of {','.join(VARIANTS)}", file=sys.stderr)
        return 2
    if args.output.exists() and any(args.output.iterdir()):
        print("Output directory must be empty to prevent overwriting experiment records.", file=sys.stderr)
        return 2
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        adapter = None if fixture else AnthropicAdapter(args.model, args.max_tokens, args.temperature)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    manifest = {"pilot_version": __version__, "dataset_sha256": digest,
                "dataset_cases": len(cases), "created_utc": datetime.now(timezone.utc).isoformat(),
                "backend": "deterministic_fixture" if fixture else "anthropic_api",
                "model": "fixture-not-a-model" if fixture else args.model,
                "sdk_version": "none" if fixture else adapter.sdk_version,
                "python": platform.python_version(), "variants": variants, "seed": args.seed,
                "max_turns": args.max_turns, "max_tokens": None if fixture else args.max_tokens,
                "temperature": None if fixture else args.temperature,
                "system_prompt": SYSTEM,
                "note": "All submit_action effects are simulated. No external send/share/payment/publish calls exist."}
    write_json(args.output / "manifest.json", manifest)
    jobs = [(case, variant) for case in cases for variant in variants]
    random.Random(args.seed).shuffle(jobs)
    episodes = []
    with (args.output / "episodes.jsonl").open("w", encoding="utf-8") as stream:
        for index, (case, variant) in enumerate(jobs, 1):
            current_adapter = FixtureAdapter(case) if fixture else adapter
            try:
                episode = run_episode(case, variant, current_adapter, args.max_turns)
            except Exception as exc:
                episode = {"case_id": case["id"], "pair": case["pair"], "language": case["language"],
                           "workflow": case["workflow"], "condition": case["condition"], "variant": variant,
                           "status": f"error:{type(exc).__name__}", "turns": 0, "usage": {}, "trace": []}
            episodes.append(episode)
            stream.write(json.dumps(episode, ensure_ascii=False) + "\n")
            stream.flush()
            print(f"{index}/{len(jobs)} {case['id']} {variant}: {episode['status']}", file=sys.stderr)
    write_json(args.output / "summary.json", summarize(cases, episodes))
    return 0 if all(e["status"] == "complete" for e in episodes) else 1


def score(args: argparse.Namespace) -> int:
    cases, digest = load_cases()
    manifest = json.loads((args.input / "manifest.json").read_text(encoding="utf-8"))
    if manifest["dataset_sha256"] != digest:
        print("Dataset hash differs from the run manifest; refusing to rescore.", file=sys.stderr)
        return 2
    episodes = [json.loads(line) for line in (args.input / "episodes.jsonl").read_text(encoding="utf-8").splitlines() if line]
    report = summarize(cases, episodes)
    write_json(args.input / "summary.json", report)
    print(json.dumps(report["variants"], ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-safety")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="Validate the 16 paired cases and print their SHA-256")
    for name in ("demo", "run"):
        p = sub.add_parser(name, help="Run a deterministic fixture" if name == "demo" else "Run actual Anthropic model calls")
        p.add_argument("--output", type=Path, required=True)
        p.add_argument("--variants", default=",".join(VARIANTS))
        p.add_argument("--seed", type=int, default=42)
        p.add_argument("--max-turns", type=int, default=6)
        if name == "run":
            p.add_argument("--model", required=True)
            p.add_argument("--max-tokens", type=int, default=1024)
            p.add_argument("--temperature", type=float, default=None)
    p = sub.add_parser("score", help="Rescore a recorded run after checking its dataset hash")
    p.add_argument("--input", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "validate":
        cases, digest = load_cases()
        print(f"{len(cases)} cases; SHA-256 {digest}")
        return 0
    if args.command == "score":
        return score(args)
    return run(args, fixture=args.command == "demo")


if __name__ == "__main__":
    raise SystemExit(main())
