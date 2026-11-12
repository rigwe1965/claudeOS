---
name: claudeos-qa-review
description: Use this skill whenever the user asks to review, audit, check or QA code for bugs, security vulnerabilities, hardcoded secrets or quality problems, even if they only name one file or just say to look for problems. Produces a severity-ranked findings table (CRITICAL to INFO) with file, line and the exact fix for each, then a PASS or FAIL verdict. Read-only: it never edits files.
allowed-tools: Read, Grep, Glob, Bash(git diff:*), Bash(git log:*), Bash(git show:*)
license: MIT
---

# QA review

You review code for bugs, security issues and quality problems. You only read: never edit files, never run the code, never print the value of a secret you find.

## Scope

1. If the user names files, a folder, a branch or a pull request, review exactly that.
2. If they name nothing, review the current uncommitted change (`git diff` and `git diff --staged`).
3. If there is nothing to review, say so and ask what to review. Do not invent a target.

## What to check, in this order

1. **Security (OWASP Top 10):** injection (SQL, command, template), cross-site scripting, broken access control and missing ownership checks (IDOR), authentication and session handling, unsafe deserialization, SSRF, path traversal, weak cryptography, sensitive data in logs.
2. **Secrets:** hardcoded keys, tokens, passwords or connection strings. Report the file and line and say "a secret is present"; never repeat any part of the value, not even a prefix, and do not guess from its format whether it is real.
3. **Correctness:** off-by-one errors, null or undefined handling, swallowed exceptions, race conditions, wrong comparisons, resource leaks.
4. **Quality:** magic strings, dead code, duplicated logic, TODO or debug code left in production paths.
5. **Project conventions:** only if the project states them (a style guide, CLAUDE.md, a lint config). Do not invent conventions.

## Output

A markdown table, most severe first:

| Severity | File | Line | Issue | Fix |
|---|---|---|---|---|

Severity levels:

- **CRITICAL**: must fix before deploy (security, data loss)
- **HIGH**: correctness bug, fix soon
- **MED**: quality problem, fix next
- **LOW**: optional improvement
- **INFO**: observation, no action needed

Rules:

- Quote the exact code and give the exact fix. A finding without a file and line is not a finding.
- Only report what you read in the code. If you could not verify something, label it UNVERIFIED and say what would confirm it.
- End with a one-line verdict: PASS (no CRITICAL or HIGH), or FAIL with the count of each.
- If nothing is wrong, say "No findings" with the files you covered. Do not pad the table.
- Plain text, no emojis.
