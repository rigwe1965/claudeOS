"""Skills page: the skills installed on this machine, what is in them, and which ones you have reviewed.

Admin and operator only (the API enforces it; the nav hides the page from everyone else). Only an admin can approve.
Everything a skill says about itself (name, description, SKILL.md, scan snippets) is untrusted text: it is shown with st.text,
st.code and st.dataframe, never as Markdown or HTML, so a skill cannot put a link, an image or markup on this page.
"""
from __future__ import annotations

import streamlit as st

_VERDICT = {"risky": "Risky", "review": "Needs a look", "ok": "No warnings"}
_STATUS = {"unreviewed": "Not reviewed", "approved": "Approved", "changed": "Changed since approved"}
_SEVERITY = {"high": "High", "medium": "Medium", "low": "Low"}


def _rows(skills):
    return [{
        "Skill": s["name"],
        "Source": s["source"],
        "Scan": _VERDICT.get(s["verdict"], s["verdict"]),
        "Format": "OK" if not s["spec_problems"] else f"{len(s['spec_problems'])} problem(s)",
        "Status": _STATUS.get(s["status"], s["status"]),
        "Fingerprint": s["fingerprint_short"],
        "Files": s["file_count"],
        "Location": s["location"],
    } for s in skills]


def _filtered(skills):
    c1, c2, c3 = st.columns([2, 2, 3])
    status = c1.selectbox("Status", ["All"] + list(_STATUS.values()), key="skills_f_status")
    scan = c2.selectbox("Scan result", ["All"] + list(_VERDICT.values()), key="skills_f_scan")
    text = c3.text_input("Search name or source", key="skills_f_text").strip().lower()
    out = []
    for s in skills:
        if status != "All" and _STATUS.get(s["status"]) != status:
            continue
        if scan != "All" and _VERDICT.get(s["verdict"]) != scan:
            continue
        if text and text not in s["name"].lower() and text not in s["source"].lower():
            continue
        out.append(s)
    return out


def _detail(api_get, api_post, skill_summary, is_admin):
    sid = skill_summary["id"]
    d = api_get(f"/skills/{sid}", timeout=15)
    if not d:
        st.error("Could not open this skill. It may have been moved or deleted: reload the page.")
        return
    st.subheader(d["name"])
    st.text(d["description"] or "(no description)")
    st.caption(f"{d['source']}  ·  {d['location']}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Scan", _VERDICT.get(d["verdict"], d["verdict"]))
    m2.metric("Status", _STATUS.get(d["status"], d["status"]))
    m3.metric("Files", d["file_count"])
    m4.metric("Size", f"{d['size_bytes'] / 1024:.1f} KB")
    st.text(f"Fingerprint (SHA-256): {d['fingerprint']}")
    if d["allowed_tools"]:
        st.text("Tools it asks for: " + ", ".join(d["allowed_tools"]))
    if d["license"]:
        st.text("Licence: " + d["license"])

    if d["status"] == "changed":
        st.warning(f"This skill was approved on {d['approved_at']} by {d['approved_by']}, but its files are different now. "
                   "Read it again before you approve the new version.")
    elif d["status"] == "approved":
        st.success(f"Approved on {d['approved_at']} by {d['approved_by']}. The files are the same as when it was approved."
                   + (f" Note: {d['approved_note']}" if d.get("approved_note") else ""))

    if d["findings"]:
        st.markdown("**Warning signs found**")
        st.dataframe([{"Level": _SEVERITY.get(f["severity"], f["severity"]), "What": f["message"],
                       "Where": f"{f['file']}:{f['line']}" if f["line"] else f["file"], "Text": f["snippet"]} for f in d["findings"]],
                     hide_index=True, width="stretch")
    else:
        st.info("The scan found no warning signs. That is not proof the skill is safe: read it before you trust it.")
    if d["spec_problems"]:
        st.markdown("**Differences from the Agent Skills format** (other tools that read the format may skip this skill)")
        for p in d["spec_problems"]:
            st.text("• " + p)
    if d["notes"]:
        with st.expander("Files that were skipped"):
            for n in d["notes"]:
                st.text("• " + n)

    with st.expander("Files and hashes"):
        st.dataframe([{"File": f["path"], "Bytes": f["size"], "SHA-256": str(f["sha256"])[:16]} for f in d["files"]], hide_index=True, width="stretch")
    with st.expander("Read SKILL.md (the whole skill)"):
        st.code(d["skill_md"] or "(empty)", language="markdown", wrap_lines=True)
        if d.get("skill_md_truncated"):
            st.caption("Only the first part is shown.")

    st.divider()
    if not is_admin:
        st.caption("Only an admin can approve or un-approve a skill.")
        return
    if d["status"] == "approved":
        if st.button("Take the approval back", key=f"skills_revoke_{sid}"):
            if api_post(f"/skills/{sid}/approve", method="DELETE"):
                st.toast("Approval removed")
                st.rerun()
            else:
                st.error("Could not remove the approval.")
        return
    note = st.text_input("Note (optional, for yourself)", max_chars=500, key=f"skills_note_{sid}")
    ack = True
    if d["verdict"] == "risky":
        ack = st.checkbox("I have read the warnings above and still want to approve this skill", key=f"skills_ack_{sid}")
    if st.button("Approve exactly this content", type="primary", disabled=not ack, key=f"skills_approve_{sid}"):
        res = api_post(f"/skills/{sid}/approve", {"fingerprint": d["fingerprint"], "note": note, "acknowledge_risk": bool(ack)})
        if res:
            st.toast("Skill approved")
            st.rerun()
        else:
            st.error("Could not approve it. The skill may have changed while you were reading: reload the page and review it again.")


