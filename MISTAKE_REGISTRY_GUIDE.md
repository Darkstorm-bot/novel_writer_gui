# NovelForge v2.1 — Mistake Registry Integration Guide
## The "Head File" for Self-Improving Agents

---

## What Is the Mistake Registry?

The Mistake Registry is a **persistent knowledge base** that records:

1. **Every mistake** the head model (21B) or critic model (14B) makes
2. **How it was corrected** (auto-revision, manual edit, critic feedback)
3. **Why it happened** (root cause analysis)
4. **How to prevent it** (prevention prompts + examples)
5. **Whether the fix worked** (success rate tracking)

Before executing **any task**, the orchestrator:
- Queries the registry for similar past mistakes
- Injects prevention prompts into the system prompt
- Executes with mistake-awareness
- Records new mistakes found by the critic
- Updates success rates after fixes

**Result**: The system gets better with every chapter written.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    NOVELFORGE ORCHESTRATOR v2.1                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  BEFORE TASK:                                                    │
│  ┌─────────────┐     ┌─────────────────────┐                   │
│  │  Task Node  │────►│  Mistake Registry   │                   │
│  │  (scene_    │     │  Query:             │                   │
│  │   draft)    │     │  "Any past POV      │                   │
│  └─────────────┘     │   slips in scenes?" │                   │
│                      └──────────┬──────────┘                   │
│                                 │                                │
│                                 ▼                                │
│                      ┌─────────────────────┐                   │
│                      │  Prevention Prompt  │                   │
│                      │  "Stay in POV. No   │                   │
│                      │   head-hopping..."  │                   │
│                      └──────────┬──────────┘                   │
│                                 │                                │
│                                 ▼                                │
│  ┌────────────────────────────────────────────────────────────┐│
│  │  ENRICHED SYSTEM PROMPT:                                   ││
│  │  "Be vivid and precise...                                  ││
│  │   === MISTAKE PREVENTION ===                               ││
│  │   【POV_SLIP】Don't head-hop. Stay in designated POV.      ││
│  │   【DIALOGUE_TAGS】Use 'said' 90%. No hissed/ejaculated.   ││
│  │   【EMOTIONAL_TELL】Show, don't tell.                      ││
│  │   === END PREVENTION ==="                                  ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                  │
│  AFTER TASK:                                                     │
│  ┌─────────────┐     ┌─────────────────────┐                   │
│  │  Critic     │────►│  Mistake Registry   │                   │
│  │  Review     │     │  Record:            │                   │
│  │  (score 0.4)│     │  "POV slip found    │                   │
│  └─────────────┘     │   at line 12"       │                   │
│                      └──────────┬──────────┘                   │
│                                 │                                │
│                                 ▼                                │
│                      ┌─────────────────────┐                   │
│                      │  Auto-Revision      │                   │
│                      │  (max 3 attempts)   │                   │
│                      └──────────┬──────────┘                   │
│                                 │                                │
│                                 ▼                                │
│                      ┌─────────────────────┐                   │
│                      │  Update Success     │                   │
│                      │  Rate: 0.7 → 0.85   │                   │
│                      └─────────────────────┘                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 21 Mistake Categories

| Category | Severity | Typical Fix Rate | Prevention Focus |
|----------|----------|------------------|------------------|
| **pov_slip** | Critical | ~60% | POV discipline |
| **continuity_error** | Critical | ~55% | Timeline/character consistency |
| **hallucination** | Critical | ~50% | Fact-checking, context grounding |
| **cringe** | Major | ~70% | Prose discipline |
| **emotional_tell** | Major | ~75% | Show-don't-tell |
| **dialogue_tag_abuse** | Major | ~85% | "Said" as default |
| **character_voice_loss** | Major | ~65% | Distinct speech patterns |
| **pacing_break** | Major | ~60% | Structural awareness |
| **style_drift** | Minor | ~55% | Voice consistency |
| **repetition** | Minor | ~80% | Vocabulary variation |
| **over_description** | Minor | ~70% | Selective detail |
| **under_description** | Minor | ~65% | Sensory grounding |
| **anachronism** | Minor | ~90% | Era-appropriate details |
| **motivation_gap** | Major | ~50% | Character logic |
| **foreshadow_fail** | Minor | ~45% | Subtlety calibration |
| **worldbuild_dump** | Minor | ~75% | Exposition weaving |
| **theme_contradiction** | Major | ~40% | Thematic coherence |
| **structural_error** | Major | ~50% | Scene purpose |
| **grammar_syntax** | Cosmetic | ~85% | Technical polish |
| **research_fail** | Minor | ~70% | Source verification |

---

## Setup Steps

### Step 1: Start the Mistake Registry MCP Server

```bash
# Terminal 4 (in addition to the other 3 MCP servers)
source venv/bin/activate
python mistake_registry_mcp_server.py
```

### Step 2: Update NovelForge Initialization

```python
forge = NovelForge(
    head_endpoint="http://localhost:1234/v1",
    critic_endpoint="http://localhost:1235/v1",
    mcp_servers=[
        "mempalace_mcp_server.py",
        "crawl4ai_mcp_server.py",
        "filesystem_mcp_server.py",
        "mistake_registry_mcp_server.py"  # <-- ADD THIS
    ]
)
```

