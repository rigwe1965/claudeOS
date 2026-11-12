"""Agents page — Phase 10, 12, 13 upgrades.

New capabilities:
- Multi-turn conversation chat UI (Phase 13.4)
- SSE streaming responses via requests (Phase 10.1)
- Native file attachment via chat_input(accept_file=True): images + .md/.txt (Phase 13.2+)
  - Sidebar file_uploader kept as fallback; both merged into _all_files
  - Text files (.md/.txt) injected as fenced context block in prompt
  - Images encoded as base64 content blocks, multiple supported
- Voice input via audio recording (Phase 13.1)
- Eval score display on run history (Phase 10.3)
- A2A Agent Card viewer (Phase 12.3)
"""
from __future__ import annotations

import base64
import json
import re
import time
import uuid

import requests
import streamlit as st
from dashboard.components.brand import PRIMARY, PRIMARY_LIGHT, SURFACE, badge, get_theme_vars
from dashboard.components.proxy import proxy_button, COS_CLICK_PROXY_JS

CATEGORY_COLORS = {
    "ops":         "#407E3C",
    "research":    "#3b82f6",
    "content":     "#8b5cf6",
    "analysis":    "#f59e0b",
    "comms":       "#ec4899",
    "system":      "#6b7280",
    "engineering": "#ef4444",
    "domain":      "#14b8a6",
}

_SCORE_COLOR = {
    (4.0, 5.1): "#5a9e56",
    (2.5, 4.0): "#f59e0b",
    (0.0, 2.5): "#ef4444",
}


def _score_badge(score) -> str:
    if score is None:
        return ""
    for (lo, hi), color in _SCORE_COLOR.items():
        if lo <= float(score) < hi:
            return f'<span style="background:{color}22;color:{color};border:1px solid {color}55;padding:1px 7px;border-radius:10px;font-size:0.72rem;font-weight:700;">{score:.1f}</span>'
    return ""


def render(api_get, api_post, bulk_delete=None):
    st.title("Agents")

    agents_data = api_get("/agents?enabled_only=false")
    if not agents_data:
        st.error("API unreachable")
        return

    agents = agents_data.get("agents", [])
    if not agents:
        st.info("No agents registered. Run `python scripts/seed_agents.py`")
        return

    # Tab navigation and persistence across reruns (card clicks + theme toggles).
    # Python signals target=0 on card click; all other reruns use sessionStorage
    # (browser-side, invisible to Streamlit backend, survives theme-toggle reruns).
    _goto_chat_now = st.session_state.pop("_goto_chat", False)
    _target_tab = 0 if _goto_chat_now else -1  # -1 = "restore from sessionStorage"

    import time as _t
    import streamlit.components.v1 as _cv1
    _cv1.html(f"""<script>
(function(){{
    var target={_target_tab}, nonce={int(_t.time()*1000)};
    var KEY='claudeos_agents_tab';
    setTimeout(function(){{
        var tabs=window.parent.document.querySelectorAll('[data-testid="stTab"]');
        if(!tabs.length) return;
        var desired;
        if(target>=0){{
            // Explicit navigation (catalog card click) — go to target and save
            desired=target;
            window.parent.sessionStorage.setItem(KEY,desired);
        }}else{{
            // Restore: read last user-selected tab (default 1 = Catalog on first visit)
            var stored=window.parent.sessionStorage.getItem(KEY);
            desired=stored!==null?parseInt(stored):1;
        }}
        // Only click if tab is not already active (prevents infinite rerun loop)
        if(desired<tabs.length&&tabs[desired].getAttribute('aria-selected')!=='true'){{
            tabs[desired].click();
        }}
        // Track future user tab clicks into sessionStorage (no rerun triggered)
        tabs.forEach(function(tab,idx){{
            if(!tab._agentsBound){{
                tab._agentsBound=true;
                tab.addEventListener('click',function(){{
                    window.parent.sessionStorage.setItem(KEY,idx);
                }});
            }}
        }});
    }},120);
}})();
</script>""", height=0)

    tab_chat, tab_catalog, tab_runs = st.tabs(["Chat", "Catalog", "Run History"])

    with tab_chat:
        _render_chat_tab(agents, api_get, api_post)

    with tab_catalog:
        _render_catalog_tab(agents, api_get, api_post)

    with tab_runs:
        _render_runs_tab(api_get)


# ── Chat Tab ──────────────────────────────────────────────────────────────────

