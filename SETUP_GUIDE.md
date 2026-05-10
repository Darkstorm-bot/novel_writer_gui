# NovelForge v2.0 — Setup Guide
## Agentic Novel Writing with MCP + Dual-Model Intelligence

---

## 🚀 Quick Start (TL;DR)

**One command to start the backend:**

```powershell
.\start-backend.ps1
```

This script will:
- ✅ Auto-detect and activate your venv/.venv
- ✅ Install requirements
- ✅ Check required ports (1234, 1235, 11235, 8765, 8080)
- ✅ Launch the bridge in the background
- ✅ Wait for servers to be ready

**Then open your browser:**

```
http://localhost:8080
```

**Status indicators:**
- ✅ Backend: CONNECTED (NovelForge active) — you're good to write
- ⚠️ Backend: OFFLINE (NovelForge not available) — check prerequisites below

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    NOVELFORGE ORCHESTRATOR                       │
│  (Hierarchical Task Planner + Self-Reflection + Decision AI)     │
├─────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │  HEAD MODEL │  │  ORCHESTRATOR│  │  CRITIC MODEL      │   │
│  │  (21B/40B)  │  │  (State+Plan)│  │  (14B Grammar/Plot) │   │
│  │  Creative   │  │  MCP Client  │  │  Review & Polish    │   │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘   │
│         │                │                     │              │
│         └────────────────┼─────────────────────┘              │
│                          │                                    │
│         ┌────────────────┴────────────────┐                   │
│         │      MCP TOOL SERVERS            │                   │
│         ├──────────┬──────────┬───────────┤                   │
│         │MemPalace │ Crawl4AI │ FileSystem│                   │
│         │  Memory  │ Research │  I/O      │                   │
│         └──────────┴──────────┴───────────┘                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### Hardware
- **GPU or CPU**: 24GB+ VRAM for 21B model (LM Studio / Ollama on port 1234)
- **RAM**: 8GB+ minimum, 16GB+ recommended
- **Storage**: 20GB+ for models and projects

### Software
- **Python 3.10+** with pip
- **LM Studio** or **Ollama** running:
  - Head model (21B or 40B) on `localhost:1234` ✅ **Required**
  - Critic model (14B) on `localhost:1235` ⚠️ Optional (falls back to 1234 if unavailable)
- **Crawl4AI** on `localhost:11235` ✅ **Required for Research**

### Network
- Ports 8080 (HTTP), 8765 (WebSocket), 1234 (head model), 11235 (Crawl4AI) must be available

---

## Step 1: Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt

# Install MemPalace
pip install mempalace  / uv tool install mempalace

# Verify MCP SDK
python -c "import mcp; print(mcp.__version__)"
```

---

## Step 2: Start Crawl4AI (Research Engine)

```bash
# Pull and run Crawl4AI
docker pull unclecode/crawl4ai:latest
docker run -d -p 11235:11235 --name crawl4ai --shm-size=1g unclecode/crawl4ai:latest

# Verify it's running
curl http://localhost:11235/health
```

---

## Step 3: Load Your Models

### Option A: LM Studio (Recommended for Deckard)

1. Open LM Studio
2. Load **21B Deckard** on GPU 0:
   - Model: `DavidAU/Qwen3.5-21B-Claude-4.6-Opus-Deckard-Heretic-Uncensored-Thinking`
   - Context: 16384
   - Temperature: 1.0 (creative mode)
   - Rep Penalty: 1.05
   - **Important**: Enable thinking mode in Jinja template
   - Server port: 1234

3. Load **14B Critic** on GPU 1 (or CPU):
   - Model: Any strong 14B instruct model (Qwen 2.5 14B, etc.)
   - Context: 8192
   - Temperature: 0.3
   - Rep Penalty: 1.0
   - Server port: 1235

### Option B: Ollama

```bash
# Pull models
ollama pull qwen2.5:14b

# Run servers
ollama serve &
OLLAMA_HOST=localhost:1234 ollama run qwen2.5:14b &
```

### Option C: vLLM (Production)

```bash
# 21B Head Model
python -m vllm.entrypoints.openai.api_server \
    --model DavidAU/Qwen3.5-21B-Claude-4.6-Opus-Deckard-Heretic-Uncensored-Thinking \
    --port 1234 \
    --tensor-parallel-size 1 \
    --max-model-len 32768

# 14B Critic Model
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-14B-Instruct \
    --port 1235 \
    --tensor-parallel-size 1 \
    --max-model-len 16384
```

---

## Step 4: Start MCP Servers

### One-command backend start
Use the PowerShell launcher when you want the backend checked and started from the local virtual environment:

```powershell
.\start-backend.ps1
```

It activates `.venv` or `venv`, installs requirements, checks the main ports, and then starts `bridge.py`.
The bridge starts the MCP server processes it needs.

If you prefer to run the backend pieces manually, open **3 separate terminals**:

### Terminal 1: MemPalace Server
```bash
source venv/bin/activate
python mempalace_mcp_server.py
```

### Terminal 2: Crawl4AI Server
```bash
source venv/bin/activate
python crawl4ai_mcp_server.py
```

### Terminal 3: FileSystem Server
```bash
source venv/bin/activate
python filesystem_mcp_server.py
```

---

## Step 5: Run NovelForge

```python
import asyncio
from novelforge_v2 import NovelForge