### Step 3: Enable Mistake Learning

```python
# In your main script, after initialize:
await forge.initialize()

# Enable aggressive mistake learning (records ALL issues, not just failures)
forge.orchestrator.mistake_registry_enabled = True
forge.orchestrator.mistake_learning_aggressive = True
forge.orchestrator.mistake_prevention_threshold = 0.5  # Only inject fixes with >50% success
```

---

## How It Works in Practice

### Example 1: POV Slip Prevention

**Chapter 1** (no prevention knowledge):
```
Kai looked at her. She was thinking about her children back in the
arcology. He could tell she regretted coming here.
```
❌ **POV slip**: We're in Kai's head but know her thoughts.

**Critic finds it** → **Recorded to registry** → **Prevention prompt generated**:
```
Stay in the designated POV. No head-hopping. Use sensory details
from that character only.
DON'T: She was thinking about her children. He could tell she regretted it.
DO: Her fingers twitched toward her pocket—probably a holo of her kids.
    Kai had seen that look before.
```

**Chapter 2** (with prevention):
```
The exec's face tightened. Her fingers twitched toward her pocket—
probably a holo of her kids. Kai had seen that look before.
```
✅ **Fixed**: Kai infers from observation, doesn't access her thoughts.

---

### Example 2: Dialogue Tag Abuse Prevention

**Chapter 1**:
```
"You promised me clean ware," she hissed.
"I don't make promises," he ejaculated.
```
❌ **Tag abuse**: "hissed", "ejaculated"

**Prevention prompt**:
```
Use 'said' 90% of the time. Let actions and context carry emotion.
DON'T: "Stop," he hissed.
DO: "Stop," he said, his hand tightening on the wrench.
```

**Chapter 2**:
```
"You promised me clean ware," she said. Her voice didn't shake, but
her thumb kept brushing the stunner's safety.
```
✅ **Fixed**: "Said" + action carries emotion.

---

### Example 3: Emotional Tell Prevention

**Chapter 1**:
```
Kai slammed his fist on the workbench. He was angry.
The corp exec flinched. She was scared.
```
❌ **Telling**: "was angry", "was scared"

**Prevention prompt**:
```
Show emotion through action, dialogue, and physical sensation.
Never name emotions directly.
DON'T: He was angry.
DO: His fist came down on the workbench. A wrench clattered to the floor.
```

**Chapter 2**:
```
Kai's fist came down on the workbench. A wrench clattered to the
concrete floor. The exec flinched, her hand darting to the stunner
holstered at her hip.
```
✅ **Fixed**: Action shows emotion without naming it.

---

## Registry File Structure

```
novels_project/
├── mistake_registry.jsonl      # All mistakes (append-only)
├── mistake_index.json          # Search index
├── LESSONS_LEARNED.md          # Auto-generated human-readable summary
└── novel_output/
    └── ...
```

### mistake_registry.jsonl Format

Each line is a JSON object:

```json
{
  "mistake_id": "a3f7b2d9e8c1",
  "timestamp": 1715280000.0,
  "task_type": "scene_draft",
  "task_description": "Underground chop-shop scene",
  "model_used": "head_21b",
  "category": "pov_slip",
  "severity": "critical",
  "mistake_description": "Head-hopped from Kai's POV to exec's internal thoughts",
  "original_output": "...",
  "mistake_excerpt": "She was thinking about her children...",
  "corrected_output": "...",
  "correction_method": "critic_feedback",
  "root_cause": "Head model prioritized emotional depth over POV discipline",
  "trigger_context": "Scene with multiple characters where emotions run high",
  "prevention_prompt": "Stay in the designated POV...",
  "trigger_keywords": ["thinking", "wondered", "knew", "felt"],
  "negative_examples": ["She was thinking about her children."],
  "positive_examples": ["Her fingers twitched toward her pocket..."],
  "occurrence_count": 1,
  "success_rate": 0.0,
  "revision_attempts": 1,
  "success_after_fix": 0,
  "failure_after_fix": 0
}
```

---

## MCP Tools Reference

### Recording Mistakes

```python
# Record a single mistake
await mcp.call_tool("mistake_record", {
    "task_type": "scene_draft",
    "task_description": "Kai meets corp exec",
    "model_used": "head_21b",
    "category": "pov_slip",
    "severity": "critical",
    "mistake_description": "Head-hopped to exec's thoughts",
    "original_output": draft,
    "mistake_excerpt": "She was thinking...",
    "corrected_output": revision,
    "correction_method": "critic_feedback",
    "root_cause": "No POV constraint in prompt",
    "trigger_context": "Multi-character emotional scene",
    "prevention_prompt": "Stay in designated POV...",
    "trigger_keywords": json.dumps(["thinking", "wondered"]),
    "negative_examples": json.dumps(["She was thinking..."]),
    "positive_examples": json.dumps(["Her fingers twitched..."])
})

# Record multiple mistakes at once
await mcp.call_tool("mistake_batch_record", {
    "entries_json": json.dumps([mistake1, mistake2, ...])
})
```