def _render_chat_tab(agents: list, api_get, api_post):
    """Multi-turn chat — centered compose card layout."""
    tv = get_theme_vars()
    _is_dark = tv.get("BG", "#000") < "#888"

    # ── Polish CSS for compose card ───────────────────────────────────────────
    _card_bg   = "#0f1f10" if _is_dark else "#ffffff"
    _text_col  = "#d4edda" if _is_dark else "#1a1a1a"
    _ph_col    = "rgba(255,255,255,0.30)" if _is_dark else "rgba(0,0,0,0.35)"
    _ctrl_lbl  = "rgba(255,255,255,0.40)" if _is_dark else "rgba(0,0,0,0.40)"
    _sep_col   = "rgba(90,158,86,0.15)"   if _is_dark else "rgba(64,126,60,0.12)"
    _file_bg   = "rgba(64,126,60,0.08)"   if _is_dark else "rgba(64,126,60,0.05)"
    st.markdown(f"""<style>
/* ── Compose card ── */
[data-testid="stForm"] {{
    background: {_card_bg} !important;
    border: 1px solid rgba(90,158,86,0.22) !important;
    border-radius: 18px !important;
    box-shadow: 0 4px 32px rgba(0,0,0,0.38), 0 0 0 1px rgba(64,126,60,0.08) !important;
    padding: 20px 22px 14px !important;
    margin-bottom: 10px !important;
}}
[data-testid="stForm"] > div:first-child {{
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}}
/* Text area — kill ALL intermediate wrapper backgrounds */
[data-testid="stForm"] [data-testid="stTextArea"],
[data-testid="stForm"] [data-testid="stTextArea"] > div,
[data-testid="stForm"] [data-testid="stTextArea"] > div > div,
[data-testid="stForm"] [data-testid="stTextArea"] > div > div > div,
[data-testid="stForm"] [data-testid="stTextArea"] label,
[data-testid="stForm"] [data-baseweb="textarea"],
[data-testid="stForm"] [data-baseweb="base-input"] {{
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
}}
[data-testid="stForm"] [data-testid="stTextArea"] textarea {{
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    border-bottom: 1px solid {_sep_col} !important;
    border-radius: 0 !important;
    color: {_text_col} !important;
    font-size: 15px !important;
    line-height: 1.7 !important;
    caret-color: #5a9e56 !important;
    resize: none !important;
    padding: 4px 0 12px !important;
    box-shadow: none !important;
    outline: none !important;
}}
[data-testid="stForm"] [data-testid="stTextArea"] textarea::placeholder {{
    color: {_ph_col} !important;
    opacity: 1 !important;
}}
[data-testid="stForm"] [data-testid="stTextArea"] textarea:focus {{
    outline: none !important;
    box-shadow: none !important;
    border-bottom-color: rgba(90,158,86,0.55) !important;
}}
/* File uploader compact */
[data-testid="stForm"] [data-testid="stFileUploaderDropzone"] {{
    background: {_file_bg} !important;
    border: 1px dashed rgba(90,158,86,0.28) !important;
    border-radius: 8px !important;
    min-height: 38px !important;
    padding: 4px 10px !important;
}}
[data-testid="stForm"] [data-testid="stFileUploaderDropzone"]:hover {{
    border-color: rgba(90,158,86,0.55) !important;
}}
/* Send button */
[data-testid="stForm"] [data-testid="stFormSubmitButton"] button,
[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] {{
    background: #407E3C !important;
    background-color: #407E3C !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    letter-spacing: 0.3px !important;
    box-shadow: 0 2px 10px rgba(64,126,60,0.45) !important;
    transition: background .15s, transform .12s, box-shadow .15s !important;
    height: 38px !important;
    padding: 0 18px !important;
}}
[data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {{
    background: #5a9e56 !important;
    background-color: #5a9e56 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 18px rgba(64,126,60,0.60) !important;
}}
/* Save checkbox inside form */
[data-testid="stForm"] [data-testid="stCheckbox"] label span {{
    color: {_ctrl_lbl} !important;
    font-size: 12px !important;
}}
/* Controls row labels below compose */
[data-testid="stSelectbox"] label {{
    font-size: 11px !important;
    color: {_ctrl_lbl} !important;
    text-transform: uppercase !important;
    letter-spacing: 0.8px !important;
    font-weight: 500 !important;
}}
</style>""", unsafe_allow_html=True)

    agent_names = [a["name"] for a in agents if a.get("enabled")]
    _agent_descs = {
        a["name"]: f"[{a.get('category','').upper()}] {a.get('description','')[:60]}"
        for a in agents if a.get("enabled")
    }

    # Resolve agent from pending catalog click or session state
    _pending = st.session_state.pop("_pending_agent", None)
    if _pending and _pending in agent_names:
        st.session_state["chat_agent"] = _pending
    sel_agent = st.session_state.get("chat_agent") or (agent_names[0] if agent_names else "")
    if sel_agent not in agent_names and agent_names:
        sel_agent = agent_names[0]
        st.session_state["chat_agent"] = sel_agent

    # Resolve namespace
    _role    = st.session_state.get("user_role", "admin")
    _user_ns = st.session_state.get("user_namespace")
    if _role in ("client", "viewer") and _user_ns:
        _ns_opts = [_user_ns]
    else:
        _ns_data = api_get("/namespaces") or []
        _ns_opts = [n["slug"] for n in _ns_data if isinstance(n, dict) and n.get("slug")] or ["global"]
    sel_ns = st.session_state.get("chat_ns") or (_ns_opts[0] if _ns_opts else "global")
    if sel_ns not in _ns_opts and _ns_opts:
        sel_ns = _ns_opts[0]
        st.session_state["chat_ns"] = sel_ns

    conv_key = f"conv_{sel_agent}_{sel_ns}"
    if conv_key not in st.session_state:
        # Seed from DB — restores history after page refresh
        _hist = api_get(f"/agents/{sel_agent}/conversations/turns?namespace={sel_ns}&limit=40") or {}
        _db_turns = _hist.get("turns", [])
        _seeded: list[dict] = []
        for _t in _db_turns:
            _seeded.append({"role": _t["role"], "content": _t["content"], "meta": {}})
        st.session_state[conv_key] = _seeded
    history: list[dict] = st.session_state[conv_key]

    # ── Centered layout ───────────────────────────────────────────────────────
    _, col_main, _ = st.columns([1, 6, 1])

    with col_main:

        # ── Conversation history ──────────────────────────────────────────────
        for turn in history:
            role = turn["role"]
            with st.chat_message(role, avatar="🧑" if role == "user" else "assistant"):
                st.markdown(turn["content"])
                if role == "assistant" and turn.get("meta"):
                    meta = turn["meta"]
                    score_html = _score_badge(meta.get("eval_score"))
                    st.markdown(
                        f'<span style="color:{tv["TEXT_MUTED"]};font-size:0.73rem;">'
                        f'{meta.get("duration_ms",0)}ms · '
                        f'{meta.get("tokens_in",0)}+{meta.get("tokens_out",0)} tokens'
                        f'</span> {score_html}',
                        unsafe_allow_html=True,
                    )

        # ── Pre-fill compose from voice transcription ─────────────────────────
        _pending_voice = st.session_state.pop("_transcribed_text", None)
        if _pending_voice:
            st.session_state["chat_compose_text"] = _pending_voice

        # ── Compose card ──────────────────────────────────────────────────────
        if st.session_state.get("_voice_prefilled"):
            st.caption("Voice captured — edit or send")
            st.session_state.pop("_voice_prefilled", None)
        _jwt   = st.session_state.get("jwt_token", "")
        _fport = __import__("os").environ.get("FLASK_PORT", "5000")
        _transcribe_url = f"http://127.0.0.1:{_fport}/api/v1/transcribe"

        with st.form("chat_compose", clear_on_submit=True):
            user_input = st.text_area(
                "",
                placeholder=f"Message {sel_agent}…",
                height=130,
                label_visibility="collapsed",
                key="chat_compose_text",
            )
            f1, f2, f3, f4 = st.columns([4, 1, 1, 1])
            with f1:
                uploaded = st.file_uploader(
                    "Attach",
                    type=["png", "jpg", "jpeg", "webp", "gif", "md", "txt"],
                    key=f"chat_file_{sel_agent}",
                    label_visibility="collapsed",
                    accept_multiple_files=True,
                )
            with f2:
                save_out = st.checkbox("Save", value=True, key="chat_save")
            with f3:
                st.components.v1.html(_mic_button_html(_jwt, _transcribe_url), height=62)
            with f4:
                submitted = st.form_submit_button(
                    "Send ↑", use_container_width=True, type="primary"
                )

        # ── Controls below compose ────────────────────────────────────────────
        def _do_clear():
            _ag = st.session_state.get("chat_agent", "")
            _ns = st.session_state.get("chat_ns", "")
            st.session_state.pop(f"conv_{_ag}_{_ns}", None)
            st.session_state.pop(f"conv_id_{_ag}", None)
            st.session_state.pop("_last_audio_hash", None)

        c1, c2, c3 = st.columns([3, 3, 1])
        with c1:
            st.selectbox(
                "Agent", agent_names, key="chat_agent",
                format_func=lambda n: _agent_descs.get(n, n),
            )
        with c2:
            st.selectbox("Namespace", _ns_opts, key="chat_ns")
        with c3:
            st.markdown('<div style="height:1.75rem"></div>', unsafe_allow_html=True)
            st.button("Clear", key="chat_clear", on_click=_do_clear, use_container_width=True)

    # ── Determine prompt (form submit only — voice pre-fills textarea) ─────────
    prompt_text = (user_input or "").strip() if submitted else None

    if not prompt_text:
        return

    _all_files: list = []
    if uploaded:
        _all_files.extend(uploaded if isinstance(uploaded, list) else [uploaded])

    _IMG_EXTS   = {"png", "jpg", "jpeg", "webp", "gif"}
    _img_files  = [f for f in _all_files if f.name.lower().rsplit(".", 1)[-1] in _IMG_EXTS]
    _text_files = [f for f in _all_files if f.name.lower().rsplit(".", 1)[-1] in ("md", "txt")]

    prompt = prompt_text
    for _tf in _text_files:
        _file_text = _tf.read().decode("utf-8", errors="replace")
        prompt = f"--- FILE: {_tf.name} ---\n{_file_text}\n---\n\n{prompt}"

    user_turn = {"role": "user", "content": prompt}
    if _img_files:
        user_turn["has_image"] = True
    history.append(user_turn)

    # Re-render in col_main context for consistent layout
    with col_main:
        with st.chat_message("user", avatar="🧑"):
            st.markdown(prompt)
            for _imf in _img_files:
                st.image(_imf, width=200)

    api_messages = _history_to_api_messages(history[:-1])

    images = None
    if _img_files:
        images = []
        for _imf in _img_files:
            _imf.seek(0)
            _b64 = base64.b64encode(_imf.read()).decode("utf-8")
            images.append({"data": _b64, "media_type": _mime_type(_imf.name)})

    with col_main:
        with st.chat_message("assistant", avatar="assistant"):
            response_text, meta = _stream_response(
                sel_agent, prompt, sel_ns, api_messages, images, api_get,
                api_post=api_post, save_out=save_out,
            )
            err = st.session_state.pop("_stream_error", None)
            if response_text:
                history.append({"role": "assistant", "content": response_text, "meta": meta})
                st.session_state[conv_key] = history
                st.rerun()
            elif err:
                history.append({"role": "assistant", "content": f"**Error:** {err}"})
                st.session_state[conv_key] = history
                st.rerun()


