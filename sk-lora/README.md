# SK-LoRA — Security Knowledge in the weights

This folder trains and packages the **Phase 3** model: a small LoRA adapter that teaches Llama-3.1-8B sharper security-weakness reasoning, then merges it and converts to GGUF for Ollama.

The adapter carries **Security Knowledge only** — never LatamPay customer-pack (CK) data. CK stays in RAG.

> The trained adapter is published separately on Hugging Face; this repo ships the **scripts and seed data** to reproduce it, not the merged Llama-derived weights (see [Licensing](#licensing)).

## Files

| Path | Purpose |
| --- | --- |
| `sk_seed.jsonl` | Curated instruction examples (weakness classification, remediation, distinctions). |
| `build_sk_dataset.py` | Expands the seed with public CWE/NVD sources → `sk_train.jsonl`. |
| `prepare_mlx_dataset.py` | Converts `sk_train.jsonl` into `mlx-lm` train/valid/test splits. |
| `train_qlora.py` | CUDA/`bitsandbytes` QLoRA trainer (Linux/NVIDIA GPU path). |
| `merge_lora.py` | Merges the trained adapter into the Llama-3.1-8B-Instruct base. |

## Build path (Apple Silicon, recommended)

The reference build is a Mac M4 Pro (24 GB) using `mlx-lm` — QLoRA-style: a LoRA adapter trained on top of a frozen 4-bit base.

```bash
# 1. build the SK training set (network-enabled)
python sk-lora/build_sk_dataset.py --nvd-pages 20 --max-per-cwe 40
#    offline smoke: python sk-lora/build_sk_dataset.py --no-cwe --nvd-pages 0

# 2. prepare mlx-lm splits
python sk-lora/prepare_mlx_dataset.py

# 3. train the adapter with mlx-lm (example)
#    pip install mlx-lm
mlx_lm.lora --model meta-llama/Llama-3.1-8B-Instruct --train \
            --data sk-lora/mlx_data --iters 600 --batch-size 1 --num-layers 8

# 4. fuse the adapter into the base, then convert to GGUF with llama.cpp, quantize Q4_K_M
#    → produces llama31-8b-sk-lora-q4_k_m.gguf
```

Suggested QLoRA profile: rank 8, alpha 16, 1 epoch, seq len 2048–4096, LR 1e-4–2e-4.

The Linux/NVIDIA alternative uses `train_qlora.py` (`bitsandbytes`).

## Training target

The goal is **not** broad instruction tuning — it is precise weakness distinctions on the lab's recurring misses:

- CWE-917 Expression Language / lookup injection vs generic code injection or deserialization
- CWE-90 LDAP Injection vs generic code injection
- CWE-367 TOCTOU vs path traversal / generic race
- CWE-306 Missing Authentication vs broad access control
- CWE-798 Hard-coded Credentials vs "outdated component"
- CWE-601 Open Redirect vs SSRF/XSS

## Package for Ollama

Once you have `llama31-8b-sk-lora-q4_k_m.gguf`, place it in `../models/` and import (see [`../models/README.md`](../models/README.md)):

```bash
cd ../models
ollama create llama3.1-8b-sk-lora -f Modelfile.sk-lora
```

Keep the explicit Llama-3.1 template in `Modelfile.sk-lora` — GGUF metadata alone can yield continuation-style answers instead of instruction-following.

## Validation probes

```bash
ollama run llama3.1-8b-sk-lora "Return only the CWE ID and name: Code checks a file is safe and later opens it by name after it can be swapped."
ollama run llama3.1-8b-sk-lora "Return only the CWE ID and name: A login flow redirects to an unvalidated returnUrl after authentication."
ollama run llama3.1-8b-sk-lora "Return only the CWE ID and name: An LDAP filter is built by concatenating form input containing ) and *."
```

Expected: `CWE-367 TOCTOU`, `CWE-601 Open Redirect`, `CWE-90 LDAP Injection`.

## Licensing

The merged model is a **Llama-3.1 derivative** and is governed by the Meta Llama 3.1 Community License. To stay clean, this repo publishes only the **LoRA adapter** (the delta) on Hugging Face plus these reproduction scripts — not the merged base weights. See the repo `NOTICE`.
