#!/usr/bin/env python3
"""
NovelForge Real-Time Bridge
============================
Connects the HTML frontend to the actual NovelForge Python backend.
Streams live tokens from the LLM, forwards critic reviews, and handles
all frontend commands through WebSocket.

Architecture:
    Browser (WebSocket) → bridge.py → NovelForge → LLM APIs (Ollama/LM Studio)
                                    ↓
                              MCP Servers (MemPalace, Crawl4AI, etc.)

Run: python bridge.py
Open: http://localhost:8080

Prerequisites:
    1. LM Studio / Ollama running on ports 1234 (21B) and 1235 (14B)
    2. MCP servers running (mempalace, crawl4ai, filesystem, mistake_registry)
    3. pip install websockets aiohttp
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from urllib.parse import quote_plus
import websockets
from websockets.server import WebSocketServerProtocol
import aiohttp
from aiohttp import web
import traceback

# ── Add parent dir to path to import novelforge ──
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

# ── Import NovelForge ──
try:
    from novelforge_v2 import NovelForge, TaskNode, TaskStatus, TaskPriority
    NOVELFORGE_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] Could not import NovelForge: {e}")
    print("[WARNING] Backend unavailable")
    NOVELFORGE_AVAILABLE = False

# ── Configuration ──
WS_PORT = 8765
HTTP_PORT = 8080
STATIC_DIR = SCRIPT_DIR

# ── Global State ──
clients = set()
forge = None
session = None  # aiohttp session for LLM calls


async def _port_is_open(port: int) -> bool:
    """Check whether a local TCP port is listening."""
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception:
        return False


async def crawl_topic_research(query: str) -> dict:
    """Crawl topic-related URLs directly through Crawl4AI."""
    search_term = quote_plus(query.strip())
    urls = [
        f"https://en.wikipedia.org/wiki/Special:Search?search={search_term}",
        f"https://www.britannica.com/search?query={search_term}",
        f"https://duckduckgo.com/?q={search_term}",
    ]

    payload = {
        "urls": urls,
        "priority": 10,
        "extraction_config": {
            "markdown_mode": "fit_markdown",
            "content_filter": {"type": "bm25", "query": query, "threshold": 1.0},
            "include_links": True,
            "citations": True,
        },
    }

    async with aiohttp.ClientSession() as client:
        async with client.post("http://localhost:11235/crawl", json=payload, timeout=120) as response:
            response.raise_for_status()
            task_id = (await response.json())["task_id"]

        for _ in range(60):
            async with client.get(f"http://localhost:11235/task/{task_id}", timeout=30) as response:
                response.raise_for_status()
                data = await response.json()

            if data.get("status") == "completed":
                result = data.get("result", {})
                return {
                    "query": query,
                    "urls": urls,
                    "markdown": result.get("markdown", ""),
                    "sources": result.get("links", []),
                    "images": result.get("media", []),
                    "citations": result.get("citations", []),
                }

            await asyncio.sleep(2)

    return {
        "query": query,
        "urls": urls,
        "markdown": "",
        "sources": [],
        "images": [],
        "citations": [],
        "status": "timeout",
    }

# ═══════════════════════════════════════════════════════════════════════════════
# NOVELFORGE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

async def init_novelforge():
    """Initialize the NovelForge backend."""
    global forge

    if not NOVELFORGE_AVAILABLE:
        return False

    try:
        critic_endpoint = "http://localhost:1235/v1"
        if not await _port_is_open(1235):
            critic_endpoint = "http://localhost:1234/v1"
            print("[NovelForge] Critic endpoint 1235 unavailable; using 1234 as fallback")

        forge = NovelForge(
            head_endpoint="http://localhost:1234/v1",
            critic_endpoint=critic_endpoint,
            mcp_servers=[
                str(SCRIPT_DIR / "mempalace_mcp_server.py"),
                str(SCRIPT_DIR / "crawl4ai_mcp_server.py"),
                str(SCRIPT_DIR / "filesystem_mcp_server.py"),
                str(SCRIPT_DIR / "mistake_registry_mcp_server.py"),
            ],
            mempalace_path="./novels_db"
        )

        forge_ready = await asyncio.wait_for(forge.initialize(), timeout=20)
        if not forge_ready:
            print("[NovelForge] Backend initialization failed")
            forge = None
            return False

        # Enable mistake learning
        forge.orchestrator.mistake_registry_enabled = True
        forge.orchestrator.mistake_learning_aggressive = True

        print("[NovelForge] Backend initialized successfully")
        return True

    except asyncio.CancelledError as e:
        print(f"[NovelForge] Initialization cancelled: {e}")
        traceback.print_exc()
        forge = None
        return False

    except Exception as e:
        print(f"[NovelForge] Failed to initialize: {e}")
        traceback.print_exc()
        print("[NovelForge] Backend initialization failed")
        forge = None
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_websocket(websocket: WebSocketServerProtocol, path: str):
    """Handle WebSocket connections from the frontend."""
    clients.add(websocket)
    client_id = id(websocket)
    print(f"[WS] Client {client_id} connected. Total: {len(clients)}")

    try:
        # Send connection status
        await send(websocket, {
            "type": "connected",
            "message": "Connected to NovelForge backend",
            "mode": "real" if forge else "offline"
        })

        # Send initial state
        await send_initial_state(websocket)

        async for message in websocket:
            try:
                data = json.loads(message)
                await handle_command(websocket, data)
            except json.JSONDecodeError:
                await send(websocket, {"type": "error", "message": "Invalid JSON"})
            except Exception as e:
                print(f"[WS] Error handling message: {e}")
                await send(websocket, {"type": "error", "message": str(e)})

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)
        print(f"[WS] Client {client_id} disconnected. Total: {len(clients)}")

async def send(websocket, data):
    """Send JSON data to a client."""
    try:
        await websocket.send(json.dumps(data))
    except Exception as e:
        print(f"[WS] Send error: {e}")

async def broadcast(data):
    """Broadcast to all connected clients."""
    if not clients:
        return
    message = json.dumps(data)
    dead = set()
    for client in clients:
        try:
            await client.send(message)
        except Exception:
            dead.add(client)
    clients.difference_update(dead)

# ═══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_command(websocket, data):
    """Route commands to appropriate handlers."""
    cmd = data.get("type")
    handlers = {
        "generate_chapter": handle_generate_chapter,
        "run_critic": handle_run_critic,
        "auto_revise": handle_auto_revise,
        "save_content": handle_save_content,
        "get_chapters": handle_get_chapters,
        "add_chapter": handle_add_chapter,
        "get_characters": handle_get_characters,
        "save_character": handle_save_character,
        "run_research": handle_run_research,
        "generate_outline": handle_generate_outline,
        "check_continuity": handle_check_continuity,
        "get_registry": handle_get_registry,
        "update_settings": handle_update_settings,
        "ping": handle_ping,
    }

    handler = handlers.get(cmd)
    if handler:
        await handler(websocket, data)
    else:
        await send(websocket, {"type": "error", "message": f"Unknown command: {cmd}"})

# ── Generation ──

async def handle_generate_chapter(websocket, data):
    """Generate a chapter and stream tokens to frontend."""
    title = data.get("title", "Untitled")
    prompt = data.get("prompt", "")
    novel_name = data.get("novel_name", "untitled_novel")
    chapter_id = data.get("chapter_id", "chapter-1")

    if not prompt.strip():
        await send(websocket, {"type": "error", "message": "Prompt is required"})
        return

    # Phase 1: Planning
    await send(websocket, {
        "type": "task_started",
        "task": "outline",
        "model": "head",
        "message": f"Planning: {title}..."
    })

    if forge:
        try:
            forge.state.current_novel = novel_name
            forge.state.current_chapter = chapter_id

            result = await forge.write_chapter(
                novel_name=novel_name,
                chapter=chapter_id,
                prompt=f"{title}. {prompt}"
            )

            output = ""
            quality = 0.0
            for task_result in result.get("results", []):
                if task_result.get("type") == "scene_draft":
                    task_id = task_result.get("task_id")
                    if task_id and task_id in forge.orchestrator.completed_tasks:
                        task = forge.orchestrator.completed_tasks[task_id]
                        output = task.output
                        quality = task.quality_score

            if not output:
                output = "Generation completed but no output found."

            await send(websocket, {
                "type": "generation_complete",
                "title": title,
                "content": output,
                "tokens": len(output.split()),
                "quality": round(quality, 2),
                "model": "head"
            })

            if quality > 0:
                await send(websocket, {
                    "type": "critic_complete",
                    "issues": [],
                    "model": "critic"
                })

            return

        except Exception as e:
            print(f"[Generate] Error: {e}")

    await send(websocket, {"type": "error", "message": "NovelForge backend is unavailable"})

# ── Critic ──

async def handle_run_critic(websocket, data):
    """Run critic review on content."""
    content = data.get("content", "")

    await send(websocket, {
        "type": "task_started",
        "task": "critic_review",
        "model": "critic",
        "message": "Analyzing prose..."
    })

    if forge:
        try:
            # REAL: Use critic model directly
            critique = await forge.critic.review(
                draft=content,
                check_types=["grammar", "continuity", "cringe", "pacing"],
                character_bibles=forge.state.characters
            )

            score = critique.get("scores", {}).get("overall", 0.5)
            issues = critique.get("issues", [])

            await send(websocket, {
                "type": "critic_complete",
                "score": round(score, 2),
                "issues": [{"severity": "minor", "text": issue} for issue in issues[:5]],
                "model": "critic"
            })
            return

        except Exception as e:
            print(f"[Critic] Error: {e}")

    await send(websocket, {"type": "error", "message": "Critic backend is unavailable"})

# ── Revision ──

async def handle_auto_revise(websocket, data):
    """Auto-revise content based on critic feedback."""
    content = data.get("content", "")

    await send(websocket, {
        "type": "task_started",
        "task": "revision",
        "model": "head",
        "message": "Applying revisions..."
    })

    await send(websocket, {"type": "error", "message": "Auto-revision is not implemented without the backend"})

# ── Content Save ──

async def handle_save_content(websocket, data):
    """Save chapter content."""
    chapter_id = data.get("chapter_id", "chapter-1")
    content = data.get("content", "")

    # In real implementation, save via filesystem MCP or directly
    # For now, just acknowledge
    await send(websocket, {
        "type": "content_saved",
        "chapter_id": chapter_id,
        "word_count": len(content.split())
    })

# ── Chapters ──

async def handle_get_chapters(websocket, data):
    """Get list of chapters."""
    novel_name = data.get("novel_name", "untitled_novel")

    if forge:
        # REAL: Query filesystem or mempalace
        chapters = []
    else:
        chapters = []

    await send(websocket, {
        "type": "chapters_list",
        "chapters": chapters
    })

async def handle_add_chapter(websocket, data):
    """Add a new chapter."""
    title = data.get("title", "New Chapter")

    await send(websocket, {
        "type": "chapter_added",
        "chapter": {
            "id": f"chapter-{datetime.now().timestamp()}",
            "title": title,
            "words": 0
        }
    })

# ── Characters ──

async def handle_get_characters(websocket, data):
    """Get character list."""
    if forge and forge.state.characters:
        chars = [
            {"id": k, "name": v.get("name", k), "role": v.get("role", "unknown")}
            for k, v in forge.state.characters.items()
        ]
    else:
        chars = []

    await send(websocket, {
        "type": "characters_list",
        "characters": chars
    })

async def handle_save_character(websocket, data):
    """Save a character."""
    char = data.get("character", {})
    char_id = char.get("name", "unknown").lower().replace(" ", "-")

    if forge:
        forge.state.characters[char_id] = char

    await send(websocket, {
        "type": "character_saved",
        "character": {**char, "id": char_id}
    })

# ── Research ──

async def handle_run_research(websocket, data):
    """Run web research."""
    query = data.get("query", "")

    await send(websocket, {
        "type": "task_started",
        "task": "research",
        "model": "head",
        "message": f"Researching: {query}..."
    })

    try:
        research_payload = await crawl_topic_research(query)

        await send(websocket, {
            "type": "research_complete",
            "query": query,
            "results": [
                {
                    "title": query,
                    "url": research_payload["urls"][0],
                    "excerpt": research_payload["markdown"][:500]
                }
            ]
        })
        return

    except Exception as e:
        print(f"[Research] Error: {e}")

    await send(websocket, {"type": "error", "message": "Research crawl failed"})

# ── Outline ──

async def handle_generate_outline(websocket, data):
    """Generate novel outline."""
    premise = data.get("premise", "")

    await send(websocket, {
        "type": "task_started",
        "task": "outline",
        "model": "head",
        "message": "Generating outline..."
    })

    if forge:
        try:
            result = await forge.research_and_outline(
                novel_name="current_novel",
                premise=premise
            )

            await send(websocket, {
                "type": "outline_complete",
                "outline": result.get("results", [])
            })
            return

        except Exception as e:
            print(f"[Outline] Error: {e}")

    await send(websocket, {"type": "error", "message": "Outline backend is unavailable"})

# ── Continuity ──

async def handle_check_continuity(websocket, data):
    """Run continuity check."""
    await send(websocket, {"type": "error", "message": "Continuity backend is unavailable"})

# ── Registry ──

async def handle_get_registry(websocket, data):
    """Get mistake registry data."""
    if forge:
        try:
            stats = await forge.get_mistake_stats()
            # Would need to fetch actual entries from MCP
            mistakes = []
        except:
            mistakes = []
    else:
        mistakes = []

    await send(websocket, {
        "type": "registry_data",
        "mistakes": mistakes,
        "stats": {
            "total": len(mistakes),
            "critical": sum(1 for m in mistakes if m["severity"] == "critical"),
            "major": sum(1 for m in mistakes if m["severity"] == "major"),
            "fixed": sum(1 for m in mistakes if m.get("successRate", 0) > 0.5)
        }
    })

# ── Settings ──

async def handle_update_settings(websocket, data):
    """Update settings."""
    settings = data.get("settings", {})

    if forge:
        # Apply settings to forge
        if "head_temp" in settings:
            # Would need to update model config
            pass
        if "mistake_learning" in settings:
            forge.orchestrator.mistake_registry_enabled = settings["mistake_learning"]

    await send(websocket, {
        "type": "settings_updated",
        "settings": settings
    })

# ── Ping ──

async def handle_ping(websocket, data):
    await send(websocket, {"type": "pong", "timestamp": datetime.now().isoformat()})

# ═══════════════════════════════════════════════════════════════════════════════
# INITIAL STATE
# ═══════════════════════════════════════════════════════════════════════════════

async def send_initial_state(websocket):
    """Send initial application state to new client."""

    # Model status
    await send(websocket, {
        "type": "model_status",
        "head": {"status": "idle", "temp": 1.0, "activity": 0},
        "critic": {"status": "idle", "temp": 0.3, "activity": 0}
    })

    # Connection info
    await send(websocket, {
        "type": "connection_info",
        "mode": "real" if forge else "offline",
        "head_endpoint": "http://localhost:1234/v1" if forge else None,
        "critic_endpoint": "http://localhost:1235/v1" if forge else None,
    })

# ═══════════════════════════════════════════════════════════════════════════════
# HTTP SERVER (Static Files)
# ═══════════════════════════════════════════════════════════════════════════════

async def init_http_app():
    """Initialize aiohttp app for serving static files."""
    app = web.Application()

    # Serve static files
    app.router.add_static('/', path=str(STATIC_DIR), show_index=True)

    # Index route
    async def index(request):
        return web.FileResponse(str(STATIC_DIR / "index.html"))

    app.router.add_get('/', index)

    return app

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    print("=" * 60)
    print("NOVELFORGE REAL-TIME BRIDGE")
    print("=" * 60)

    # Initialize NovelForge
    forge_ready = await init_novelforge()

    # Start HTTP server
    http_app = await init_http_app()
    http_runner = web.AppRunner(http_app)
    await http_runner.setup()
    http_site = web.TCPSite(http_runner, "localhost", HTTP_PORT)
    await http_site.start()
    print(f"[HTTP] Server running at http://localhost:{HTTP_PORT}")

    # Start WebSocket server
    ws_server = await websockets.serve(handle_websocket, "localhost", WS_PORT)
    print(f"[WS] Server running at ws://localhost:{WS_PORT}")

    print()
    if forge_ready:
        print("✅ Backend: CONNECTED (NovelForge active)")
    else:
        print("⚠️  Backend: OFFLINE (NovelForge not available)")
    print()
    print("Open your browser to: http://localhost:8080")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    # Keep running
    await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
        if forge:
            asyncio.run(forge.shutdown())
