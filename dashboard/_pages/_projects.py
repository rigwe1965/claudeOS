"""Client Vault page — namespaces, projects, workspace stats."""
import re
import json
from pathlib import Path

import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed


PRIORITY_LABELS = {1: "High", 2: "Medium", 3: "Low"}
STATUS_ICONS = {"active": "●", "paused": "○", "archived": "×"}


def render(api_get, api_post, bulk_delete=None):
    st.title("Client Vault")

    # Fetch namespaces once — shared across all three tabs
    namespaces = api_get("/namespaces") or []

    tab_ns, tab_proj, tab_ctx = st.tabs(["Namespaces", "Projects", "Context Files"])

    with tab_ns:
        _render_namespaces(api_get, api_post, namespaces)

    with tab_proj:
        _render_projects(api_get, api_post, namespaces)

    with tab_ctx:
        _render_context(api_get, api_post, namespaces)


def _render_namespaces(api_get, api_post, namespaces: list):
    role = st.session_state.get("user_role", "admin")
    user_ns = st.session_state.get("user_namespace")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("Namespaces")
    with col2:
        show_all = st.toggle("Show disabled", value=False) if role in ("admin", "operator") else False

    # Use pre-fetched list; re-fetch only if user toggled "show disabled"
    if show_all:
        all_namespaces = api_get("/namespaces?enabled=false") or []
    else:
        all_namespaces = namespaces
    # Clients see only their namespace
    if role in ("client", "viewer") and user_ns:
        namespaces = [ns for ns in all_namespaces if ns.get("slug") == user_ns]
    else:
        namespaces = all_namespaces

    if not namespaces:
        st.info("No namespaces found. Run `python scripts/seed_namespaces.py`")
    else:
        # Fetch workspace stats + projects for all namespaces in parallel
        slugs = [ns["slug"] for ns in namespaces]
        ws_results: dict = {}
        proj_results: dict = {}
        if slugs:
            with ThreadPoolExecutor(max_workers=min(len(slugs) * 2, 10)) as ex:
                ws_futs   = {ex.submit(api_get, f"/namespaces/{s}/workspace"): s for s in slugs}
                proj_futs = {ex.submit(api_get, f"/projects?namespace={s}"): s for s in slugs}
                for f in as_completed(ws_futs):
                    ws_results[ws_futs[f]] = f.result()
                for f in as_completed(proj_futs):
                    proj_results[proj_futs[f]] = f.result()

        for ns in namespaces:
            color = ns.get("color", "#407E3C")
            enabled = ns.get("enabled", True)
            badge = "●" if enabled else "○"

            with st.expander(f"{badge} **{ns['display_name']}** `{ns['slug']}`"):
                col_info, col_stats, col_actions = st.columns([2, 2, 1])

                with col_info:
                    st.markdown(f"**Type:** `{ns.get('type','?')}`")
                    st.markdown(f"**Description:** {ns.get('description','—')}")
                    st.markdown(f"**Color:** `{color}`")

                with col_stats:
                    ws = ws_results.get(ns["slug"])
                    if ws and ws.get("workspace"):
                        for subdir, stat in ws["workspace"].items():
                            fc = stat.get("file_count", 0)
                            kb = round(stat.get("size_bytes", 0) / 1024, 1)
                            st.markdown(f"**{subdir}:** {fc} files · {kb} KB")

                with col_actions:
                    projects = proj_results.get(ns["slug"]) or []
                    st.metric("Projects", len(projects))

    st.markdown("---")
    if role in ("admin", "operator"):
        with st.expander("+ New Namespace"):
            _new_namespace_form(api_post)


