# Sovereign AI That Understands Your Network — Demo Lab

A self-contained lab showing where different kinds of knowledge belong in an on-prem LLM stack:

> **Security Knowledge (SK) belongs in the model weights. Customer Knowledge (CK) belongs in RAG. Both run on infrastructure you control.**

One vulnerability (an Apache Struts OGNL RCE) is triaged four ways against a synthetic payment provider, **LatamPay**, entirely on a laptop:

| Phase | Setup | What it proves |
|------|-------|----------------|
| 1 | Llama-3.1-8B (Q4) | Generic baseline — blind to your estate |
| 2 | Llama-3.1-8B + CK-RAG | Customer-aware, security-shallow |
| 3 | Llama-3.1-8B + SK-LoRA + CK-RAG | Sharper weakness diagnosis |
| 4 | Foundation-Sec-8B + CK-RAG | Purpose-built security reasoning |

Everything runs locally via **Ollama** (Metal on Apple Silicon). After setup it runs fully offline.

## Quickstart

_Setup steps finalized during validation — see `docs/setup.md` (coming)._

```bash
# 1. environment
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. models (Ollama)
ollama pull llama3.1:8b-instruct-q4_K_M
ollama create llama3.1-8b-sk-lora   -f models/Modelfile.sk-lora
ollama create foundation-sec-8b-q4  -f models/Modelfile.foundation-sec

# 3. customer-knowledge index
python data/build_ck_index.py --persist ./customer_ck_chromadb --device cpu \
       --embed-model models/bge-small-en-v1.5

# 4. run the notebook
jupyter lab notebook/workshop_demo.ipynb
```

## Repository layout

```
notebook/   workshop_demo.ipynb — the live demo surface
data/       LatamPay customer pack (SYNTHETIC) + scenarios + CK index builder
eval/       batch evaluation harness (phases 1–4)
models/     Ollama Modelfiles + notes on obtaining each model
sk-lora/    SK adapter training/merge scripts (adapter hosted on Hugging Face)
docs/       setup + architecture
results/    precomputed rubric panels
```

## Models & data

- **Base** `llama3.1:8b-instruct-q4_K_M` — pulled from the Ollama registry (Meta Llama 3.1 Community License).
- **SK-LoRA** — the adapter is published separately on Hugging Face; `sk-lora/` holds the training + merge/convert scripts. Not redistributed here as merged weights.
- **Foundation-Sec-8B** — Cisco Foundation AI, open-weight (Apache-2.0). Obtain per `models/README.md`; not redistributed here.
- **LatamPay** customer pack is **fully synthetic** — no real customer data. Not for production security decisions.

See `NOTICE` for third-party attributions (Meta Llama 3.1, Cisco Foundation-Sec, MITRE CWE, NVD).
