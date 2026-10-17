"""Rebuild the ChromaDB semantic index from memory_entries (the source of truth).

Usage:
    python scripts/reindex_vectors.py                       # builds data/chromadb_rebuild
    python scripts/reindex_vectors.py --out some/dir --force

The index is derived data, so it can always be rebuilt. Use this when ChromaDB reports
errors such as KeyError '_type' (collections written by a different chromadb version).

The new index is built in a separate directory so a running API (which holds the live one
open) is not disturbed. To switch over: stop the API, rename data/chromadb to a backup,
rename the rebuild directory to data/chromadb, start the API.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the ChromaDB index from memory_entries")
    parser.add_argument("--out", default=str(ROOT / "data" / "chromadb_rebuild"),
                        help="directory for the new index (must not already exist unless --force)")
    parser.add_argument("--force", action="store_true", help="replace --out if it exists")
    args = parser.parse_args()

    out = Path(args.out).resolve()
    if out.exists():
        if not args.force:
            print(f"ERROR: {out} already exists. Use --force to replace it.")
            return 1
        shutil.rmtree(out)

    # Must be set before settings are first read so vector_store writes to --out.
    os.environ["CHROMADB_PATH"] = str(out)

    from core.config import get_settings
    get_settings()
    from core.database import get_db
    from core.utils import new_id
    from memory import vector_store

    if not vector_store._init():
        print("ERROR: ChromaDB / sentence-transformers failed to initialise. See the warning above.")
        return 1

    with get_db() as conn:
        entries = conn.execute(
            """SELECT id, namespace, category, key, value, confidence
               FROM memory_entries WHERE archived = 0 ORDER BY namespace, created_at"""
        ).fetchall()

    ok = failed = 0
    per_ns: dict[str, int] = {}
    for e in entries:
        # Same text and metadata that memory.engine._upsert_vector writes.
        chroma_id = vector_store.upsert(
            memory_id=e["id"],
            namespace=e["namespace"],
            text=f"{e['key']}: {e['value']}",
            metadata={"namespace": e["namespace"], "category": e["category"],
                      "key": e["key"], "confidence": str(e["confidence"])},
        )
        if not chroma_id:
            failed += 1
            print(f"  FAILED  {e['namespace']}  {e['key']}")
            continue
        ok += 1
        per_ns[e["namespace"]] = per_ns.get(e["namespace"], 0) + 1
        with get_db() as conn:
            conn.execute("DELETE FROM memory_vectors WHERE memory_id = ?", (e["id"],))
            conn.execute("INSERT INTO memory_vectors(id, memory_id, chroma_id) VALUES (?, ?, ?)",
                         (new_id(), e["id"], chroma_id))

    print(f"\nIndexed {ok} entries ({failed} failed) into {out}")
    for ns, n in sorted(per_ns.items()):
        print(f"  {ns:20} {n} vectors, collection count = {vector_store.count(ns)}")

    # Sanity check: every namespace must answer a query.
    bad = [ns for ns in per_ns if not vector_store.search("test query", ns, top_k=1)]
    if bad:
        print(f"\nWARNING: no search results from: {', '.join(bad)}")
        return 1
    print("\nSearch check passed for every namespace.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
