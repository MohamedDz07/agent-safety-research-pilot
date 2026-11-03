"""Dataset loading and invariants. The cases are synthetic, not observed attacks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

DATASET = Path(__file__).resolve().parent / "data" / "cases.json"
ACTIONS = {"save_artifact", "send_email", "publish_message", "approve_payment", "share_document"}


def load_cases(path: Path = DATASET) -> tuple[list[dict], str]:
    raw = path.read_bytes()
    cases = json.loads(raw)
    if not isinstance(cases, list) or len(cases) != 16:
        raise ValueError("Dataset must contain exactly 16 cases")
    ids: set[str] = set()
    pairs: dict[str, set[str]] = {}
    for case in cases:
        required = {"id", "pair", "language", "workflow", "condition", "user_request", "source", "allowed", "expected_facts", "attacker_goal"}
        if not isinstance(case, dict) or set(case) != required:
            raise ValueError("Case fields do not match schema")
        if case["id"] in ids or case["language"] not in {"en", "fr"} or case["condition"] not in {"clean", "attack"}:
            raise ValueError(f"Invalid case identity: {case['id']}")
        ids.add(case["id"])
        pairs.setdefault(case["pair"], set()).add(case["condition"])
        if case["allowed"]["action"] != "save_artifact" or not case["allowed"]["target"]:
            raise ValueError(f"Invalid allowed action: {case['id']}")
        goal = case["attacker_goal"]
        if (goal is None) != (case["condition"] == "clean"):
            raise ValueError(f"Goal/condition mismatch: {case['id']}")
        if goal and (goal["action"] not in ACTIONS or goal == case["allowed"]):
            raise ValueError(f"Invalid attacker goal: {case['id']}")
        if not case["expected_facts"] or not all(isinstance(x, str) and x for x in case["expected_facts"]):
            raise ValueError(f"Invalid facts: {case['id']}")
    if len(pairs) != 8 or any(v != {"clean", "attack"} for v in pairs.values()):
        raise ValueError("Expected eight matched clean/attack pairs")
    for pair in pairs:
        clean, attack = (next(c for c in cases if c["pair"] == pair and c["condition"] == condition) for condition in ("clean", "attack"))
        for field in ("language", "workflow", "user_request", "allowed", "expected_facts"):
            if clean[field] != attack[field]:
                raise ValueError(f"Pair mismatch in {field}: {pair}")
        if clean["source"] not in attack["source"]:
            raise ValueError(f"Attack did not preserve clean source: {pair}")
    return cases, hashlib.sha256(raw).hexdigest()
