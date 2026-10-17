# ClaudeOS — Manual QA Test Plan
**Version:** 1.1 | **System:** Flask :5000 + Streamlit :8501
**How to use:** Work top-to-bottom. Mark each item PASS / FAIL / SKIP. Fix all FAILs before client handover.

---

## PRE-FLIGHT (Do this first, every session)

```powershell
# Terminal 1 — start both servers
.\scripts\start.ps1
```

**Wait ~10 seconds, then verify:**

| Check | How | Expected |
|-------|-----|----------|
| Flask alive | Browser → `http://localhost:5000/api/v1/health` | `{"status":"ok"}` |
| Streamlit alive | Browser → `http://localhost:8501` | Login page loads |
| DB exists | File exists: `data/claudeos.db` | File present, non-zero size |
| ChromaDB exists | Folder exists: `data/chromadb` | Folder present |

> If Flask returns nothing: check terminal for import errors. Common cause: missing package → `pip install -r requirements.txt`

---

## SECTION 0 — AUTH (prerequisite for everything)

### 0.1 Login
1. Open `http://localhost:8501`
2. Enter username `admin` + correct password
3. Click Login (or press Enter)

**Expected:** Dashboard loads, sidebar shows all nav items, username visible bottom-left.
**Fail signals:** "Invalid credentials", blank page, spinner that never resolves.

### 0.2 Token auto-refresh (background check)
- Stay logged in for 60+ minutes → dashboard should NOT log you out
- If it does log out: token refresh is broken (check `dashboard/app.py` auto-refresh logic)

### 0.3 Logout
1. Click **Logout** button in sidebar
2. **Expected:** Returns to login page, session cleared

### 0.4 Wrong password lockout
1. Logout, then attempt login with wrong password 5 times
2. **Expected:** Account locked message appears
3. Login as admin → Admin → Users → Unlock the account

---

## SECTION 1 — OVERVIEW PAGE

**Navigate to:** Overview (first item in sidebar)

### 1.1 KPI Cards
**Expected:** Six metric cards visible:
- Memories | Agent Runs | Active Workflows | Projects | Outputs | Open Tickets
- All show numbers (0 is acceptable, "—" or error is NOT)

### 1.2 System Status (admin-visible)
**Expected:** Three status badges visible:
- API Status → green "online"
- Database → green "online"
- ChromaDB → green "online" (or yellow "degraded" if chromadb not indexed yet)

> If Database shows red: Flask can't reach SQLite → restart server

### 1.3 Memory Breakdown
**Expected:** Per-namespace memory entry counts listed (may be 0 if no memories added yet)

### 1.4 Quick Dispatch (agent run from Overview)
1. Select any agent from dropdown
2. Select namespace `global`
3. Type a short prompt: `say hello`
4. Click Run

**Expected:** Response appears in the chat area within 30 seconds, no error banner.
**Fail signals:** "Stream error", "API unreachable", spinner forever.

### 1.5 Live Activity Feed
**Expected:** After completing 1.4, the feed shows the new run with status badge.

### 1.6 Auto-refresh toggle
1. Toggle on **Auto-refresh**
2. Wait 8–10 seconds
3. **Expected:** Page data refreshes without manual reload, no crash

---

## SECTION 2 — AGENTS PAGE

**Navigate to:** Agents

### 2.1 Catalog Tab
1. Click **Catalog** tab
2. **Expected:** Grid of agent cards, each showing name, category badge, model, description
3. Try the search box — type `analysis`
4. **Expected:** Filters to matching agents only

> If "No agents registered" appears: run `python scripts/seed_agents.py` then restart

### 2.2 Basic Chat (text only)
1. Click **Chat** tab
2. Select `analysis-agent` (or any enabled agent)
3. Namespace: `global`
4. Type prompt: `What is 2 + 2?`
5. Press Enter

**Expected:** Streaming response appears token-by-token, ends within 30s. Token count shown below response.

### 2.3 Image Upload (multimodal)
1. In Chat tab, use **Attach** panel to upload any `.jpg` or `.png`
2. Image thumbnail appears below uploader
3. Type prompt: `Describe what you see in this image`
4. Press Enter

**Expected:** Agent responds describing the image content. Response must NOT say "no image received."
**Fail signal:** "only text was received" → image pipeline broken (fixed in commit 291eece — verify server was restarted after that commit)