def _render_projects(api_get, api_post, namespaces: list):
    st.subheader("Projects")

    role = st.session_state.get("user_role", "admin")
    user_ns = st.session_state.get("user_namespace")

    # Clients/viewers see only their namespace — no cross-namespace access
    if role in ("client", "viewer") and user_ns:
        namespaces = [ns for ns in namespaces if ns.get("slug") == user_ns]

    ns_options = {ns["display_name"]: ns["slug"] for ns in namespaces}
    # Only admins/operators get "All" option
    if role in ("admin", "operator"):
        ns_options = {"All": None, **ns_options}

    col1, col2 = st.columns(2)
    with col1:
        selected_ns_name = st.selectbox("Filter by namespace", list(ns_options.keys()), key="proj_ns_filter")
    with col2:
        status_filter = st.selectbox("Status", ["all", "active", "paused", "archived"], key="proj_status_filter")

    ns_slug = ns_options[selected_ns_name]
    url = "/projects"
    params = []
    if ns_slug:
        params.append(f"namespace={ns_slug}")
    if status_filter != "all":
        params.append(f"status={status_filter}")
    if params:
        url += "?" + "&".join(params)

    projects = api_get(url) or []

    if not projects:
        st.info("No projects found.")
    else:
        for proj in projects:
            status = proj.get("status", "active")
            priority = proj.get("priority", 2)
            sicon = STATUS_ICONS.get(status, "•")
            plabel = PRIORITY_LABELS.get(priority, "")

            with st.expander(f"{sicon} **{proj['name']}** `{proj['slug']}` — {plabel}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**Description:** {proj.get('description','—')}")
                    stack = proj.get("tech_stack") or []
                    if stack:
                        st.markdown(f"**Stack:** {' · '.join(f'`{t}`' for t in stack)}")
                    if proj.get("path"):
                        st.markdown(f"**Path:** `{proj['path']}`")
                    st.caption(f"Created: {(proj.get('created_at') or '')[:10]}")
                with col2:
                    new_status = st.selectbox(
                        "Status",
                        ["active", "paused", "archived"],
                        index=["active", "paused", "archived"].index(status),
                        key=f"status_{proj['id']}",
                    )
                    if st.button("Update", key=f"upd_{proj['id']}", width='stretch'):
                        api_post(f"/projects/{proj['id']}", {"status": new_status}, method="PATCH")
                        st.rerun()

    # Project creation is admin/operator-only in the API; the attach scan reads the server filesystem
    if role in ("admin", "operator"):
        st.markdown("---")
        with st.expander("+ New Project"):
            _new_project_form(api_post, namespaces)

        with st.expander("Attach Existing Project"):
            _attach_project_form(api_post, namespaces)


def _render_context(api_get, api_post, namespaces: list):
    st.subheader("Context Files")
    st.caption("Per-namespace context injected into agent prompts.")

    role = st.session_state.get("user_role", "admin")
    user_ns = st.session_state.get("user_namespace")
    if role in ("client", "viewer") and user_ns:
        namespaces = [ns for ns in namespaces if ns.get("slug") == user_ns]

    if not namespaces:
        st.info("No namespaces.")
        return

    ns_names = {ns["display_name"]: ns["slug"] for ns in namespaces}
    selected = st.selectbox("Namespace", list(ns_names.keys()), key="ctx_ns_select")
    slug = ns_names[selected]

    files = api_get(f"/namespaces/{slug}/context")
    file_list = files.get("files", []) if files else []

    if file_list:
        st.markdown(f"**{len(file_list)} context files in `{slug}`:**")
        for fname in file_list:
            st.markdown(f"- `{fname}`")
    else:
        st.info("No context files yet.")

    st.markdown("---")

    # ── Upload files ──────────────────────────────────────────────────────────
    st.markdown("**Upload context file(s):**")
    uploaded_files = st.file_uploader(
        "Upload files",
        accept_multiple_files=True,
        key="ctx_file_upload",
        label_visibility="collapsed",
        help="Files are decoded as UTF-8 and saved to this namespace's context directory.",
    )
    if uploaded_files:
        all_ok = True
        for uf in uploaded_files:
            safe_name = Path(uf.name).name
            try:
                content = uf.read().decode("utf-8")
            except UnicodeDecodeError:
                st.warning(f"Skipped `{safe_name}` — not valid UTF-8 (binary file).")
                all_ok = False
                continue
            except Exception as e:
                st.warning(f"Skipped `{safe_name}` — read error: {e}")
                all_ok = False
                continue
            result = api_post(f"/namespaces/{slug}/context", {"filename": safe_name, "content": content})
            if result:
                st.success(f"Uploaded `{safe_name}` to `{slug}`")
            else:
                st.error(f"Failed to save `{safe_name}`")
                all_ok = False
        if all_ok:
            st.rerun()

    st.markdown("---")
    st.markdown("**Or write context file manually:**")
    filename = st.text_input("Filename", value="notes.md", key="ctx_filename")
    content = st.text_area("Content", height=150, key="ctx_content",
                           placeholder="Background info, preferences, or instructions for this namespace's agents.")
    if st.button("Save Context File", width='stretch'):
        result = api_post(f"/namespaces/{slug}/context", {"filename": filename, "content": content})
        if result:
            st.success(f"Saved `{filename}` to `{slug}`")
            st.rerun()
        else:
            st.error("Save failed")


# ── Directory scan ────────────────────────────────────────────────────────────

