
"""
NovelForge v2.0 — Agentic Novel Writing System
================================================
MCP-Integrated | Dual-Model | Hierarchical Intelligence

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                    NOVELFORGE ORCHESTRATOR                   │
    │  (Hierarchical Task Planner + Self-Reflection + Decision AI) │
    ├─────────────────────────────────────────────────────────────┤
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
    │  │  HEAD MODEL │  │  ORCHESTRATOR│  │  CRITIC MODEL      │ │
    │  │  (21B/40B)  │  │  (State+Plan)│  │  (14B Grammar/Plot) │ │
    │  │  Creative   │  │  MCP Client  │  │  Review & Polish    │ │
    │  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
    │         │                │                     │            │
    │         └────────────────┼─────────────────────┘            │
    │                          │                                  │
    │         ┌────────────────┴────────────────┐                 │
    │         │      MCP TOOL SERVERS            │                 │
    │         ├──────────┬──────────┬───────────┤                 │
    │         │MemPalace │ Crawl4AI │ FileSystem│                 │
    │         │  Memory  │ Research │  I/O      │                 │
    │         └──────────┴──────────┴───────────┘                 │
    └─────────────────────────────────────────────────────────────┘
"""

import asyncio
import json
import hashlib
import time
import sys
from dataclasses import dataclass, field
from typing import Literal, Optional, Any, Callable
from enum import Enum, auto
from datetime import datetime
from collections import deque
import logging

# Resource Manager for Low-VRAM sequential loading
from resource_manager import resource_manager

# MCP SDK
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

# External
import aiohttp
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("NovelForge")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. INTELLIGENT ORCHESTRATOR CORE
# ═══════════════════════════════════════════════════════════════════════════════

class TaskPriority(Enum):
    CRITICAL = auto()   # Plot-blocking, continuity-breaking
    HIGH = auto()       # Character development, worldbuilding
    MEDIUM = auto()     # Scene polish, description enhancement
    LOW = auto()        # Grammar, style tweaks

class TaskStatus(Enum):
    PENDING = auto()
    PLANNING = auto()
    EXECUTING = auto()
    REVIEWING = auto()
    REVISING = auto()
    COMPLETED = auto()
    FAILED = auto()

@dataclass
class TaskNode:
    """A node in the hierarchical task tree with self-reflection capability."""
    task_id: str
    task_type: Literal[
        "outline", "worldbuild", "character_sheet", "scene_draft",
        "dialogue_polish", "continuity_check", "research", "style_analysis",
        "chapter_review", "plot_weave", "foreshadow_plant", "cringe_sweep"
    ]
    description: str
    priority: TaskPriority
    parent_id: Optional[str] = None
    children: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING

    # Intelligence metadata
    estimated_tokens: int = 0
    actual_tokens: int = 0
    quality_score: float = 0.0  # 0-1, from critic
    revision_count: int = 0
    max_revisions: int = 3

    # Context routing
    preferred_model: str = "head"  # "head" | "critic" | "both"
    temperature: float = 0.7
    rep_penalty: float = 1.0
    context_window: int = 16384

    # Results
    output: str = ""
    critique: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