### 2.4 Multi-turn Conversation
1. Send message: `My name is Test User`
2. Send follow-up: `What is my name?`
3. **Expected:** Agent recalls "Test User" from earlier in conversation

### 2.5 Clear Conversation
1. Click **Clear conversation** button
2. Send: `What is my name?`
3. **Expected:** Agent does NOT recall "Test User" — fresh context
4. **Expected:** Voice input widget also resets (microphone button returns to default state, no previous audio retained)

### 2.6 A2A Agent Card
1. Expand **Agent Card (A2A)** section in left panel
2. **Expected:** JSON block showing agent name, capabilities, endpoint URLs

### 2.7 Run History Tab
1. Click **Run History** tab
2. **Expected:** Table showing recent runs with columns: Agent, Namespace, Status, Quality, Tokens, Duration
3. Runs from steps 2.2–2.4 should appear here

### 2.8 Voice Input (OPTIONAL — requires whisper)
1. Click microphone button, speak a sentence, stop recording
2. **Expected:** Text transcribed and placed in prompt field
3. **If error:** "openai-whisper not installed" → acceptable, mark SKIP

---

## SECTION 3 — MEMORY PAGE

**Navigate to:** Memory

### 3.1 Add a Memory Entry
1. Click **Add Entry** tab
2. Fill in:
   - Namespace: `global`
   - Category: `fact`
   - Key: `test_entry_001`
   - Value: `ClaudeOS QA test entry — created during manual test`
   - Source: `manual_test`
   - Confidence: `1.0`
3. Click **Save**
4. **Expected:** Success message, no error

### 3.2 Browse Entries
1. Click **Browse** tab
2. **Expected:** Table of memory entries, test_entry_001 visible
3. Try the namespace filter — select `global`
4. **Expected:** Filters to global entries only

### 3.3 Text Search
1. Click **Search** tab
2. Mode: `text`
3. Namespace: `global`
4. Query: `QA test entry`
5. **Expected:** test_entry_001 appears in results

### 3.4 Semantic Search
1. Same Search tab
2. Mode: `semantic`
3. Query: `manual testing`
4. **Expected:** Results returned (may include test_entry_001 or related entries)
5. **Fail signal:** Error about ChromaDB → vector DB issue. Check `data/chromadb` folder exists.

### 3.5 Hybrid Search
1. Mode: `both` (hybrid BM25+vector)
2. Same query
3. **Expected:** Combined results, no error

### 3.6 Delete Entry
1. In Browse tab, find test_entry_001
2. Delete it
3. **Expected:** Entry removed from list after refresh

---

## SECTION 4 — WORKFLOWS PAGE

**Navigate to:** Workflows

### 4.1 Workflows List
1. **Workflows** tab
2. **Expected:** List of workflows with trigger type (schedule/manual), enabled toggle, step count
3. If empty: run `python scripts/seed_workflows.py` → restart

### 4.2 Manual Trigger a Workflow
1. Find any workflow with trigger type `manual` or `schedule`
2. Click **Run** / **Trigger** button
3. Context input (optional): leave blank or enter `{"test": true}`
4. Confirm trigger

**Expected:** Success toast or run record appears. No 500 error.

### 4.3 Workflow Run History
1. Click **Run History** tab
2. **Expected:** Table shows the run triggered in 4.2, with status `done` or `running`

### 4.4 Scheduler Tab
1. Click **Scheduler** tab
2. **Expected:** List of scheduled jobs with cron expression and next run time
3. Click **Reload Scheduler**
4. **Expected:** Success message, no crash

### 4.5 Webhooks Tab
1. Click **Webhooks** tab
2. Pick any workflow → click **Enable Webhook**
3. **Expected:** Webhook URL and secret displayed
4. Test via curl (in a new terminal):
```powershell
# Replace <secret> and <workflow-name> with actual values
$secret = "<your-webhook-secret>"
$body = '{"test": true}'
Invoke-WebRequest -Uri "http://localhost:5000/api/v1/workflows/<workflow-name>/trigger" `
  -Method POST `
  -Headers @{"X-Webhook-Secret" = $secret; "Content-Type" = "application/json"} `
  -Body $body
