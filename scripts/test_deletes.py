"""Delete endpoint test suite — checks every delete area in the system."""
import requests, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = "http://localhost:5000/api/v1"
results = {}

# Auth
r = requests.post(f"{BASE}/auth/login", json={"username":"admin","password":"Admin123!"}, timeout=5)
if not r.ok:
    print("LOGIN FAILED:", r.status_code, r.text[:200]); sys.exit(1)
tok = r.json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
print("LOGIN OK")

# ─────────────────────────────── MEMORY ───────────────────────────────

# 1. Memory single delete
r = requests.post(f"{BASE}/memory", headers=H,
    json={"key":"_test_del","value":"test","namespace":"global"}, timeout=5)
if r.ok:
    mid = r.json().get("id")
    r2 = requests.delete(f"{BASE}/memory/{mid}", headers=H, timeout=5)
    results["memory_single"] = "PASS" if r2.ok else f"FAIL {r2.status_code} {r2.text[:80]}"
else:
    results["memory_single"] = f"CREATE_FAIL {r.status_code} {r.text[:80]}"

# 2. Memory bulk delete
ids = []
for i in range(3):
    r = requests.post(f"{BASE}/memory", headers=H,
        json={"key":f"_tbulk_{i}","value":"x","namespace":"global"}, timeout=5)
    if r.ok: ids.append(r.json().get("id"))
if ids:
    r2 = requests.delete(f"{BASE}/memory/bulk", headers=H, json={"ids": ids}, timeout=5)
    results["memory_bulk"] = "PASS" if r2.ok else f"FAIL {r2.status_code} {r2.text[:80]}"
else:
    results["memory_bulk"] = "CREATE_FAIL"

# ─────────────────────────── AGENT RUNS ───────────────────────────────

# 3. Agent run soft-delete
runs_r = requests.get(f"{BASE}/agents/runs?limit=1", headers=H, timeout=5)
if runs_r.ok and runs_r.json().get("runs"):
    run_id = runs_r.json()["runs"][0]["id"]
    r2 = requests.delete(f"{BASE}/agents/runs/{run_id}", headers=H, timeout=5)
    results["agent_run_delete"] = "PASS" if r2.ok else f"FAIL {r2.status_code} {r2.text[:80]}"
    if r2.ok:
        r3 = requests.get(f"{BASE}/agents/runs/{run_id}", headers=H, timeout=5)
        results["agent_run_soft_check"] = "PASS (still in DB)" if r3.ok else "WARN: gone from DB"
else:
    results["agent_run_delete"] = "SKIP (no runs)"

# ─────────────────────────── WORKFLOW RUNS ───────────────────────────

# 4. Workflow run delete
wruns = requests.get(f"{BASE}/workflows/runs/all?limit=1", headers=H, timeout=5)
wrun_list = wruns.json() if wruns.ok else []
if isinstance(wrun_list, list) and wrun_list:
    wrid = wrun_list[0]["id"]
    r2 = requests.delete(f"{BASE}/workflows/runs/{wrid}", headers=H, timeout=5)
    results["workflow_run_delete"] = "PASS" if r2.ok else f"FAIL {r2.status_code} {r2.text[:80]}"
else:
    results["workflow_run_delete"] = "SKIP (no runs)"

# ─────────────────────────────── OUTPUTS ──────────────────────────────

# 5. Output single delete
outs = requests.get(f"{BASE}/outputs?namespace=global&limit=1", headers=H, timeout=5)
out_list = outs.json() if outs.ok else []
if isinstance(out_list, list) and out_list:
    oid = out_list[0]["id"]
    r2 = requests.delete(f"{BASE}/outputs/{oid}", headers=H, timeout=5)
    results["output_single"] = "PASS" if r2.ok else f"FAIL {r2.status_code} {r2.text[:80]}"
else:
    results["output_single"] = "SKIP (no outputs)"

# 6. Output bulk delete
outs2 = requests.get(f"{BASE}/outputs?namespace=global&limit=2", headers=H, timeout=5)
out_list2 = outs2.json() if outs2.ok else []
if isinstance(out_list2, list) and out_list2:
    oids = [o["id"] for o in out_list2]
    rb = requests.delete(f"{BASE}/outputs/bulk", headers=H, json={"ids": oids}, timeout=5)
    results["output_bulk"] = "PASS" if rb.ok else f"FAIL {rb.status_code} {rb.text[:80]}"
else:
    results["output_bulk"] = "SKIP (no outputs)"

# ──────────────────────────── API KEYS ────────────────────────────────

# 7. API key single delete
ck = requests.post(f"{BASE}/admin/api-keys", headers=H,
    json={"name":"_test_del_key","namespace":"global","permissions":["read"]}, timeout=5)
if ck.ok:
    kid = ck.json().get("id")
    r2 = requests.delete(f"{BASE}/admin/api-keys/{kid}", headers=H, timeout=5)
    results["api_key_single"] = "PASS" if r2.ok else f"FAIL {r2.status_code} {r2.text[:80]}"
else:
    results["api_key_single"] = f"CREATE_FAIL {ck.status_code} {ck.text[:80]}"

# 8. API key bulk delete
ck2 = requests.post(f"{BASE}/admin/api-keys", headers=H,
    json={"name":"_test_bulk_key","namespace":"global","permissions":["read"]}, timeout=5)