def _stream_response(
    agent_name: str,
    prompt: str,
    namespace: str,
    messages: list,
    images,
    api_get,
    api_post=None,
    save_out: bool = False,
) -> tuple[str, dict]:
    """Stream SSE response from Flask SSE endpoint."""
    import os
    _FLASK_PORT = os.environ.get("FLASK_PORT", "5000")
    token = st.session_state.get("jwt_token", "")
    headers = {"Authorization": f"Bearer {token}", "Accept": "text/event-stream"}

    params = {
        "prompt": prompt,
        "namespace": namespace,
        "save_output": "true" if save_out else "false",
    }
    if messages:
        params["messages"] = json.dumps(messages)

    url = f"http://127.0.0.1:{_FLASK_PORT}/api/v1/agents/{agent_name}/stream"

    placeholder = st.empty()
    full_text = ""
    meta: dict = {"tokens_in": 0, "tokens_out": 0}
    start = time.monotonic()

    # Use POST when images present (GET can't carry body); GET otherwise
    if images:
        body = {"prompt": prompt, "namespace": namespace, "save_output": save_out}
        if messages:
            body["messages"] = messages
        body["images"] = images
        req_ctx = requests.post(url, json=body, headers=headers, stream=True, timeout=300)
    else:
        req_ctx = requests.get(url, params=params, headers=headers, stream=True, timeout=300)

    try:
        with req_ctx as resp:
            if not resp.ok:
                st.error(f"Stream error: {resp.status_code}")
                return "", {}

            for line in resp.iter_lines():
                if not line:
                    continue
                decoded = line.decode("utf-8")
                if not decoded.startswith("data: "):
                    continue
                payload = json.loads(decoded[6:])
                if payload.get("type") == "token":
                    full_text += payload.get("text", "")
                    placeholder.markdown(full_text + "▌")
                elif payload.get("type") == "done":
                    placeholder.markdown(full_text)
                    meta["tokens_in"] = payload.get("tokens_in", 0)
                    meta["tokens_out"] = payload.get("tokens_out", 0)
                    break
                elif payload.get("type") == "context_degraded":
                    meta["ctx_degraded"] = True
                elif payload.get("type") == "error":
                    err = payload.get("message", "Stream error")
                    st.session_state["_stream_error"] = err
                    return full_text, {}

        meta["duration_ms"] = int((time.monotonic() - start) * 1000)
        return full_text, meta

    except Exception as e:
        st.session_state["_stream_error"] = f"Streaming failed: {e}"
        return "", {}