class HierarchicalPlanner:
    """
    Decomposes high-level novel goals into executable task trees.
    Uses recursive self-reflection to validate plans before execution.
    """

    PLANNING_PROMPT = """You are the Hierarchical Planning Engine for NovelForge.

    Given a high-level writing goal, decompose it into a tree of atomic tasks.
    Each task must specify:
    - task_type: one of [outline, worldbuild, character_sheet, scene_draft, dialogue_polish, continuity_check, research, style_analysis, chapter_review, plot_weave, foreshadow_plant, cringe_sweep]
    - priority: CRITICAL | HIGH | MEDIUM | LOW
    - dependencies: list of task_ids that must complete first
    - preferred_model: head (creative) | critic (analytical) | both
    - estimated_tokens: approximate token count needed
    - context_strategy: what memory to load (character_bibles, plot_outline, previous_chapter, research_notes)

    RULES:
    1. CRITICAL tasks are plot-blocking (e.g., "establish protagonist motivation")
    2. HIGH tasks are character/world depth (e.g., "flesh out antagonist backstory")
    3. MEDIUM tasks are execution (e.g., "draft scene 3 with dialogue")
    4. LOW tasks are polish (e.g., "grammar check", "cringe detection")
    5. A scene_draft MUST depend on its outline and character_sheet
    6. A continuity_check MUST depend on all previous scene_drafts
    7. A cringe_sweep should use the critic model, temp 0.3
    8. A foreshadow_plant should use the head model, temp 1.0

    Return ONLY valid JSON array of TaskNode objects.
    """

    def __init__(self, head_model_client):
        self.head = head_model_client
        self.task_counter = 0

    def _generate_task_id(self) -> str:
        self.task_counter += 1
        return f"task_{self.task_counter:04d}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:6]}"

    async def create_plan(self, goal: str, novel_state: "NovelState") -> list[TaskNode]:
        """Decompose a goal into a validated task tree."""

        # Phase 1: Generate initial plan
        prompt = f"""{self.PLANNING_PROMPT}

        NOVEL STATE:
        - Current Chapter: {novel_state.current_chapter}
        - Current Arc: {novel_state.current_arc}
        - Characters: {list(novel_state.characters.keys())}
        - Word Count: {novel_state.total_word_count}

        GOAL: {goal}

        Generate the task decomposition tree."""

        # Sequential loading: Load Head model before generation
        await self.head.ensure_model_loaded()
        
        plan_json = await self.head.generate(
            system_prompt=self.PLANNING_PROMPT,
            user_prompt=prompt,
            temperature=0.3,  # Low temp for structured planning
            max_tokens=4000
        )
        
        # Unload Head after planning to free VRAM
        await self.head.unload_model_if_needed()

        try:
            tasks_data = json.loads(self._extract_json(plan_json))
        except json.JSONDecodeError:
            logger.error("Planner returned invalid JSON, retrying with stricter prompt...")
            return await self.create_plan(goal + "\n\nIMPORTANT: Return ONLY valid JSON.", novel_state)

        # Phase 2: Build task nodes
        tasks = []
        for t in tasks_data:
            node = TaskNode(
                task_id=self._generate_task_id(),
                task_type=t["task_type"],
                description=t["description"],
                priority=TaskPriority[t["priority"]],
                dependencies=t.get("dependencies", []),
                preferred_model=t.get("preferred_model", "head"),
                estimated_tokens=t.get("estimated_tokens", 2000),
                temperature=t.get("temperature", 0.7),
                rep_penalty=t.get("rep_penalty", 1.0),
                context_window=t.get("context_window", 16384),
                metadata={"context_strategy": t.get("context_strategy", "general")}
            )
            tasks.append(node)

        # Phase 3: Self-reflection — validate plan consistency
        validated_tasks = await self._validate_plan(tasks, novel_state)

        return validated_tasks

    async def _validate_plan(self, tasks: list[TaskNode], novel_state: "NovelState") -> list[TaskNode]:
        """Reflect on the plan and fix logical errors."""

        # Check for circular dependencies
        task_ids = {t.task_id for t in tasks}
        for t in tasks:
            for dep in t.dependencies:
                if dep not in task_ids:
                    logger.warning(f"Task {t.task_id} has invalid dependency {dep}, removing")
                    t.dependencies.remove(dep)

        # Check for orphaned critical tasks
        critical_tasks = [t for t in tasks if t.priority == TaskPriority.CRITICAL]
        for ct in critical_tasks:
            if not any(ct.task_id in other.dependencies for other in tasks if other != ct):
                logger.info(f"Critical task {ct.task_id} has no dependents — may be orphaned")

        # Ensure scene drafts have prerequisites
        scene_tasks = [t for t in tasks if t.task_type == "scene_draft"]
        for st in scene_tasks:
            has_outline = any(
                t.task_type == "outline" and t.task_id in st.dependencies 
                for t in tasks
            )
            if not has_outline:
                logger.warning(f"Scene draft {st.task_id} missing outline dependency")
                # Auto-inject outline task
                outline_task = TaskNode(
                    task_id=self._generate_task_id(),
                    task_type="outline",
                    description=f"Auto-generated outline for: {st.description}",
                    priority=TaskPriority.HIGH,
                    preferred_model="head",
                    temperature=0.7
                )
                tasks.insert(0, outline_task)
                st.dependencies.append(outline_task.task_id)

        return tasks

    def _extract_json(self, text: str) -> str:
        """Extract JSON from model output (handles markdown code blocks)."""
        if "```json" in text:
            return text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            return text.split("```")[1].split("```")[0].strip()
        return text.strip()


