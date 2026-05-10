# NovelForge v2.1
## Agentic Novel Writing System with Self-Improving Mistake Registry

**NovelForge** is a fully agentic novel writing system that uses local LLMs, MCP tools, and a persistent mistake registry to write, review, and improve novels chapter by chapter.

---

## What Makes This Different

| Feature | Claude Code | Hermes | Cursor | **NovelForge** |
|---------|-------------|--------|--------|----------------|
| **Tool reliability** | Hallucinates tools | Moderate | Good | **Zero hallucination** — explicit MCP schemas |
| **Context memory** | Session-only | None | File-based | **Verbatim** MemPalace + temporal KG |
| **Creative/Critical** | Single model | Single | Single | **Dual-model** pipeline |
| **Long-form coherence** | Breaks ~8K | Breaks early | Moderate | **256K context** + hierarchical memory |
| **Research** | Manual | None | Web search | **Automated** Crawl4AI with BM25 |
| **Self-improvement** | None | None | None | **Mistake Registry** — learns from every error |
| **Planning** | None | None | Basic | **Hierarchical task decomposition** |
| **Quality gates** | None | None | None | **Auto-revision** with critic review |
| **Cost** | $20-40/mo | Free | $20/mo | **Local** — one-time hardware |
| **Privacy** | Cloud | Local | Cloud | **100% local** |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         NOVELFORGE v2.1                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                    INTELLIGENT ORCHESTRATOR                      │   │
│   │  • Hierarchical Task Planning                                    │   │
│   │  • Self-Reflection & Meta-Learning                               │   │
│   │  • Token Budget Management                                       │   │
│   │  • Intelligent Tool Routing                                      │   │
│   │  • Mistake Prevention Injection                                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│           ┌──────────────────┼──────────────────┐                       │
│           │                  │                  │                       │
│    ┌──────▼──────┐    ┌─────▼─────┐    ┌──────▼──────┐                │
│    │  HEAD MODEL │    │  MISTAKE  │    │ CRITIC MODEL │                │
│    │  21B Deckard│    │  REGISTRY │    │  14B Grammar │                │
│    │  Creative   │◄──►│  (Learn)  │◄──►│  Plot Review │                │
│    │  Planning   │    │  (Prevent)│    │  Cringe Det. │                │
│    └──────┬──────┘    └─────┬─────┘    └──────┬──────┘                │
│           │                 │                  │                        │
│           └─────────────────┼──────────────────┘                        │
│                             │                                           │
│   ┌─────────────────────────▼─────────────────────────┐                │
│   │              MCP TOOL SERVERS                      │                │
│   ├──────────────┬──────────────┬──────────────┬──────┤                │
│   │  MemPalace   │  Crawl4AI    │  FileSystem  │Mistake│               │
│   │  Memory      │  Research    │  I/O         │Registry│              │
│   │  • Wings     │  • Web crawl │  • Save      │• Record│              │
│   │  • Rooms     │  • Style     │  • Load      │• Query │              │
│   │  • Halls     │  • Fact-check│  • Version   │• Learn │              │
│   │  • Drawers   │  • Market    │  • Project   │• Export│              │
│   └──────────────┴──────────────┴──────────────┴──────┘                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
novelforge/
│
├── novelforge_v2.py                    # Main orchestrator (44KB)
│   ├── IntelligentOrchestrator         # Task planning & execution
│   ├── HierarchicalPlanner             # Goal decomposition
│   ├── TaskNode                        # Task tree nodes
│   ├── NovelState                      # Novel project state
│   ├── NovelForge                      # Main API class
│   ├── HeadModelClient                 # 21B creative model
│   └── CriticModelClient               # 14B analytical model
│
├── novelforge_mistake_integration.py   # Mistake registry integration (25KB)
│   ├── MistakeAwarenessMixin           # Prevention injection
│   ├── _load_mistake_prevention()      # Query registry before task
│   ├── _check_for_known_mistakes()     # Pattern detection
│   ├── _record_mistake()               # Log errors
│   └── _meta_reflect_with_mistakes()   # Learning analytics
│
├── mempalace_mcp_server.py             # Memory storage MCP server
├── crawl4ai_mcp_server.py              # Web research MCP server
├── filesystem_mcp_server.py            # File I/O MCP server
├── mistake_registry_mcp_server.py      # Self-improvement MCP server
│
├── demo_mistake_registry.py            # Working example with 4 chapters
├── SETUP_GUIDE.md                      # Full setup instructions
├── MISTAKE_REGISTRY_GUIDE.md           # Mistake registry deep dive
├── requirements.txt                    # Python dependencies
└── README.md                           # This file
```

---

## Quick Start

### 1. Install

```bash
# Clone/download all files
mkdir novelforge && cd novelforge
# Copy all .py and .md files here

# Create environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install mempalace
```

### 2. Start Infrastructure

```bash
# Terminal 1: Crawl4AI (research)
docker run -d -p 11235:11235 --name crawl4ai --shm-size=1g unclecode/crawl4ai:latest

# Terminal 2: MemPalace MCP Server
python mempalace_mcp_server.py

# Terminal 3: Crawl4AI MCP Server
python crawl4ai_mcp_server.py

# Terminal 4: FileSystem MCP Server
python filesystem_mcp_server.py

