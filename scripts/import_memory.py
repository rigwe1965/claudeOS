"""Seed ClaudeOS memory DB from .claude/memory/ directory."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import get_settings
from memory.importer import import_directory
from scripts.migrate import run_all as run_migrations


def main():
    run_migrations()

    settings = get_settings()
    memory_dir = Path(settings.CLAUDE_MEMORY_PATH)

    print(f"Importing from: {memory_dir}")
    if not memory_dir.exists():
        print(f"  Directory not found: {memory_dir}")
        sys.exit(1)

    results = import_directory(memory_dir, namespace="global")

    print("\nResults:")
    for filename, count in sorted(results.items()):
        status = "OK" if count else "--"
        print(f"  {status}  {filename}")

    total = sum(results.values())
    print(f"\nTotal imported: {total}/{len(results)} files")


if __name__ == "__main__":
    main()
