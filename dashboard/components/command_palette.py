"""Ctrl/Cmd+K command palette — jump to any dashboard page from the keyboard.

Streamlit has no native command palette, so the overlay is injected into the parent
document from a zero-height components.html iframe (same technique as theme_toggle).
Selecting a page clicks the hidden sidebar proxy button `nav_btn_<page>`, which runs the
existing Python navigation callback — no second navigation path to keep in sync.
"""
import json

import streamlit.components.v1 as components

from dashboard.components.proxy import COS_CLICK_PROXY_JS

# Page -> one-line hint shown under the name and matched by the search box.
PAGE_HINTS = {
    "Overview":      "Live feed, KPIs, quick dispatch",
    "Agents":        "Chat with agents, catalog, runs",
    "Memory":        "Search and manage memory entries",
    "Workflows":     "Pipelines, schedules, webhooks",
    "Projects":      "Client vault and workspaces",
    "Outputs":       "Generated documents and exports",
    "Tickets":       "Support tickets and SLAs",
    "Usage":         "Your namespace usage and pulse score",
    "Observability": "Quality, latency, tokens, memory health",
    "Settings":      "Sync, integrations, configuration",
    "Admin":         "Users, API keys, audit log, branding",
}


def build_palette_script(pages: list[str], theme: dict, current: str) -> str:
    """Return the full HTML document for the injector iframe (pure function, unit-tested)."""
    items = [{"name": p, "hint": PAGE_HINTS.get(p, "")} for p in pages]
    cfg = {
        "items": items,
        "current": current,
        "bg": theme["SURFACE"],
        "text": theme["TEXT"],
        "muted": theme["TEXT_MUTED"],
        "border": theme["BORDER"],
        "accent": theme["BTN_BG"],
    }
    # </script> inside JSON would end the tag early; page names are static but stay safe.
    payload = json.dumps(cfg).replace("</", "<\\/")
    return f"""<!DOCTYPE html><html><body><script>
{COS_CLICK_PROXY_JS}
(function() {{
  var cfg = {payload};
  var win = window.parent, doc = win.document;

  // Re-runs on every Streamlit rerun: drop the previous listener/overlay, then rebuild.
  if (win.__cosPaletteKey) doc.removeEventListener('keydown', win.__cosPaletteKey, true);
  var old = doc.getElementById('cos-palette');
  if (old) old.remove();

  var overlay = doc.createElement('div');
  overlay.id = 'cos-palette';
  overlay.style.cssText = 'display:none;position:fixed;inset:0;z-index:999999;'
    + 'background:rgba(0,0,0,0.5);align-items:flex-start;justify-content:center;padding-top:14vh;';
  var box = doc.createElement('div');
  box.setAttribute('role', 'dialog');
  box.setAttribute('aria-label', 'Command palette');
  box.style.cssText = 'width:min(520px,92vw);background:' + cfg.bg + ';color:' + cfg.text
    + ';border:1px solid ' + cfg.border + ';border-radius:14px;overflow:hidden;'
    + 'box-shadow:0 20px 60px rgba(0,0,0,0.45);font-family:Inter,Inter,system-ui,sans-serif;';
  var input = doc.createElement('input');
  input.type = 'text';
  input.placeholder = 'Go to page\\u2026';
  input.setAttribute('aria-label', 'Search pages');
  input.style.cssText = 'width:100%;box-sizing:border-box;padding:14px 16px;font-size:14px;'
    + 'background:transparent;color:' + cfg.text + ';border:0;border-bottom:1px solid '
    + cfg.border + ';outline:none;';
  var list = doc.createElement('div');
  list.setAttribute('role', 'listbox');
  list.style.cssText = 'max-height:340px;overflow-y:auto;padding:6px;';
  var foot = doc.createElement('div');
  foot.textContent = '\\u2191\\u2193 navigate   \\u21B5 open   esc close';
  foot.style.cssText = 'padding:8px 14px;font-size:11px;color:' + cfg.muted
    + ';border-top:1px solid ' + cfg.border + ';';
  box.appendChild(input); box.appendChild(list); box.appendChild(foot);
  overlay.appendChild(box);
  doc.body.appendChild(overlay);

  var shown = [], active = 0;

  function matches(item, q) {{
    if (!q) return true;
    var hay = (item.name + ' ' + item.hint).toLowerCase();
    return q.toLowerCase().split(/\\s+/).every(function(w) {{ return hay.indexOf(w) !== -1; }});
  }}

  function render() {{
    var q = input.value.trim();
    shown = cfg.items.filter(function(it) {{ return matches(it, q); }});
    if (active >= shown.length) active = Math.max(0, shown.length - 1);
    list.textContent = '';
    if (!shown.length) {{
      var none = doc.createElement('div');
      none.textContent = 'No matching pages';
      none.style.cssText = 'padding:14px;font-size:13px;color:' + cfg.muted + ';';
      list.appendChild(none);
      return;
    }}
    shown.forEach(function(it, i) {{
      var row = doc.createElement('div');
      row.setAttribute('role', 'option');
      var on = i === active;
      row.style.cssText = 'display:flex;flex-direction:column;gap:1px;padding:9px 12px;'
        + 'border-radius:8px;cursor:pointer;border-left:3px solid '
        + (on ? cfg.accent : 'transparent') + ';background:' + (on ? cfg.accent + '33' : 'transparent') + ';';
      var name = doc.createElement('span');
      name.textContent = it.name + (it.name === cfg.current ? '  \\u00B7 current' : '');
      name.style.cssText = 'font-size:13.5px;font-weight:500;';
      var hint = doc.createElement('span');
      hint.textContent = it.hint;
      hint.style.cssText = 'font-size:11.5px;color:' + cfg.muted + ';';
      row.appendChild(name); row.appendChild(hint);
      row.addEventListener('mousemove', function() {{
        if (active !== i) {{ active = i; render(); }}
      }});
      row.addEventListener('click', function() {{ go(it); }});
      list.appendChild(row);
    }});
    var el = list.children[active];
    if (el && el.scrollIntoView) el.scrollIntoView({{block: 'nearest'}});
  }}

  function open() {{
    input.value = ''; active = 0; render();
    overlay.style.display = 'flex';
    input.focus();
  }}
  function close() {{ overlay.style.display = 'none'; }}
  win.__cosPaletteOpen = open;     // lets the Overview search box (a separate iframe) open the palette
  function go(it) {{
    close();
    if (it.name === cfg.current) return;
    cosClickProxy(doc, 'nav:' + it.name);
  }}

  input.addEventListener('input', function() {{ active = 0; render(); }});
  input.addEventListener('keydown', function(e) {{
    if (e.key === 'ArrowDown') {{ e.preventDefault(); active = Math.min(active + 1, shown.length - 1); render(); }}
    else if (e.key === 'ArrowUp') {{ e.preventDefault(); active = Math.max(active - 1, 0); render(); }}
    else if (e.key === 'Enter') {{ e.preventDefault(); if (shown[active]) go(shown[active]); }}
  }});
  overlay.addEventListener('mousedown', function(e) {{ if (e.target === overlay) close(); }});

  win.__cosPaletteKey = function(e) {{
    var isOpen = overlay.style.display !== 'none';
    if ((e.ctrlKey || e.metaKey) && (e.key === 'k' || e.key === 'K')) {{
      e.preventDefault(); e.stopPropagation();
      isOpen ? close() : open();
    }} else if (e.key === 'Escape' && isOpen) {{
      e.preventDefault(); close();
    }}
  }};
  doc.addEventListener('keydown', win.__cosPaletteKey, true);
}})();
</script></body></html>"""


