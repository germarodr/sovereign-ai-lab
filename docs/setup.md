# Setup — run the lab locally

Everything runs on one machine through **Ollama**. Tested on an Apple M4 Pro (24 GB, macOS). After setup it runs **fully offline**.

## 1. Prerequisites

- [Ollama](https://ollama.com) installed and running — check with `ollama --version`
- Python 3.12
- `git` + `git-lfs` (for the embedding model)
- ~15 GB free disk (three 8B Q4 models + the embedding model)

## 2. Python environment

Run all commands from the repo root.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Embedding model (RAG)

Clone the local embedding model into `models/`. It is used both to build and to query the CK index, so it must be identical on both sides.

```bash
cd models && git lfs install && git clone https://huggingface.co/BAAI/bge-small-en-v1.5 && cd ..
```

`eval_phase12.py` auto-detects `models/bge-small-en-v1.5/` and uses it offline; otherwise it falls back to the Hugging Face id.

## 4. Ollama models (the four phases)

```bash
# Phase 1 & 2 — base model
ollama pull llama3.1:8b-instruct-q4_K_M

# Phase 3 — SK-LoRA. Put the GGUF in models/ first (see sk-lora/README.md to build it),
# then import from the models/ directory so the relative FROM path resolves:
cd models && ollama create llama3.1-8b-sk-lora -f Modelfile.sk-lora && cd ..

# Phase 4 — Foundation-Sec. Obtain the GGUF (see models/README.md), then:
cd models && ollama create foundation-sec-8b-q4 -f Modelfile.foundation-sec && cd ..
```

Verify all three demo tags exist:

```bash
ollama list | grep -E "llama3.1:8b-instruct-q4_K_M|llama3.1-8b-sk-lora|foundation-sec-8b-q4"
```

## 5. Customer-Knowledge index (ships prebuilt)

The `customer_ck_chromadb/` vector store is **included in the repo** (~600 KB, fully synthetic), so the demo works out of the box — you can skip this step. You only need to rebuild it if you change `data/customer_pack/`:

```bash
python data/build_ck_index.py --persist ./customer_ck_chromadb --device cpu \
       --embed-model models/bge-small-en-v1.5
```

This builds the **CK-only** `latampay_ck` ChromaDB collection from `data/customer_pack/`. Note: the embedding model (step 3) is still required at query time to embed the scenario, even when using the prebuilt index.

## 6. Run the demo

```bash
jupyter lab demo_session.ipynb    # the stage-by-stage session notebook
```

Register the kernel once if needed:

```bash
python -m ipykernel install --user --name latampay-demo --display-name "LatamPay Demo"
```

Or run the batch evaluators headlessly:

```bash
python data/eval_phase12.py --repeats 1                 # Phases 1 & 2
python data/eval_stage3.py                              # Phase 3 (SK-LoRA)
python data/eval_stage4.py                              # Phase 4 (Foundation-Sec)
```

## Offline note

Once steps 3–5 are complete, turn the network **off** — the whole demo runs on the laptop. Running it in airplane mode is the sovereignty thesis, demonstrated live.
