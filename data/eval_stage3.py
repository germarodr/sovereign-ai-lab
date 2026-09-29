#!/usr/bin/env python3
"""
eval_stage3.py - run SK-LoRA Stage 3 tests for the LatamPay lab.

Stage 3 uses a Llama-3.1-8B model with Security Knowledge LoRA merged into the
weights, plus the same CK-RAG path used in Phase 2 and Stage 4.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from eval_phase12 import (
    DEFAULT_CK_PERSIST,
    DEFAULT_COLLECTION,
    DEFAULT_EMBED_MODEL,
    DEFAULT_OLLAMA_URL,
    heuristic_score,
    load_retriever,
    load_scenarios,
    ollama_generate,
    retrieve_ck,
    scenario_prompt,
)
from eval_stage4 import STAGE4_SYSTEM

DEFAULT_STAGE3_MODEL = "llama3.1-8b-sk-lora"

# Phase 3 uses the identical shared CK prompt (same as Phases 2 and 4); only the model differs.
STAGE3_SYSTEM = STAGE4_SYSTEM


def write_stage3_outputs(records: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "stage3_results.jsonl"
    csv_path = out_dir / "stage3_results.csv"
    md_path = out_dir / "stage3_summary.md"

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    csv_fields = [
        "timestamp",
        "stage",
        "model",
        "repeat",
        "scenario_id",
        "archetype",
        "expected_cwe",
        "expected_applicability",
        "expected_priority",
        "elapsed_seconds",
        "sk_hit",
        "cwe_hit",
        "weakness_name_hit",
        "applicability_hit",
        "priority_hit",
        "ck_term_hit",
        "retrieved_sources",
        "answer_excerpt",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for record in records:
            score = record["heuristic_score"]
            writer.writerow({
                "timestamp": record["timestamp"],
                "stage": record["stage"],
                "model": record["model"],
                "repeat": record["repeat"],
                "scenario_id": record["scenario_id"],
                "archetype": record["archetype"],
                "expected_cwe": score["expected_cwe"],
                "expected_applicability": score["expected_applicability"],
                "expected_priority": score["expected_priority"],
                "elapsed_seconds": f"{record['elapsed_seconds']:.2f}",
                "sk_hit": score["sk_hit"],
                "cwe_hit": score["cwe_hit"],
                "weakness_name_hit": score["weakness_name_hit"],
                "applicability_hit": score["applicability_hit"],
                "priority_hit": score["priority_hit"],
                "ck_term_hit": score["ck_term_hit"],
                "retrieved_sources": ";".join(item["source"] for item in record.get("retrieved", [])),
                "answer_excerpt": record["answer"].replace("\n", " ")[:500],
            })

    md_path.write_text(summarize_stage3(records), encoding="utf-8")
    print(f"Wrote {jsonl_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")


def summarize_stage3(records: list[dict[str, Any]]) -> str:
    total = len(records)
    sk_hits = sum(1 for record in records if record["heuristic_score"]["sk_hit"])
    ck_hits = sum(1 for record in records if record["heuristic_score"]["ck_term_hit"])
    app_hits = sum(1 for record in records if record["heuristic_score"]["applicability_hit"])
    prio_hits = sum(1 for record in records if record["heuristic_score"]["priority_hit"])
    avg_elapsed = sum(record["elapsed_seconds"] for record in records) / total if total else 0
    model = records[0]["model"] if records else "unknown"

    lines = [
        "# Stage 3 Evaluation Summary",
        "",
        f"Model: `{model}`",
        "",
        "Heuristic scores are review aids, not authoritative grading.",
        "",
        "## Metrics",
        "",
        f"- Runs: {total}",
        f"- SK heuristic hits: {sk_hits}/{total}",
        f"- CK grounding hits: {ck_hits}/{total}",
        f"- Applicability heuristic hits: {app_hits}/{total}",
        f"- Priority heuristic hits: {prio_hits}/{total}",
        f"- Average elapsed seconds: {avg_elapsed:.2f}",
        "",
        "## Review Queue",
        "",
    ]

    failed_records = 0
    for record in records:
        score = record["heuristic_score"]
        if not score["sk_hit"] or not score["applicability_hit"] or not score["priority_hit"]:
            failed_records += 1
            lines.append(
                f"- {record['scenario_id']} repeat={record['repeat']}: "
                f"sk={score['sk_hit']} applicability={score['applicability_hit']} priority={score['priority_hit']}"
            )

    if not records:
        lines.append("No records generated.")
    elif failed_records == 0:
        lines.append("No failed heuristic checks.")

    lines.extend([
        "",
        "## Interpretation",
        "",
        "Compare these results against Phase 2 and Stage 4. Stage 3 is successful when targeted QLoRA-style tuning improves SK on the stable SK-gap scenarios while preserving CK grounding and acceptable latency.",
        "",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage 3 SK-LoRA + CK-RAG LatamPay tests.")
    parser.add_argument("--scenarios", default="scenarios.json", help="Path to scenarios.json")
    parser.add_argument("--out", default="./results/phase3", help="Output directory")
    parser.add_argument("--model", default=DEFAULT_STAGE3_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--ck-persist", default=DEFAULT_CK_PERSIST)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--embed-model", default=DEFAULT_EMBED_MODEL)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--scenario-ids", nargs="*", help="Optional scenario IDs to run")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--k", type=int, default=2, help="Scenario-specific CK passages to retrieve")
    parser.add_argument("--policy-k", type=int, default=2, help="Policy/SLA CK passages to retrieve")
    parser.add_argument("--num-predict", type=int, default=180)
    parser.add_argument("--num-thread", type=int, default=16)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=300)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenarios = load_scenarios(Path(args.scenarios))
    if args.scenario_ids:
        wanted = set(args.scenario_ids)
        scenarios = [scenario for scenario in scenarios if scenario["id"] in wanted]

    embedder, collection = load_retriever(args.ck_persist, args.collection, args.embed_model, args.device)
    records: list[dict[str, Any]] = []
    timestamp = datetime.now(timezone.utc).isoformat()

    for repeat in range(1, args.repeats + 1):
        for scenario in scenarios:
            ck_context, retrieved = retrieve_ck(scenario, embedder, collection, args.k, args.policy_k)
            prompt = scenario_prompt(scenario, ck_context)
            print(f"[phase3] repeat={repeat} scenario={scenario['id']} model={args.model}", flush=True)
            answer, elapsed = ollama_generate(
                model=args.model,
                system=STAGE3_SYSTEM,
                prompt=prompt,
                ollama_url=args.ollama_url,
                num_predict=args.num_predict,
                num_thread=args.num_thread,
                temperature=args.temperature,
                timeout=args.timeout,
            )
            score = heuristic_score("phase3", scenario, answer)
            records.append({
                "timestamp": timestamp,
                "stage": "phase3",
                "model": args.model,
                "repeat": repeat,
                "scenario_id": scenario["id"],
                "archetype": scenario.get("archetype"),
                "prompt": prompt,
                "retrieved": retrieved,
                "answer": answer,
                "elapsed_seconds": elapsed,
                "heuristic_score": score,
                "expected": {
                    "cwe": scenario.get("expected_cwe"),
                    "weakness_name": scenario.get("weakness_name"),
                    "applicability": scenario.get("expected_applicability"),
                    "priority": scenario.get("expected_priority"),
                    "action": scenario.get("expected_action"),
                },
            })

    write_stage3_outputs(records, Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