def _blocking_response(
    agent_name: str,
    prompt: str,
    namespace: str,
    save_out: bool,
    messages: list,
    images,
    api_post,
    api_get,
) -> tuple[str, dict]:
    """Non-streaming: dispatch + poll until done."""
    payload = {
        "prompt": prompt,
        "namespace": namespace,
        "save_output": save_out,
    }
    if messages:
        payload["messages"] = messages
    if images:
        payload["images"] = images

    result = api_post(f"/agents/{agent_name}/run", payload)
    if not result:
        st.error("Dispatch failed")
        return "", {}

    run_id = result.get("run_id")
    placeholder = st.empty()
    placeholder.info("Agent running…")

    for _ in range(60):  # max 5 minutes
        time.sleep(5)
        run = api_get(f"/agents/runs/{run_id}")
        if not run:
            break
        status = run.get("status")
        if status == "done":
            placeholder.empty()
            output_text = (run.get("output") or {}).get("text", "")
            # Clean markdown fences
            output_text = re.sub(r"^```[a-zA-Z]*\n?", "", output_text)
            output_text = re.sub(r"\n?```$", "", output_text).strip()
            st.markdown(output_text)
            meta = {
                "duration_ms": run.get("duration_ms", 0),
                "tokens_in": run.get("tokens_in", 0),
                "tokens_out": run.get("tokens_out", 0),
                "eval_score": run.get("eval_score"),
            }
            return output_text, meta
        elif status == "failed":
            placeholder.empty()
            st.error(run.get("error", "Agent failed"))
            return "", {}

    placeholder.empty()
    st.warning("Agent timed out — check Run History")
    return "", {}