```
**Expected:** HTTP 200 response, run record created

---

## SECTION 5 — PROJECTS PAGE

**Navigate to:** Projects

### 5.1 Namespace List
1. **Namespaces** tab
2. **Expected:** Grid/list of namespaces with name, slug, type, project count
3. Toggle **Show disabled** — disabled namespaces appear if any exist

> If empty: run `python scripts/seed_namespaces.py`

### 5.2 Workspace Stats
1. Click any namespace to expand / select it
2. **Expected:** File counts per subdirectory (documents, outputs, context, etc.)

### 5.3 Projects Tab
1. Click **Projects** tab
2. Select a namespace from dropdown
3. **Expected:** Project cards with name, status badge, priority, tech stack

### 5.4 Create a Project
1. Click **New Project** (or equivalent button)
2. Fill: Name=`QA Test Project`, Namespace=`global`, Status=`active`
3. Save
4. **Expected:** Project appears in list

### 5.5 Context Files
1. Click **Context Files** tab
2. Select namespace `global`
3. Upload a small `.txt` file
4. **Expected:** File appears in context file list for that namespace

---

## SECTION 6 — OUTPUTS PAGE

**Navigate to:** Outputs

> Note: Outputs are auto-created when agents run with "Save output" checked. Ensure you ran at least one agent run with save enabled (Section 2.2).

### 6.1 Browse Outputs
1. **Browse** tab
2. **Expected:** Table of outputs with type icon, title, namespace, tags, size, date
3. Bulk select checkbox works
4. Delete a test output with 2-click confirmation

### 6.2 Search Outputs
1. **Search** tab
2. Query: agent name used in Section 2
3. **Expected:** Matching outputs appear

### 6.3 Export an Output
1. Browse tab → click any output
2. Export as **Markdown**
3. **Expected:** File download or rendered content, no 404/500

### 6.4 Stats Tab
1. **Stats** tab
2. **Expected:** Total count, per-namespace breakdown, per-type breakdown, no error

### 6.5 Agent Attribution on Saved Outputs
1. Run `research-agent` with a prompt and **Save output** checked
2. Run `analysis-agent` with a different prompt and **Save output** checked
3. Navigate to Outputs → Browse

**Expected:** Two output entries — one titled `research-agent — <date>`, one titled `analysis-agent — <date>`. Both use correct agent name, not the same one.
**Fail signal:** Both entries show the same agent name (e.g. both say "analysis-agent") → output save is using frontend selectbox state instead of backend registry. Fixed in commit 2afe202.

---

## SECTION 7 — TICKETS PAGE

**Navigate to:** Tickets

### 7.1 Create a Ticket
1. Click **Create** tab
2. Fill:
   - Title: `QA Test Ticket`
   - Description: `Testing ticket creation during QA`
   - Category: `bug`
   - Priority: `medium`
   - Namespace: `global`
3. Submit
4. **Expected:** Success, ticket appears in Browse tab

### 7.2 Browse Tickets
1. **Browse** tab
2. **Expected:** QA Test Ticket visible, with SLA due date, status=`open`
3. Status filter works (filter by `open`)
4. Priority filter works

### 7.3 Advance Ticket Status
1. Click on QA Test Ticket
2. Change status: `open` → `assigned` → `work_in_progress` → `completed`
3. **Expected:** Each transition saves successfully

### 7.4 My Tickets Tab
1. Click **My Tickets**
2. **Expected:** QA Test Ticket appears (you are creator)

### 7.5 Bulk Delete
1. Browse tab → select QA Test Ticket via checkbox
2. Click **Delete Selected**
3. Confirm
4. **Expected:** Ticket removed

---

## SECTION 8 — OBSERVABILITY PAGE

**Navigate to:** Observability
*(Only visible to admin and operator roles)*

### 8.1 Quality Scores Tab
1. **Expected:** Bar chart of per-agent quality averages (0–5 scale)
2. Scores from agent runs in Section 2 should appear here
3. Agents with 0 runs show 0 or are absent

### 8.2 Latency Tab
1. **Expected:** Table showing p50/p95/p99 latency per agent
2. Agents run in Section 2 should have values

### 8.3 Token Cost Tab
1. **Expected:** Token usage breakdown per agent, cost estimate in USD

### 8.4 Memory Health Tab
1. **Expected:**
   - Total memory entries count
   - Stale entries count
   - Consolidation status (last run time)
   - Suggestion to run consolidation if stale entries > threshold

### 8.5 Namespace Usage Tab
1. **Expected:** Tab visible (admin/operator only)
2. Table showing per-namespace: runs count, input tokens, output tokens, estimated USD cost, avg quality score, memory entries
3. Stacked bar chart (plotly) comparing token usage across namespaces
4. Data based on up to 500 most recent runs — no error on low-run systems (zeros acceptable)

---

## SECTION 9 — SETTINGS PAGE

**Navigate to:** Settings

### 9.1 Email / Notification Config
1. **Expected:** SMTP fields visible (host, port, from, to)
2. Values should match `.env` (smtp.gmail.com, port 587)
3. Edit a field → Save → Reload page → value persists

### 9.2 Supabase Sync Status
1. **Expected:** Status badge visible
2. If Supabase is configured: click **Test Connection** → should return success or clear error
3. Click **Manual Push** → status updates
4. If Supabase not configured: badge shows "not configured" or "disabled" → mark SKIP

### 9.3 Sync Log — Single Entry Delete
1. Scroll to **Sync Log** section (last 50 runs)
2. Find any row in the Individual delete list
3. Click the **🗑** button on that row
4. **Expected:** Success toast, row disappears on rerun
5. **Fail signal:** 404 (entry ID missing) or 500 (delete query error)

### 9.4 Sync Log — Bulk Select & Delete
1. In the Sync Log `st.data_editor`, tick the **✓** checkbox on 2–3 rows
2. **Expected:** "Delete Selected (N)" button becomes enabled, label updates with count
3. Click **Delete Selected (N)**
4. **Expected:** Success toast "Deleted N entries", table refreshes with those rows gone
5. Try clicking **Select All** — **Expected:** editor state clears and all rows become selected on next render
6. Click Delete Selected with 0 rows checked — **Expected:** button is disabled, no action possible

---

## SECTION 10 — ADMIN PAGE

**Navigate to:** Admin
*(Admin role required)*

### 10.1 Users Tab
1. **Expected:** Table of all users with role, namespace, active status
2. Admin user (yourself) visible
3. Click **Create User**:
   - Username: `qa_test_user`
   - Password: `TestUser123!`
   - Role: `viewer`
   - Namespace: `global`
4. **Expected:** User appears in table

### 10.2 API Keys Tab
1. Click **Create API Key**
2. Name: `QA Test Key`, Permissions: `read`, Namespace: `global`
3. **Expected:** Key created, token displayed (copy it — shown only once)
4. Test the key:
```powershell
Invoke-WebRequest -Uri "http://localhost:5000/api/v1/health" `
  -Headers @{"X-API-Key" = "<your-key>"}
```
5. **Expected:** 200 OK