def render(api_get, api_post, bulk_delete=None):
    st.title("Skills")
    st.caption("The skills installed on this machine: where each one came from, what is in it, and whether you have reviewed it. "
               "Nothing here runs a skill.")
    role = st.session_state.get("user_role", "viewer")
    if role not in ("admin", "operator"):
        st.error("This page is for admins and operators.")
        return

    data = api_get("/skills", timeout=20)
    if not data:
        st.error("Could not load the skill list. Is the API running?")
        return
    skills, counts = data["skills"], data["counts"]

    c = st.columns(5)
    c[0].metric("Skills found", counts["total"])
    c[1].metric("Approved", counts["approved"])
    c[2].metric("Not reviewed", counts["unreviewed"])
    c[3].metric("Changed since approved", counts["changed"])
    c[4].metric("Warnings", counts["risky"] + counts["review"])
    if counts["changed"]:
        st.warning(f"{counts['changed']} approved skill(s) have been edited since you approved them. Filter by status to see which.")
    if counts["risky"]:
        st.error(f"{counts['risky']} skill(s) show serious warning signs. Open them and read the findings.")

    shown = _filtered(skills)
    st.caption(f"Showing {len(shown)} of {len(skills)}")
    if shown:
        st.dataframe(_rows(shown), hide_index=True, width="stretch")
    else:
        st.info("No skill matches these filters." if skills else "No skills were found in the folders below.")

    if shown:
        labels = {s["id"]: f"{s['name']}  ·  {s['source']}  ·  {s['fingerprint_short']}" for s in shown}
        sid = st.selectbox("Open a skill", list(labels), format_func=labels.get, key="skills_open")
        _detail(api_get, api_post, next(s for s in shown if s["id"] == sid), is_admin=(role == "admin"))

    with st.expander("Folders that are scanned"):
        for r in data["roots"]:
            st.text(f"{r['kind']:8}  {r['location']}  ·  " + (f"{r['count']} skill(s)" if r["exists"] else "folder not found"))
        st.caption("Add more with the SKILL_ROOTS setting in .env (separate folders with ; on Windows).")
    st.caption(data.get("note", ""))
