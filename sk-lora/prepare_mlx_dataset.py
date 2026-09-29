#!/usr/bin/env python3
"""
prepare_mlx_dataset.py - convert sk_train.jsonl into an mlx-lm LoRA dataset.

Input rows use the repo format:
  {"instruction": "...", "input": "...", "output": "..."}

Output directory contains train/valid/test JSONL files with prompt/completion
fields, which are accepted by mlx-lm LoRA workflows.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def load_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        instruction = row["instruction"].strip()
        input_text = row.get("input", "").strip()
        output = row["output"].strip()
        prompt = instruction if not input_text else f"{instruction}\n\n{input_text}"
        rows.append({"prompt": prompt, "completion": output})
    return rows


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare mlx-lm train/valid/test files from sk_train.jsonl.")
    parser.add_argument("--input", default="sk_train.jsonl")
    parser.add_argument("--out", default="mlx_data")
    parser.add_argument("--valid-ratio", type=float, default=0.05)
    parser.add_argument("--test-ratio", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=13)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = load_rows(Path(args.input))
    if len(rows) < 3:
        raise SystemExit("Need at least 3 rows to create train/valid/test splits")

    random.Random(args.seed).shuffle(rows)
    test_count = max(1, round(len(rows) * args.test_ratio))
    valid_count = max(1, round(len(rows) * args.valid_ratio))
    test_rows = rows[:test_count]
    valid_rows = rows[test_count:test_count + valid_count]
    train_rows = rows[test_count + valid_count:]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "train.jsonl", train_rows)
    write_jsonl(out / "valid.jsonl", valid_rows)
    write_jsonl(out / "test.jsonl", test_rows)

    print(f"Wrote {len(train_rows)} train rows to {out / 'train.jsonl'}")
    print(f"Wrote {len(valid_rows)} valid rows to {out / 'valid.jsonl'}")
    print(f"Wrote {len(test_rows)} test rows to {out / 'test.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