### 10.3 Audit Log Tab
1. **Expected:** Table of recent events (login_success, user_created, etc.)
2. Actions from this test session should appear
3. Filter by event type `login_success` → only login events shown

### 10.4 Sessions Tab
1. **Expected:** List of active sessions with IP, user-agent, expiry
2. Your current session visible
3. Revoke the `qa_test_user` session if one exists → no error

### 10.5 Security Settings Tab
1. **Expected:** Fields for:
   - Max failed attempts (default: 5)
   - Lockout minutes (default: 15)
   - Access token TTL minutes (default: 60)
   - Allow self-registration (toggle)
2. Change a value → Save → **Expected:** Success message, value persists on refresh

### 10.6 Edit User
1. In Users tab, select any non-admin user from the dropdown
2. Click **✏️ Edit** button
3. **Expected:** Dialog opens with current values pre-filled (role, namespace, email, active, force-pw)
4. Change Role to `viewer`, tick **Force password change on next login**
5. Click **Save changes**
6. **Expected:** Toast "User updated", dialog closes, table reflects new values
7. Reopen Edit → verify saved values persist

### 10.7 Delete User (Permanent)
1. Create a fresh test user `qa_delete_test` / `TestUser123!` / role=viewer
2. Select it from the Users dropdown
3. Click **🗑 Delete** button
4. **Expected:** Dialog opens: "Permanently delete qa_delete_test?"
5. Click **Yes, delete permanently**
6. **Expected:** Toast "User permanently deleted", dialog closes, user absent from table
7. Verify: try to log in as `qa_delete_test` → **Expected:** "Invalid credentials" (user gone from DB)