class IntelligentOrchestrator:
    """
    The brain of NovelForge. Makes intelligent decisions about:
    - Which model to use for which task
    - When to parallelize vs serialize
    - When to invoke tools (MCP)
    - When to self-correct
    - Resource allocation (token budgets)
    """

    def __init__(
        self,
        head_model_client,
        critic_model_client,
        mcp_session: ClientSession,
        mempalace_manager,
        max_parallel: int = 3,
        token_budget_per_hour: int = 500000
    ):
        self.head = head_model_client
        self.critic = critic_model_client
        self.mcp = mcp_session
        self.memory = mempalace_manager

        self.planner = HierarchicalPlanner(head_model_client)
        self.task_queue: deque[TaskNode] = deque()
        self.active_tasks: dict[str, TaskNode] = {}
        self.completed_tasks: dict[str, TaskNode] = {}

        self.max_parallel = max_parallel
        self.token_budget = token_budget_per_hour
        self.tokens_used_this_hour = 0
        self.hour_start = time.time()

        # Decision history for learning
        self.decision_log: list[dict] = []

        # Tool registry (populated from MCP)
        self.available_tools: dict[str, dict] = {}

    async def initialize(self):
        """Discover MCP tools and initialize state."""
        if not self.mcp:
            logger.info("[Orchestrator] MCP not available, skipping tool discovery")
            return
        
        try:
            tools_response = await self.mcp.list_tools()
            for tool in tools_response.tools:
                self.available_tools[tool.name] = {
                    "description": tool.description,
                    "schema": tool.inputSchema
                }
            logger.info(f"Discovered {len(self.available_tools)} MCP tools: {list(self.available_tools.keys())}")
        except Exception as e:
            logger.warning(f"Failed to discover MCP tools: {e}")

    async def execute_goal(self, goal: str, novel_state: "NovelState") -> dict:
        """
        Main entry point: takes a high-level goal, plans, executes, and delivers.
        """
        logger.info(f"🎯 NEW GOAL: {goal}")

        # Phase 1: Planning
        plan = await self.planner.create_plan(goal, novel_state)
        logger.info(f"📋 Plan created: {len(plan)} tasks")

        # Phase 2: Topological sort + priority queue
        execution_order = self._topological_sort(plan)
        self.task_queue.extend(execution_order)

        # Phase 3: Execute with intelligent scheduling
        results = await self._execute_queue(novel_state)

        # Phase 4: Meta-reflection on execution
        reflection = await self._meta_reflect(results)

        return {
            "goal": goal,
            "tasks_completed": len(self.completed_tasks),
            "tasks_failed": len([t for t in self.completed_tasks.values() if t.status == TaskStatus.FAILED]),
            "total_tokens": self.tokens_used_this_hour,
            "results": results,
            "reflection": reflection
        }

    def _topological_sort(self, tasks: list[TaskNode]) -> list[TaskNode]:
        """Sort tasks by dependencies, then by priority."""
        # Build adjacency list
        task_map = {t.task_id: t for t in tasks}
        in_degree = {t.task_id: len(t.dependencies) for t in tasks}

        # Ready queue: tasks with no dependencies
        ready = [t for t in tasks if in_degree[t.task_id] == 0]
        ready.sort(key=lambda t: (
            t.priority.value,  # CRITICAL first
            -t.estimated_tokens  # Shorter tasks first within same priority
        ))

        sorted_tasks = []
        while ready:
            current = ready.pop(0)
            sorted_tasks.append(current)

            # Find tasks that depend on current
            for t in tasks:
                if current.task_id in t.dependencies:
                    in_degree[t.task_id] -= 1
                    if in_degree[t.task_id] == 0:
                        ready.append(t)

            ready.sort(key=lambda t: (t.priority.value, -t.estimated_tokens))

        return sorted_tasks

    async def _execute_queue(self, novel_state: "NovelState") -> list[dict]:
        """Execute tasks with parallelization and intelligent routing."""
        results = []

        while self.task_queue or self.active_tasks:
            # Check token budget
            if self._budget_exhausted():
                logger.warning("Token budget exhausted, waiting for next hour...")
                await asyncio.sleep(60)
                continue

            # Start new tasks up to max_parallel
            while len(self.active_tasks) < self.max_parallel and self.task_queue:
                task = self.task_queue.popleft()

                # Check if dependencies are met
                deps_met = all(
                    dep in self.completed_tasks and 
                    self.completed_tasks[dep].status == TaskStatus.COMPLETED
                    for dep in task.dependencies
                )

                if not deps_met:
                    # Push back and check later
                    self.task_queue.append(task)
                    break

                # Launch task
                task.status = TaskStatus.EXECUTING
                self.active_tasks[task.task_id] = task
                asyncio.create_task(self._run_task(task, novel_state))

            # Wait a bit for tasks to complete
            await asyncio.sleep(0.5)

            # Check completed tasks
            completed_now = [
                tid for tid, t in self.active_tasks.items()
                if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
            ]
            for tid in completed_now:
                task = self.active_tasks.pop(tid)
                self.completed_tasks[tid] = task
                results.append({
                    "task_id": tid,
                    "type": task.task_type,
                    "status": task.status.name,
                    "quality": task.quality_score,
                    "tokens": task.actual_tokens
                })

        return results

    async def _run_task(self, task: TaskNode, novel_state: "NovelState"):
        """Execute a single task with full intelligence."""
        logger.info(f"▶️  Executing {task.task_type}: {task.description[:60]}...")

        try:
            # Step 1: Intelligent context loading
            context = await self._load_context(task, novel_state)

            # Step 2: Decide if tools needed
            tool_plan = await self._decide_tools(task, context)

            # Step 3: Execute tool calls if needed
            tool_results = await self._execute_tools(tool_plan)

            # Step 4: Route to appropriate model
            if task.preferred_model == "head":
                output = await self._run_head(task, context, tool_results)
            elif task.preferred_model == "critic":
                output = await self._run_critic(task, context, tool_results)
            else:  # both
                draft = await self._run_head(task, context, tool_results)
                output = await self._run_critic_review(task, draft, context)

            task.output = output
            task.actual_tokens = len(output.split()) * 1.3  # Rough estimate
            self.tokens_used_this_hour += task.actual_tokens

            # Step 5: Quality gate
            if task.preferred_model in ("head", "both"):
                task.quality_score = await self._assess_quality(task)

                if task.quality_score < 0.7 and task.revision_count < task.max_revisions:
                    logger.info(f"🔄 Quality {task.quality_score:.2f} < 0.7, triggering revision")
                    task.status = TaskStatus.REVISION
                    task.revision_count += 1
                    revised = await self._revise_task(task, novel_state)
                    task.output = revised
                    task.quality_score = await self._assess_quality(task)

            # Step 6: Store to memory
            await self._store_result(task, novel_state)

            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()

        except Exception as e:
            logger.error(f"❌ Task {task.task_id} failed: {e}")
            task.status = TaskStatus.FAILED
            task.metadata["error"] = str(e)

    async def _load_context(self, task: TaskNode, novel_state: "NovelState") -> dict:
        """Intelligently load only relevant context to maximize token efficiency."""
        strategy = task.metadata.get("context_strategy", "general")
        context = {"novel_state": novel_state.to_dict()}

        if "character_bibles" in strategy:
            chars = await self.memory.retrieve(
                query="character sheets personalities motivations",
                wing=novel_state.current_novel,
                room="characters",
                top_k=5
            )
            context["characters"] = chars

        if "plot_outline" in strategy:
            outline = await self.memory.retrieve(
                query="plot outline chapter summary",
                wing=novel_state.current_novel,
                room="outline",
                top_k=3
            )
            context["outline"] = outline

        if "previous_chapter" in strategy:
            prev = await self.memory.retrieve(
                query=novel_state.current_chapter,
                wing=novel_state.current_novel,
                room=novel_state.current_chapter,
                top_k=3
            )
            context["previous_scenes"] = prev

        if "research_notes" in strategy:
            research = await self.memory.retrieve(
                query=task.description,
                wing=novel_state.current_novel,
                room="research",
                top_k=3
            )
            context["research"] = research

        return context

    async def _decide_tools(self, task: TaskNode, context: dict) -> list[dict]:
        """Intelligent tool selection using the head model."""

        if not self.available_tools:
            return []

        prompt = f"""Given this task, decide which MCP tools (if any) should be invoked.

        TASK: {task.task_type} — {task.description}
        CONTEXT_KEYS: {list(context.keys())}

        AVAILABLE TOOLS:
        {json.dumps(self.available_tools, indent=2)}

        RULES:
        - Use "crawl4ai_research" for tasks needing web research
        - Use "mempalace_store" after generating content
        - Use "mempalace_retrieve" before writing scenes for continuity
        - Use "filesystem_write" for saving drafts
        - Return empty array [] if no tools needed

        Return JSON array of tool calls: [{{"tool": "name", "params": {{}}}}]
        """

        # Sequential loading: Load Head model
        await self.head.ensure_model_loaded()
        
        decision = await self.head.generate(
            system_prompt="You are a tool router. Return ONLY valid JSON.",
            user_prompt=prompt,
            temperature=0.1,
            max_tokens=1000
        )
        
        # Unload Head after decision
        await self.head.unload_model_if_needed()

        try:
            return json.loads(self._extract_json(decision))
        except:
            return []

    async def _execute_tools(self, tool_plan: list[dict]) -> dict:
        """Execute MCP tool calls."""
        results = {}
        for call in tool_plan:
            tool_name = call.get("tool")
            params = call.get("params", {})

            try:
                result = await self.mcp.call_tool(tool_name, params)
                results[tool_name] = result
                logger.info(f"🔧 Tool {tool_name} executed successfully")
            except Exception as e:
                logger.error(f"🔧 Tool {tool_name} failed: {e}")
                results[tool_name] = {"error": str(e)}

        return results

    async def _run_head(self, task: TaskNode, context: dict, tool_results: dict) -> str:
        """Execute creative task with head model."""

        system_prompt = self._build_system_prompt(task, "creative")
        user_prompt = self._build_user_prompt(task, context, tool_results)

        # Sequential loading: Load Head model
        await self.head.ensure_model_loaded()
        
        result = await self.head.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=task.temperature,
            rep_pen=task.rep_penalty,
            max_tokens=min(task.estimated_tokens * 2, 8000)
        )
        
        # Unload Head after generation
        await self.head.unload_model_if_needed()
        
        return result

    async def _run_critic(self, task: TaskNode, context: dict, tool_results: dict) -> str:
        """Execute analytical task with critic model."""

        system_prompt = self._build_system_prompt(task, "analytical")
        user_prompt = self._build_user_prompt(task, context, tool_results)

        # Sequential loading: Load Critic model
        await self.critic.ensure_model_loaded()
        
        result = await self.critic.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            rep_pen=1.05,
            max_tokens=4000
        )
        
        # Unload Critic after generation
        await self.critic.unload_model_if_needed()
        
        return result

    async def _run_critic_review(self, task: TaskNode, draft: str, context: dict) -> str:
        """Run critic review on head model output and integrate feedback."""

        review_prompt = f"""Review this draft and provide specific revision instructions.

        DRAFT:
        {draft}

        CONTEXT: {json.dumps(context, indent=2)[:2000]}

        Check for:
        1. Grammar and syntax errors
        2. Continuity issues with established plot/characters
        3. Cringe/purple prose
        4. Pacing problems
        5. POV consistency

        Return JSON: {{
            "score": 0-1,
            "issues": ["..."],
            "revision_instructions": "..."
        }}
        """

        # Sequential loading: Load Critic model for review
        await self.critic.ensure_model_loaded()
        
        review = await self.critic.generate(
            system_prompt="You are a ruthless literary editor.",
            user_prompt=review_prompt,
            temperature=0.3,
            max_tokens=3000
        )

        try:
            review_data = json.loads(self._extract_json(review))
            task.quality_score = review_data.get("score", 0.5)
            task.critique = review_data

            if review_data.get("score", 1.0) < 0.8:
                # Unload Critic before loading Head for revision
                await self.critic.unload_model_if_needed()
                
                # Load Head for revision
                await self.head.ensure_model_loaded()
                
                # Auto-revise
                revise_prompt = f"""Revise this draft based on editor feedback.

                DRAFT: {draft}
                FEEDBACK: {review_data.get("revision_instructions", "Improve prose")}

                Produce the revised version only."""

                revised = await self.head.generate(
                    system_prompt="You are applying editorial feedback. Keep the voice but fix the issues.",
                    user_prompt=revise_prompt,
                    temperature=task.temperature,
                    max_tokens=8000
                )
                
                # Unload Head after revision
                await self.head.unload_model_if_needed()
                
                return revised
        except:
            pass
        finally:
            # Ensure Critic is unloaded
            await self.critic.unload_model_if_needed()

        return draft

    async def _assess_quality(self, task: TaskNode) -> float:
        """Quick quality assessment using critic model."""

        prompt = f"""Rate this writing on a scale of 0.0 to 1.0.
        Consider: coherence, creativity, voice consistency, technical skill.

        TEXT: {task.output[:2000]}

        Return ONLY a number between 0.0 and 1.0."""

        # Sequential loading: Load Critic model
        await self.critic.ensure_model_loaded()
        
        score_text = await self.critic.generate(
            system_prompt="You are a quality rater. Return ONLY a float.",
            user_prompt=prompt,
            temperature=0.1,
            max_tokens=10
        )
        
        # Unload Critic after assessment
        await self.critic.unload_model_if_needed()

        try:
            return float(score_text.strip())
        except:
            return 0.5

    async def _revise_task(self, task: TaskNode, novel_state: "NovelState") -> str:
        """Trigger a revision cycle."""
        context = await self._load_context(task, novel_state)

        revise_prompt = f"""Revise the following content. Address these issues:
        {json.dumps(task.critique, indent=2)}

        ORIGINAL:
        {task.output}

        Produce the improved version."""

        # Sequential loading: Load Head model for revision
        await self.head.ensure_model_loaded()
        
        result = await self.head.generate(
            system_prompt="You are revising based on editorial feedback. Maintain voice, fix issues.",
            user_prompt=revise_prompt,
            temperature=task.temperature,
            max_tokens=8000
        )
        
        # Unload Head after revision
        await self.head.unload_model_if_needed()
        
        return result

    async def _store_result(self, task: TaskNode, novel_state: "NovelState"):
        """Store task output to MemPalace via MCP."""
        try:
            await self.mcp.call_tool("mempalace_store", {
                "content": task.output,
                "wing": novel_state.current_novel,
                "room": novel_state.current_chapter,
                "hall": task.task_type,
                "metadata": {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "quality_score": task.quality_score,
                    "revision_count": task.revision_count
                }
            })
        except Exception as e:
            logger.warning(f"Failed to store to memory: {e}")

    async def _meta_reflect(self, results: list[dict]) -> dict:
        """Reflect on the entire execution run and learn."""

        avg_quality = sum(r.get("quality", 0) for r in results) / max(len(results), 1)
        total_tokens = sum(r.get("tokens", 0) for r in results)

        reflection = {
            "avg_quality": avg_quality,
            "total_tokens": total_tokens,
            "tasks_completed": len(results),
            "efficiency": total_tokens / max(len(results), 1),
            "suggestions": []
        }

        if avg_quality < 0.7:
            reflection["suggestions"].append("Consider increasing revision cycles or lowering temperature")

        if total_tokens > self.token_budget * 0.8:
            reflection["suggestions"].append("Token usage high — consider more aggressive context pruning")

        # Log decision for future learning
        self.decision_log.append({
            "timestamp": time.time(),
            "results": results,
            "reflection": reflection
        })

        return reflection

    def _budget_exhausted(self) -> bool:
        """Check if hourly token budget is exhausted."""
        if time.time() - self.hour_start > 3600:
            self.hour_start = time.time()
            self.tokens_used_this_hour = 0
        return self.tokens_used_this_hour >= self.token_budget

    def _build_system_prompt(self, task: TaskNode, mode: str) -> str:
        """Build context-aware system prompt."""

        base = {
            "creative": "Be vivid and precise. You are a master novelist.",
            "analytical": "You are a ruthless literary editor. Be precise and critical."
        }.get(mode, "Be helpful.")

        if task.task_type == "scene_draft":
            base += " Aim for 50% dialogue, 25% narration, 15% body language, 10% thoughts."
        elif task.task_type == "dialogue_polish":
            base += " Fix dialogue tags, ensure each character has a distinct voice."
        elif task.task_type == "cringe_sweep":
            base += " Detect purple prose, clichés, telling-not-showing, filter words."
        elif task.task_type == "continuity_check":
            base += " Verify character motivations, plot logic, timeline consistency."

        return base

    def _build_user_prompt(self, task: TaskNode, context: dict, tool_results: dict) -> str:
        """Build comprehensive user prompt with all context."""

        parts = [f"TASK: {task.description}"]

        if context.get("characters"):
            parts.append(f"CHARACTERS: {json.dumps(context['characters'], indent=2)[:1500]}")

        if context.get("outline"):
            parts.append(f"OUTLINE: {json.dumps(context['outline'], indent=2)[:1500]}")

        if context.get("previous_scenes"):
            parts.append(f"PREVIOUS: {json.dumps(context['previous_scenes'], indent=2)[:1500]}")

        if context.get("research"):
            parts.append(f"RESEARCH: {json.dumps(context['research'], indent=2)[:1500]}")

        if tool_results:
            parts.append(f"TOOL RESULTS: {json.dumps(tool_results, indent=2)[:1000]}")

        return "\n\n".join(parts)

    def _extract_json(self, text: str) -> str:
        if "```json" in text:
            return text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            return text.split("```")[1].split("```")[0].strip()
        return text.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. MCP SERVERS (MemPalace + Crawl4AI + FileSystem)
