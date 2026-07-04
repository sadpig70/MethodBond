"""CLI triplet: sample / evaluate / report."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .engine import evaluate, hash_artifact
from .ledger import append_entry
from .report import render


DEFAULT_LEDGER = "methodbond_ledger.jsonl"


def _sample_artifact() -> dict:
    return {
        "id": "sample-method-v1",
        "license": {
            "transfer_type": "permissive",
            "source_domain": "academia",
            "target_industry": "general",
            "revenue_share_pct": 0.0,
        },
        "provenances": [
            {
                "input_hash": "sha256:abc123",
                "output_hash": "sha256:matched",
                "build_command": "python reproduce.py",
                "builder_id": "lab-a",
            },
            {
                "input_hash": "sha256:abc123",
                "output_hash": "sha256:matched",
                "build_command": "python reproduce.py",
                "builder_id": "lab-b",
            },
        ],
        "baseline_policy": {
            "rules": {
                "max_inference_latency_ms": 100,
                "requires_human_in_the_loop": False,
            }
        },
        "candidate_policy": {
            "rules": {
                "max_inference_latency_ms": 100,
                "requires_human_in_the_loop": False,
            }
        },
    }


def _write_sample(args: argparse.Namespace) -> int:
    path = args.output or "sample.json"
    artifact = _sample_artifact()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2)
    print(f"Sample artifact written to {path}")
    print(f"Artifact fingerprint: {hash_artifact(artifact)}")
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    with open(args.input, "r", encoding="utf-8") as f:
        artifact = json.load(f)

    result = evaluate(artifact)

    ledger_path = args.ledger or DEFAULT_LEDGER
    append_entry(
        ledger_path,
        artifact_id=result["artifact_id"],
        verdict=result["verdict"],
        details=result["details"],
        now=args.now,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"verdict={result['verdict']} artifact_id={result['artifact_id']}")

    return 0 if result["verdict"] != "rejected" else 1


def _report(args: argparse.Namespace) -> int:
    with open(args.input, "r", encoding="utf-8") as f:
        artifact = json.load(f)

    result = evaluate(artifact)
    md = render(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Report written to {args.output}")
    else:
        print(md)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="MethodBond",
        description="Method-publishing trust-bundle gate: license + reproducibility + certification.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sample = sub.add_parser("sample", help="Emit a valid sample artifact descriptor.")
    sample.add_argument("-o", "--output", default="sample.json", help="Output file path.")
    sample.set_defaults(func=_write_sample)

    ev = sub.add_parser("evaluate", help="Evaluate an artifact descriptor.")
    ev.add_argument("input", help="Path to artifact descriptor JSON.")
    ev.add_argument("-l", "--ledger", default=None, help="Ledger file path.")
    ev.add_argument("--now", default=None, help="ISO timestamp override.")
    ev.add_argument("--json", action="store_true", help="Emit full JSON output.")
    ev.set_defaults(func=_evaluate)

    rep = sub.add_parser("report", help="Render a Markdown evaluation report.")
    rep.add_argument("input", help="Path to artifact descriptor JSON.")
    rep.add_argument("-o", "--output", default=None, help="Output file path.")
    rep.set_defaults(func=_report)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