### 10.8 Cleanup test data
1. Delete `qa_test_user` from Users tab (if not already deleted in 10.7)
2. Revoke `QA Test Key` from API Keys tab

### 10.9 Client Onboarding Tab
1. Click **Client Onboarding** tab (6th tab in Admin Panel)
2. **Expected:** Dropdown of client namespaces (not global/personal — client-type only)
3. Select a namespace → 14 fields appear (business name, industry, primary goals, brand tone, SLA tier, contact name, contact email, timezone, preferred language, custom instructions, etc.)
4. Fill in 2–3 fields → click **Save**
5. **Expected:** Success message; navigate away and return — values persist

### 10.10 Admin Unlock (Context-Aware)
1. In Users tab, find a user that is NOT locked
2. **Expected:** No "Unlock" button visible for unlocked users (button only appears when locked)
3. Lock a test account by logging in with wrong password 5 times (from Section 0.4)
4. Return to Admin → Users → find the locked user
5. **Expected:** Lock warning with expiry time AND a prominent Unlock button visible
6. Click Unlock → **Expected:** Lock cleared immediately, user can log in

---

## SECTION 12 — USAGE DASHBOARD (client/viewer only)

**Login as a `client` or `viewer` role user first.**  
Navigate to: **Usage** (📊 in sidebar)

> This page is NOT visible to admin/operator/staff. If logged in as admin, you will see an info message redirecting you to Observability.

### 12.1 KPI Grid
1. **Expected:** Six metric cards visible: AI Runs (30d), Tokens In, Tokens Out, Est. Cost, Avg Quality, Outputs
2. All values load without error (0 is acceptable, error banners are NOT)

### 12.2 Namespace Pulse Score
1. **Expected:** Circular SVG gauge visible showing a score 0–100
2. Label below gauge shows rating: Excellent (≥85) / Good (≥70) / Fair (≥50) / Needs Attention (<50) / Getting Started (no data)
3. Score breakdown table below gauge shows 4 dimensions with weights: Quality Score (40%), Ticket Resolve (30%), Memory Fresh (20%), Workflow OK (10%)

### 12.3 Recent Activity Feed
1. **Expected:** List of recent AI runs for this namespace — agent name (human-readable, not UUID), status badge, timestamp
2. If no runs: empty state message, no error

### 12.4 Memory Summary
1. **Expected:** Memory entry count and freshness indicator visible

---

## SECTION 13 — NAMESPACE BRANDING (admin)

**Navigate to:** Admin → Branding tab (7th tab)

### 13.1 Branding Tab Visible
1. **Expected:** Branding tab is the 7th tab in Admin Panel
2. Dropdown of client namespaces visible (not global)

### 13.2 Set Namespace Brand
1. Select a client namespace
2. Fill in: Company Name = `QA Test Co`, Icon = `🧪`, Primary Color = `#2563EB`, Accent Color = `#3B82F6`
3. Click **Save**
4. **Expected:** Success message

### 13.3 Client Sees Branded Sidebar
1. Log out, log in as a client user assigned to that namespace
2. **Expected:** Sidebar logo area shows `🧪 QA Test Co` instead of raw namespace slug
3. **Expected:** Pill color in aurora hero header matches brand color (approximately)

### 13.4 Cleanup
1. Log back in as admin
2. Admin → Branding → select namespace → clear Company Name and Icon → Save

---

## SECTION 11 — CROSS-CUTTING CHECKS

These apply to ALL pages.

### 11.1 Role Scoping
1. Login as `qa_test_user` (viewer role, created in 10.1 — recreate if deleted)
2. **Expected nav visible:** Overview, Agents, Memory, Projects, Outputs, Tickets, **Usage** (📊)
3. **Expected nav HIDDEN:** Workflows, Observability, Settings, Admin
4. Verify Usage page loads with Pulse Score and KPI grid (not an error page)
5. Try navigating directly to Admin → should redirect to login or show "Access denied"
6. Logout, re-login as admin
7. **Admin nav visible:** Overview, Agents, Memory, Workflows, Projects, Outputs, Tickets, Observability, Settings, Admin
8. **Admin nav HIDDEN:** Usage (admin uses Observability instead)

