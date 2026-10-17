"""Seed default namespaces into the database."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import get_settings
from vault.manager import get_namespace_by_slug, create_namespace
from vault.schemas import NamespaceCreate

NAMESPACES = [
    NamespaceCreate(
        slug="global",
        display_name="Global",
        description="System-wide default namespace",
        type="system",
        color="#407E3C",
        icon="",
    ),
    NamespaceCreate(
        slug="reci-transport",
        display_name="RECI Transport Ltd",
        description="Transport & logistics operations — Nigeria",
        type="client",
        color="#1a56db",
        icon="",
    ),
    NamespaceCreate(
        slug="ivycandy-hair",
        display_name="Ivycandy Hair",
        description="Hair brand — products, content, client comms",
        type="client",
        color="#7e3af2",
        icon="",
    ),
    NamespaceCreate(
        slug="faiyke-ai",
        display_name="Faiyke AI",
        description="AI product & SaaS development",
        type="client",
        color="#ff5a1f",
        icon="",
    ),
    NamespaceCreate(
        slug="personal",
        display_name="Personal",
        description="Personal tasks, notes, and projects",
        type="personal",
        color="#0e9f6e",
        icon="",
    ),
]

if __name__ == "__main__":
    get_settings()
    seeded = 0
    for ns_data in NAMESPACES:
        if get_namespace_by_slug(ns_data.slug):
            print(f"  exists  {ns_data.slug}")
        else:
            create_namespace(ns_data)
            print(f"  created {ns_data.slug}")
            seeded += 1
    print(f"Done — {seeded} new namespaces seeded.")
