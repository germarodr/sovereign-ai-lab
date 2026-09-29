#!/usr/bin/env python3
"""
build_ck_index.py — embed the LatamPay Customer-Knowledge (CK) pack into ChromaDB.

This is the ONLY data that RAG serves at query time. It contains Customer
Knowledge only (assets, SBOM, policy, zones, tickets, data classification).
It deliberately contains NO CWE/MITRE catalog — Security Knowledge lives in the
model weights (see lora_sk/), not in retrieval.

Chunking: markdown files are split into heading-led sections so section titles,
tables, and bullets stay together as useful passages. The SBOM JSON is flattened
into one passage per component plus the "not in estate" note (which drives the
Miss scenarios).

Usage (run from the repo root):
  python data/build_ck_index.py --persist ./customer_ck_chromadb --device cpu \
         --embed-model models/bge-small-en-v1.5

Requires: pip install chromadb sentence-transformers
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE / "customer_pack"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
COLLECTION = "latampay_ck"


def md_passages(path: Path) -> list[str]:
    passages: list[str] = []
    document_title = ""
    current_heading = ""
    current_body: list[str] = []

    def flush() -> None:
        if not current_heading or not current_body:
            return
        heading = [document_title, current_heading] if document_title else [current_heading]
        text = "\n".join(heading + current_body).strip()
        if len(text) > 40:
            passages.append(text)

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line.startswith("# "):
            flush()
            document_title = line
            current_heading = ""
            current_body = []
        elif line.startswith("##"):
            flush()
            current_heading = line
            current_body = []
        elif line.strip():
            current_body.append(line)
    flush()

    return passages


def sbom_passages(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    meta_note = ""
    for p in data.get("metadata", {}).get("properties", []):
        meta_note = p.get("value", "")
    if meta_note:
        out.append(f"SBOM note: {meta_note}")
    for c in data.get("components", []):
        props = "; ".join(f"{p['name']}={p['value']}" for p in c.get("properties", []))
        desc = c.get("description", "")
        out.append(
            f"SBOM component: {c.get('name')} {c.get('version','')} "
            f"({c.get('type','')}). {desc} {props}".strip()
        )
    for p in data.get("properties", []):
        if p.get("name", "").endswith("not_in_estate"):
            out.append(f"NOT in the LatamPay estate: {p['value']}")
    return out


def collect() -> list[dict]:
    docs: list[dict] = []
    for path in sorted(PACK.glob("*")):
        if path.suffix == ".md":
            for i, passage in enumerate(md_passages(path)):
                docs.append({"id": f"{path.stem}-{i}", "text": passage, "source": path.name})
        elif path.name.endswith(".cdx.json"):
            for i, passage in enumerate(sbom_passages(path)):
                docs.append({"id": f"{path.stem}-{i}", "text": passage, "source": path.name})
    return docs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--persist", required=True, help="ChromaDB persist directory")
    ap.add_argument("--device", default="cpu", choices=["cpu", "cuda"])
    ap.add_argument("--embed-model", default=EMBED_MODEL,
                    help="Embedding model name or local folder path")
    args = ap.parse_args()

    import chromadb
    from sentence_transformers import SentenceTransformer

    docs = collect()
    if not docs:
        print("No customer-pack documents found.")
        return 1
    print(f"Collected {len(docs)} CK passages from {PACK}")

    model = SentenceTransformer(args.embed_model, device=args.device)
    embeddings = model.encode(
        [d["text"] for d in docs], normalize_embeddings=True, show_progress_bar=True
    ).tolist()

    client = chromadb.PersistentClient(path=args.persist)
    try:
        client.delete_collection(COLLECTION)
    except Exception:  # noqa: BLE001
        pass
    col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    col.add(
        ids=[d["id"] for d in docs],
        documents=[d["text"] for d in docs],
        embeddings=embeddings,
        metadatas=[{"source": d["source"]} for d in docs],
    )
    print(f"Indexed {len(docs)} passages into '{COLLECTION}' at {args.persist}")
    print("Reminder: this store is CK-only. Do not add CWE/MITRE content here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