# ═══════════════════════════════════════════════════════════════════════════════

"""
Save these as separate files and run them as MCP servers:

--- mempalace_mcp_server.py ---
"""

MEMPALACE_SERVER_CODE = '''
from mcp.server.fastmcp import FastMCP
from mempalace import Palace
import json

mcp = FastMCP("MemPalaceServer")
palace = Palace("./novels_db")

@mcp.tool()
def mempalace_store(content: str, wing: str, room: str, hall: str, metadata: str = "{}") -> str:
    """Store content in the memory palace."""
    meta = json.loads(metadata)
    drawer_id = f"{wing}/{room}/{hall}/{time.time()}"
    palace.add_batch(
        documents=[content],
        metadatas=[{"wing": wing, "room": room, "hall": hall, "drawer": drawer_id, **meta}],
        ids=[drawer_id]
    )
    return f"Stored to {drawer_id}"

@mcp.tool()
def mempalace_retrieve(query: str, wing: str, room: str = None, top_k: int = 5) -> str:
    """Retrieve relevant memories from the palace."""
    results = palace.search(query=query, wing=wing, room=room, top_k=top_k, mode="hybrid_v4")
    return json.dumps(results)

@mcp.tool()
def mempalace_kg_query(subject: str, relation_type: str = None, validity_window: str = None) -> str:
    """Query the temporal knowledge graph."""
    results = palace.kg.query(subject=subject, relation_type=relation_type)
    return json.dumps(results)

@mcp.tool()
def mempalace_create_wing(wing_name: str) -> str:
    """Create a new wing (novel project)."""
    palace.create_wing(wing_name)
    return f"Created wing: {wing_name}"

@mcp.tool()
def mempalace_create_room(wing: str, room_name: str) -> str:
    """Create a new room (chapter/arc)."""
    palace.create_room(wing, room_name)
    return f"Created room {room_name} in {wing}"

if __name__ == "__main__":
    mcp.run()
'''

