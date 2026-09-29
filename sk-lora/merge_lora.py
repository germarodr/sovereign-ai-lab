#!/usr/bin/env python3
"""
merge_lora.py - merge the Stage 3 SK-LoRA adapter into the Llama base model.

Run this in a GPU or high-memory CPU environment after train_qlora.py completes.
The merged Hugging Face checkpoint is the input to llama.cpp GGUF conversion.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

DEFAULT_BASE_MODEL = "meta-llama/Llama-3.1-8B-Instruct"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge SK-LoRA adapter into base model.")
    parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--adapter", default="llama31_sk_lora_adapter")
    parser.add_argument("--out", default="llama31_sk_lora_merged")
    parser.add_argument("--dtype", choices=["bfloat16", "float16"], default="bfloat16")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dtype = torch.bfloat16 if args.dtype == "bfloat16" else torch.float16

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=dtype,
        device_map="auto",
    )
    model = PeftModel.from_pretrained(model, args.adapter)
    merged = model.merge_and_unload()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(out, safe_serialization=True)

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, use_fast=True)
    tokenizer.save_pretrained(out)
    print(f"Saved merged model to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