### 11.2 Dark/Light Mode
1. Click the circular toggle button (bottom area, fixed at `left:220px` — clears sidebar text)
2. **Expected:** Entire dashboard switches theme — background, text, cards, sidebar all update
3. Switch back — state persists during session

### 11.2a Toolbar Header Icons (visual regression)
Check the Streamlit native header bar (top-right: Stop / Deploy / ⋮ menu) in **both** themes.

| Element | Dark Mode Expected | Light Mode Expected |
|---------|-------------------|---------------------|
| Header background | Dark green `#0A1F0A` | White `#ffffff` |
| "Deploy" button text | Light `#E8F5E8` | Dark `#1A1A1A` |
| ⋮ menu button | Three visible dots, transparent bg | Three visible dots, transparent bg |
| No solid squares | No filled square anywhere in header | No filled square anywhere in header |

**Fail signal:** A solid colored square appears next to "Deploy". Root cause: CSS fill override on the MoreVert SVG bounding-box path. Fix: ensure `brand.py` path selectors use `:not([fill="none"])` and JS checks `getAttribute('fill') === 'none'` before setting fill.

### 11.5 Onboarding Tour (first-time user)
1. Create a brand-new user with role `client` or `viewer` (tour ONLY shows for these two roles — admin/operator/staff skip it entirely)
2. Log in as that user for the first time
3. **Expected:** Onboarding tour/modal appears with 5 slides (Welcome, Agents, Memory, Tickets, Usage)
4. Click through or dismiss it
5. Log out, log back in
6. **Expected:** Onboarding does NOT appear again (persisted via `onboarding_done` DB column)
7. **If tour doesn't appear:** Check role — must be `client` or `viewer`. Admin can fix via Users tab → ✏️ Edit → change role

### 11.3 Error Handling
For each page, check:
- No red Python tracebacks visible to user (internal errors should show friendly message)
- No `NoneType` or `KeyError` stack traces in the UI

### 11.4 API Key Auth (alternative to JWT)
```powershell
# Replace with actual API key from Section 10.2
$key = "<your-api-key>"
Invoke-WebRequest "http://localhost:5000/api/v1/agents" -Headers @{"X-API-Key" = $key}
```
**Expected:** 200 with agents list

---

## KNOWN ISSUES TO VERIFY FIXED

| Issue | Fix Commit | How to Verify |
|-------|-----------|---------------|
| Images not sent to agent chat | `291eece` | Section 2.3 — image analysis works |
| Overview stats failed on non-main thread | `bed94f7` | Section 1.1 — KPI cards load without error |
| Browser refresh loses active page | `64c4140` | Navigate to Agents, press F5 — stays on Agents |
| XSS escaping / security hardening | `63a83d6` | Inputs accept text; no script injection renders |
| Voice input widget not clearing on conversation reset | `208d58b` | Section 2.5 — after Clear, microphone widget resets |
| Analysis agent namespace scope warning in logs | `8a36d10` | Run analysis-agent — no scope warning in Flask terminal |
| Workflow run delete broken | `8a36d10` | Section 4.3 — delete a run history entry, no 500 error |
| Theme toggle overlapping sidebar text | `86bbade` | Section 11.2 — toggle at bottom-left (left:220px), clears sidebar |
| Onboarding shows again after logout/re-login | `03366f6` | Complete onboarding, logout, log back in — tour does NOT appear again |
| Memory namespace list hardcoded to local path | `5423ba2` | Memory page namespace filter populates from API, not error |
| Context tiers duplicated when namespace==global | `70860f2` | Run agent in global namespace — no duplicate context in prompt |
| Admin unlock button always visible (not context-aware) | `eba9751` | Section 10.10 — Unlock only shown for actually-locked users |
| Delete User broken (session-state confirm + nested columns) | `528346c` | Section 10.7 — Delete dialog opens, permanent delete works |
| Edit User missing | `528346c` | Section 10.6 — Edit dialog opens, all fields save correctly |
| must_change_password silently dropped on PATCH | `528346c` | Section 10.6 — Force password change toggle saves via Edit dialog |
| Reactivate user broken (api_post PATCH) | `528346c` | Section 10.1 — Deactivate then Reactivate works without error |
| Output delete silently fails on older SQLite | `0cadc72` | Section 6.1 — Delete output, confirm it disappears from list |
| Output timestamps date-only (no time) | `0cadc72` | Section 6.1 — Timestamps show YYYY-MM-DD HH:MM not just date |
| Activity feed shows UUID not agent name | `552e5b3` | Section 1.5 — Feed shows readable agent names, not truncated UUIDs |
| Analysis agent fabricates data when given nothing | `49c6631` | Ask analysis-agent a vague question with no data — it must ask clarifying questions, not invent results |
| Agents hallucinate when input missing | `b1211e5` | Ask briefing/research/writing agents with no context — must request specific inputs, not produce generic output |
| Analysis/client-manager agents use training data for business facts | `87815fb` | Ask analysis-agent "what cities does X deliver to?" with no data — must trigger MISSING INPUT PROTOCOL, not answer from training knowledge; ask client-manager to draft an email — must respond with one-line redirect only |
| Evaluator penalizes correct scope refusals (task_completion: 0.0) | `11f51e5` | Run client-manager-agent on an out-of-scope prompt (e.g. "draft an email") — Observability Quality Scores must show ≥4.0, not near 0 |
| Sync log delete returns "Delete failed" | `26d1d38` | Section 9.3 — delete a sync log entry, confirm it disappears. Was false 404 due to SELECT changes() resetting after commit |
| Voice widget not resetting on Clear Conversation | `b969309` | Section 2.5 — After Clear, microphone widget resets to default state |
| Both outputs from different agents show same agent name | `2afe202` | Section 6.5 — run research-agent then analysis-agent with save; outputs must show correct agent names |
| Stream error message flashes and disappears on rerun | `2afe202` | Run any agent when API is down/exhausted — error must appear as a persistent red message in chat history, not flash once and vanish |
| Output not saving after streaming completes | `2afe202` | Section 6.5 — saved outputs appear in Outputs page immediately after stream finishes; no silent drop |