def _mic_button_html(jwt: str, transcribe_url: str) -> str:
    """Return HTML for the branded mic button component.

    Records audio via Web Audio API (raw PCM → WAV, no ffmpeg).
    POSTs WAV to Flask /api/v1/transcribe.
    Injects transcribed text into the parent Streamlit textarea.
    """
    return f"""<!DOCTYPE html>
<html>
<head>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:transparent; display:flex; align-items:center; justify-content:center; height:62px; padding-top:10px; }}
  #mic-btn {{
    width:40px; height:40px; border-radius:50%;
    background:#407E3C; border:none; cursor:pointer;
    display:flex; align-items:center; justify-content:center;
    box-shadow:0 2px 12px rgba(64,126,60,0.45);
    transition:background .15s, box-shadow .15s, transform .12s;
    outline:none;
  }}
  #mic-btn:hover {{ background:#5a9e56; transform:scale(1.07); box-shadow:0 4px 18px rgba(64,126,60,0.6); }}
  #mic-btn.recording {{ background:#c0392b; animation:pulse 1.1s infinite; }}
  #mic-btn.loading  {{ background:#888; cursor:wait; }}
  @keyframes pulse {{
    0%,100% {{ box-shadow:0 0 0 0 rgba(192,57,43,0.55); }}
    50%      {{ box-shadow:0 0 0 10px rgba(192,57,43,0); }}
  }}
  #status {{ font-size:11px; color:#aaa; margin-top:4px; text-align:center; height:14px; }}
</style>
</head>
<body>
<div style="display:flex;flex-direction:column;align-items:center;">
  <button id="mic-btn" title="Click to record voice">
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"
         fill="white">
      <path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3z"/>
      <path d="M19 11a1 1 0 0 0-2 0 5 5 0 0 1-10 0 1 1 0 0 0-2 0 7 7 0 0 0 6 6.92V20H9a1 1 0 0 0 0 2h6a1 1 0 0 0 0-2h-2v-2.08A7 7 0 0 0 19 11z"/>
    </svg>
  </button>
  <div id="status"></div>
</div>
<script>
const JWT   = {repr(jwt)};
const URL_T = {repr(transcribe_url)};

let audioCtx, processor, source, stream;
let recording = false;
let pcmChunks  = [];
let sampleRate = 16000;

const btn    = document.getElementById('mic-btn');
const status = document.getElementById('status');

btn.addEventListener('click', () => {{
  if (recording) stopRecording();
  else           startRecording();
}});

async function startRecording() {{
  try {{
    stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
    audioCtx   = new AudioContext({{ sampleRate: 16000 }});
    sampleRate = audioCtx.sampleRate;
    source     = audioCtx.createMediaStreamSource(stream);
    processor  = audioCtx.createScriptProcessor(4096, 1, 1);
    pcmChunks  = [];

    processor.onaudioprocess = (e) => {{
      const data = e.inputBuffer.getChannelData(0);
      pcmChunks.push(new Float32Array(data));
    }};

    source.connect(processor);
    processor.connect(audioCtx.destination);

    recording = true;
    btn.classList.add('recording');
    status.textContent = 'Recording…';
  }} catch(err) {{
    status.textContent = 'Mic access denied';
    console.error(err);
  }}
}}

function stopRecording() {{
  recording = false;
  btn.classList.remove('recording');
  btn.classList.add('loading');
  status.textContent = 'Transcribing…';

  processor.disconnect();
  source.disconnect();
  stream.getTracks().forEach(t => t.stop());
  audioCtx.close();

  const wav = encodeWAV(pcmChunks, sampleRate);
  sendToFlask(wav);
}}

function encodeWAV(chunks, sr) {{
  // Merge all PCM float32 chunks
  const total  = chunks.reduce((s, c) => s + c.length, 0);
  const merged = new Float32Array(total);
  let offset = 0;
  for (const c of chunks) {{ merged.set(c, offset); offset += c.length; }}

  // Convert float32 → int16
  const pcm16 = new Int16Array(merged.length);
  for (let i = 0; i < merged.length; i++) {{
    const s = Math.max(-1, Math.min(1, merged[i]));
    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }}

  // Build WAV file
  const dataLen  = pcm16.length * 2;
  const buf      = new ArrayBuffer(44 + dataLen);
  const view     = new DataView(buf);
  const writeStr = (o, s) => {{ for (let i=0;i<s.length;i++) view.setUint8(o+i, s.charCodeAt(i)); }};
  writeStr(0, 'RIFF');
  view.setUint32(4,  36 + dataLen, true);
  writeStr(8, 'WAVE');
  writeStr(12,'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20,  1, true); // PCM
  view.setUint16(22,  1, true); // mono
  view.setUint32(24, sr, true);
  view.setUint32(28, sr * 2, true);
  view.setUint16(32,  2, true);
  view.setUint16(34, 16, true);
  writeStr(36,'data');
  view.setUint32(40, dataLen, true);
  new Int16Array(buf, 44).set(pcm16);
  return new Blob([buf], {{ type: 'audio/wav' }});
}}

async function sendToFlask(wavBlob) {{
  try {{
    const fd = new FormData();
    fd.append('audio', wavBlob, 'voice.wav');
    const resp = await fetch(URL_T, {{
      method: 'POST',
      headers: {{ 'Authorization': 'Bearer ' + JWT }},
      body: fd
    }});
    const data = await resp.json();
    if (data.text) {{
      injectText(data.text);
      status.textContent = '✓ Done';
    }} else {{
      status.textContent = data.error || 'No speech detected';
    }}
  }} catch(err) {{
    status.textContent = 'Error: ' + err.message;
    console.error(err);
  }} finally {{
    btn.classList.remove('loading');
    setTimeout(() => {{ status.textContent = ''; }}, 2500);
  }}
}}

function injectText(text) {{
  const doc = window.parent.document;
  const ta  = doc.querySelector('[data-testid="stForm"] [data-testid="stTextArea"] textarea');
  if (!ta) return;
  // React controlled input — must use native setter
  const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
  nativeSetter.call(ta, text);
  ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
  ta.focus();
}}
</script>
</body>
</html>"""


