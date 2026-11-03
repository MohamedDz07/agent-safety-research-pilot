"""Frozen 48-case dataset and preflight checks."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

DATASET = Path(__file__).parent / "data" / "cases.json"
ACTIONS = {"save_artifact", "send_email", "publish_report", "approve_payment", "share_document"}
CONDITIONS = {"clean", "benign_quote", "attack"}


def load_cases(path: Path = DATASET) -> tuple[list[dict], str]:
    raw = path.read_bytes()
    cases = json.loads(raw)
    if not isinstance(cases, list) or len(cases) != 48:
        raise ValueError("Study dataset must contain exactly 48 cases")
    identifiers = set()
    groups: dict[str, list[dict]] = defaultdict(list)
    for case in cases:
        required = {"id", "base_id", "language", "workflow", "mode", "split", "condition",
                    "user_request", "source", "grant", "attacker_goal", "expected_facts"}
        if not isinstance(case, dict) or set(case) != required or case["id"] in identifiers:
            raise ValueError("Invalid case fields or duplicate ID")
        identifiers.add(case["id"])
        groups[case["base_id"]].append(case)
        if case["language"] not in {"en", "fr"} or case["condition"] not in CONDITIONS or case["split"] not in {"dev", "holdout"}:
            raise ValueError(f"Invalid case labels: {case['id']}")
        if case["mode"] not in {"draft", "authorized_sensitive"}:
            raise ValueError(f"Invalid mode: {case['id']}")
        grant = case["grant"]
        goal = case["attacker_goal"]
        if grant.get("origin") != "user_request" or grant.get("action") not in ACTIONS or not grant.get("target"):
            raise ValueError(f"Invalid trusted grant: {case['id']}")
        if goal.get("action") not in ACTIONS or not goal.get("target") or (goal["action"], goal["target"]) == (grant["action"], grant["target"]):
            raise ValueError(f"Invalid attacker goal: {case['id']}")
        source = case["source"]
        if source.get("origin") != "untrusted_tool_result" or not source.get("source_id") or not source.get("body"):
            raise ValueError(f"Invalid source provenance: {case['id']}")
        if not case["expected_facts"] or not all(isinstance(f, str) and f for f in case["expected_facts"]):
            raise ValueError(f"Invalid facts: {case['id']}")
    if len(groups) != 16:
        raise ValueError("Expected 16 base tasks")
    for base_id, trio in groups.items():
        if {c["condition"] for c in trio} != CONDITIONS or len(trio) != 3:
            raise ValueError(f"Missing matched conditions: {base_id}")
        clean = next(c for c in trio if c["condition"] == "clean")
        for case in trio:
            for field in ("base_id", "language", "workflow", "mode", "split", "user_request", "grant", "attacker_goal", "expected_facts"):
                if case[field] != clean[field]:
                    raise ValueError(f"Pair mismatch: {base_id} {field}")
            if clean["source"]["body"] not in case["source"]["body"]:
                raise ValueError(f"Source facts changed: {base_id}")
    counts = Counter((c["split"], c["language"]) for c in cases)
    if any(counts[(split, language)] != 12 for split in ("dev", "holdout") for language in ("en", "fr")):
        raise ValueError("Split/language balance is invalid")
    return cases, hashlib.sha256(raw).hexdigest()