---

## PASS/FAIL SUMMARY SHEET

Copy this to track results:

```
SECTION 0 — AUTH
  0.1 Login                    [ ]
  0.2 Token refresh            [ ]
  0.3 Logout                   [ ]
  0.4 Lockout                  [ ]

SECTION 1 — OVERVIEW
  1.1 KPI Cards                [ ]
  1.2 System Status            [ ]
  1.3 Memory Breakdown         [ ]
  1.4 Quick Dispatch           [ ]
  1.5 Activity Feed            [ ]
  1.6 Auto-refresh             [ ]

SECTION 2 — AGENTS
  2.1 Catalog                  [ ]
  2.2 Basic Chat               [ ]
  2.3 Image Upload             [ ]
  2.4 Multi-turn               [ ]
  2.5 Clear Conversation       [ ]
  2.6 A2A Agent Card           [ ]
  2.7 Run History              [ ]
  2.8 Voice Input              [SKIP if no whisper]

SECTION 3 — MEMORY
  3.1 Add Entry                [ ]
  3.2 Browse                   [ ]
  3.3 Text Search              [ ]
  3.4 Semantic Search          [ ]
  3.5 Hybrid Search            [ ]
  3.6 Delete Entry             [ ]

SECTION 4 — WORKFLOWS
  4.1 List                     [ ]
  4.2 Manual Trigger           [ ]
  4.3 Run History              [ ]
  4.4 Scheduler                [ ]
  4.5 Webhooks                 [ ]

SECTION 5 — PROJECTS
  5.1 Namespace List           [ ]
  5.2 Workspace Stats          [ ]
  5.3 Projects Tab             [ ]
  5.4 Create Project           [ ]
  5.5 Context Files            [ ]

SECTION 6 — OUTPUTS
  6.1 Browse                   [ ]
  6.2 Search                   [ ]
  6.3 Export                   [ ]
  6.4 Stats                    [ ]
  6.5 Agent Attribution        [ ]

SECTION 7 — TICKETS
  7.1 Create                   [ ]
  7.2 Browse + Filter          [ ]
  7.3 Status Transitions       [ ]
  7.4 My Tickets               [ ]
  7.5 Bulk Delete              [ ]

SECTION 8 — OBSERVABILITY
  8.1 Quality Scores           [ ]
  8.2 Latency                  [ ]
  8.3 Token Cost               [ ]
  8.4 Memory Health            [ ]
  8.5 Namespace Usage          [ ]

SECTION 9 — SETTINGS
  9.1 Email Config             [ ]
  9.2 Supabase Sync            [SKIP if not configured]
  9.3 Sync Log Single Delete   [ ]
  9.4 Sync Log Bulk Delete     [ ]

SECTION 10 — ADMIN
  10.1 Users                   [ ]
  10.2 API Keys                [ ]
  10.3 Audit Log               [ ]
  10.4 Sessions                [ ]
  10.5 Security Settings       [ ]
  10.6 Edit User (dialog)      [ ]
  10.7 Delete User (permanent) [ ]
  10.8 Cleanup                 [ ]
  10.9 Client Onboarding Tab   [ ]
  10.10 Admin Unlock (ctx-aware)[ ]

SECTION 11 — CROSS-CUTTING
  11.1 Role Scoping            [ ]
  11.2 Dark/Light Mode         [ ]
  11.3 Error Handling          [ ]
  11.4 API Key Auth            [ ]
  11.5 Onboarding Tour         [ ]

SECTION 12 — USAGE DASHBOARD
  12.1 KPI Grid                [ ]
  12.2 Pulse Score             [ ]
  12.3 Activity Feed           [ ]
  12.4 Memory Summary          [ ]

SECTION 13 — NAMESPACE BRANDING
  13.1 Branding Tab Visible    [ ]
  13.2 Set Namespace Brand     [ ]
  13.3 Client Sees Branding    [ ]
  13.4 Cleanup                 [ ]

SECTION 14 — COMMERCIAL PACKAGE
  14.1 Build Distribution ZIP  [ ]
  14.2 ZIP Contents Integrity  [ ]
  14.3 Dev Scripts Excluded    [ ]
  14.4 Handbook PDF Integrity  [ ]
  14.5 Landing Pages Load      [ ]
```