if ck2.ok:
    kid2 = ck2.json().get("id")
    rb = requests.delete(f"{BASE}/admin/api-keys/bulk", headers=H, json={"ids":[kid2]}, timeout=5)
    results["api_key_bulk"] = "PASS" if rb.ok else f"FAIL {rb.status_code} {rb.text[:80]}"
else:
    results["api_key_bulk"] = f"CREATE_FAIL {ck2.status_code} {ck2.text[:80]}"

# ─────────────────────────────── SESSIONS ─────────────────────────────

# 9. Session single revoke (create a throwaway session first)
requests.post(f"{BASE}/auth/login", json={"username":"admin","password":"Admin123!"}, timeout=5)
sess_r = requests.get(f"{BASE}/admin/sessions", headers=H, timeout=5)
sess_list = sess_r.json() if sess_r.ok else []
if isinstance(sess_list, list) and sess_list:
    sid = sess_list[-1]["id"]
    r2 = requests.delete(f"{BASE}/admin/sessions/{sid}", headers=H, timeout=5)
    results["session_revoke"] = "PASS" if r2.ok else f"FAIL {r2.status_code} {r2.text[:80]}"
else:
    results["session_revoke"] = "SKIP (no sessions)"

# 10. Session bulk revoke
requests.post(f"{BASE}/auth/login", json={"username":"admin","password":"Admin123!"}, timeout=5)
sess_r2 = requests.get(f"{BASE}/admin/sessions", headers=H, timeout=5)
sess_list2 = sess_r2.json() if sess_r2.ok else []
if isinstance(sess_list2, list) and sess_list2:
    sids = [sess_list2[-1]["id"]]
    rb = requests.delete(f"{BASE}/admin/sessions/bulk", headers=H, json={"ids": sids}, timeout=5)
    results["session_bulk"] = "PASS" if rb.ok else f"FAIL {rb.status_code} {rb.text[:80]}"
else:
    results["session_bulk"] = "SKIP"

# ─────────────────────────────── TICKETS ──────────────────────────────

# 11. Ticket single delete
ct = requests.post(f"{BASE}/tickets", headers=H,
    json={"title":"_test_del_ticket","description":"test","priority":4,"namespace":"global"}, timeout=5)
if ct.ok:
    tid = ct.json().get("id")
    r2 = requests.delete(f"{BASE}/tickets/{tid}", headers=H, timeout=5)
    results["ticket_single"] = "PASS" if r2.ok else f"FAIL {r2.status_code} {r2.text[:80]}"
else:
    results["ticket_single"] = f"CREATE_FAIL {ct.status_code} {ct.text[:80]}"

# 12. Ticket bulk delete
btids = []
for i in range(2):
    cr = requests.post(f"{BASE}/tickets", headers=H,
        json={"title":f"_bulk_del_{i}","description":"x","priority":4,"namespace":"global"}, timeout=5)
    if cr.ok: btids.append(cr.json().get("id"))
if btids:
    rb = requests.delete(f"{BASE}/tickets/bulk", headers=H, json={"ids": btids}, timeout=5)
    results["ticket_bulk"] = "PASS" if rb.ok else f"FAIL {rb.status_code} {rb.text[:80]}"
else:
    results["ticket_bulk"] = "CREATE_FAIL"

# ─────────────────────────────── SYNC LOG ─────────────────────────────

# 13. Sync log single + bulk
sl = requests.get(f"{BASE}/sync/log?limit=3", headers=H, timeout=5)
log_list = sl.json() if sl.ok else []
if isinstance(log_list, list) and log_list:
    r2 = requests.delete(f"{BASE}/sync/log/{log_list[0]['id']}", headers=H, timeout=5)
    results["sync_log_single"] = "PASS" if r2.ok else f"FAIL {r2.status_code} {r2.text[:80]}"
    if len(log_list) >= 2:
        r3 = requests.delete(f"{BASE}/sync/log", headers=H, json={"ids": [log_list[1]["id"]]}, timeout=5)
        results["sync_log_bulk"] = "PASS" if r3.ok else f"FAIL {r3.status_code} {r3.text[:80]}"
else:
    results["sync_log_single"] = "SKIP (no entries)"

# ──────────────────────────── USER DELETE ─────────────────────────────

# 14. User permanent delete (create via admin endpoint)
from core.database import get_db
with get_db() as conn:
    existing = conn.execute("SELECT id FROM users WHERE username='_testdel'").fetchone()

if existing:
    uid = existing["id"]
else:
    ru = requests.post(f"{BASE}/admin/users", headers=H,
        json={"username":"_testdel","password":"TestDel123!","role":"viewer","namespace":"global"}, timeout=5)
    if ru.ok:
        uid = ru.json().get("id")
    else:
        uid = None
        results["user_perm_delete"] = f"ADMIN_CREATE_FAIL {ru.status_code} {ru.text[:80]}"

if uid and "user_perm_delete" not in results:
    r2 = requests.delete(f"{BASE}/admin/users/{uid}/permanent", headers=H, timeout=5)
    results["user_perm_delete"] = "PASS" if r2.ok else f"FAIL {r2.status_code} {r2.text[:80]}"

# ─────────────────────── RESULTS ──────────────────────────────────────

print("\n=== DELETE TEST RESULTS ===")
fails = []
for k, v in results.items():
    icon = "OK " if "PASS" in v else ("SKP" if "SKIP" in v else "ERR")
    if icon == "ERR": fails.append(k)
    print(f"  [{icon}] {k:30s} {v}")

print(f"\nOVERALL: {'ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails)}")
sys.exit(0 if not fails else 1)
