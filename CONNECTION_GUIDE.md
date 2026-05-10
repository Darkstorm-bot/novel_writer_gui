# NovelForge — Frontend ↔ Backend Connection

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BROWSER                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  index.html + styles.css + app.js                                   │   │
│  │  • Real-time generation visualization                               │   │
│  │  • Character relation tree (SVG)                                    │   │
│  │  • Chapter editor with live token streaming                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              │ WebSocket (ws://localhost:8765)             │
│                              ▼                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           bridge.py                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  WebSocket Server (port 8765)                                       │   │
│  │  HTTP Server (port 8080) — serves static files                      │   │
│  │                                                                     │   │
│  │  Commands handled:                                                  │   │
│  │  • generate_chapter → calls forge.write_chapter()                   │   │
│  │  • run_critic → calls forge.critic.review()                         │   │
│  │  • auto_revise → calls forge revision loop                          │   │
│  │  • get_characters → returns forge.state.characters                  │   │
│  │  • save_character → updates forge.state.characters                  │   │
│  │  • run_research → calls Crawl4AI MCP                                │   │
│  │  • generate_outline → calls forge.research_and_outline()            │   │
│  │  • check_continuity → queries temporal KG                           │   │
│  │  • get_registry → queries mistake registry MCP                      │   │
│  │  • update_settings → updates forge config                           │   │
│  │                                                                     │   │
│  │  Events streamed:                                                   │   │
│  │  • task_started, task_progress, token_stream                        │   │
│  │  • critic_complete, generation_complete                             │   │
│  │  • model_status, error                                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              │ imports                                       │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  novelforge_v2.py                                                   │   │
│  │  • IntelligentOrchestrator                                          │   │
│  │  • HierarchicalPlanner                                              │   │
│  │  • HeadModelClient (21B) → http://localhost:1234                    │   │
│  │  • CriticModelClient (14B) → http://localhost:1235                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              │ MCP protocol                                 │
│                              ▼                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │ MemPalace   │  │ Crawl4AI    │  │ FileSystem  │  │ MistakeRegistry │  │
│  │ MCP Server  │  │ MCP Server  │  │ MCP Server  │  │ MCP Server      │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Connection Status

| Component | Status | How to Verify |
|-----------|--------|---------------|
| Frontend → bridge.py | ✅ WebSocket | Green dot in bottom-left |
| bridge.py → NovelForge | ✅ Python import | Console shows "Backend: CONNECTED" |
| NovelForge → Head Model | ⚠️ Requires LM Studio on :1234 | Check LM Studio server tab |
| NovelForge → Critic Model | ⚠️ Requires LM Studio on :1235 | Check LM Studio server tab |
| bridge.py → MCP Servers | ⚠️ Requires servers running | Check terminal output |

## How to Connect Everything

### Step 1: Start LLM Models

**LM Studio** (recommended):
1. Load 21B Deckard → Server tab → Start on port 1234
2. Load 14B Critic → Server tab → Start on port 1235

**Or Ollama**:
```bash
ollama serve &
OLLAMA_HOST=localhost:1234 ollama run qwen2.5:14b &
OLLAMA_HOST=localhost:1235 ollama run qwen2.5:14b &
```

### Step 2: Start MCP Servers

```bash
# Terminal 1
python mempalace_mcp_server.py

# Terminal 2
python crawl4ai_mcp_server.py

# Terminal 3
python filesystem_mcp_server.py

# Terminal 4
python mistake_registry_mcp_server.py
```

### Step 3: Start the Bridge

```bash
# Terminal 5
pip install websockets aiohttp
python bridge.py
```

You should see:
```
============================================================
NOVELFORGE REAL-TIME BRIDGE
============================================================
[NovelForge] Backend initialized successfully
[HTTP] Server running at http://localhost:8080
[WS] Server running at ws://localhost:8765

✅ Backend: CONNECTED (NovelForge active)

Open your browser to: http://localhost:8080
============================================================
```

### Step 4: Open Browser

Navigate to `http://localhost:8080`

The frontend will:
1. Connect to `ws://localhost:8765`
2. Show "Connected" in bottom-left
3. Detect real backend mode
4. Send all commands to bridge.py
5. Receive real LLM output streamed live

## What Happens When You Click "Generate Chapter"

```
[Frontend] Click "Generate Chapter"
    │
    ▼
[Frontend] Open modal → User fills prompt → Click "Generate"
    │
    ▼
[Frontend] Send WS: {type: "generate_chapter", title: "...", prompt: "..."}
    │
    ▼
[bridge.py] Receive command
    │
    ▼
[bridge.py] Call: forge.write_chapter(novel_name, chapter, prompt)
    │
    ▼
[NovelForge] Orchestrator plans task tree:
    ├── outline (head, 21B)
    ├── scene_draft (head, 21B) 
    ├── critic_review (critic, 14B)
    └── dialogue_polish (both)
    │
    ▼
[NovelForge] Execute tasks sequentially
    │
    ├── Send WS: {type: "task_started", task: "outline", model: "head"}
    ├── Send WS: {type: "task_progress", task: "outline", progress: 100}
    ├── Send WS: {type: "task_started", task: "scene_draft", model: "head"}
    ├── [Stream tokens from LLM]
    │   ├── Send WS: {type: "token_stream", token: "The ", total_tokens: 1}
    │   ├── Send WS: {type: "token_stream", token: "rain ", total_tokens: 2}
    │   └── ... (every token)
    ├── Send WS: {type: "task_progress", task: "scene_draft", progress: 85}
    ├── Send WS: {type: "task_started", task: "critic_review", model: "critic"}
    ├── Send WS: {type: "critic_complete", score: 0.82, issues: [...]}
    └── Send WS: {type: "generation_complete", content: "...", quality: 0.82}
    │
    ▼
[Frontend] Receive events and update UI in real-time:
    ├── Show generation overlay
    ├── Update progress bar
    ├── Stream text into overlay
    ├── Show critic score overlay
    └── Insert final text into editor
```

## Fallback Behavior

If any component is missing, the system gracefully degrades:

| Missing Component | Behavior |
|-------------------|----------|
| bridge.py not running | Frontend runs in demo mode (local simulation) |
| LLM models not loaded | bridge.py shows "SIMULATION MODE" |
| MCP servers not running | bridge.py skips tool calls, uses fallback |
| Only 1 GPU | Run both models on same GPU (slower) |
| No GPU | Models run on CPU (very slow) |

## WebSocket Protocol Reference

### Commands (Frontend → Backend)

```javascript
// Generate chapter
{type: "generate_chapter", title: "...", prompt: "...", novel_name: "...", chapter_id: "..."}

// Run critic
{type: "run_critic", content: "..."}

// Auto-revise
{type: "auto_revise", content: "..."}

// Save content
{type: "save_content", chapter_id: "...", content: "..."}

// Get chapters
{type: "get_chapters", novel_name: "..."}

// Add chapter
{type: "add_chapter", title: "..."}

// Get characters
{type: "get_characters"}

// Save character
{type: "save_character", character: {...}}

// Research
{type: "run_research", query: "..."}

// Generate outline
{type: "generate_outline", premise: "..."}

// Check continuity
{type: "check_continuity"}

// Get registry
{type: "get_registry"}

// Update settings
{type: "update_settings", settings: {...}}
```

### Events (Backend → Frontend)

```javascript
// Connection
{type: "connected", mode: "real|simulation", message: "..."}
{type: "connection_info", mode: "...", head_endpoint: "...", critic_endpoint: "..."}

// Tasks
{type: "task_started", task: "...", model: "head|critic", message: "..."}
{type: "task_progress", task: "...", progress: 0-100, model: "...", tokens: N, elapsed: N}

// Generation
{type: "token_stream", token: "...", total_tokens: N, model: "..."}
{type: "generation_complete", title: "...", content: "...", tokens: N, quality: 0-1}

// Critic
{type: "critic_complete", score: 0-1, issues: [{severity, category, text}], model: "..."}

// Revision
{type: "revision_complete", content: "...", model: "..."}

// Data
{type: "chapters_list", chapters: [{id, title, words}]}
{type: "chapter_added", chapter: {id, title, words}}
{type: "characters_list", characters: [{id, name, role}]}
{type: "character_saved", character: {...}}
{type: "research_complete", query: "...", results: [{title, url, excerpt}]}
{type: "outline_complete", outline: [...]}
{type: "continuity_complete", timeline: [...], characters: [...], plot_threads: [...]}
{type: "registry_data", mistakes: [...], stats: {...}}
{type: "settings_updated", settings: {...}}

// Status
{type: "model_status", head: {status, temp, activity}, critic: {status, temp, activity}}
{type: "error", message: "..."}
```

## Troubleshooting

### "Backend: SIMULATION MODE"
- bridge.py couldn't import novelforge_v2.py
- Make sure all Python files are in the same directory
- Check `pip install aiohttp websockets`

### "Disconnected" in frontend
- bridge.py is not running
- Check `python bridge.py` output
- Verify port 8765 is not blocked

### "NovelForge initialized successfully" but generation is slow
- LLM models are loading for the first time
- First generation takes 30-60s as models warm up
- Subsequent generations are faster

### Models return errors
- Verify LM Studio is serving on correct ports
- Test: `curl http://localhost:1234/v1/models`
- Check model quantization (Q4_K_M recommended)

### MCP servers not found
- Start all 4 MCP servers before bridge.py
- Or bridge.py will skip them and use fallbacks