async def main():
    forge = NovelForge(
        head_endpoint="http://localhost:1234/v1",
        critic_endpoint="http://localhost:1235/v1",
        mcp_servers=[
            "mempalace_mcp_server.py",
            "crawl4ai_mcp_server.py",
            "filesystem_mcp_server.py"
        ]
    )

    await forge.initialize()

    # Write a chapter
    result = await forge.write_chapter(
        novel_name="neon_shadows",
        chapter="chapter_3_the_meeting",
        prompt="Kai meets a nervous corp exec in an underground chop-shop. Tone: gritty noir. 2000 words."
    )

    print(f"Tasks: {result['tasks_completed']}")
    print(f"Quality: {result['reflection']['avg_quality']:.2f}")
    print(f"Tokens: {result['total_tokens']}")

    await forge.shutdown()

asyncio.run(main())
```

---

## Intelligent Orchestrator Features

### 1. Hierarchical Task Planning
The orchestrator decomposes goals into task trees:
```
Write Chapter 3
├── outline (HIGH) → scene beats, emotional arc
├── character_sheet (HIGH) → ensure consistency
├── scene_draft (CRITICAL) → actual prose
├── continuity_check (MEDIUM) → verify timeline
├── dialogue_polish (MEDIUM) → tighten speech
└── cringe_sweep (LOW) → remove purple prose
```

### 2. Self-Reflection Loops
- **Plan validation**: Checks for circular dependencies, orphaned critical tasks
- **Quality gates**: Critic scores < 0.7 trigger auto-revision (max 3 cycles)
- **Meta-reflection**: After each goal, analyzes efficiency and suggests improvements

### 3. Intelligent Tool Routing
The orchestrator decides which MCP tools to invoke:
- `crawl4ai_research` → for tasks with "research", "historical", "setting"
- `mempalace_retrieve` → before every scene draft for continuity
- `mempalace_store` → after every completed task
- `filesystem_write` → for final chapter saves

### 4. Context-Aware Loading
Only loads relevant context to save tokens:
- `character_bibles` strategy → loads character sheets
- `plot_outline` strategy → loads chapter outline
- `previous_chapter` strategy → loads last 3 scenes
- `research_notes` strategy → loads crawled research

### 5. Dual-Model Pipeline
- **Head (21B)**: Creative writing, planning, worldbuilding, dialogue
- **Critic (14B)**: Grammar, continuity, cringe detection, pacing
- **Both**: Draft → Review → Revise cycle

### 6. Token Budget Management
- Hourly token budget (default: 500K)
- Auto-throttles when budget exhausted
- Tracks usage per task type

---

## Task Types Reference

| Task Type | Model | Purpose |
|-----------|-------|---------|
| `outline` | head | Chapter/scene outlines |
| `worldbuild` | head | Setting, culture, history |
| `character_sheet` | head | Character bios, arcs |
| `scene_draft` | both | Prose writing + review |
| `dialogue_polish` | both | Dialogue tightening |
| `continuity_check` | critic | Plot/character consistency |
| `research` | head | Setting/historical research |
| `style_analysis` | critic | Voice/tone analysis |
| `chapter_review` | critic | Full editorial pass |
| `plot_weave` | head | Foreshadowing, callbacks |
| `foreshadow_plant` | head | Plant future plot points |
| `cringe_sweep` | critic | Purple prose, clichés |

---

## Model Settings Quick Reference

### Head Model (21B Deckard)
```json
{
  "model": "Qwen3.5-21B-Claude-4.6-Opus-Deckard-Heretic-Uncensored-Thinking",
  "context_length": 16384,
  "temperature": 1.0,
  "repetition_penalty": 1.05,
  "thinking": true,
  "system_prompt": "Be vivid and precise. You are a master novelist."
}
```

### Critic Model (14B)
```json
{
  "model": "qwen3.5-14b-instruct",
  "context_length": 8192,
  "temperature": 0.3,
  "repetition_penalty": 1.0,
  "system_prompt": "You are a ruthless literary editor. Detect cringe, continuity errors, and weak prose."
}
```

---

## Troubleshooting

### "MCP server not found"
- Ensure all 3 MCP servers are running in separate terminals
- Check that `mcp` package is installed: `pip show mcp`

### "Model endpoint connection refused"
- Verify LM Studio / Ollama / vLLM is running on the correct port
- Test: `curl http://localhost:1234/v1/models`

### "Out of memory"
- Reduce context window: 8192 instead of 16384
- Use Q4_K_M quantization for 21B model
- Run 14B critic on CPU

### "Crawl4AI timeout"
- Check Docker container: `docker ps | grep crawl4ai`
- Increase timeout in `crawl4ai_mcp_server.py`
- Verify port 11235 is not blocked

### "Quality scores too low"
- Increase `max_revisions` in task config
- Lower temperature for head model (0.8 instead of 1.0)
- Provide more detailed prompts with context strategy

---

## Advanced: Custom MCP Tools

Add your own tools by creating a new MCP server:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MyCustomServer")

@mcp.tool()
def my_custom_tool(param: str) -> str:
    return f"Result: {param}"

if __name__ == "__main__":
    mcp.run()
```

Then add to `mcp_servers` list in NovelForge initialization.

---

## License
MIT — Use freely for your novels.