def _scan_directory(path_str: str) -> dict:
    """Scan a local directory and infer project metadata. Never raises."""
    result = {"ok": False, "error": None, "name": "", "slug": "", "description": "", "tech_stack": []}

    if st.session_state.get("user_role") not in ("admin", "operator"):
        result["error"] = "Not permitted."
        return result

    try:
        p = Path(path_str.strip())
    except Exception:
        result["error"] = "Invalid path string."
        return result

    if not p.exists():
        result["error"] = f"Path does not exist: {path_str}"
        return result
    if not p.is_dir():
        result["error"] = f"Path is a file, not a directory: {path_str}"
        return result

    # Name from directory
    raw_name = p.name or (p.parts[-1] if p.parts else "project")
    result["name"] = raw_name

    # Slug: lowercase, spaces/underscores/dots → hyphens, strip non-alphanum-hyphen
    slug = raw_name.lower()
    slug = re.sub(r'[\s_\.]+', '-', slug)
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    result["slug"] = slug or "project"

    # Description from CLAUDE.md or README.md
    description = ""
    for readme_name in ("CLAUDE.md", "README.md", "readme.md", "Readme.md"):
        readme = p / readme_name
        if readme.exists():
            try:
                text = readme.read_text(encoding="utf-8", errors="replace")
                lines = text.splitlines()
                para_lines = []
                in_para = False
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        if in_para:
                            break
                        continue
                    if stripped == "":
                        if in_para:
                            break
                        continue
                    in_para = True
                    para_lines.append(stripped)
                description = " ".join(para_lines)[:300]
            except Exception:
                pass
            if description:
                break
    result["description"] = description

    # Tech stack detection
    tech: set[str] = set()

    # Python
    if any([
        (p / "requirements.txt").exists(),
        (p / "pyproject.toml").exists(),
        (p / "setup.py").exists(),
        bool(list(p.glob("*.py"))),
    ]):
        tech.add("Python")

    # Python frameworks via requirements.txt
    req = p / "requirements.txt"
    if req.exists():
        try:
            req_text = req.read_text(encoding="utf-8", errors="replace").lower()
            for fw in ("flask", "django", "fastapi", "streamlit"):
                if fw in req_text:
                    tech.add(fw.capitalize())
        except Exception:
            pass

    # Python frameworks via pyproject.toml
    pyp = p / "pyproject.toml"
    if pyp.exists():
        try:
            pyp_text = pyp.read_text(encoding="utf-8", errors="replace").lower()
            for fw in ("flask", "django", "fastapi", "streamlit"):
                if fw in pyp_text:
                    tech.add(fw.capitalize())
        except Exception:
            pass

    # Node / JS
    pkg_json = p / "package.json"
    if pkg_json.exists():
        tech.add("Node.js")
        try:
            pkg = json.loads(pkg_json.read_text(encoding="utf-8", errors="replace"))
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            dep_keys = {k.lower() for k in deps}
            if "react" in dep_keys:
                tech.add("React")
            if "next" in dep_keys:
                tech.add("Next.js")
            if "vue" in dep_keys:
                tech.add("Vue.js")
            if "svelte" in dep_keys:
                tech.add("Svelte")
            if "typescript" in dep_keys or (p / "tsconfig.json").exists():
                tech.add("TypeScript")
        except Exception:
            pass

    # TypeScript files
    if list(p.glob("*.ts")) or list(p.glob("*.tsx")):
        tech.add("TypeScript")

    # Docker
    if any([
        (p / "Dockerfile").exists(),
        (p / "docker-compose.yml").exists(),
        (p / "docker-compose.yaml").exists(),
    ]):
        tech.add("Docker")

    # SQL
    if list(p.glob("*.sql")) or (p / "migrations").exists():
        tech.add("SQL")

    # Go
    if (p / "go.mod").exists():
        tech.add("Go")

    # Rust
    if (p / "Cargo.toml").exists():
        tech.add("Rust")

    result["tech_stack"] = sorted(tech)
    result["ok"] = True
    return result


# ── Forms ─────────────────────────────────────────────────────────────────────