### Querying & Prevention

```python
# Get prevention prompt for a task type
result = await mcp.call_tool("mistake_get_prevention_prompt", {
    "task_type": "scene_draft",
    "categories": json.dumps(["pov_slip", "cringe", "emotional_tell"])
})

# Find similar past mistakes
result = await mcp.call_tool("mistake_find_similar", {
    "query": "The character suddenly knows things they shouldn't",
    "task_type": "scene_draft",
    "top_k": 5
})

# Get all mistakes in a category
result = await mcp.call_tool("mistake_get_by_category", {
    "category": "cringe",
    "limit": 10
})
```

### Tracking Success

```python
# Update whether a fix worked
await mcp.call_tool("mistake_update_success", {
    "mistake_id": "a3f7b2d9e8c1",
    "success": True  # The revision fixed the issue
})
```

### Analytics

```python
# Get global patterns
result = await mcp.call_tool("mistake_get_patterns", {})
# Returns: category counts, avg success rates, most common triggers

# Get overall stats
result = await mcp.call_tool("mistake_get_stats", {})
# Returns: total mistakes, by severity, by model, by category

# Export lessons learned
result = await mcp.call_tool("mistake_export_lessons", {})
# Generates LESSONS_LEARNED.md
```

---

## Integration with NovelForge Orchestrator

The orchestrator automatically handles all of this. You don't need to call these tools manually. But here's what happens under the hood:

### 1. Before Task Execution

```python
# In _run_task():
prevention = await self._load_mistake_prevention(task)
# Queries registry, gets prevention prompt for task.task_type

system_prompt = await self._get_mistake_enriched_prompt(task, base_prompt)
# Injects prevention into system prompt
```

### 2. After Critic Review

```python
# If quality < 0.7:
recorded_mistake_id = await self._record_mistake(task, draft, critique, revision)
# Records each issue found by critic

# After revision:
await self._record_success_or_failure(recorded_mistake_id, new_score >= 0.7)
# Tracks whether the fix worked
```

### 3. Meta-Reflection

```python
# In _meta_reflect_with_mistakes():
patterns = await mcp.call_tool("mistake_get_patterns", {})
# Analyzes which mistakes recur

if recurring_issues > 3:
    await mcp.call_tool("mistake_export_lessons", {})
    # Auto-exports lessons when patterns emerge
```

---

## Manual Inspection

You can inspect the registry at any time:

```bash
# View raw registry
cat mistake_registry.jsonl | jq '.category, .severity, .mistake_description'

# View lessons learned
cat LESSONS_LEARNED.md

# Count mistakes by category
cat mistake_registry.jsonl | jq -r '.category' | sort | uniq -c | sort -rn

# Find high-recurrence, low-fix-rate issues
cat mistake_registry.jsonl | jq 'select(.occurrence_count > 3 and .success_rate < 0.5) | .category'
```

---

## Tuning Parameters

```python
# In IntelligentOrchestrator:

# Only inject prevention for fixes with >50% success rate
self.mistake_prevention_threshold = 0.5

# Record ALL issues (even minor ones)
self.mistake_learning_aggressive = True

# Only record critical/major issues
self.mistake_learning_aggressive = False  # + filter in _record_mistake

# Disable entirely
self.mistake_registry_enabled = False
```

---

## Expected Behavior Over Time

| Chapters Written | Registry Size | Avg Quality | Critical Errors/Ch | Notes |
|-----------------|---------------|-------------|-------------------|-------|
| 1-3 | 5-15 entries | 0.40-0.60 | 3-5 | Learning phase |
| 4-10 | 15-40 entries | 0.65-0.80 | 1-2 | Prevention kicks in |
| 11-25 | 40-80 entries | 0.80-0.90 | 0-1 | Mature patterns |
| 26+ | 80-150 entries | 0.85-0.95 | 0-0.5 | Highly optimized |

---

## Troubleshooting

### "Registry not recording mistakes"
- Check that `mistake_learning_aggressive = True`
- Verify critic is finding issues (quality scores < 0.7)
- Check MCP server is running: `python mistake_registry_mcp_server.py`

### "Prevention prompts too long"
- Reduce `top_k` in `_load_mistake_prevention()`
- Filter by severity: only inject critical/major
- Limit to top 5 most successful fixes

### "Same mistake keeps happening"
- Check success rate: `mistake_get_stats`
- If success_rate < 0.3, the fix isn't working → adjust prevention prompt
- Consider switching model or temperature for that task type

### "Registry growing too large"
- The registry uses append-only JSONL — very efficient
- Old entries with 100% success rate can be archived
- Use `mistake_export_lessons()` to compact into markdown

---

## Advanced: Custom Mistake Categories

Add your own categories by editing the `MistakeRegistry.__init__` index:

```python
self.index = {
    # ... existing categories ...
    "my_custom_issue": [],
}
```

And update `_classify_issue()` in the orchestrator:

```python
def _classify_issue(self, issue: str) -> str:
    # ... existing classifications ...
    if "my trigger word" in issue_lower:
        return "my_custom_issue"
    return "style_drift"  # default
```
