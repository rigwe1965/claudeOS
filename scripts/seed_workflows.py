"""Seed workflow definitions from YAML files into the database."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import get_settings
from workflows.registry import seed_from_directory

if __name__ == "__main__":
    get_settings()
    count = seed_from_directory()
    print(f"Seeded {count} workflows.")
