"""Generate ClaudeOS_Agents_Documentation.pdf from live agent YAML definitions."""
import yaml
import markdown2
from xhtml2pdf import pisa
import io
from datetime import date
from pathlib import Path

CSS = """
@page { size: A4; margin: 2cm 2cm 2cm 2cm; }
body { font-family: Arial, sans-serif; font-size: 11pt; color: #1a1a1a; line-height: 1.6; }
h1 { color: #407E3C; font-size: 22pt; border-bottom: 3px solid #407E3C; padding-bottom: 8px; margin-top: 0; }
h2 { color: #407E3C; font-size: 15pt; border-bottom: 1px solid #5a9e56; padding-bottom: 4px; margin-top: 28px; }
h3 { color: #2d5a29; font-size: 12pt; margin-top: 14px; }
table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 10pt; table-layout: fixed; }
th { background: #407E3C; color: #ffffff; padding: 7px 10px; text-align: left; word-wrap: break-word; }
td { padding: 6px 10px; border-bottom: 1px solid #d0e8c8; vertical-align: top; word-wrap: break-word; overflow-wrap: break-word; }
tr:nth-child(even) td { background: #f4faf2; }
code { background: #f0f0f0; padding: 1px 4px; font-family: Courier New, monospace; font-size: 9pt; word-break: break-all; }
.col-id { width: 22%; }
.col-name { width: 22%; }
.col-cat { width: 12%; }
.col-desc { width: 36%; }
.col-en { width: 8%; }
pre { background: #f4faf2; border-left: 4px solid #407E3C; padding: 10px 14px; font-family: Courier New, monospace; font-size: 8.5pt; white-space: pre-wrap; word-wrap: break-word; }
ul, ol { margin: 6px 0; padding-left: 22px; }
li { margin: 3px 0; }
hr { border: none; border-top: 1px solid #c8e0c0; margin: 18px 0; }
strong { color: #2d5a29; }
.agent-card { border: 1px solid #c8e0c0; padding: 14px 18px; margin: 18px 0; background: #fafffe; }
.agent-title { font-size: 14pt; color: #407E3C; font-weight: bold; margin-bottom: 4px; }
.agent-meta { font-size: 9pt; color: #666; margin-bottom: 10px; }
.badge { background: #407E3C; color: white; padding: 2px 8px; font-size: 9pt; margin-right: 4px; }
.header-bar { background: #407E3C; color: white; padding: 18px 24px; margin: -2cm -2cm 24px -2cm; }
"""


def load_agents():
    agents = []
    for f in sorted(Path('agents/definitions').glob('*.yaml')):
        with open(f, encoding='utf-8') as fh:
            try:
                data = yaml.safe_load(fh)
                agents.append(data)
            except Exception as e:
                print(f"Skip {f.name}: {e}")
    return agents


