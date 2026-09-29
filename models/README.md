# Models

Three Ollama models drive the four phases. All run locally at 4-bit (Q4_K_M) — an 8B model is ~4.9 GB and fits comfortably on a 24 GB laptop with Metal acceleration.

| Phase | Ollama tag | Source | In git? |
|---|---|---|---|
| 1 & 2 | `llama3.1:8b-instruct-q4_K_M` | Ollama registry (`ollama pull`) | no — pulled |
| 3 | `llama3.1-8b-sk-lora` | local GGUF + `Modelfile.sk-lora` | no — GGUF gitignored |
| 4 | `foundation-sec-8b-q4` | local GGUF + `Modelfile.foundation-sec` | no — GGUF gitignored |

GGUF files never live in git (size + license). This folder keeps only the **Modelfiles** (chat template + system prompt + parameters); you supply the weights locally.

## Phase 1 & 2 — base Llama

```bash
ollama pull llama3.1:8b-instruct-q4_K_M
```

Meta Llama-3.1-8B-Instruct, 4-bit. Used alone (Phase 1) and with CK-RAG (Phase 2).

## Phase 3 — SK-LoRA

Build or obtain `llama31-8b-sk-lora-q4_k_m.gguf` (see [`../sk-lora/README.md`](../sk-lora/README.md)), place it in this folder, then:

```bash
cd models
ollama create llama3.1-8b-sk-lora -f Modelfile.sk-lora
```

## Phase 4 — Foundation-Sec-8B

**Cisco Foundation-Sec-8B** is an open-weight (Apache-2.0), security-specialized model. This lab uses the **Instruct** variant at Q4_K_M. Obtain a GGUF and import:

```bash
cd models
curl -L -o foundation-sec-8b-instruct-q4_k_m.gguf \
  "https://huggingface.co/gabriellarson/Foundation-Sec-8B-Instruct-GGUF/resolve/main/Foundation-Sec-8B-Instruct-Q4_K_M.gguf?download=true"
ollama create foundation-sec-8b-q4 -f Modelfile.foundation-sec
```

Notes:
- The GGUF above is a community re-quantization of Cisco's open-weight model. The provenance-first alternative is the official `fdtn-ai` GGUF (see the model card / `NOTICE`).
- The deck highlights the newer **Foundation-Sec-8B-Reasoning** variant; this lab uses **Instruct** for speed and because it matches the validated results. Reasoning emits `<think>` traces (slower, needs a parser).

## Why the explicit Modelfile template

Both Modelfiles pin the Llama-3.1 chat template and stop tokens:

```
FROM ./<model>.gguf
TEMPLATE """...<|start_header_id|>...<|eot_id|>"""
SYSTEM """..."""
PARAMETER temperature 0
```

Relying on GGUF metadata alone can produce continuation-style answers instead of instruction-following ones. Keep the template when importing.

## Smoke probes

```bash
ollama run llama3.1-8b-sk-lora   "Return only the CWE ID and name: An LDAP filter is built by concatenating form input."
ollama run foundation-sec-8b-q4  "Return only the CWE ID and name: A service fetches a user-supplied URL server-side without restricting destinations."
```

Expected: `CWE-90: LDAP Injection` and `CWE-918: Server-Side Request Forgery (SSRF)`.

## Reference results

On the E02 Struts OGNL payment-gateway scenario (CWE-917), the four-phase ladder behaves as designed: the base model is generic, CK-RAG adds customer grounding, SK-LoRA sharpens the weakness, and **Foundation-Sec returns the exact CWE-917 with Critical priority and a PCI-aware action**. On an M4 Pro each phase runs in ~5–9 s (Metal), well under the demo budget.