"""
--- crawl4ai_mcp_server.py ---
"""

CRAWL4AI_SERVER_CODE = '''
from mcp.server.fastmcp import FastMCP
import httpx
import json

mcp = FastMCP("Crawl4AIServer")
CRAWL4AI_ENDPOINT = "http://localhost:11235"

@mcp.tool()
def crawl4ai_research(urls: str, query: str, mode: str = "fit_markdown") -> str:
    """Crawl URLs for research. urls is JSON array string."""
    url_list = json.loads(urls)
    payload = {
        "urls": url_list,
        "priority": 10,
        "extraction_config": {
            "markdown_mode": mode,
            "content_filter": {"type": "bm25", "query": query, "threshold": 1.0},
            "include_links": True,
            "citations": True
        }
    }

    response = httpx.post(f"{CRAWL4AI_ENDPOINT}/crawl", json=payload, timeout=120)
    task_id = response.json()["task_id"]

    # Poll for result
    for _ in range(60):
        result = httpx.get(f"{CRAWL4AI_ENDPOINT}/task/{task_id}", timeout=30)
        data = result.json()
        if data.get("status") == "completed":
            return json.dumps(data.get("result", {}))
        import time
        time.sleep(2)

    return json.dumps({"error": "Timeout"})

@mcp.tool()
def crawl4ai_style_analysis(author_url: str) -> str:
    """Analyze an author's writing style from their website."""
    return crawl4ai_research(json.dumps([author_url]), "writing style tone voice", "fit_markdown")

@mcp.tool()
def crawl4ai_fact_check(claim: str, sources: str) -> str:
    """Fact-check a claim against sources. sources is JSON array."""
    source_list = json.loads(sources)
    research = crawl4ai_research(json.dumps(source_list), claim, "fit_markdown")

    # Now ask an LLM to verify
    return json.dumps({
        "claim": claim,
        "research": json.loads(research),
        "verification": "LLM verification would go here"
    })

if __name__ == "__main__":
    mcp.run()
'''