def _attach_project_form(api_post, namespaces: list):
    ns_map = {ns["display_name"]: ns["id"] for ns in namespaces}
    if not ns_map:
        st.info("Create a namespace first.")
        return

    # Path input + scan — must come BEFORE field widgets to avoid session_state key conflict
    path_input = st.text_input(
        "Project directory path",
        key="attach_path",
        placeholder=r"C:\Users\you\Desktop\MyProject",
    )

    scan_clicked = st.button("Scan Directory", key="attach_scan_btn")
    if scan_clicked:
        if path_input.strip():
            result = _scan_directory(path_input.strip())
            if not result["ok"]:
                st.error(result["error"])
                for k in ("attach_scan_result", "attach_name", "attach_slug", "attach_desc", "attach_stack"):
                    st.session_state.pop(k, None)
            else:
                st.session_state["attach_scan_result"] = result
                st.session_state["attach_name"]  = result["name"]
                st.session_state["attach_slug"]  = result["slug"]
                st.session_state["attach_desc"]  = result["description"]
                st.session_state["attach_stack"] = ", ".join(result["tech_stack"])
                stack_display = ", ".join(f"`{t}`" for t in result["tech_stack"]) or "none detected"
                st.success(f"Scanned — detected stack: {stack_display}")
        else:
            st.warning("Enter a directory path first.")

    st.markdown("---")

    # Editable fields (pre-filled from scan via session_state)
    selected_ns = st.selectbox("Namespace", list(ns_map.keys()), key="attach_proj_ns")

    name = st.text_input(
        "Project Name",
        key="attach_name",
        value=st.session_state.get("attach_name", ""),
    )
    slug = st.text_input(
        "Slug",
        key="attach_slug",
        value=st.session_state.get("attach_slug", ""),
    )
    description = st.text_input(
        "Description",
        key="attach_desc",
        value=st.session_state.get("attach_desc", ""),
    )
    stack_raw = st.text_input(
        "Tech Stack (comma-separated)",
        key="attach_stack",
        value=st.session_state.get("attach_stack", ""),
        placeholder="Python, Flask, Streamlit",
    )
    priority = st.selectbox(
        "Priority", [1, 2, 3],
        format_func=lambda x: PRIORITY_LABELS[x],
        key="attach_proj_priority",
    )

    if st.button("Attach Project", key="attach_proj_btn", width='stretch'):
        if name.strip() and slug.strip():
            tech_stack = [s.strip() for s in stack_raw.split(",") if s.strip()]
            result = api_post("/projects", {
                "namespace_id": ns_map[selected_ns],
                "name": name.strip(),
                "slug": slug.strip(),
                "description": description.strip(),
                "tech_stack": tech_stack,
                "priority": priority,
                "path": path_input.strip(),
            })
            if result:
                for k in ("attach_scan_result", "attach_name", "attach_slug", "attach_desc", "attach_stack"):
                    st.session_state.pop(k, None)
                st.success(f"Attached project `{slug.strip()}`")
                st.rerun()
            else:
                st.error("Attach failed — slug may already exist in this namespace")
        else:
            st.warning("Name and slug required")


def _new_namespace_form(api_post):
    slug = st.text_input("Slug (e.g. my-client)", key="new_ns_slug")
    display_name = st.text_input("Display Name", key="new_ns_name")
    description = st.text_input("Description", key="new_ns_desc")
    ns_type = st.selectbox("Type", ["client", "personal", "system"], key="new_ns_type")
    color = st.color_picker("Color", value="#407E3C", key="new_ns_color")
    icon = st.text_input("Icon (text, optional)", value="", key="new_ns_icon")
    if st.button("Create Namespace", width='stretch', key="create_ns_btn"):
        if slug and display_name:
            result = api_post("/namespaces", {
                "slug": slug, "display_name": display_name,
                "description": description, "type": ns_type,
                "color": color, "icon": icon,
            })
            if result:
                st.success(f"Created namespace `{slug}`")
                st.rerun()
            else:
                st.error("Create failed — slug may already exist")
        else:
            st.warning("Slug and display name required")


def _new_project_form(api_post, namespaces: list):
    ns_map = {ns["display_name"]: ns["id"] for ns in namespaces}
    if not ns_map:
        st.info("Create a namespace first.")
        return

    selected_ns = st.selectbox("Namespace", list(ns_map.keys()), key="new_proj_ns")
    name = st.text_input("Project Name", key="new_proj_name")
    slug = st.text_input("Slug", key="new_proj_slug")
    description = st.text_input("Description", key="new_proj_desc")
    stack_raw = st.text_input("Tech Stack (comma-separated)", key="new_proj_stack",
                               placeholder="Python, Flask, Streamlit")
    priority = st.selectbox("Priority", [1, 2, 3],
                             format_func=lambda x: PRIORITY_LABELS[x], key="new_proj_priority")
    if st.button("Create Project", width='stretch', key="create_proj_btn"):
        if name and slug:
            tech_stack = [s.strip() for s in stack_raw.split(",") if s.strip()]
            result = api_post("/projects", {
                "namespace_id": ns_map[selected_ns],
                "name": name, "slug": slug,
                "description": description,
                "tech_stack": tech_stack,
                "priority": priority,
            })
            if result:
                st.success(f"Created project `{slug}`")
                st.rerun()
            else:
                st.error("Create failed — slug may already exist in this namespace")
        else:
            st.warning("Name and slug required")
