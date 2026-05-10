#!/usr/bin/env python3
"""
NovelForge WebSocket Bridge Launcher
====================================
Compatibility entrypoint that delegates to bridge.py.

Run: python websocket_server.py
Then open: http://localhost:8080
"""

import asyncio

from bridge import main as bridge_main


if __name__ == "__main__":
    try:
        asyncio.run(bridge_main())
    except KeyboardInterrupt:
        print("\n[Server] Shutting down...")
