"""ClaudeOS MCP Tool Server — Phase 12.2.

Exposes ClaudeOS agents as MCP (Model Context Protocol) tools so any
MCP-compatible client (Claude Desktop, Cursor, VS Code, external agents)
can discover and call them directly.

Each enabled ClaudeOS agent → one MCP Tool.
Memory search → one MCP Resource.

Transport: HTTP (streamable) on port MCP_PORT (default 5100).

Start: python -m mcp.server  (or via scripts/start_mcp.ps1)
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on path when run as __main__
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

logger = logging.getLogger("claudeos.mcp")


def build_server():
    """Build and return the MCP server instance."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError(
            "mcp package not installed. Run: pip install mcp"
        )

    mcp = FastMCP(
        name="ClaudeOS",
        instructions=(
            "ClaudeOS is an AI Operating System with 12 specialized agents. "
            "Each tool corresponds to one agent. Pass a 'prompt' string and optional "
            "'namespace' to target a specific client workspace. "
            "Results are returned synchronously (agent runs block until complete)."
        ),
    )

    # Register each enabled agent as an MCP tool
    _register_agent_tools(mcp)

    # Register memory search as a resource
    _register_memory_resource(mcp)

    return mcp


def _register_agent_tools(mcp) -> None:
    """Dynamically create one MCP tool per enabled ClaudeOS agent."""
    try:
        from agents import registry
        agents = registry.list_agents(enabled_only=True)
    except Exception as e:
        logger.warning("Could not load agents for MCP registration: %s", e)
        return

    for agent in agents:
        # Capture loop variable in closure
        def _make_tool(a):
            async def tool_fn(prompt: str, namespace: str = "global") -> str:
                """Dispatch to ClaudeOS agent and return output."""
                from agents.dispatcher import dispatch
                from agents.schemas import AgentDispatchRequest
                req = AgentDispatchRequest(
                    prompt=prompt,
                    namespace=namespace,
                    save_output=False,
                )
                run_id = dispatch(a.name, req, block=True)
                # Fetch result from DB
                from agents.dispatcher import get_run
                run = get_run(run_id)
                if run and run.get("output"):
                    return run["output"].get("text", "No output")
                if run and run.get("error"):
                    return f"Error: {run['error']}"
                return "No output returned"

            tool_fn.__name__ = a.name.replace("-", "_")
            tool_fn.__doc__ = f"{a.description}\n\nCategory: {a.category}\nModel: {a.model}"
            return tool_fn

        mcp.tool(
            name=agent.name,
            description=agent.description,
        )(_make_tool(agent))

    logger.info("Registered %d ClaudeOS agents as MCP tools", len(agents))


def _register_memory_resource(mcp) -> None:
    """Expose memory search as an MCP resource."""
    @mcp.resource("claudeos://memory/search")
    async def memory_search_resource() -> str:
        """Returns instructions for memory search — use tool instead for parameterized search."""
        return json.dumps({
            "description": "ClaudeOS memory search",
            "usage": "Call the 'search_memory' tool with query and namespace parameters",
        })

    @mcp.tool(name="search_memory", description="Search ClaudeOS memory store for relevant facts")
    async def search_memory(query: str, namespace: str = "global", mode: str = "hybrid") -> str:
        from memory.retriever import hybrid_search
        from memory import engine as mem
        try:
            if mode == "hybrid":
                results = hybrid_search(query=query, namespace=namespace, top_k=8)
            else:
                results = mem.search_semantic(query, namespace, top_k=8)
            if not results:
                return "No matching memories found."
            lines = [f"Found {len(results)} memories:\n"]
            for e in results:
                lines.append(f"- [{e.category}] {e.key}: {e.value}")
            return "\n".join(lines)
        except Exception as e:
            return f"Memory search error: {e}"


def main():
    import uvicorn
    port = int(os.environ.get("MCP_PORT", 5100))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logger.info("Starting ClaudeOS MCP server on port %d", port)

    server = build_server()
    # FastMCP provides a streamable_http_app for HTTP transport
    app = server.streamable_http_app()
    # Bind to 127.0.0.1 — MCP has no auth layer; external exposure = full agent access
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
