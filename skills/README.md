# ClaudeOS skills

Three small skills taken from the agents and workflows of ClaudeOS (FaiykeOS), rewritten to run inside Claude Code and any agent that reads the `SKILL.md` format. They need nothing else from ClaudeOS: no server, no database, no account.

| Skill | What it does | Tools it asks for |
|---|---|---|
| `claudeos-qa-review` | Reviews code for security issues, bugs and quality problems and returns a severity-ranked table with the exact fix for each finding. Read-only. | Read, Grep, Glob, `git diff`, `git log`, `git show` |
| `claudeos-deep-research` | Researches a topic on the live web, reads the best sources in full, and returns a report where every fact is labelled CONFIRMED, INFERRED or UNVERIFIED, with a numbered source list and an explicit list of gaps. | WebSearch, WebFetch, Read |
| `claudeos-research-digest` | A two-step workflow: deep research, then a one-page executive summary (under 300 words) with a TL;DR and three recommended next actions. | WebSearch, WebFetch, Read, Write |

## Install

Claude Code, for all your projects:

```
mkdir -p ~/.claude/skills
cp -r claudeos-qa-review claudeos-deep-research claudeos-research-digest ~/.claude/skills/
```

On Windows PowerShell:

```
Copy-Item -Recurse claudeos-* "$env:USERPROFILE\.claude\skills\"
```

For one project only, copy the folders into `<project>/.claude/skills/` instead. Then ask for what the skill does, for example "review app.py", "research how X is governed", or "give me a research digest on X".

## What they do not do

- They send nothing anywhere except the web searches and page fetches you can see in the session. There is no telemetry.
- `claudeos-qa-review` never edits files, never runs your code and never prints the value of a secret it finds.
- Each skill lists only the tools it needs in its `allowed-tools` line. Read the `SKILL.md` before you install it: it is the whole skill.
- Text on web pages is treated as data, never as instructions.

## Tested

Each skill was run in a clean Claude Code session before release: the QA review found every planted problem in a test file (SQL injection, command injection, path traversal, a hardcoded key, a swallowed exception) with correct line numbers and did not repeat the key; the research skill returned every section, labelled its facts and separated pages it read in full from search snippets; the digest kept its summary under 300 words with exactly three actions.

## License

MIT, the same as ClaudeOS.