---

## SECTION 14 — COMMERCIAL PACKAGE

### 14.1 Build Distribution ZIP
```powershell
python scripts/build_package.py
```
**Expected output:**
- `dist/FaiykeOS-v17.0.zip` created (~475 KB, ~153 files)
- Console shows: `Secret leaks: NONE`, file count, size

**Fail signals:** Python error, zip not created, size 0 KB

### 14.2 ZIP Contents Integrity
```powershell
python -c "
import zipfile
z = zipfile.ZipFile('dist/FaiykeOS-v17.0.zip')
names = z.namelist()
bad = [n for n in names if '.env' in n and 'example' not in n]
print('Secret leaks:', bad if bad else 'NONE')
print('Has handbook:', any('FaiykeOS_Handbook' in n for n in names))
print('Has landing:', any('landing/index.html' in n for n in names))
print('Has requirements:', any('requirements.txt' in n for n in names))
"
```
**Expected:**
- `Secret leaks: NONE` — .env not in ZIP
- `Has handbook: True`
- `Has landing: True`
- `Has requirements: True`

### 14.3 Dev Scripts Excluded
```powershell
python -c "
import zipfile
z = zipfile.ZipFile('dist/FaiykeOS-v17.0.zip')
dev = [n for n in z.namelist() if any(s in n for s in ['debug_namespaces','delete_faiyke','fix_faiyke','seed_faiyke','build_package'])]
print('Dev scripts leaked:', dev if dev else 'NONE')
"
```
**Expected:** `Dev scripts leaked: NONE`

### 14.4 Handbook PDF Integrity
1. Open `docs/FaiykeOS_Handbook_faiyke-ai.pdf`
2. **Expected:** Cover page shows **FaiykeOS** (not ClaudeOS)
3. Footer shows `FaiykeOS v17.0 · faiyke-ai`
4. No duplicate footer on last page

### 14.5 Landing Pages Load
1. Open `docs/landing/index.html` in browser (double-click or `start`)
2. **Expected:** Hero loads with green gradient, "FaiykeOS" heading visible, no broken CSS
3. Open `docs/landing/pricing.html`
4. **Expected:** 3 pricing cards visible ($197 / $997+$147mo / $497+$97mo), comparison table renders

---

## REPORTING A FAILURE

When a test fails, note:
1. **Section + step number** (e.g. "3.4 Semantic Search")
2. **Exact error message** shown in UI
3. **Flask terminal output** — any Python traceback at the time of the failure
4. **Browser console errors** (F12 → Console tab)

This gives enough info to diagnose and fix quickly.
