"""Load all agent YAML definitions into the ClaudeOS DB."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.migrate import run_all as run_migrations
from agents.registry import seed_from_directory, list_agents, DEFINITIONS_DIR


def main():
    run_migrations()

    print(f"Seeding agents from: {DEFINITIONS_DIR}")
    count = seed_from_directory()
    print(f"Seeded {count} agents.")

    agents = list_agents(enabled_only=False)
    print(f"\nRegistered agents ({len(agents)}):")
    for a in agents:
        status = "ON" if a.enabled else "off"
        print(f"  [{status}] {a.name:<30} {a.category}")


if __name__ == "__main__":
    main()
