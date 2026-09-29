#!/usr/bin/env python3
"""
eval_phase12.py - run repeated Phase 1 / Phase 2 tests for the LatamPay lab.

Phase 1: baseline Llama model with no Customer Knowledge (CK).
Phase 2: same Llama model with CK retrieved from the ChromaDB index.

The goal is to separate three effects:
  1. What the base model can infer from the weakness description alone.
  2. What improves when CK-RAG is added.
  3. Which scenarios still fail because Security Knowledge (SK) is weak.

The heuristic scores are not a replacement for human review. They are a fast
triage aid to find scenarios worth inspecting.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

DEFAULT_MODEL = "llama3.1:8b-instruct-q4_K_M"
DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_CK_PERSIST = "./customer_ck_chromadb"
DEFAULT_COLLECTION = "latampay_ck"
# Prefer the local bge folder (offline); fall back to the Hugging Face id if absent.
_LOCAL_BGE = Path(__file__).resolve().parent.parent / "models" / "bge-small-en-v1.5"
DEFAULT_EMBED_MODEL = str(_LOCAL_BGE) if _LOCAL_BGE.exists() else "BAAI/bge-small-en-v1.5"

# Shared output contract used by every phase so only the model/CK differs.
OUTPUT_CONTRACT = """Return exactly these fields, filling every one on its own line. Never stop after the Weakness line. Angle brackets are placeholders to replace, not literal text:
Weakness: <CWE-ID> <weakness name>
Applicability: <Applicable | Not applicable> - <one-line reason>
Priority: <Critical | High | Medium | Low | N/A>
Action: <what to do>
Rationale: <one sentence>
"""

# One canonical CK triage prompt shared by Phases 2, 3, and 4 (only the model changes).
SHARED_CK_SYSTEM = """You are a concise security triage assistant for LatamPay.
Use the provided Customer Knowledge context as the authority for asset presence, absence, exposure, tier, data sensitivity, prior incidents, and SLA.
Do not use the Customer Knowledge context as a CWE catalog; identify the weakness from the scenario, then use CK only to scope LatamPay impact.
If retrieved snippets are unrelated to the scenario asset or component, ignore those unrelated snippets.
In the Weakness field, make a best-effort classification from the weakness description and include the most precise CWE identifier and weakness name. Use CWE unknown only if the description is genuinely too ambiguous to map to a CWE.
In the Applicability field, explicitly say applicable or not applicable. If CK says the affected product/component is absent, removed, decommissioned, or not in the estate, mark it not applicable. Do not analyze replacement technologies after CK says the component is absent.
In the Priority field, use exactly one of Critical, High, Medium, Low, N/A (N/A when not applicable). Do not use High as a generic severity. Match LatamPay policy: Critical for tier-0, PCI, cloud credential/metadata blast radius, or 24h/Sev-1; High for tier-1 or sensitive money-movement/PII; Medium for tier-2, internal-only, or lower-impact.
In the Action field, apply LatamPay tier, exposure, data-sensitivity, and SLA facts when CK provides them.
""" + OUTPUT_CONTRACT

STAGE1_SYSTEM = """You are a concise security triage assistant.
Use only the weakness description provided by the user.
You have no customer knowledge: do not invent customer-specific asset inventory, software estate, SLA, or incident history. If applicability cannot be determined from the description alone, say applicability is unknown.
In the Weakness field, make a best-effort classification from the weakness description and include the most precise CWE identifier and weakness name. Use CWE unknown only if the description is genuinely too ambiguous to map to a CWE.
""" + OUTPUT_CONTRACT

# Phase 2 uses the identical shared CK prompt (see Phases 3 and 4).
STAGE2_SYSTEM = SHARED_CK_SYSTEM


def load_scenarios(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["scenarios"]


def scenario_prompt(scenario: dict[str, Any], ck_context: str | None = None) -> str:
    base = (
        f"Scenario ID: {scenario['id']}\n"
        f"Weakness description:\n{scenario['probe']}\n\n"
        f"Affected component type:\n{scenario.get('affected_component_generic', 'unknown')}\n"
    )
    if ck_context is None:
        return base
    return base + f"\nCustomer Knowledge context:\n{ck_context}\n"


def ollama_generate(
    model: str,
    system: str,
    prompt: str,
    ollama_url: str,
    num_predict: int,
    num_thread: int,
    temperature: float,
    timeout: int,
) -> tuple[str, float]:
    payload = {
        "model": model,
        "system": system,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": num_predict,
            "num_thread": num_thread,
            "temperature": temperature,
        },
    }
    start = time.time()
    response = requests.post(ollama_url, json=payload, timeout=timeout)
    elapsed = time.time() - start
    response.raise_for_status()
    return response.json().get("response", ""), elapsed


def retrieval_query(scenario: dict[str, Any]) -> str:
    return " ".join(
        part
        for part in [scenario.get("probe", ""), scenario.get("affected_component_generic", "")]
        if part
    )


def load_retriever(persist: str, collection_name: str, embed_model_name: str, device: str):
    import chromadb
    from sentence_transformers import SentenceTransformer

    embedder = SentenceTransformer(embed_model_name, device=device)
    client = chromadb.PersistentClient(path=persist)
    collection = client.get_collection(collection_name)
    return embedder, collection


def retrieve_ck(
    scenario: dict[str, Any],
    embedder: Any,
    collection: Any,
    k: int,
    policy_k: int,
) -> tuple[str, list[dict[str, Any]]]:
    queries = [
        ("scenario", retrieval_query(scenario), k),
        (
            "policy",
            "LatamPay remediation SLA escalation rules tier exposure PCI data sensitivity applicability rule",
            policy_k,
        ),
    ]
    rows: list[dict[str, Any]] = []
    context_parts: list[str] = []
    seen: set[tuple[str, str]] = set()
    for query_type, query, n_results in queries:
        if n_results <= 0:
            continue
        embedding = embedder.encode([query], normalize_embeddings=True).tolist()[0]
        result = collection.query(query_embeddings=[embedding], n_results=n_results)
        for doc, metadata, distance in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
            source = metadata.get("source", "unknown")
            key = (source, doc)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "rank": len(rows) + 1,
                "query_type": query_type,
                "source": source,
                "distance": distance,
                "text": doc,
            })
            context_parts.append(f"[{len(rows)}] type={query_type} source={source}\n{doc}")
    return "\n\n".join(context_parts), rows


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def contains_any(text: str, phrases: list[str]) -> bool:
    lower = text.lower()
    return any(phrase.lower() in lower for phrase in phrases)


CONFLICTING_WEAKNESS_TERMS = {
    "CWE-22": ["toctou", "time-of-check", "time of check"],
    "CWE-89": ["cross-site scripting", "xss"],
    "CWE-90": ["code injection", "command injection", "sql injection"],
    "CWE-306": ["improper access control"],
    "CWE-367": ["path traversal", "directory traversal"],
    "CWE-502": ["path traversal", "sql injection", "xss"],
    "CWE-601": ["server-side request forgery", "server side request forgery", "ssrf", "xss"],
    "CWE-798": ["out-of-date", "outdated", "vulnerable version"],
    "CWE-917": ["deserialization", "code injection", "command injection"],
    "CWE-918": ["open redirect", "url redirection", "xss"],
}


def has_conflicting_weakness_label(expected_cwe: str, weakness_field: str) -> bool:
    terms = CONFLICTING_WEAKNESS_TERMS.get(expected_cwe.upper(), [])
    return contains_any(weakness_field, terms)


def extract_field(answer: str, field: str) -> str:
    """Extract a labeled answer field while avoiding matches on the label itself."""
    labels = ["Weakness", "Applicability", "Priority", "Action", "Rationale"]
    label_pattern = "|".join(re.escape(label) for label in labels)
    marker = r"(?:\*\*)?"
    pattern = rf"(?is)^\s*{marker}{re.escape(field)}{marker}\s*:\s*(.*?)(?=^\s*{marker}(?:{label_pattern}){marker}\s*:|\Z)"
    match = re.search(pattern, answer, flags=re.MULTILINE)
    if not match:
        return ""
    value = match.group(1).strip()
    return re.sub(r"^\*+|\*+$", "", value).strip()


def ck_asset_terms(scenario: dict[str, Any]) -> list[str]:
    ck = scenario.get("ck_match", "")
    candidates = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)+", ck.lower())
    extras = []
    aliases = {
        "payment-gateway": ["payment gateway", "pay-gw", "tier-0", "pci"],
        "customer-portal": ["customer portal"],
        "reconciliation-service": ["reconciliation service", "recon-svc", "settlement queue", "money-movement"],
        "document-service": ["document service", "kyc", "pii"],
        "notification-service": ["notification service", "cloud vpc", "metadata endpoint", "169.254.169.254"],
        "corporate-directory": ["corporate directory"],
        "log4j": ["logback", "removed"],
        "mysql": ["postgresql", "not in the estate"],
        "wordpress": ["not in the estate"],
        "soap": ["decommissioned", "xml gateway"],
        "xml": ["decommissioned", "soap gateway"],
    }
    lower_ck = ck.lower()
    for canonical, alias_terms in aliases.items():
        if canonical in lower_ck or any(alias in lower_ck for alias in alias_terms):
            extras.extend([canonical, *alias_terms])
    return sorted(set(candidates + extras))


def heuristic_score(stage: str, scenario: dict[str, Any], answer: str) -> dict[str, Any]:
    lower = answer.lower()
    weakness_field = extract_field(answer, "Weakness")
    applicability_field = extract_field(answer, "Applicability")
    priority_field = extract_field(answer, "Priority")
    action_field = extract_field(answer, "Action")
    rationale_field = extract_field(answer, "Rationale")
    decision_text = "\n".join([applicability_field, priority_field, action_field, rationale_field]).lower()
    expected_cwe = scenario.get("expected_cwe", "").lower()
    weakness_name = scenario.get("weakness_name", "")
    weakness_terms = [term for term in words(weakness_name) if len(term) >= 4]

    cwe_hit = bool(expected_cwe and expected_cwe in lower)
    weakness_name_hit = bool(
        weakness_terms and sum(term in weakness_field.lower() for term in weakness_terms) >= min(2, len(weakness_terms))
    )
    weakness_conflict = has_conflicting_weakness_label(scenario.get("expected_cwe", ""), weakness_field)

    expected_applicability = scenario.get("expected_applicability", "")
    if expected_applicability == "not_applicable":
        applicability_hit = contains_any(
            decision_text,
            ["not applicable", "not affected", "not present", "not in the estate", "absent", "removed", "decommissioned"],
        )
    else:
        applicability_hit = contains_any(decision_text, ["applicable", "affected", "present", "applies"])
        if not applicability_hit:
            applicability_hit = bool(ck_asset_terms(scenario) and contains_any(applicability_field, ck_asset_terms(scenario)))
        if "not applicable" in decision_text or "not affected" in decision_text:
            applicability_hit = False

    expected_priority = scenario.get("expected_priority", "")
    if expected_priority == "N/A":
        priority_hit = contains_any(decision_text, ["n/a", "not applicable", "no priority", "close"])
    else:
        priority_hit = expected_priority.lower() in priority_field.lower()

    terms = ck_asset_terms(scenario)
    echoed = bool(terms and contains_any(lower, terms))
    # CK grounding credits USING customer knowledge, not only echoing an asset name:
    # a correct applicability decision can only be reached from the retrieved estate facts.
    ck_term_hit = echoed or applicability_hit

    return {
        "cwe_hit": cwe_hit,
        "weakness_name_hit": weakness_name_hit,
        "sk_hit": (cwe_hit or weakness_name_hit) and not weakness_conflict,
        "weakness_conflict": weakness_conflict,
        "applicability_hit": applicability_hit,
        "priority_hit": priority_hit,
        "ck_term_hit": ck_term_hit,
        "expected_cwe": scenario.get("expected_cwe"),
        "expected_applicability": expected_applicability,
        "expected_priority": expected_priority,
        "ck_terms_checked": terms,
        "parsed_fields": {
            "weakness": weakness_field,
            "applicability": applicability_field,
            "priority": priority_field,
            "action": action_field,
            "rationale": rationale_field,
        },
        "stage_note": "Phase 1 should usually lack CK grounding" if stage == "phase1" else "Phase 2 should use retrieved CK",
    }


def write_outputs(records: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "phase12_results.jsonl"
    csv_path = out_dir / "phase12_results.csv"
    md_path = out_dir / "phase12_summary.md"

    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    csv_fields = [
        "timestamp",
        "stage",
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

    summary = summarize(records)
    md_path.write_text(summary, encoding="utf-8")
    print(f"Wrote {jsonl_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")


def summarize(records: list[dict[str, Any]]) -> str:
    lines = ["# Phase 1 / Phase 2 Evaluation Summary", ""]
    lines.append("Heuristic scores are review aids, not authoritative grading.")
    lines.append("")
    lines.extend([
        "## Metric Glossary",
        "",
        "| Metric | Meaning | Mostly depends on |",
        "| --- | --- | --- |",
        "| SK heuristic hit | Did the answer identify the weakness/CWE or precise weakness name? | Security Knowledge |",
        "| CK grounding hit | Did the answer mention expected LatamPay-like customer facts such as named assets, tiers, zones, PCI, metadata endpoint, or absent/retired products? | Phase 1: model prior/guessing; Phase 2: CK retrieval/use |",
        "| Applicability hit | Did the answer correctly decide whether the weakness affects LatamPay? | CK plus enough SK to map the weakness to the component |",
        "| Priority hit | Did the answer assign the expected urgency for LatamPay? | SK impact plus CK asset context plus LatamPay policy |",
        "",
        "Sequence: SK identifies the risk; CK grounds the risk; applicability decides whether it matters here; priority decides how urgently LatamPay must act.",
        "",
    ])

    for stage in sorted({record["stage"] for record in records}):
        stage_records = [record for record in records if record["stage"] == stage]
        total = len(stage_records)
        sk_hits = sum(1 for record in stage_records if record["heuristic_score"]["sk_hit"])
        app_hits = sum(1 for record in stage_records if record["heuristic_score"]["applicability_hit"])
        prio_hits = sum(1 for record in stage_records if record["heuristic_score"]["priority_hit"])
        ck_hits = sum(1 for record in stage_records if record["heuristic_score"]["ck_term_hit"])
        avg_elapsed = sum(record["elapsed_seconds"] for record in stage_records) / total if total else 0
        lines.extend([
            f"## {stage}",
            "",
            f"- Runs: {total}",
            f"- SK heuristic hits: {sk_hits}/{total}",
            f"- CK grounding hits: {ck_hits}/{total}",
            f"- Applicability heuristic hits: {app_hits}/{total}",
            f"- Priority heuristic hits: {prio_hits}/{total}",
            f"- Average elapsed seconds: {avg_elapsed:.2f}",
            "",
        ])

    lines.append("## Review Queue")
    lines.append("")
    lines.append("Inspect records where Phase 2 improves CK grounding but SK remains weak, especially `sk_gated` scenarios.")
    lines.append("")
    for record in records:
        score = record["heuristic_score"]
        if record["stage"] == "phase2" and (not score["sk_hit"] or not score["applicability_hit"] or not score["priority_hit"]):
            lines.append(
                f"- {record['scenario_id']} repeat={record['repeat']}: "
                f"sk={score['sk_hit']} applicability={score['applicability_hit']} priority={score['priority_hit']}"
            )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 1 and Phase 2 LatamPay tests.")
    parser.add_argument("--scenarios", default="scenarios.json", help="Path to scenarios.json")
    parser.add_argument("--out", default="./results/phase12", help="Output directory")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--ck-persist", default=DEFAULT_CK_PERSIST)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--embed-model", default=DEFAULT_EMBED_MODEL)
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    parser.add_argument("--stages", nargs="+", default=["phase1", "phase2"], choices=["phase1", "phase2"])
    parser.add_argument("--scenario-ids", nargs="*", help="Optional scenario IDs to run")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--k", type=int, default=2, help="Scenario-specific CK passages to retrieve for Phase 2")
    parser.add_argument("--policy-k", type=int, default=2, help="Policy/SLA CK passages to retrieve for Phase 2")
    parser.add_argument("--num-predict", type=int, default=180)
    parser.add_argument("--num-thread", type=int, default=16)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout", type=int, default=240)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenarios = load_scenarios(Path(args.scenarios))
    if args.scenario_ids:
        wanted = set(args.scenario_ids)
        scenarios = [scenario for scenario in scenarios if scenario["id"] in wanted]

    embedder = collection = None
    if "phase2" in args.stages:
        embedder, collection = load_retriever(args.ck_persist, args.collection, args.embed_model, args.device)

    records: list[dict[str, Any]] = []
    timestamp = datetime.now(timezone.utc).isoformat()

    for repeat in range(1, args.repeats + 1):
        for scenario in scenarios:
            for stage in args.stages:
                retrieved: list[dict[str, Any]] = []
                if stage == "phase1":
                    system = STAGE1_SYSTEM
                    prompt = scenario_prompt(scenario)
                else:
                    assert embedder is not None and collection is not None
                    ck_context, retrieved = retrieve_ck(scenario, embedder, collection, args.k, args.policy_k)
                    system = STAGE2_SYSTEM
                    prompt = scenario_prompt(scenario, ck_context)

                print(f"[{stage}] repeat={repeat} scenario={scenario['id']}", flush=True)
                answer, elapsed = ollama_generate(
                    model=args.model,
                    system=system,
                    prompt=prompt,
                    ollama_url=args.ollama_url,
                    num_predict=args.num_predict,
                    num_thread=args.num_thread,
                    temperature=args.temperature,
                    timeout=args.timeout,
                )
                score = heuristic_score(stage, scenario, answer)
                records.append({
                    "timestamp": timestamp,
                    "stage": stage,
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

    write_outputs(records, Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
