"""
scripts/build_package.py
Builds distributable FaiykeOS ZIP package.

Excludes:
  - .env (secrets)
  - data/ (live database + chromadb + backups)
  - vault/workspaces/ (client workspace files)
  - logs/ (runtime logs)
  - outputs/store/ (generated output files)
  - __pycache__ / *.pyc / .pytest_cache
  - .git / .claude / claude/
  - sync/ (local sync state)
  - notifications/ (runtime state)
  - assets/ (large binaries not needed by buyers)
  - *.db / *.db-shm / *.db-wal (database files)

Produces: dist/FaiykeOS-v17.3.zip
"""

import os
import zipfile
import shutil
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

VERSION = "17.3"
ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
OUT_ZIP = DIST_DIR / f"FaiykeOS-v{VERSION}.zip"

# Directories to skip entirely
SKIP_DIRS = {
    ".git",
    ".claude",
    "claude",
    "__pycache__",
    ".pytest_cache",
    "data",
    "logs",
    "sync",
    "notifications",
    "assets",
    "dist",                      # don't include previous builds
}

# Specific sub-paths to skip (relative to ROOT, posix)
SKIP_SUBPATHS = {
    "vault/workspaces",
    "outputs/store",
}

# File extensions to skip
SKIP_EXTS = {".pyc", ".pyo", ".db", ".db-shm", ".db-wal", ".log"}

# Specific filenames to skip
SKIP_FILES = {
    ".env",                      # secrets
    "claudeos.db",
    "claudeos.db-shm",
    "claudeos.db-wal",
    # dev/internal scripts — not for buyers
    "debug_namespaces.py",
    "delete_faiyke_ai.py",
    "fix_faiyke_namespace.py",
    "seed_faiyke.py",
    "apply_supabase_schema.py",
    "import_memory.py",
    "generate_agents_pdf.py",
    "generate_docs.py",
    "md_to_pdf.py",
    "serve_api.py",
    "build_package.py",          # packaging script itself
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def should_skip(path: Path) -> bool:
    """Return True if this path should be excluded from the ZIP."""
    rel = path.relative_to(ROOT)
    parts = rel.parts

    # Skip dirs by name at any depth
    for part in parts[:-1]:        # directory components
        if part in SKIP_DIRS:
            return True

    # Skip specific sub-paths
    for skip in SKIP_SUBPATHS:
        skip_parts = tuple(skip.split("/"))
        if parts[:len(skip_parts)] == skip_parts:
            return True

    # Skip hidden files/dirs (starts with .) except .env.example
    for part in parts:
        if part.startswith(".") and part not in {".env.example", ".gitignore"}:
            return True

    # File-level checks
    if path.is_file():
        if path.name in SKIP_FILES:
            return True
        if path.suffix in SKIP_EXTS:
            return True

    return False


def build_zip():
    DIST_DIR.mkdir(exist_ok=True)

    # Remove previous build
    if OUT_ZIP.exists():
        OUT_ZIP.unlink()
        print(f"Removed old: {OUT_ZIP.name}")

    included = []
    skipped = []

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(ROOT.rglob("*")):
            if path.is_dir():
                continue
            if should_skip(path):
                skipped.append(path.relative_to(ROOT))
                continue

            arcname = Path("FaiykeOS") / path.relative_to(ROOT)
            zf.write(path, arcname)
            included.append(path.relative_to(ROOT))

    size_kb = OUT_ZIP.stat().st_size // 1024
    print(f"\nPackage built: {OUT_ZIP}")
    print(f"Size:          {size_kb:,} KB")
    print(f"Files included:{len(included)}")
    print(f"Files skipped: {len(skipped)}")
    print("\nTop-level contents:")
    top = sorted({str(p).split(os.sep)[0] for p in included})
    for t in top:
        print(f"  FaiykeOS/{t}/")


if __name__ == "__main__":
    build_zip()