"""
--- filesystem_mcp_server.py ---
"""

FILESYSTEM_SERVER_CODE = '''
from mcp.server.fastmcp import FastMCP
from pathlib import Path
import json

mcp = FastMCP("FileSystemServer")
BASE_DIR = Path("./novel_output")
BASE_DIR.mkdir(exist_ok=True)

@mcp.tool()
def filesystem_write(filepath: str, content: str, append: bool = False) -> str:
    """Write content to a file."""
    path = BASE_DIR / filepath
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with open(path, mode, encoding="utf-8") as f:
        f.write(content)
    return f"Wrote to {path}"

@mcp.tool()
def filesystem_read(filepath: str) -> str:
    """Read content from a file."""
    path = BASE_DIR / filepath
    if not path.exists():
        return f"Error: {path} not found"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

@mcp.tool()
def filesystem_list(directory: str = ".") -> str:
    """List files in a directory."""
    path = BASE_DIR / directory
    files = [str(p.relative_to(BASE_DIR)) for p in path.rglob("*") if p.is_file()]
    return json.dumps(files)

@mcp.tool()
def filesystem_chapter_save(novel_name: str, chapter: str, content: str) -> str:
    """Save a chapter with proper naming."""
    filepath = f"{novel_name}/chapters/{chapter}.md"
    return filesystem_write(filepath, f"# {chapter}\n\n{content}")

if __name__ == "__main__":
    mcp.run()
'''


# ═══════════════════════════════════════════════════════════════════════════════
# 3. MODEL CLIENTS (Head + Critic)
# ═══════════════════════════════════════════════════════════════════════════════

class BaseModelClient:
    """Base client for OpenAI-compatible local LLM endpoints."""

    def __init__(self, endpoint: str, model_name: str, api_key: str = "dummy"):
        self.endpoint = endpoint.rstrip("/")
        self.model = model_name
        self.api_key = api_key
        self.session = None
        self._model_loaded = False  # Track if model is currently loaded in VRAM

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
        # Unload model when session closes to free VRAM
        if self._model_loaded:
            resource_manager.unload_model(self)
            self._model_loaded = False

    async def ensure_model_loaded(self):
        """
        Ensure model is loaded in VRAM using sequential loading.
        For remote endpoints, this just marks the model as 'active'.
        """
        if not self._model_loaded:
            logger.info(f"Activating model: {self.model}")
            # For remote API calls, we don't actually load weights locally
            # but we track it for resource management purposes
            self._model_loaded = True
            
    async def unload_model_if_needed(self):
        """Unload model from VRAM to free resources."""
        if self._model_loaded:
            logger.info(f"Deactivating model: {self.model} to free VRAM")
            resource_manager.unload_model(self)
            self._model_loaded = False

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        rep_pen: float = 1.0,
        max_tokens: int = 4000,
        stop: list[str] = None
    ) -> str:
        """Generate text from the model with sequential loading."""
        
        # Ensure this model is active before generation
        await self.ensure_model_loaded()

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "repetition_penalty": rep_pen,
            "max_tokens": max_tokens,
            "stop": stop or []
        }

        try:
            async with self.session.post(
                f"{self.endpoint}/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload
            ) as resp:
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
        finally:
            # Unload after generation to free VRAM for next model
            # Comment this out if you want to keep model loaded between calls
            # await self.unload_model_if_needed()
            pass