def render(pages: list[str], theme: dict, current: str) -> None:
    """Inject the palette. Call once per run, after the auth gate and after nav proxy buttons exist."""
    components.html(build_palette_script(pages, theme, current), height=0)


def build_search_trigger_html(theme: dict) -> str:
    """A search-box lookalike that opens the palette on click (pure function, unit-tested)."""
    return f"""<!DOCTYPE html><html><head><style>
*{{margin:0;padding:0;box-sizing:border-box;font-family:'Inter',system-ui,sans-serif;}}
body{{background:transparent;display:flex;justify-content:center;padding:6px 4px;}}
.box{{width:100%;max-width:520px;display:flex;align-items:center;gap:10px;height:42px;padding:0 14px;
      background:{theme['SURFACE']};border:1px solid {theme['BORDER']};border-radius:10px;cursor:pointer;
      color:{theme['TEXT_MUTED']};font-size:13.5px;transition:border-color .15s,box-shadow .15s;}}
.box:hover{{border-color:{theme['BTN_BG']};box-shadow:0 0 0 3px {theme['BTN_BG']}22;}}
.box svg{{flex:none;}}
.box span{{flex:1;text-align:left;}}
kbd{{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px;padding:2px 7px;border-radius:5px;
     border:1px solid {theme['BORDER']};background:{theme['SURFACE2']};color:{theme['TEXT_MUTED']};}}
</style></head><body>
<div class="box" role="button" tabindex="0" aria-label="Search pages (Ctrl+K)"
     onclick="window.parent.__cosPaletteOpen && window.parent.__cosPaletteOpen()"
     onkeydown="if(event.key==='Enter'||event.key===' '){{window.parent.__cosPaletteOpen && window.parent.__cosPaletteOpen();}}">
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
       stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
  <span>Search pages, agents, memory…</span><kbd>Ctrl K</kbd>
</div></body></html>"""


def search_trigger(theme: dict) -> None:
    """Render the centered search box (call under the hero on Overview)."""
    components.html(build_search_trigger_html(theme), height=54)
