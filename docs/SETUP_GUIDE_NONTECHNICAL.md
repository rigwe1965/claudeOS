# FaiykeOS — Setup Guide for Business Owners
**No technical experience required. Follow each step in order.**

---

## Before You Start — What You Need

Gather these four things before beginning:

| Item | Where to Get It | Cost |
|------|----------------|------|
| A computer or server | You already have this | — |
| An Anthropic API key | console.anthropic.com → Create account → API Keys | Free to create; pay per use |
| Python 3.11 installed | python.org/downloads | Free |
| FaiykeOS files | Provided after purchase | Included |

> **Tip:** If you have a Windows laptop or PC, you can run FaiykeOS on it today. You do not need a special server to get started.

---

## Part 1 — Get Your Anthropic API Key

1. Go to **console.anthropic.com** in your browser
2. Click **Sign Up** and create an account
3. Once logged in, click **API Keys** in the left menu
4. Click **Create Key** — give it a name like `FaiykeOS`
5. **Copy the key and save it somewhere safe** — it starts with `sk-ant-`
6. Add a payment method in **Billing** (you only pay for what you use — typically $5–$20/month for a small team)

---

## Part 2 — Install Python

1. Go to **python.org/downloads**
2. Download Python **3.11** (not 3.12 or 3.13 — use 3.11 for best compatibility)
3. Run the installer
4. **Important:** On the first screen, tick the box that says **"Add Python to PATH"**
5. Click **Install Now**
6. When done, click **Close**

**Verify it worked:**
- Press `Windows + R`, type `cmd`, press Enter
- In the black window, type: `python --version`
- You should see: `Python 3.11.x`

---

## Part 3 — Set Up the FaiykeOS Files

1. Extract the FaiykeOS ZIP file you received — put it in a folder you can find easily, like `C:\FaiykeOS\`
2. Open the folder — you should see files like `requirements.txt`, `CLAUDE.md`, and folders like `agents/`, `dashboard/`, `core/`

---

## Part 4 — Open a Command Window Inside the Folder

1. In File Explorer, navigate to your FaiykeOS folder
2. Click in the address bar at the top (where it shows the folder path)
3. Type `cmd` and press Enter
4. A black command window opens already in the right folder

> All commands in the next steps are typed into this black window. Press Enter after each one.

---

## Part 5 — Install Required Packages

Type this command and press Enter. It will take 5–10 minutes on the first run:

```
pip install -r requirements.txt
```

You will see a lot of text scrolling. When it stops and you see a `>` prompt again, it is done.

---

## Part 6 — Create Your Settings File

1. In File Explorer, find the file called `.env.example` inside the FaiykeOS folder
2. Copy it and rename the copy to `.env` (remove the word "example")
3. Right-click `.env` → Open with → Notepad
4. Find the line that says `ANTHROPIC_API_KEY=` and paste your key after the `=`:
   ```
   ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE
   ```
5. Find the line `CLAUDEOS_SECRET_KEY=` and type any long random phrase (at least 32 characters):
   ```
   CLAUDEOS_SECRET_KEY=my-super-secret-key-for-faiykeOS-2026
   ```
6. Find (or add) the line `SCHEDULER_TIMEZONE=` and set it to your local timezone:
   ```
   SCHEDULER_TIMEZONE=Europe/Berlin
   ```
   Common values: `UTC`, `Europe/London`, `America/New_York`, `America/Los_Angeles`, `Asia/Lagos`, `Africa/Lagos`. This controls when scheduled workflows and daily backups run. If you skip this, it defaults to `Europe/Berlin`.

7. Save the file (`Ctrl + S`)

---

## Part 7 — Set Up the Database

In the command window, run these commands one by one (press Enter after each):

```
python scripts/migrate.py
```
*(Creates the database — takes a few seconds)*

```
python scripts/seed_agents.py
```
*(Loads the 12 AI agents)*

```
python scripts/seed_workflows.py
```
*(Loads the 7 workflow pipelines)*

```
python scripts/seed_namespaces.py
```
*(Creates your workspace)*

---

## Part 8 — Create Your Admin Account

Replace `YourName` and `YourPassword` with your actual choice:

```
python scripts/create_admin.py --username YourName --password YourPassword123!
```

**Password rules:** at least 10 characters, one uppercase letter, one lowercase letter, one number.

Write down your username and password — you will need them to log in.

---

## Part 9 — Start FaiykeOS

```
.\scripts\start.ps1
```

Wait about 10 seconds. You will see messages saying Flask and Streamlit are running.

---

## Part 10 — Open in Your Browser

Open your web browser (Chrome, Edge, or Firefox) and go to:

```
http://localhost:8501
```

The FaiykeOS login page appears. Enter the username and password you created in Part 8.

**You are in!** 🎉

---

## First Things to Do After Login

### 1. Run your first AI agent
- Click **Agents** in the left menu
- Click the **Chat** tab
- Select **briefing-agent** from the dropdown
- Type: `Give me a brief introduction to what you can do`
- Press Enter and watch the response stream in

> **Tip:** You can also attach images or document files to your message using the 📎 icon in the chat bar — useful for sharing screenshots, reports, or notes with an agent.

### 2. Add some memory about your business
- Click **Memory** in the left menu
- Click **Add Entry**
- Category: `fact`
- Key: `business.name`
- Value: your business name
- Click **Save**

Now every agent knows your business name automatically.

### 3. Explore the catalog
- Click **Agents** → **Catalog** tab
- See all 12 agents and what they each do
- **Click any card** to go straight to Chat with that agent already selected — no need to use the dropdown

---

## Starting FaiykeOS After Restart

Every time you restart your computer, you need to start FaiykeOS again. Open a command window in your FaiykeOS folder and run:

```
.\scripts\start.ps1
```

Then open `http://localhost:8501` in your browser.

---

## Common Problems

| Problem | Solution |
|---------|----------|
| "pip is not recognised" | Reinstall Python and tick "Add Python to PATH" during install |
| "Python is not recognised" | Reinstall Python and tick "Add Python to PATH" during install |
| Dashboard shows blank page | Wait 15 seconds and refresh — Streamlit is still starting |
| "Invalid credentials" at login | Check you typed your username and password correctly |
| Agent gives no response | Check your Anthropic API key in `.env` is correct and has billing set up |
| Page shows error after restart | Run `.\scripts\start.ps1` again |
| Agents show "running" but never finish | This cleans up automatically on next restart — FaiykeOS resets any stuck runs when it starts |
| Scheduled workflows fire at wrong time | Set `SCHEDULER_TIMEZONE=` in your `.env` file to match your local timezone (see Part 6) |

---

## Getting Help

If you are stuck at any step:

- **Email:** hello@faiyke-ai.com
- **Subject:** `FaiykeOS Setup Help`
- **Tell us:** which step number you are on, and paste any error message shown in the command window

We respond within 24 hours on business days.

---

## Next Steps (Optional Upgrades)

Once you are comfortable with the basics:

| Feature | What to Do |
|---------|-----------|
| Set up email notifications for tickets | Settings → Email Notifications → fill in your SMTP details |
| Add your brand colours | Admin → Branding → select your namespace → set colours |
| Invite a team member | Admin → Users → Create User |
| Run a workflow automatically | Workflows → find a workflow → toggle Schedule on |
| Connect to Claude Desktop | Run `.\scripts\start_mcp.ps1` (optional) |
| Attach files to agent messages | In Chat tab, use the 📎 icon to attach images or .md/.txt documents inline |