class HeadModelClient(BaseModelClient):
    """21B/40B Deckard model — creative, planning, worldbuilding."""

    DEFAULT_CONFIG = {
        "temperature": 1.0,
        "rep_pen": 1.05,
        "context_length": 16384,
        "thinking": True
    }

    def __init__(self, endpoint: str):
        super().__init__(
            endpoint=endpoint,
            model_name="DavidAU/Qwen3.5-21B-Claude-4.6-Opus-Deckard-Heretic-Uncensored-Thinking"
        )


class CriticModelClient(BaseModelClient):
    """14B model — grammar, continuity, cringe detection, plot review."""

    DEFAULT_CONFIG = {
        "temperature": 0.3,
        "rep_pen": 1.0,
        "context_length": 8192
    }

    def __init__(self, endpoint: str):
        super().__init__(
            endpoint=endpoint,
            model_name="qwen3.5-14b-instruct"  # Or any strong 14B instruct model
        )

    async def review(
        self,
        draft: str,
        check_types: list[str] | None = None,
        character_bibles: dict | None = None,
    ) -> dict:
        """Return a structured critique for bridge callers."""
        checks = check_types or ["grammar", "continuity", "cringe", "pacing"]
        prompt = f"""Review this draft and return JSON only.

        DRAFT:
        {draft}

        CHECKS: {', '.join(checks)}
        CHARACTERS: {json.dumps(character_bibles or {}, indent=2)[:2000]}

        Return JSON with keys:
        - scores: {{"overall": 0.0-1.0}}
        - issues: ["..."]
        """

        raw = await self.generate(
            system_prompt="You are a ruthless literary editor. Return only JSON.",
            user_prompt=prompt,
            temperature=0.3,
            rep_pen=1.0,
            max_tokens=2000,
        )

        try:
            data = json.loads(self._extract_json(raw))
            if not isinstance(data, dict):
                raise ValueError("Critic review did not return an object")
            return data
        except Exception:
            return {
                "scores": {"overall": 0.5},
                "issues": [raw[:500] if raw else "Critic review unavailable"],
            }


