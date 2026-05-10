# NovelForge Frontend — Quick Start

## What You Get

A complete web-based frontend for NovelForge with:

- **Left sidebar**: LLM mode indicators (Head 21B + Critic 14B) with real-time activity bars, hamburger navigation menu, task queue, connection status
- **75% center panel**: Full-featured novel editor with chapter tabs, generation overlay with live token streaming, critic review overlay, outline panel, formatting toolbar
- **15% right sidebar**: Character selector, detailed character profiles (profile/relations/timeline/talents tabs), SVG relation tree, chapter context, session stats
- **Real-time visualization**: WebSocket connection shows exactly what the models are doing as they work

## Files

| File | Purpose |
|------|---------|
| `index.html` | Main SPA — all UI structure |
| `styles.css` | Dark theme, responsive layout, animations |
| `app.js` | Interactive logic, event handling, demo data |
| `websocket_server.py` | Python backend bridge (WebSocket + HTTP) |
| `requirements_frontend.txt` | Frontend dependencies |

## Run It

```bash
# 1. Install frontend dependencies
pip install -r requirements_frontend.txt

# 2. Start the WebSocket bridge
python websocket_server.py

# 3. Open browser
# http://localhost:8080
```

## Architecture

```
Browser (localhost:8080)
    ├── index.html + styles.css + app.js
    └── WebSocket → ws://localhost:8765
                        │
                        ▼
              websocket_server.py
                        │
            ┌───────────┼───────────┐
            │           │           │
            ▼           ▼           ▼
      Head Model   Critic Model   MCP Tools
      (port 1234)  (port 1235)   (various)
```

## Features

### Real-Time Generation Visualization
When you click "Generate Chapter":
1. Generation overlay appears with spinning indicator
2. Shows which model is active (Head 21B or Critic 14B)
3. Live token counter and timer
4. Progress bar shows task phase (outline → draft → review → revision)
5. Text streams in real-time as tokens are generated
6. Critic review appears automatically with score and issues

### LLM Mode Indicators
- **Head Model (21B)**: Shows temperature, activity bar, status (idle/thinking/writing)
- **Critic Model (14B)**: Shows temperature, activity bar, status
- Color-coded: Purple for Head, Green for Critic
- Pulsing dot when active

### Character Management
- Character list with avatars
- Click to view detailed profile
- **Profile tab**: Age, origin, motivation, fear, voice, appearance
- **Relations tab**: SVG relation tree showing connections, relationship types
- **Timeline tab**: Vertical timeline of character appearances per chapter
- **Talents tab**: Skill bars with descriptions, weaknesses highlighted in red

### Chapter Management
- Tab-based chapter navigation
- Add new chapters with "+" button
- Contenteditable editor with formatting toolbar
- Word count tracking
- Outline panel (toggle with 📋 button)
- Fullscreen mode

### Task Queue
- Shows active tasks in left sidebar
- Color-coded by model (purple = head, green = critic)
- Progress percentage
- Auto-updates as generation progresses

### Mistake Registry Page
- Filter by severity (All/Critical/Major/Minor/Cosmetic)
- Shows mistake category, description, fix success rate
- Auto-populated from critic reviews

### Settings Page
- Head model: endpoint, temperature, rep penalty, context window, thinking mode
- Critic model: endpoint, temperature, quality threshold, max revisions
- Orchestrator: max parallel tasks, token budget, mistake learning toggles
- Appearance: theme, font, font size, line height

## Connecting to Real Backend

The frontend works in demo mode out of the box. To connect to the real NovelForge backend:

1. Start NovelForge backend:
```python
from novelforge_v2 import NovelForge
forge = NovelForge(
    head_endpoint="http://localhost:1234/v1",
    critic_endpoint="http://localhost:1235/v1",
    mcp_servers=[...]
)
```

2. Update `websocket_server.py` to call NovelForge methods instead of simulating

3. The frontend will automatically receive real generation streams via WebSocket

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Ctrl+G | Generate chapter |
| Ctrl+R | Run critic review |
| Ctrl+S | Save |
| Ctrl+F | Fullscreen |
| Esc | Close modals/overlays |
