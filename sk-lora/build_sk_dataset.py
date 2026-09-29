#!/usr/bin/env python3
"""
build_sk_dataset.py — assemble the Security-Knowledge (SK) LoRA training set.

This produces instruction-tuning pairs that teach SECURITY KNOWLEDGE (weakness
taxonomy + reasoning). The output goes into the model WEIGHTS via LoRA; it is
NOT used at query time. (Customer Knowledge stays in RAG; see build_ck_index.py.)

Sources (authoritative, public, no hand-labeling required):
  1. MITRE CWE catalog (XML)  -> describe->CWE, CWE->mitigation, relationships
  2. NVD CVE feeds (API 2.0)  -> "given this description, what CWE?" pairs
  3. data/lora_sk/sk_seed.jsonl -> curated high-quality seed pairs (always included)

Output: data/lora_sk/sk_train.jsonl  (records: {"instruction","input","output"})

Usage:
  python build_sk_dataset.py --nvd-pages 20 --max-per-cwe 40
  # then train QLoRA (rank 8, 1 epoch) on sk_train.jsonl

Notes:
  - Network access is required to fetch CWE/NVD. The seed file alone is enough to
    smoke-test the pipeline offline.
  - Respect NVD rate limits; set NVD_API_KEY env var to raise them.
"""

from __future__ import annotations
import argparse
import io
import json
import os
import random
import sys
import time
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = HERE / "sk_seed.jsonl"
OUT = HERE / "sk_train.jsonl"

CWE_ZIP_URL = "https://cwe.mitre.org/data/xml/cwec_latest.xml.zip"
NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"

CLASSIFY_INSTR = (
    "You are a security weakness classifier. Read the described software "
    "weakness and respond with the single most precise CWE identifier and its name."
)
MITIGATE_INSTR = "Explain how to remediate the given weakness class."
DESC_INSTR = (
    "You are a security triage assistant. Read the vulnerability description "
    "and respond with the most precise CWE identifier."
)


def _get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "latampay-sk-builder/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def load_seed() -> list[dict]:
    if not SEED.exists():
        return []
    rows = []
    for line in SEED.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def fetch_cwe_pairs() -> list[dict]:
    """Template the MITRE CWE catalog into instruction pairs."""
    print("[cwe] downloading MITRE CWE catalog ...", file=sys.stderr)
    raw = _get(CWE_ZIP_URL)
    zf = zipfile.ZipFile(io.BytesIO(raw))
    xml_name = next(n for n in zf.namelist() if n.endswith(".xml"))
    tree = ET.parse(zf.open(xml_name))
    root = tree.getroot()
    # Strip namespaces for simpler XPath-ish traversal.
    for el in root.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]

    pairs: list[dict] = []
    for w in root.iter("Weakness"):
        cwe_id = w.get("ID")
        name = w.get("Name")
        if not cwe_id or not name:
            continue
        label = f"CWE-{cwe_id}: {name}"

        desc_el = w.find("Description")
        desc = (desc_el.text or "").strip() if desc_el is not None else ""
        if desc:
            pairs.append({
                "instruction": CLASSIFY_INSTR,
                "input": desc,
                "output": label + ".",
            })

        # Mitigations -> remediation pairs.
        mits = [
            (m.findtext("Description") or "").strip()
            for m in w.iter("Mitigation")
        ]
        mits = [m for m in mits if m]
        if mits:
            pairs.append({
                "instruction": MITIGATE_INSTR,
                "input": label,
                "output": " ".join(mits[:3]),
            })
    print(f"[cwe] templated {len(pairs)} pairs", file=sys.stderr)
    return pairs


def fetch_nvd_pairs(pages: int, page_size: int = 2000) -> list[dict]:
    """Pull CVE descriptions + their primary CWE mapping from NVD API 2.0."""
    api_key = os.environ.get("NVD_API_KEY")
    headers = {"User-Agent": "latampay-sk-builder/1.0"}
    if api_key:
        headers["apiKey"] = api_key

    pairs: list[dict] = []
    for page in range(pages):
        start = page * page_size
        url = f"{NVD_API}?resultsPerPage={page_size}&startIndex={start}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            print(f"[nvd] page {page} failed: {e}", file=sys.stderr)
            break
        for item in data.get("vulnerabilities", []):
            cve = item.get("cve", {})
            descs = [d["value"] for d in cve.get("descriptions", []) if d.get("lang") == "en"]
            if not descs:
                continue
            cwe = None
            for wk in cve.get("weaknesses", []):
                for d in wk.get("description", []):
                    v = d.get("value", "")
                    if v.startswith("CWE-") and v[4:].isdigit():
                        cwe = v
                        break
                if cwe:
                    break
            if not cwe:
                continue
            pairs.append({
                "instruction": DESC_INSTR,
                "input": descs[0].strip(),
                "output": cwe,
                "_cwe": cwe,
            })
        print(f"[nvd] page {page + 1}/{pages}: total {len(pairs)} pairs", file=sys.stderr)
        time.sleep(6 if not api_key else 1)  # NVD rate limits
    return pairs


def balance_by_cwe(pairs: list[dict], max_per_cwe: int) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for p in pairs:
        key = p.get("_cwe") or p["output"].split(":")[0]
        buckets[key].append(p)
    out: list[dict] = []
    for key, items in buckets.items():
        random.shuffle(items)
        out.extend(items[:max_per_cwe])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nvd-pages", type=int, default=10, help="NVD pages to pull (0 to skip)")
    ap.add_argument("--max-per-cwe", type=int, default=40, help="class balancing cap for NVD pairs")
    ap.add_argument("--no-cwe", action="store_true", help="skip MITRE CWE catalog")
    ap.add_argument("--seed", type=int, default=13)
    args = ap.parse_args()
    random.seed(args.seed)

    rows: list[dict] = list(load_seed())
    print(f"[seed] {len(rows)} curated pairs", file=sys.stderr)

    if not args.no_cwe:
        try:
            rows += fetch_cwe_pairs()
        except Exception as e:  # noqa: BLE001
            print(f"[cwe] skipped ({e})", file=sys.stderr)

    if args.nvd_pages > 0:
        nvd = fetch_nvd_pairs(args.nvd_pages)
        nvd = balance_by_cwe(nvd, args.max_per_cwe)
        for p in nvd:
            p.pop("_cwe", None)
        rows += nvd

    # Deduplicate on (instruction, input).
    seen = set()
    deduped = []
    for r in rows:
        k = (r["instruction"], r.get("input", ""))
        if k in seen:
            continue
        seen.add(k)
        deduped.append({"instruction": r["instruction"], "input": r.get("input", ""), "output": r["output"]})

    random.shuffle(deduped)
    with OUT.open("w", encoding="utf-8") as f:
        for r in deduped:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[out] wrote {len(deduped)} pairs -> {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
