# Architecture — where knowledge lives

**Thesis:** Security Knowledge (SK) belongs in the model **weights**; Customer Knowledge (CK) belongs in **RAG**; both run on infrastructure **you control**.

The task is customer-contextual vulnerability triage: *what is it, does it affect us, how urgent, and what do we do?*

| Knowledge | Examples | Home |
|---|---|---|
| **Security Knowledge (SK)** | weakness taxonomy (CWE), exploitation patterns, root-cause, mitigations | model **weights** — a LoRA adapter or a security foundation model |
| **Customer Knowledge (CK)** | asset inventory, SBOM, SLAs, incidents, network zones | **RAG** (vector store) |
| **Fresh threat intel** | the newly disclosed CVE / advisory | retrieved or supplied at query time |

**Design rule:** the vector store holds **CK only** — never the CWE/MITRE security taxonomy. That is what keeps the two knowledge types cleanly separated.

## Pipeline

```
scenario (weakness description) ─────────────────────────────────┐
                                                                  ├─► LLM (Ollama) ─► triage answer
query ─► embed (bge-small) ─► ChromaDB (latampay_ck) ─► CK context ┘
```

The embedding model (`bge-small-en-v1.5`) turns text into vectors; ChromaDB returns the closest LatamPay passages; those are injected into the prompt alongside the weakness description. The LLM does the reasoning.

## The four phases

1. **Llama only** — generic baseline, blind to your estate.
2. **Llama + CK-RAG** — customer-aware, but security reasoning stays shallow.
3. **Llama + SK-LoRA + CK-RAG** — sharper weakness classification (SK adapted into the weights).
4. **Foundation-Sec-8B + CK-RAG** — purpose-built security reasoning.

Across the ladder, CK-RAG is what adds customer grounding; the model side is what deepens security reasoning. Only Phase 4 reliably identifies the exact CWE **and** the correct priority — the payoff of the demo.

## Why on-prem, not cloud

No model — cloud or local — knows a brand-new CVE from its weights; the advisory is supplied at query time. The real difference is that the on-prem stack can cross-check the private estate (SBOM, inventory) **without exporting it**, and a security-tuned model reasons about the weakness far better than a generic one. Fresh facts in via retrieval; durable security reasoning from the weights.