def build_html(agents):
    summary_rows = ""
    for a in agents:
        enabled = 'Yes' if a.get('enabled', True) else 'No'
        summary_rows += (
            f"<tr><td><code>{a.get('name','?')}</code></td>"
            f"<td>{a.get('display_name','')}</td>"
            f"<td>{a.get('category','')}</td>"
            f"<td>{a.get('description','')}</td>"
            f"<td>{enabled}</td></tr>"
        )

    cards = ""
    for a in agents:
        tags_html = ' '.join(
            f'<span class="badge">{t}</span>' for t in (a.get('tags') or [])
        ) or '&#8212;'
        tools_list = ', '.join(a.get('tools') or []) or '&#8212;'
        ns_lock = a.get('namespace_lock') or 'None (global)'
        sp = (a.get('system_prompt') or '').strip()
        sp_short = sp[:400] + ('...' if len(sp) > 400 else '')
        sp_escaped = sp_short.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        cards += f"""
<div class="agent-card">
  <div class="agent-title">{a.get('display_name', a.get('name', '?'))}</div>
  <div class="agent-meta">
    ID: <code>{a.get('name','?')}</code> &nbsp;|&nbsp;
    Category: <strong>{a.get('category','?')}</strong> &nbsp;|&nbsp;
    Model: <code>{a.get('model','?')}</code> &nbsp;|&nbsp;
    Max tokens: {a.get('max_tokens','?')} &nbsp;|&nbsp;
    Temp: {a.get('temperature','?')} &nbsp;|&nbsp;
    Version: {a.get('version','1.0.0')}
  </div>
  <p><strong>Description:</strong> {a.get('description','')}</p>
  <p><strong>Tags:</strong> {tags_html}</p>
  <p><strong>Tools:</strong> {tools_list}</p>
  <p><strong>Namespace lock:</strong> {ns_lock}</p>
  <p><strong>Enabled:</strong> {'Yes' if a.get('enabled', True) else 'No'}</p>
  <p><strong>System prompt (excerpt):</strong></p>
  <pre>{sp_escaped}</pre>
</div>
"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<title>ClaudeOS Agents Documentation</title>
<style>{CSS}</style></head><body>
<div class="header-bar">
  <strong style="font-size:18pt;color:white;">ClaudeOS &mdash; Agents Documentation</strong>
  <span style="float:right;color:#c8e0c0;font-size:10pt;">v13.1 &middot; {date.today().isoformat()}</span>
</div>

<h1>Agent Registry</h1>
<p>ClaudeOS ships with {len(agents)} registered AI agents. Each agent is defined by a YAML file in
<code>agents/definitions/</code> and loaded into the registry at startup. Agents are dispatched
via <code>POST /api/v1/agents/&lt;name&gt;/run</code> (async) or
<code>GET /api/v1/agents/&lt;name&gt;/stream</code> (SSE streaming, token-by-token).</p>

<h2>Summary Table</h2>
<table>
<tr><th class="col-id">ID</th><th class="col-name">Display Name</th><th class="col-cat">Category</th><th class="col-desc">Description</th><th class="col-en">Enabled</th></tr>
{summary_rows}
</table>

<h2>Agent Details</h2>
{cards}

<h2>Dispatching Agents</h2>
<h3>Async Run (poll for result)</h3>
<pre>POST /api/v1/agents/{{name}}/run
Authorization: Bearer &lt;token&gt;

{{
  "prompt": "Your task here",
  "namespace": "global",
  "context": {{}},
  "session_id": null,
  "save_output": true
}}

Response 202:
{{
  "run_id": "abc123",
  "agent": "writing-agent",
  "status": "pending",
  "poll_url": "/api/v1/agents/runs/abc123"
}}</pre>

<h3>SSE Streaming (token-by-token)</h3>
<pre>GET /api/v1/agents/{{name}}/stream?prompt=Hello&amp;namespace=global
Authorization: Bearer &lt;token&gt;

Stream events:
  data: {{"type": "token", "text": "Hello"}}
  data: {{"type": "done", "run_id": "abc123", "tokens_in": 1500, "tokens_out": 42}}
  data: {{"type": "error", "message": "..."}}</pre>

<p>Every streaming run is automatically saved to <code>agent_runs</code> with
<code>status=done</code>, token counts, output, and eval score.</p>

<h2>A2A Agent Cards</h2>
<pre>GET /api/v1/agents/{{name}}/.well-known/agent.json</pre>
<p>Machine-readable capability card for agent-to-agent discovery. Describes name, description,
input/output schema, streaming/multi-turn capabilities, and endpoints.</p>

<h2>Quality Evaluation (LLM-as-Judge)</h2>
<p>Every run is scored by Claude Haiku asynchronously after completion (~10s).</p>
<table>
<tr><th>Dimension</th><th>Weight</th><th>What it measures</th></tr>
<tr><td>Task Completion</td><td>40%</td><td>Did the output address the prompt?</td></tr>
<tr><td>Factual Grounding</td><td>30%</td><td>Claims grounded in memory context?</td></tr>
<tr><td>Conciseness</td><td>20%</td><td>Appropriate length, no padding?</td></tr>
<tr><td>Safety</td><td>10%</td><td>No harmful/biased content (pass/fail)</td></tr>
</table>
<p>Scores are stored in <code>agent_runs.eval_score</code>. A safety fail caps the overall score at 1.0.
Scores are visible in Run History, Overview, Chat tab, and the Observability dashboard.</p>

<h2>Adding a Custom Agent</h2>
<ol>
<li>Create <code>agents/definitions/my-agent.yaml</code></li>
<li>Run <code>python scripts/seed_agents.py</code></li>
<li>The agent appears immediately in the Catalog and is dispatchable via API.</li>
</ol>
<pre>name: my-agent
display_name: My Custom Agent
description: One-line description
category: ops
system_prompt: |
  You are a custom AI agent operating within the ClaudeOS AI Operating System.
model: claude-sonnet-4-6
max_tokens: 4096
temperature: 0.7
tools: []
namespace_lock: null
tags: [custom]
enabled: true
version: "1.0.0"</pre>

</body></html>"""


if __name__ == '__main__':
    agents = load_agents()
    print(f"Loaded {len(agents)} agents")
    html = build_html(agents)
    out_path = 'ClaudeOS_Agents_Documentation.pdf'
    with open(out_path, 'wb') as out:
        result = pisa.CreatePDF(io.StringIO(html), dest=out)
    if result.err:
        print(f"PDF error: {result.err}")
    else:
        print(f"Created: {out_path}")
