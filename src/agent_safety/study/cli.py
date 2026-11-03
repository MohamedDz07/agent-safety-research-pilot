"""Commands for the authorization-boundary study."""
from __future__ import annotations

import argparse
import json
import os
import platform
import random
from datetime import datetime, timezone
from pathlib import Path

from agent_safety.adapters import AnthropicAdapter

from .controls import VARIANTS
from .dataset import load_cases
from .runner import FixtureAdapter, SYSTEM, TOOLS, run_episode
from .scoring import replay_first_proposals, summarize


def _json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _selection(cases: list[dict], split: str, variants: list[str], repeats: int, seed: int) -> list[tuple[dict, str, int]]:
    if repeats < 1 or repeats > 20 or len(set(variants)) != len(variants) or any(v not in VARIANTS for v in variants):
        raise ValueError("Repeats must be 1–20 and variants must be unique known names")
    jobs = [(case, variant, repeat) for case in cases if split == "all" or case["split"] == split
            for variant in variants for repeat in range(repeats)]
    random.Random(seed).shuffle(jobs)
    return jobs


def _prepare(output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)


def _experiment(args: argparse.Namespace, fixture: bool) -> None:
    cases, digest = load_cases()
    if not fixture and not os.environ.get("ANTHROPIC_API_KEY"):
        raise ValueError("Set ANTHROPIC_API_KEY in your local environment before a model run")
    jobs = _selection(cases, args.split, args.variants, args.repeats, args.seed)
    model_adapter = None if fixture else AnthropicAdapter(
        args.model, max_tokens=args.max_tokens, temperature=args.temperature, system=SYSTEM, tools=TOOLS)
    output = Path(args.output)
    _prepare(output)
    manifest = {"study": "authorization-boundary-48-v1", "run_type": "fixture" if fixture else "model",
                "dataset_sha256": digest, "created_utc": datetime.now(timezone.utc).isoformat(),
                "python": platform.python_version(), "model": "fixture-not-a-model" if fixture else args.model,
                "sdk_version": "none" if fixture else model_adapter.sdk_version, "split": args.split, "variants": args.variants,
                "repeats": args.repeats, "seed": args.seed, "max_turns": args.max_turns,
                "max_tokens": None if fixture else args.max_tokens,
                "temperature": None if fixture else args.temperature,
                "planned_episodes": len(jobs), "system_prompt": SYSTEM, "tools": TOOLS,
                "warning": "Fixture is scripted software verification, not model evidence" if fixture else None}
    _json(output / "manifest.json", manifest)
    episodes: list[dict] = []
    with (output / "episodes.jsonl").open("w", encoding="utf-8") as handle:
        for number, (case, variant, repeat) in enumerate(jobs, 1):
            adapter = FixtureAdapter(case) if fixture else model_adapter
            episode = run_episode(case, variant, adapter, repeat=repeat, max_turns=args.max_turns)
            episodes.append(episode)
            handle.write(json.dumps(episode, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"{number}/{len(jobs)} {case['id']} {variant} repeat={repeat} {episode['status']}", flush=True)
    _json(output / "manifest.json", manifest)
    _json(output / "summary.json", summarize(cases, episodes))
    _json(output / "first_proposal_replay.json", replay_first_proposals(cases, episodes))
    print(f"Saved {len(episodes)} episodes to {output}")


def _load_experiment(input_dir: Path) -> tuple[list[dict], list[dict], dict]:
    cases, digest = load_cases()
    manifest = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest["study"] != "authorization-boundary-48-v1" or manifest["dataset_sha256"] != digest:
        raise ValueError("Study version or dataset hash mismatch")
    episodes = [json.loads(line) for line in (input_dir / "episodes.jsonl").read_text(encoding="utf-8").splitlines() if line]
    if len(episodes) > manifest["planned_episodes"]:
        raise ValueError("More episodes than planned")
    return cases, episodes, manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="agent-safety-study")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="Validate the frozen study dataset")
    for command in ("demo", "run"):
        p = sub.add_parser(command, help="Run scripted fixture" if command == "demo" else "Run a real Anthropic model")
        p.add_argument("--output", required=True)
        p.add_argument("--split", choices=["all", "dev", "holdout"], default="all")
        p.add_argument("--variants", nargs="+", choices=VARIANTS, default=list(VARIANTS))
        p.add_argument("--repeats", type=int, default=1)
        p.add_argument("--seed", type=int, default=1307)
        p.add_argument("--max-turns", type=int, default=6)
        if command == "run":
            p.add_argument("--model", required=True)
            p.add_argument("--max-tokens", type=int, default=1024)
            p.add_argument("--temperature", type=float)
    p = sub.add_parser("score", help="Rescore recorded episodes")
    p.add_argument("--input", required=True)
    p = sub.add_parser("replay", help="Replay the first baseline proposal through all gates")
    p.add_argument("--input", required=True)
    args = parser.parse_args(argv)
    if args.command == "validate":
        cases, digest = load_cases()
        print(f"Validated {len(cases)} cases; SHA-256 {digest}")
    elif args.command in ("demo", "run"):
        if args.max_turns < 1 or (args.command == "run" and args.max_tokens < 1):
            parser.error("Turn and token caps must be positive")
        _experiment(args, fixture=args.command == "demo")
    else:
        input_dir = Path(args.input)
        cases, episodes, manifest = _load_experiment(input_dir)
        result = summarize(cases, episodes) if args.command == "score" else replay_first_proposals(cases, episodes)
        filename = "summary.json" if args.command == "score" else "first_proposal_replay.json"
        _json(input_dir / filename, result)
        print(f"{manifest['run_type']}: rescored {len(episodes)}/{manifest['planned_episodes']} episodes → {input_dir / filename}")


if __name__ == "__main__":
    main()
