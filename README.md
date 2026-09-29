# Sovereign AI That Understands Your Network — Demo Lab

A self-contained, **laptop-only** lab that shows *where different kinds of knowledge belong* in an on-prem LLM security stack:

> **Security Knowledge (SK) belongs in the model weights. Customer Knowledge (CK) belongs in RAG. Both run on infrastructure you control.**

Everything runs locally via **[Ollama](https://ollama.com)** (Metal on Apple Silicon). After a one-time setup, the whole demo runs **fully offline** — running it in airplane mode *is* the sovereignty thesis, demonstrated live.

---

## The idea in one minute

A security assistant needs two very different kinds of knowledge:

| Knowledge | Examples | Where it belongs |
|---|---|---|
| **Security Knowledge (SK)** | weakness taxonomy (CWE), exploitation patterns, mitigations | the model **weights** (a LoRA adapter, or a security-tuned base model) |
| **Customer Knowledge (CK)** | asset inventory, SBOM, SLAs, incidents, network zones | **RAG** (a local vector store) — private, current, inspectable |

We prove it by building an assistant in **four stages** and testing all four against a synthetic payment company, **LatamPay**. Only the model changes between stages; the scenarios, prompt, and decoding are held constant.

| Stage | Setup | What it adds |
|------|-------|----------------|
| **1** | Llama-3.1-8B (Q4) | Generic baseline — blind to your estate |
| **2** | Llama-3.1-8B **+ CK-RAG** | Customer grounding, retrieved at query time |
| **3** | Llama-3.1-8B **+ SK-LoRA** + CK-RAG | Build-your-own security knowledge in the weights |
| **4** | **Foundation-Sec-8B** + CK-RAG | A purpose-built, open-weight security base model |

See [`docs/architecture.md`](docs/architecture.md) for the full design and pipeline.

---

## What's in this repo

```
demo_session.ipynb     START HERE — the stage-by-stage session notebook (32-scenario benchmark)
workshop_demo.ipynb    original end-to-end walkthrough
data/                  LatamPay customer pack (SYNTHETIC) + 32 scenarios + eval scripts + CK index builder
  customer_pack/         assets, policy, incidents, SBOM, zones, data classification
  scenarios.json         the 32 benchmark scenarios
  eval_phase12/3/4.py    batch evaluation harness (Stages 1-4)
  build_ck_index.py      builds the CK vector store
customer_ck_chromadb/  prebuilt CK vector index (~600 KB, synthetic) — the demo runs out of the box
models/                Ollama Modelfiles + notes on obtaining each model
sk-lora/               SK-LoRA training/merge recipe (adapter hosted on Hugging Face)
docs/                  architecture + setup
results/               output panels
```

---

## Two ways to run it

### 1. The notebooks (the benchmark)
- **[`demo_session.ipynb`](demo_session.ipynb)** — the recommended, attendee-friendly notebook. Each section *assembles* one stage's artifact; the final section runs all four stages across the **32 scenarios** and scores **SK** (correct weakness) and **CK** (customer facts grounded).
- **[`workshop_demo.ipynb`](workshop_demo.ipynb)** — the original walkthrough.

### 2. The manual Ollama demo (the "SK ladder")
A quick, live way to show security knowledge improving *in the weights* — no RAG, just the models. Three deterministic tags (see [`models/`](models)) answer the same prompt:

```
You are a security weakness classifier. Read the described software weakness and respond with
the single most precise CWE identifier and its name, then one sentence explaining why it fits.

On an internet-facing Apache Struts payment gateway, a request parameter is placed into a
server-side OGNL expression that the framework then evaluates, letting an attacker submit a
crafted expression the server executes.
```

The CWE sharpens as security knowledge moves into the weights: `sk-demo-base` -> **CWE-95**, `sk-demo-lora` -> **CWE-94**, `sk-demo-foundation-sec` -> **CWE-917 (Expression Language Injection)**.

---

## Quickstart

Full, tested instructions are in **[`docs/setup.md`](docs/setup.md)**. The short version, from the repo root:

```bash
# 1. Python environment (3.12)
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Embedding model for RAG (needed to embed queries at runtime)
cd models && git lfs install && git clone https://huggingface.co/BAAI/bge-small-en-v1.5 && cd ..

# 3. Ollama models (the four stages)
ollama pull llama3.1:8b-instruct-q4_K_M                                        # Stages 1 & 2
cd models && ollama create llama3.1-8b-sk-lora  -f Modelfile.sk-lora  && cd ..      # Stage 3 (see sk-lora/README.md)
cd models && ollama create foundation-sec-8b-q4 -f Modelfile.foundation-sec && cd ..  # Stage 4 (see models/README.md)

# 4. Run the demo
jupyter lab demo_session.ipynb
```

The **CK vector index ships prebuilt** ([`customer_ck_chromadb/`](customer_ck_chromadb)), so you can skip building it. Rebuild only if you change [`data/customer_pack/`](data/customer_pack):

```bash
python data/build_ck_index.py --persist ./customer_ck_chromadb --device cpu \
       --embed-model models/bge-small-en-v1.5
```

---

## Models & data

- **Base** — `llama3.1:8b-instruct-q4_K_M`, pulled from the Ollama registry (Meta Llama 3.1 Community License).
- **SK-LoRA** — the adapter is published separately on Hugging Face; [`sk-lora/`](sk-lora) holds the full training + merge/convert **recipe**. Merged weights are **not** redistributed here.
- **Foundation-Sec-8B** — Cisco Foundation AI, open-weight (Apache-2.0). Obtain per [`models/README.md`](models/README.md); not redistributed here.
- **LatamPay customer pack** — **fully synthetic**, no real customer data. For demonstration only; not for production security decisions.

> Model weights (`*.gguf`, the `bge-small` folder) are intentionally **not** committed — they're freely available from Hugging Face / Ollama and are large. Only the reproducible recipe and the tiny synthetic CK index ship in the repo.

---

## Learn more

- [`docs/architecture.md`](docs/architecture.md) — where knowledge lives, the pipeline, and why on-prem beats cloud here.
- [`docs/setup.md`](docs/setup.md) — full, tested setup.
- [`sk-lora/README.md`](sk-lora/README.md) — how the SK-LoRA adapter was built.
- [`models/README.md`](models/README.md) — obtaining each model + the Modelfiles.
- [`NOTICE`](NOTICE) — third-party attributions (Meta Llama 3.1, Cisco Foundation-Sec, MITRE CWE, NVD).

## License

Code and synthetic data are released under the terms in [`LICENSE`](LICENSE). Third-party models retain their own licenses (see above and [`NOTICE`](NOTICE)).
