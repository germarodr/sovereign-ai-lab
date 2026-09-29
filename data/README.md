# LatamPay Lab Data Pack

Synthetic data for the demo. It encodes one architectural rule:

- **Customer Knowledge (CK)** goes into retrieval (`customer_pack/` → ChromaDB).
- **Security Knowledge (SK)** goes into model weights (see [`../sk-lora/`](../sk-lora/)).

Do not mix them. The CK vector store must contain **only** `customer_pack/` — no MITRE, CWE, CVE, or exploit catalogs.

> **All customer data here is fictional.** LatamPay S.A. is a made-up Latin American payment provider. Nothing is real customer data. Not for production security decisions.

## Files

| Path | Purpose |
| --- | --- |
| `scenarios.json` | 12 evaluation scenarios for the four-phase demo. |
| `demo_showcase_scenarios.json` | Extra showcase scenarios (incl. the `E02` Struts payment-gateway demo case). |
| `build_ck_index.py` | Builds the CK-only ChromaDB index from `customer_pack/`. |
| `eval_phase12.py` / `eval_stage3.py` / `eval_stage4.py` | Batch evaluators for the four phases. |
| `customer_pack/` | Synthetic LatamPay customer facts used for RAG. |

## Customer Knowledge Pack

`customer_pack/` is the only source RAG serves at query time. It describes the asset inventory, remediation SLAs, network zones, prior incidents, data classification, and an SBOM. It deliberately includes facts that separate **applicable** from **non-applicable** findings:

- Apache Struts is present on `payment-gateway` (internet-facing, tier-0, PCI).
- Log4j was removed in 2022 and replaced with Logback.
- MySQL/MariaDB and WordPress are **not** in the estate.
- The legacy SOAP/XML gateway was decommissioned in 2024.
- `notification-service` makes outbound webhook calls from a Cloud VPC where the metadata endpoint is reachable (SSRF surface).
- `reconciliation-service` handles money movement; `document-service` handles KYC/PII; `customer-portal` has a login return-URL redirect flow.

## Scenario design

`scenarios.json` spans three archetypes:

| Archetype | Meaning |
| --- | --- |
| `hit` | The weakness applies to software/assets LatamPay runs. |
| `miss` | The weakness class is real, but the affected product is absent or retired. |
| `sk_gated` | Correct triage needs stronger security knowledge before CK can scope impact. |

Each scenario tests three visible checks: (1) correct weakness/CWE, (2) correct use of LatamPay context, (3) correct priority/action. Prompts avoid CVE numbers so the demo stays cutoff-independent and focuses on weakness reasoning.

## Four phases

| Phase | Setup | Expected behavior |
| --- | --- | --- |
| 1 | Llama only | Generic baseline; no customer grounding. |
| 2 | Llama + CK-RAG | Better applicability and SLA decisions. |
| 3 | Llama + SK-LoRA + CK-RAG | Better weakness classification plus grounding. |
| 4 | Foundation-Sec-8B + CK-RAG | Strongest security reasoning plus grounding. |

## Build the CK index (local)

From the repo root, with the venv active and `models/bge-small-en-v1.5/` present:

```bash
python data/build_ck_index.py --persist ./customer_ck_chromadb --device cpu \
       --embed-model models/bge-small-en-v1.5
```

Expected:

```text
Indexed 31 passages into 'latampay_ck' at ./customer_ck_chromadb
```

Rebuild whenever any file in `customer_pack/` changes — the persisted vector DB otherwise keeps the old chunks.

## Run the evaluators

```bash
python data/eval_phase12.py --repeats 1                 # Phases 1 & 2
python data/eval_stage3.py                              # Phase 3
python data/eval_stage4.py                              # Phase 4
```

Phase 2 retrieves 2 scenario passages + 2 policy/SLA passages by default (`--k`, `--policy-k`). Each Phase 2 answer stores the retrieved CK snippets — if an answer is poor, first check whether retrieval found the right documents before blaming the model.

### Evaluation metric glossary

The summaries follow the sequence `SK → CK grounding → Applicability → Priority`.

| Metric | Meaning | Mostly depends on |
| --- | --- | --- |
| SK hit | Did the answer identify the weakness/CWE? | Security Knowledge |
| CK grounding hit | Did it cite expected LatamPay facts (assets, tiers, zones, PCI, absent products)? | Phase 1: model prior; Phase 2: CK retrieval |
| Applicability hit | Did it correctly decide whether the weakness affects LatamPay? | CK + enough SK |
| Priority hit | Did it assign the expected urgency per LatamPay policy? | SK impact + CK context + policy |

Scores are heuristic review aids — use them to find interesting failures, then read the answers.

## Optional: rebuild the SK training set

The SK dataset builder is under [`lora_sk/`](../sk-lora/) (the training scripts live in the repo's `sk-lora/` folder). Training data must **never** be indexed into CK-RAG.