# ═══════════════════════════════════════════════════════════════════════════════
# 4. NOVEL STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class NovelState:
    """Tracks the current state of the novel being written."""

    current_novel: str = "untitled"
    current_chapter: str = "chapter_1"
    current_arc: str = "act_1"
    current_scene: int = 1

    characters: dict[str, dict] = field(default_factory=dict)
    plot_points: list[dict] = field(default_factory=list)
    total_word_count: int = 0

    # Quality tracking
    chapter_scores: dict[str, float] = field(default_factory=dict)
    revision_history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "novel": self.current_novel,
            "chapter": self.current_chapter,
            "arc": self.current_arc,
            "scene": self.current_scene,
            "word_count": self.total_word_count,
            "characters": list(self.characters.keys()),
            "plot_points": len(self.plot_points)
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 5. NOVELFORGE MAIN CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class NovelForge:
    """
    Main entry point for the agentic novel writing system.

    Usage:
        forge = NovelForge(
            head_endpoint="http://localhost:1234/v1",
            critic_endpoint="http://localhost:1235/v1",
            mcp_servers=["./mempalace_mcp_server.py", "./crawl4ai_mcp_server.py", "./filesystem_mcp_server.py"]
        )
        await forge.initialize()

        result = await forge.write_chapter(
            novel_name="example_novel",
            chapter="chapter_1",
            prompt="Write the next chapter from the current story context."
        )
    """

    def __init__(
        self,
        head_endpoint: str,
        critic_endpoint: str,
        mcp_servers: list[str],
        mempalace_path: str = "./novels_db"
    ):
        self.head = HeadModelClient(head_endpoint)
        self.critic = CriticModelClient(critic_endpoint)
        self.mcp_server_paths = mcp_servers
        self.mempalace_path = mempalace_path

        self.mcp_session = None
        self.orchestrator = None
        self.state = NovelState()

    async def initialize(self):
        """Initialize all connections with sequential model loading."""
        try:
            logger.info("🚀 Initializing NovelForge...")
            logger.info(f"💾 VRAM Status: {resource_manager.get_vram_usage()}")

            # Sequential Model Loading for Low-VRAM (8GB) Systems
            # Load Head model first
            await self.head.__aenter__()
            logger.info("✅ Head model initialized")
            logger.info(f"💾 VRAM after Head: {resource_manager.get_vram_usage()}")
            
            # Unload Head before loading Critic to save VRAM
            # This ensures only one large model is in VRAM at a time
            await self.head.unload_model_if_needed()
            
            # Load Critic model
            await self.critic.__aenter__()
            logger.info("✅ Critic model initialized")
            logger.info(f"💾 VRAM after Critic: {resource_manager.get_vram_usage()}")
            
            # Keep Critic unloaded initially; will load on-demand during review
            await self.critic.unload_model_if_needed()

            # Start MCP client session (optional, with timeout)
            self.mcp_session = None
            try:
                logger.info("[MCP] Attempting to connect to MCP server...")
                server_params = StdioServerParameters(
                    command=sys.executable,
                    args=[self.mcp_server_paths[0]],
                    env=None
                )

                self._mcp_stdio = stdio_client(server_params)
                self.mcp_read, self.mcp_write = await asyncio.wait_for(
                    self._mcp_stdio.__aenter__(), timeout=5.0
                )
                self.mcp_session = ClientSession(self.mcp_read, self.mcp_write)
                await asyncio.wait_for(self.mcp_session.initialize(), timeout=5.0)
                logger.info("✅ MCP session initialized")
            except asyncio.TimeoutError:
                logger.warning("[MCP] Timeout connecting to MCP server (skipping)")
                self.mcp_session = None
            except Exception as e:
                logger.warning(f"[MCP] Failed to initialize MCP: {e} (continuing without MCP)")
                self.mcp_session = None
            
            # Initialize orchestrator (works with or without MCP)
            self.orchestrator = IntelligentOrchestrator(
                head_model_client=self.head,
                critic_model_client=self.critic,
                mcp_session=self.mcp_session,
                mempalace_manager=None,  # Would be actual manager
                max_parallel=3,
                token_budget_per_hour=500000
            )
            if self.mcp_session:
                await self.orchestrator.initialize()
            else:
                logger.info("[Orchestrator] Skipping MCP tool discovery (no MCP session)")

            logger.info("✅ NovelForge initialized!")
            return True

        except asyncio.CancelledError as e:
            logger.exception("NovelForge initialization cancelled")
            await self._cleanup_partial_initialize()
            return False

        except Exception as e:
            logger.exception(f"❌ NovelForge initialization failed: {e}")
            await self._cleanup_partial_initialize()
            return False

    async def shutdown(self):
        """Clean shutdown."""
        if getattr(self, "_mcp_stdio", None):
            try:
                await self._mcp_stdio.__aexit__(None, None, None)
            except Exception:
                pass
            self._mcp_stdio = None
        await self.head.__aexit__(None, None, None)
        await self.critic.__aexit__(None, None, None)
        if self.mcp_session:
            await self.mcp_session.aclose()

    async def _cleanup_partial_initialize(self):
        """Tear down any partially created resources after init failure."""
        if self.mcp_session:
            try:
                await self.mcp_session.aclose()
            except Exception:
                pass
            self.mcp_session = None

        if getattr(self, "_mcp_stdio", None):
            try:
                await self._mcp_stdio.__aexit__(None, None, None)
            except Exception:
                pass
            self._mcp_stdio = None
        
        if getattr(self, "mcp_read", None):
            try:
                await self.mcp_read.aclose()
            except Exception:
                pass
        
        if getattr(self, "mcp_write", None):
            try:
                await self.mcp_write.aclose()
            except Exception:
                pass

        try:
            await self.head.__aexit__(None, None, None)
        except Exception:
            pass
        try:
            await self.critic.__aexit__(None, None, None)
        except Exception:
            pass

    async def write_chapter(self, novel_name: str, chapter: str, prompt: str) -> dict:
        """High-level API: write a complete chapter."""

        self.state.current_novel = novel_name
        self.state.current_chapter = chapter

        goal = f"Write chapter '{chapter}' for novel '{novel_name}'. {prompt}"

        return await self.orchestrator.execute_goal(goal, self.state)

    async def review_chapter(self, novel_name: str, chapter: str) -> dict:
        """High-level API: full editorial review of a chapter."""

        self.state.current_novel = novel_name
        self.state.current_chapter = chapter

        goal = f"Perform full editorial review of chapter '{chapter}': grammar, continuity, cringe detection, pacing analysis"

        return await self.orchestrator.execute_goal(goal, self.state)

    async def research_and_outline(self, novel_name: str, premise: str) -> dict:
        """High-level API: research and create full novel outline."""

        self.state.current_novel = novel_name

        goal = f"Research and create complete novel outline for: {premise}"

        return await self.orchestrator.execute_goal(goal, self.state)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. USAGE EXAMPLE
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    """Example usage of NovelForge."""

    forge = NovelForge(
        head_endpoint="http://localhost:1234/v1",      # LM Studio / Ollama for 21B
        critic_endpoint="http://localhost:1235/v1",    # Second instance for 14B
        mcp_servers=[
            "mempalace_mcp_server.py",
            "crawl4ai_mcp_server.py", 
            "filesystem_mcp_server.py"
        ]
    )

    try:
        await forge.initialize()

        # Example 1: Research and outline
        outline_result = await forge.research_and_outline(
            novel_name="example_novel",
            premise="Write a character-driven story with a clear central conflict"
        )
        print(f"Outline complete: {outline_result['tasks_completed']} tasks")

        # Example 2: Write a chapter
        chapter_result = await forge.write_chapter(
            novel_name="example_novel",
            chapter="chapter_1",
            prompt="Write the next chapter based on the current story context and user instructions."
        )
        print(f"Chapter written: {chapter_result['tasks_completed']} tasks, avg quality: {chapter_result['reflection']['avg_quality']:.2f}")

        # Example 3: Review
        review_result = await forge.review_chapter(
            novel_name="example_novel",
            chapter="chapter_1"
        )
        print(f"Review complete: {review_result['tasks_completed']} tasks")

    finally:
        await forge.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