def _transcribe_audio_sync(audio_data) -> str:
    """Transcribe audio synchronously — returns text string (no session state)."""
    import io, numpy as np
    from scipy.io import wavfile
    try:
        import whisper
    except ImportError:
        st.warning("Voice input requires `openai-whisper`. Run: `pip install openai-whisper`")
        return ""
    try:
        audio_bytes = audio_data.read()
        sample_rate, data = wavfile.read(io.BytesIO(audio_bytes))
        if data.ndim > 1:
            data = data.mean(axis=1)
        if data.dtype == np.int16:
            data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32:
            data = data.astype(np.float32) / 2147483648.0
        else:
            data = data.astype(np.float32)
        target_sr = whisper.audio.SAMPLE_RATE
        if sample_rate != target_sr:
            from scipy.signal import resample_poly
            from math import gcd
            g = gcd(sample_rate, target_sr)
            data = resample_poly(data, target_sr // g, sample_rate // g).astype(np.float32)
        model = _get_whisper_model()
        result = model.transcribe(data, fp16=False, language="en", temperature=0)
        return result.get("text", "").strip()
    except Exception as e:
        st.error(f"Transcription failed: {e}")
        return ""


def _transcribe_audio(audio_data) -> None:
    """Transcribe audio using Whisper (numpy path — no ffmpeg required)."""
    import hashlib, io
    audio_bytes = audio_data.read()
    audio_hash = hashlib.md5(audio_bytes).digest()
    if st.session_state.get("_last_audio_hash") == audio_hash:
        return  # Same audio, already transcribed
    st.session_state["_last_audio_hash"] = audio_hash

    with st.spinner("Transcribing audio…"):
        try:
            import numpy as np
            import whisper
            from scipy.io import wavfile

            # Decode WAV from bytes — no temp file, no ffmpeg needed
            sample_rate, data = wavfile.read(io.BytesIO(audio_bytes))

            # Convert to float32 mono in [-1, 1]
            if data.ndim > 1:
                data = data.mean(axis=1)
            if data.dtype == np.int16:
                data = data.astype(np.float32) / 32768.0
            elif data.dtype == np.int32:
                data = data.astype(np.float32) / 2147483648.0
            else:
                data = data.astype(np.float32)

            # Resample to 16 kHz if needed (Whisper expects 16000 Hz)
            target_sr = whisper.audio.SAMPLE_RATE  # 16000
            if sample_rate != target_sr:
                from scipy.signal import resample_poly
                from math import gcd
                g = gcd(sample_rate, target_sr)
                data = resample_poly(data, target_sr // g, sample_rate // g).astype(np.float32)

            model = _get_whisper_model()
            result = model.transcribe(data, fp16=False, language="en", temperature=0)
            text = result.get("text", "").strip()
            if text:
                st.session_state["_transcribed_text"] = text
                st.session_state["_voice_prefilled"] = True
                st.rerun()
        except ImportError:
            st.warning("Voice input requires `openai-whisper`. Run: `pip install openai-whisper`")
        except Exception as e:
            st.error(f"Transcription failed: {e}")


@st.cache_resource
def _get_whisper_model():
    import whisper
    return whisper.load_model("base")


def _mime_type(filename: str) -> str:
    ext = filename.lower().split(".")[-1]
    return {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/png")


def _history_to_api_messages(history: list) -> list:
    """Convert Streamlit history list to Claude API messages format."""
    messages = []
    for turn in history:
        role = turn["role"]
        content = turn["content"]
        messages.append({"role": role, "content": content})
    return messages


# ── Catalog Tab ───────────────────────────────────────────────────────────────

CATALOG_CARD_HEIGHT = 128


def _catalog_card_html(a: dict, color: str, btn_key: str, *, card_bg: str, card_border: str,
                       card_text: str, card_muted: str, enabled_color: str) -> str:
    """Marketplace-style agent listing card (isolated iframe document). All agent fields are escaped."""
    from html import escape as _e
    title = a.get("display_name") or a["name"]
    initial = _e(title.strip()[:1].upper() or "?")
    model = _e(str(a.get("model", "")).replace("claude-", ""))
    lock = a.get("namespace_lock")
    lock_html = f'<span class="chip lock">locked: {_e(str(lock))}</span>' if lock else ""
    return f"""<!DOCTYPE html><html><head><style>
*{{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;}}
body{{background:transparent;padding:0 0 8px 0;}}
.card{{display:flex;gap:12px;height:120px;background:{card_bg};border:1px solid {card_border};
       border-radius:12px;padding:12px 14px;cursor:pointer;user-select:none;overflow:hidden;
       transition:background .15s,border-color .15s,box-shadow .15s;}}
.card:hover{{background:{color}28;border-color:{color};box-shadow:0 0 0 2px {color}44;}}
.card:active{{background:{color}44;}}
.avatar{{position:relative;flex:none;width:40px;height:40px;border-radius:10px;background:{color}33;
         color:{color};border:1px solid {color}55;display:flex;align-items:center;justify-content:center;
         font-weight:700;font-size:1rem;}}
.avatar i{{position:absolute;right:-3px;bottom:-3px;width:10px;height:10px;border-radius:50%;
           background:{enabled_color};border:2px solid {card_bg};}}
.body{{min-width:0;display:flex;flex-direction:column;gap:3px;}}
.name{{font-weight:700;color:{card_text};font-size:0.86rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.desc{{color:{card_muted};font-size:0.76rem;line-height:1.35;display:-webkit-box;
       -webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}}
.chips{{margin-top:auto;display:flex;gap:6px;flex-wrap:nowrap;overflow:hidden;}}
.chip{{flex:none;font-size:0.66rem;color:{card_muted};border:1px solid {card_border};border-radius:10px;padding:1px 7px;}}
.chip.lock{{flex:0 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.chip.cat{{background:{color}33;color:{color};border-color:{color}55;font-weight:600;text-transform:uppercase;}}
</style></head><body><script>{COS_CLICK_PROXY_JS}</script>
<div class="card" onclick="cosClickProxy(window.parent.document,'card:{btn_key}')">
  <div class="avatar">{initial}<i></i></div>
  <div class="body">
    <div class="name" title="{_e(title)}">{_e(title)}</div>
    <div class="desc">{_e(a.get("description", ""))}</div>
    <div class="chips"><span class="chip cat">{_e(str(a.get("category", "")))}</span><span class="chip">{model}</span><span class="chip">{_e(str(a.get("max_tokens", "")))} tok</span>{lock_html}</div>
  </div>
</div>
</body></html>"""



def _render_catalog_tab(agents: list, api_get, api_post):
    import streamlit.components.v1 as _cv1
    from dashboard.components.brand import _mix, get_theme, get_ns_brand
    tv = get_theme_vars()

    # Brand-aware card colors — override ClaudeOS green SURFACE for namespace clients
    _ns_brand = get_ns_brand()
    _brand_color = (_ns_brand.get("color") or "").strip()
    if _brand_color:
        _is_dark = (get_theme() == "dark")
        if _is_dark:
            _card_bg     = _mix(_brand_color, False, 0.78)
            _card_text   = "#FAF8F7"
            _card_muted  = (_ns_brand.get("accent_color") or _ns_brand.get("text_muted_color") or "#C8A96E").strip()
            _card_border = _mix(_brand_color, False, 0.52)
        else:
            _card_bg     = (_ns_brand.get("surface_color") or "").strip() or tv["SURFACE"]
            _card_text   = (_ns_brand.get("text_color") or tv["TEXT"]).strip()
            _card_muted  = (_ns_brand.get("text_muted_color") or tv["TEXT_MUTED"]).strip()
            _card_border = (_ns_brand.get("border_color") or tv["BORDER"]).strip()
        _enabled_dot_color = _brand_color
    else:
        _card_bg           = tv["SURFACE"]
        _card_text         = tv["TEXT"]
        _card_muted        = tv["TEXT_MUTED"]
        _card_border       = tv["BORDER"]
        _enabled_dot_color = "#5a9e56"

    col1, col2 = st.columns([2, 1])
    with col1:
        search = st.text_input("Search agents", placeholder="name, category, tag…",
                               label_visibility="collapsed")
    with col2:
        cats = ["All"] + sorted({a["category"] for a in agents})
        cat_filter = st.selectbox("Category", cats, label_visibility="collapsed")

    filtered = agents
    if search:
        q = search.lower()
        filtered = [a for a in filtered if
                    q in a["name"] or q in a["description"] or q in a["category"]
                    or any(q in t for t in a.get("tags", []))]
    if cat_filter != "All":
        filtered = [a for a in filtered if a["category"] == cat_filter]

    st.markdown(f"**{len(filtered)}** agents")
    st.markdown("---")

    _COLS = 3
    for i in range(0, len(filtered), _COLS):
        cols = st.columns(_COLS)
        for j, col in enumerate(cols):
            if i + j >= len(filtered):
                break
            a = filtered[i + j]
            color = CATEGORY_COLORS.get(a["category"], _brand_color or PRIMARY)
            # Replace ClaudeOS green category colors with brand primary when brand is set
            if _brand_color and color in ("#407E3C", "#5a9e56"):
                color = _brand_color
            with col:
                _safe = a['name'].replace('-', '_').replace(' ', '_')
                _btn_key = f"card_chat_{_safe}"
                _cv1.html(
                    _catalog_card_html(
                        a, color, _btn_key,
                        card_bg=_card_bg, card_border=_card_border,
                        card_text=_card_text, card_muted=_card_muted,
                        enabled_color=_enabled_dot_color if a["enabled"] else "#6b7280",
                    ),
                    height=CATALOG_CARD_HEIGHT, scrolling=False,
                )
                if proxy_button(f"card:{_btn_key}", key=_btn_key):
                    st.session_state["_pending_agent"] = a["name"]
                    st.session_state["_goto_chat"] = True
                    st.rerun()


# ── Runs Tab ──────────────────────────────────────────────────────────────────

_STATUS_LABELS = {
    "done": "● done", "failed": "● failed", "running": "● running", "pending": "○ pending",
}


def _format_duration(ms) -> str:
    """Milliseconds -> compact human duration: 850ms, 1.2s, 2m 05s."""
    try:
        ms = int(ms or 0)
    except (TypeError, ValueError):
        return "—"
    if ms <= 0:
        return "—"
    if ms < 1000:
        return f"{ms}ms"
    if ms < 60_000:
        return f"{ms / 1000:.1f}s"
    return f"{ms // 60_000}m {ms % 60_000 // 1000:02d}s"


def _runs_table_rows(runs: list) -> list:
    """Compact rows for the Runs table. Agent name falls back name > display name > short id."""
    rows = []
    for r in runs:
        agent = (r.get("agent_name") or r.get("agent_display_name")
                 or (r.get("agent_id") or "")[:12] or "—")
        score = r.get("eval_score")
        status = r.get("status", "")
        rows.append({
            "Agent":     agent,
            "Namespace": r.get("namespace") or "",
            "Status":    _STATUS_LABELS.get(status, status),
            "Quality":   float(score) if score is not None else None,
            "Tokens":    int(r.get("tokens_in") or 0) + int(r.get("tokens_out") or 0),
            "Duration":  _format_duration(r.get("duration_ms")),
            "Started":   (r.get("created_at") or "")[:16].replace("T", " "),
            "Run":       (r.get("id") or "")[:8],
        })
    return rows


def _render_runs_tab(api_get):
    tv = get_theme_vars()
    st.subheader("Recent Agent Runs")

    _role = st.session_state.get("user_role", "admin")
    _user_ns = st.session_state.get("user_namespace")
    _runs_url = (
        f"/agents/runs?limit=50&namespace={_user_ns}"
        if _role in ("client", "viewer") and _user_ns
        else "/agents/runs?limit=50"
    )
    runs_data = api_get(_runs_url)
    if not runs_data or not runs_data.get("runs"):
        st.caption("No runs yet.")
        return

    runs = runs_data["runs"]

    # Summary stats
    done = sum(1 for r in runs if r.get("status") == "done")
    failed = sum(1 for r in runs if r.get("status") == "failed")
    scored = [r for r in runs if r.get("eval_score") is not None]
    avg_score = sum(r["eval_score"] for r in scored) / len(scored) if scored else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Runs", len(runs))
    c2.metric("Completed", done)
    c3.metric("Failed", failed)
    c4.metric("Avg Quality", f"{avg_score:.1f}/5" if avg_score else "—",
              help="LLM-as-Judge weighted score")

    st.markdown("---")

    st.dataframe(
        _runs_table_rows(runs),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Status":  st.column_config.TextColumn("Status", width="small"),
            "Quality": st.column_config.ProgressColumn(
                "Quality", min_value=0, max_value=5, format="%.1f", width="small",
                help="LLM-as-Judge weighted score (0–5)"),
            "Tokens":  st.column_config.NumberColumn("Tokens", format="%d", width="small",
                help="Input + output tokens"),
            "Duration": st.column_config.TextColumn("Duration", width="small"),
            "Run":     st.column_config.TextColumn("Run", width="small"),
        },
    )

    # Show eval reasoning for selected run
    st.markdown("---")
    run_ids = [(r.get("id") or "")[:8] + "…" for r in runs if r.get("eval_reasoning")]
    if run_ids:
        sel = st.selectbox("View eval reasoning", ["—"] + run_ids, key="eval_sel")
        if sel != "—":
            idx = run_ids.index(sel)
            run = [r for r in runs if r.get("eval_reasoning")][idx]
            dims = {}
            try:
                dims = json.loads(run.get("eval_dimensions") or "{}")
            except Exception:
                pass
            st.markdown(f"**Reasoning:** {run.get('eval_reasoning', '')}")
            if dims:
                dc1, dc2, dc3, dc4 = st.columns(4)
                dc1.metric("Task Completion", f"{dims.get('task_completion', 0):.1f}/5")
                dc2.metric("Factual Grounding", f"{dims.get('factual_grounding', 0):.1f}/5")
                dc3.metric("Conciseness", f"{dims.get('conciseness', 0):.1f}/5")
                dc4.metric("Safety", "Pass" if dims.get("safety", 1) >= 1 else "Fail")
