"""Seed all desktop projects into ClaudeOS vault.
Run from ClaudeOS root: python scripts/seed_faiyke.py
Safe to re-run — skips existing namespaces/projects.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from vault.manager import (
    create_namespace, get_namespace_by_slug,
    create_project, list_projects,
)
from vault.schemas import NamespaceCreate, ProjectCreate


def get_or_create_namespace(slug, display_name, description, ns_type="internal", color="#407E3C", icon="folder"):
    existing = get_namespace_by_slug(slug)
    if existing:
        print(f"[SKIP] Namespace '{slug}' already exists (id={existing.id})")
        return existing
    ns = create_namespace(NamespaceCreate(
        slug=slug,
        display_name=display_name,
        description=description,
        type=ns_type,
        color=color,
        icon=icon,
    ))
    print(f"[OK]   Created namespace: {slug} (id={ns.id})")
    return ns


def get_or_create_project(ns_id, name, slug, description, status, priority, tech_stack, path):
    existing = list_projects(namespace_id=ns_id)
    if any(p.slug == slug for p in existing):
        print(f"[SKIP] Project '{slug}' already exists")
        return
    proj = create_project(ProjectCreate(
        namespace_id=ns_id,
        name=name,
        slug=slug,
        description=description,
        status=status,
        priority=priority,
        tech_stack=tech_stack,
        path=path,
    ))
    print(f"[OK]   Created project: {name} (id={proj.id})")


# ── faIyke (internal AI framework) ───────────────────────────────────────────
ns_faiyke = get_or_create_namespace(
    slug="faiyke",
    display_name="faIyke",
    description="Multi-agent AI system — skills and agents for Claude Code",
    ns_type="internal",
    color="#407E3C",
    icon="robot",
)
get_or_create_project(
    ns_id=ns_faiyke.id,
    name="faIyke Core",
    slug="faiyke-core",
    description="Master agent + 7 specialized agents + 9 reusable skills. Claude Code multi-agent framework.",
    status="active",
    priority=1,
    tech_stack=["python", "claude-code", "yaml"],
    path=r"C:\Users\rigwe\Desktop\faIyke",
)
# ── Website / Client Portal ───────────────────────────────────────────────────
ns_website = get_or_create_namespace(
    slug="website-portal",
    display_name="Website",
    description="Flask client portal — admin/staff/client roles, project & ticket management",
    ns_type="client",
    color="#2E6DA4",
    icon="globe",
)
get_or_create_project(
    ns_id=ns_website.id,
    name="Client Portal",
    slug="client-portal",
    description="Flask web app with auth, admin dashboard, staff view, client portal, project and ticket tracking.",
    status="active",
    priority=1,
    tech_stack=["python", "flask", "sqlite", "html", "css", "javascript"],
    path=r"C:\Users\rigwe\Desktop\Website\portal",
)

# ── RECI Transport (client) ───────────────────────────────────────────────────
ns_reci = get_or_create_namespace(
    slug="reci-transport",
    display_name="RECI Transport",
    description="Client: RECI Transport Ltd — internal dashboard for clients, bookings, and revenue",
    ns_type="client",
    color="#C0392B",
    icon="truck",
)
get_or_create_project(
    ns_id=ns_reci.id,
    name="Client Dashboard",
    slug="reci-client-dashboard",
    description="Streamlit dashboard tracking clients, bookings, and revenue for RECI Transport Ltd.",
    status="active",
    priority=1,
    tech_stack=["python", "streamlit", "pandas", "plotly"],
    path=r"C:\Users\rigwe\Desktop\reci-transport-client-dashboard",
)

# ── Ivycandy Hair (client) ────────────────────────────────────────────────────
ns_ivy = get_or_create_namespace(
    slug="ivycandy-hair",
    display_name="Ivycandy Hair",
    description="Client: Ivycandy Hair — brand design system and booking process app",
    ns_type="client",
    color="#8E44AD",
    icon="scissors",
)
get_or_create_project(
    ns_id=ns_ivy.id,
    name="Design System",
    slug="ivycandy-design-system",
    description="Complete brand identity and component library built from competitive analysis of top 5 human hair stores.",
    status="active",
    priority=1,
    tech_stack=["html", "css", "javascript"],
    path=r"C:\Users\rigwe\Desktop\IvycandyHair-DesignSystem",
)
get_or_create_project(
    ns_id=ns_ivy.id,
    name="Hair Process App",
    slug="ivycandy-hair-process",
    description="Node.js application for Ivycandy Hair booking/process management.",
    status="active",
    priority=2,
    tech_stack=["javascript", "node", "express"],
    path=r"C:\Users\rigwe\Desktop\ivycandy-hair-process",
)

# ── Internal Tools ────────────────────────────────────────────────────────────
ns_tools = get_or_create_namespace(
    slug="internal-tools",
    display_name="Internal Tools",
    description="Personal productivity tools and dashboards built for Claude Code workflows",
    ns_type="internal",
    color="#27AE60",
    icon="wrench",
)
get_or_create_project(
    ns_id=ns_tools.id,
    name="Claude Code Usage Dashboard",
    slug="claudecode-usage-dashboard",
    description="Local token usage dashboard — reads ~/.claude/ logs, tracks and visualizes token spend across sessions.",
    status="active",
    priority=2,
    tech_stack=["python", "streamlit", "sqlite"],
    path=r"C:\Users\rigwe\Desktop\ClaudeCodeUsageDashboard",
)
get_or_create_project(
    ns_id=ns_tools.id,
    name="Research Agent",
    slug="research-agent",
    description="Structured research agent — outputs saved research by topic and date.",
    status="active",
    priority=2,
    tech_stack=["python", "claude-code", "markdown"],
    path=r"C:\Users\rigwe\Desktop\ResearchAgent",
)
get_or_create_project(
    ns_id=ns_tools.id,
    name="Task Manager",
    slug="task-manager",
    description="Task/project management dashboard with tab filtering, delete/restore, and progress tracking.",
    status="active",
    priority=2,
    tech_stack=["python", "javascript", "html", "css"],
    path=r"C:\Users\rigwe\Desktop\task-manager",
)

# ── SuperClaude (reference) ───────────────────────────────────────────────────
ns_super = get_or_create_namespace(
    slug="superclaude",
    display_name="SuperClaude",
    description="SuperClaude open-source framework — reference and contribution tracking",
    ns_type="internal",
    color="#E67E22",
    icon="star",
)
get_or_create_project(
    ns_id=ns_super.id,
    name="SuperClaude Framework",
    slug="superclaude-core",
    description="Open-source Claude Code enhancement framework with commands, personas, and PM agent.",
    status="active",
    priority=3,
    tech_stack=["python", "claude-code", "yaml", "markdown"],
    path=r"C:\Users\rigwe\Desktop\SuperClaude",
)

print("\nAll done. Refresh ClaudeOS dashboard -> Client Vault -> Projects.")
print("Namespaces created: faiyke, website-portal, reci-transport, ivycandy-hair, internal-tools, superclaude")