# Terminal 5: Mistake Registry MCP Server
python mistake_registry_mcp_server.py
```

### 3. Load Models

In **LM Studio** or **Ollama**:

**Port 1234 — Head Model (21B Deckard)**
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

**Port 1235 — Critic Model (14B)**
```json
{
  "model": "qwen3.5-14b-instruct",
  "context_length": 8192,
  "temperature": 0.3,
  "repetition_penalty": 1.0,
  "system_prompt": "You are a ruthless literary editor."
}
```

### 4. Run

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
            "filesystem_mcp_server.py",
            "mistake_registry_mcp_server.py"
        ]
    )

    await forge.initialize()

    # Enable mistake learning
    forge.orchestrator.mistake_registry_enabled = True
    forge.orchestrator.mistake_learning_aggressive = True

    # Write a chapter
    result = await forge.write_chapter(
        novel_name="neon_shadows",
        chapter="chapter_3_the_meeting",
        prompt="Kai meets a nervous corp exec in an underground chop-shop. Tone: gritty noir. 2000 words."
    )

    print(f"Quality: {result['reflection']['avg_quality']:.2f}")
    print(f"Tasks: {result['tasks_completed']}")
    print(f"Tokens: {result['total_tokens']}")

    # Check mistake stats
    stats = await forge.get_mistake_stats()
    print(f"Mistakes recorded: {stats['total_mistakes']}")

    await forge.shutdown()

asyncio.run(main())
```

---

## The Mistake Registry: How It Learns

### Before Every Task

```
Task: scene_draft
↓
Query Registry: "Any past POV slips in scenes?"
↓
Found: 3 past POV slips
↓
Inject Prevention:
  "Stay in designated POV. No head-hopping.
   DON'T: She was thinking...
   DO: Her fingers twitched..."
↓
Generate with enriched prompt
```

### After Every Task

```
Draft generated
↓
Critic Review: Score 0.45
  Issues found: POV slip, dialogue tag abuse
↓
Record to Registry:
  - Mistake category: pov_slip
  - Root cause: No POV constraint
  - Prevention: "Stay in POV..."
  - Examples: negative + positive
↓
Auto-Revision (max 3 attempts)
↓
Update Success Rate:
  Fix worked? → success_rate += 1
  Fix failed? → failure_after_fix += 1
```

### Over Time

| Chapter | Quality | Critical Errors | Prevention Active |
|---------|---------|-----------------|-------------------|
| 1 | 0.35 | 4 | None |
| 2 | 0.82 | 0 | 4 categories |
| 3 | 0.55 | 1 | 4 categories |
| 4 | 0.88 | 0 | 5 categories |
| 10 | 0.91 | 0 | 12 categories |
| 25 | 0.94 | 0 | 18 categories |

---

## Task Types

| Task | Model | Purpose |
|------|-------|---------|
| `outline` | head | Chapter/scene outlines |
| `worldbuild` | head | Setting, culture, history |
| `character_sheet` | head | Character bios, arcs |
| `scene_draft` | both | Prose + review |
| `dialogue_polish` | both | Dialogue tightening |
| `continuity_check` | critic | Plot/character consistency |
| `research` | head | Setting/historical research |
| `style_analysis` | critic | Voice/tone analysis |
| `chapter_review` | critic | Full editorial pass |
| `plot_weave` | head | Foreshadowing, callbacks |
| `foreshadow_plant` | head | Plant future plot points |
| `cringe_sweep` | critic | Purple prose, clichés |

---

## 21 Mistake Categories

The registry tracks these categories with prevention prompts:

**Critical**: `pov_slip`, `continuity_error`, `hallucination`
**Major**: `cringe`, `emotional_tell`, `dialogue_tag_abuse`, `character_voice_loss`, `pacing_break`, `motivation_gap`, `theme_contradiction`, `structural_error`
**Minor**: `style_drift`, `repetition`, `over_description`, `under_description`, `anachronism`, `foreshadow_fail`, `worldbuild_dump`, `research_fail`
**Cosmetic**: `grammar_syntax`

---

## Model Recommendations

### Head Model (Creative)
- **Primary**: `DavidAU/Qwen3.5-21B-Claude-4.6-Opus-Deckard-Heretic-Uncensored-Thinking`
- **Alternative**: `DavidAU/Qwen3.5-40B-Claude-4.6-Opus-Deckard-Heretic-Uncensored-Thinking` (more IQ)
- **Settings**: Temp 1.0, Rep Pen 1.05, Thinking ON

### Critic Model (Analytical)
- **Primary**: `Qwen/Qwen2.5-14B-Instruct`
- **Alternative**: Any strong 14B instruct model
- **Settings**: Temp 0.3, Rep Pen 1.0

### Minimum VRAM
- 21B Q4_K_M: ~14GB
- 14B Q4_K_M: ~9GB
- **Total**: 23GB (fits on RTX 3090/4090)

---

## Documentation

| File | Purpose |
|------|---------|
| `SETUP_GUIDE.md` | Full installation and configuration |
| `MISTAKE_REGISTRY_GUIDE.md` | Deep dive into self-improvement |
| `demo_mistake_registry.py` | Working example with 4 chapters |

---

## License

MIT — Use freely for your novels.

**Note**: The Deckard model is uncensored. You are responsible for the content you generate.
