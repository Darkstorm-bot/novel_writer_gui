#!/usr/bin/env python3
"""
Mistake Registry MCP Server — The "Head File" for Agent Self-Improvement
============================================================================

Records every mistake made by head/critic models, the corrections applied,
and the root causes. Before any task execution, the orchestrator queries
this registry to inject "mistake prevention" prompts.

Mistake Categories:
    hallucination        — Invented facts, characters, events
    continuity_error     — Plot/character/timeline contradictions
    cringe               — Purple prose, clichés, filter words
    grammar_syntax       — Technical writing errors
    style_drift          — Voice/tone inconsistency within scene
    character_voice_loss — Characters sound identical
    pacing_break         — Too fast/slow, info-dumps
    pov_slip             — Head-hopping, inconsistent perspective
    research_fail        — Wrong facts about setting/history
    repetition           — Word/phrase/idea repetition
    over_description     — Too much showing where telling works
    under_description    — White room syndrome
    dialogue_tag_abuse   — "he ejaculated", "she hissed"
    anachronism          — Wrong tech/language for era
    motivation_gap       — Character acts without clear reason
    foreshadow_fail      — Planted hints too obvious/too hidden
    emotional_tell       — "He was angry" instead of showing
    worldbuild_dump      — Exposition walls
    theme_contradiction  — Story argues against itself
    structural_error     — Scene doesn't serve plot/character

Run: python mistake_registry_mcp_server.py
"""

import json
import time
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("MistakeRegistryServer")

REGISTRY_PATH = Path("./mistake_registry.jsonl")
INDEX_PATH = Path("./mistake_index.json")

# ─────────────────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class MistakeEntry:
    mistake_id: str
    timestamp: float

    # Task context
    task_type: str
    task_description: str
    model_used: str          # "head_21b" | "critic_14b" | "both"

    # Classification
    category: str            # One of the categories above
    severity: str            # "critical" | "major" | "minor" | "cosmetic"

    # The mistake
    mistake_description: str # What went wrong (human-readable)
    original_output: str     # The bad output (truncated)
    mistake_excerpt: str     # Specific problematic text

    # The correction
    corrected_output: str    # The fixed version (truncated)
    correction_method: str   # "auto_revision" | "manual_edit" | "critic_feedback" | "continuity_check"

    # Root cause analysis
    root_cause: str          # Why it happened
    trigger_context: str     # What in the prompt/context caused it

    # Prevention
    prevention_prompt: str   # System prompt addition to prevent this
    trigger_keywords: list   # Words/phrases that signal this mistake
    negative_examples: list  # Examples of what NOT to do
    positive_examples: list  # Examples of what TO do instead

    # Learning metrics
    occurrence_count: int = 1
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    revision_attempts: int = 0
    success_after_fix: int = 0
    failure_after_fix: int = 0
    success_rate: float = 0.0

    # Related mistakes (clustering)
    related_mistake_ids: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MistakeEntry":
        return cls(**d)


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY ENGINE
# ─────────────────────────────────────────────────────────────────────────────

class MistakeRegistry:
    """Persistent mistake registry with vector-like search and clustering."""

    def __init__(self, path: Path = REGISTRY_PATH):
        self.path = path
        self.entries: dict[str, MistakeEntry] = {}
        self.index: dict[str, list[str]] = {  # category -> [mistake_ids]
            "hallucination": [],
            "continuity_error": [],
            "cringe": [],
            "grammar_syntax": [],
            "style_drift": [],
            "character_voice_loss": [],
            "pacing_break": [],
            "pov_slip": [],
            "research_fail": [],
            "repetition": [],
            "over_description": [],
            "under_description": [],
            "dialogue_tag_abuse": [],
            "anachronism": [],
            "motivation_gap": [],
            "foreshadow_fail": [],
            "emotional_tell": [],
            "worldbuild_dump": [],
            "theme_contradiction": [],
            "structural_error": [],
        }
        self.task_type_index: dict[str, list[str]] = {}  # task_type -> [mistake_ids]
        self.keyword_index: dict[str, list[str]] = {}    # keyword -> [mistake_ids]
        self._load()

    def _generate_id(self, entry: MistakeEntry) -> str:
        content = f"{entry.task_type}:{entry.category}:{entry.mistake_description[:100]}:{time.time()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _load(self):
        """Load all entries from disk."""
        if not self.path.exists():
            return

        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entry = MistakeEntry.from_dict(data)
                    self.entries[entry.mistake_id] = entry
                    self._index_entry(entry)
                except Exception as e:
                    print(f"Warning: Failed to load mistake entry: {e}")

    def _save(self):
        """Append-only save to JSONL."""
        with open(self.path, "a", encoding="utf-8") as f:
            for entry in self.entries.values():
                if not self._entry_exists_on_disk(entry.mistake_id):
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    def _entry_exists_on_disk(self, mistake_id: str) -> bool:
        """Check if entry already exists in file (naive)."""
        if not self.path.exists():
            return False
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                if mistake_id in line:
                    return True
        return False

    def _index_entry(self, entry: MistakeEntry):
        """Add entry to in-memory indexes."""
        # Category index
        if entry.category in self.index:
            if entry.mistake_id not in self.index[entry.category]:
                self.index[entry.category].append(entry.mistake_id)

        # Task type index
        if entry.task_type not in self.task_type_index:
            self.task_type_index[entry.task_type] = []
        if entry.mistake_id not in self.task_type_index[entry.task_type]:
            self.task_type_index[entry.task_type].append(entry.mistake_id)

        # Keyword index
        for kw in entry.trigger_keywords:
            kw_lower = kw.lower()
            if kw_lower not in self.keyword_index:
                self.keyword_index[kw_lower] = []
            if entry.mistake_id not in self.keyword_index[kw_lower]:
                self.keyword_index[kw_lower].append(entry.mistake_id)

    def add(self, entry: MistakeEntry) -> str:
        """Add a new mistake entry. Returns the mistake_id."""
        entry.mistake_id = self._generate_id(entry)
        entry.first_seen = time.time()
        entry.last_seen = time.time()

        self.entries[entry.mistake_id] = entry
        self._index_entry(entry)
        self._save()

        return entry.mistake_id

    def update_success(self, mistake_id: str, success: bool):
        """Update success metrics after a fix is applied."""
        if mistake_id not in self.entries:
            return False

        entry = self.entries[mistake_id]
        entry.last_seen = time.time()
        entry.revision_attempts += 1

        if success:
            entry.success_after_fix += 1
        else:
            entry.failure_after_fix += 1

        total = entry.success_after_fix + entry.failure_after_fix
        entry.success_rate = entry.success_after_fix / total if total > 0 else 0.0

        return True

    def find_similar(self, query: str, task_type: str = None, category: str = None, top_k: int = 5) -> list[dict]:
        """Find mistakes similar to the query using keyword + category matching."""
        scores: dict[str, float] = {}
        query_lower = query.lower()
        query_words = set(query_lower.split())

        # Score by keyword overlap
        for word in query_words:
            if word in self.keyword_index:
                for mid in self.keyword_index[word]:
                    scores[mid] = scores.get(mid, 0) + 1.0

        # Score by category match
        if category and category in self.index:
            for mid in self.index[category]:
                scores[mid] = scores.get(mid, 0) + 2.0

        # Score by task type match
        if task_type and task_type in self.task_type_index:
            for mid in self.task_type_index[task_type]:
                scores[mid] = scores.get(mid, 0) + 1.5

        # Boost by success rate (prefer solutions that work)
        for mid in scores:
            if mid in self.entries:
                entry = self.entries[mid]
                scores[mid] += entry.success_rate * 2.0
                # Penalize entries with high occurrence but low success
                if entry.occurrence_count > 3 and entry.success_rate < 0.5:
                    scores[mid] -= 1.0

        # Sort and return top_k
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_k]
        return [self.entries[mid].to_dict() for mid in sorted_ids if mid in self.entries]

    def get_prevention_prompt(self, task_type: str, category_filter: list[str] = None) -> str:
        """Build a prevention prompt for a specific task type."""

        if task_type not in self.task_type_index:
            return ""

        relevant_ids = self.task_type_index[task_type]
        if category_filter:
            relevant_ids = [mid for mid in relevant_ids 
                          if self.entries[mid].category in category_filter]

        if not relevant_ids:
            return ""

        # Sort by: severity (critical first), then occurrence count, then success rate
        sorted_entries = sorted(
            [self.entries[mid] for mid in relevant_ids],
            key=lambda e: (
                {"critical": 0, "major": 1, "minor": 2, "cosmetic": 3}.get(e.severity, 4),
                -e.occurrence_count,
                -e.success_rate
            )
        )

        lines = ["\n=== MISTAKE PREVENTION GUIDE ===\n"]
        lines.append(f"Based on {len(sorted_entries)} past mistakes in {task_type} tasks:\n")

        seen_categories = set()
        for entry in sorted_entries[:10]:  # Top 10 most important
            if entry.category in seen_categories:
                continue
            seen_categories.add(entry.category)

            lines.append(f"\n【{entry.category.upper()}】")
            lines.append(f"  Problem: {entry.mistake_description[:150]}")
            lines.append(f"  Prevention: {entry.prevention_prompt[:200]}")
            if entry.negative_examples:
                lines.append(f"  DON'T: {entry.negative_examples[0][:100]}")
            if entry.positive_examples:
                lines.append(f"  DO: {entry.positive_examples[0][:100]}")
            lines.append(f"  Success rate of fix: {entry.success_rate:.0%} ({entry.success_after_fix}/{entry.success_after_fix + entry.failure_after_fix})")

        lines.append("\n=== END PREVENTION GUIDE ===\n")
        return "\n".join(lines)

    def get_global_patterns(self) -> dict:
        """Get global mistake patterns across all tasks."""
        patterns = {}
        for cat, ids in self.index.items():
            if not ids:
                continue
            entries = [self.entries[mid] for mid in ids]
            total_occurrences = sum(e.occurrence_count for e in entries)
            avg_success = sum(e.success_rate for e in entries) / len(entries) if entries else 0

            patterns[cat] = {
                "count": len(ids),
                "total_occurrences": total_occurrences,
                "avg_success_rate": round(avg_success, 2),
                "most_common_task": self._most_common([e.task_type for e in entries]),
                "top_trigger": self._most_common([kw for e in entries for kw in e.trigger_keywords])
            }
        return patterns

    def _most_common(self, items: list) -> str:
        if not items:
            return ""
        from collections import Counter
        return Counter(items).most_common(1)[0][0]

    def export_lessons_learned(self) -> str:
        """Export a human-readable "lessons learned" document."""
        lines = ["# NovelForge Lessons Learned\n"]
        lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M')}\n")
        lines.append(f"Total mistakes recorded: {len(self.entries)}\n")

        patterns = self.get_global_patterns()

        lines.append("\n## Mistake Frequency by Category\n")
        for cat, data in sorted(patterns.items(), key=lambda x: x[1]["total_occurrences"], reverse=True):
            if data["count"] == 0:
                continue
            lines.append(f"\n### {cat.replace('_', ' ').title()}")
            lines.append(f"- Occurrences: {data['total_occurrences']}")
            lines.append(f"- Unique mistakes: {data['count']}")
            lines.append(f"- Avg fix success: {data['avg_success_rate']:.0%}")
            lines.append(f"- Most common in: {data['most_common_task']}")
            if data["top_trigger"]:
                lines.append(f"- Common trigger: '{data['top_trigger']}'")

        lines.append("\n## High-Impact Prevention Rules\n")
        for entry in sorted(self.entries.values(), 
                          key=lambda e: (e.occurrence_count * (1 - e.success_rate)), 
                          reverse=True)[:20]:
            lines.append(f"\n### {entry.category} — {entry.severity}")
            lines.append(f"**Problem:** {entry.mistake_description}")
            lines.append(f"**Solution:** {entry.prevention_prompt}")
            lines.append(f"**Occurs in:** {entry.task_type} | **Fixed:** {entry.success_rate:.0%} of attempts")

        return "\n".join(lines)


# Global registry instance
_registry = MistakeRegistry()


# ─────────────────────────────────────────────────────────────────────────────
# MCP TOOLS
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def mistake_record(
    task_type: str,
    task_description: str,
    model_used: str,
    category: str,
    severity: str,
    mistake_description: str,
    original_output: str,
    mistake_excerpt: str,
    corrected_output: str,
    correction_method: str,
    root_cause: str,
    trigger_context: str,
    prevention_prompt: str,
    trigger_keywords: str,  # JSON array string
    negative_examples: str = "[]",
    positive_examples: str = "[]",
    related_mistake_ids: str = "[]"
) -> str:
    """Record a new mistake and its correction.

    Args:
        task_type: e.g., "scene_draft", "dialogue_polish"
        task_description: What the task was trying to do
        model_used: "head_21b", "critic_14b", or "both"
        category: mistake category (see docstring)
        severity: "critical", "major", "minor", "cosmetic"
        mistake_description: Human-readable description of what went wrong
        original_output: The bad output (will be truncated)
        mistake_excerpt: Specific problematic text
        corrected_output: The fixed version
        correction_method: How it was fixed
        root_cause: Why it happened
        trigger_context: What caused it
        prevention_prompt: System prompt addition to prevent this
        trigger_keywords: JSON array of keywords that signal this mistake
        negative_examples: JSON array of what NOT to do
        positive_examples: JSON array of what TO do
        related_mistake_ids: JSON array of related mistake IDs
    """
    entry = MistakeEntry(
        mistake_id="",  # Will be generated
        timestamp=time.time(),
        task_type=task_type,
        task_description=task_description,
        model_used=model_used,
        category=category,
        severity=severity,
        mistake_description=mistake_description,
        original_output=original_output[:3000],
        mistake_excerpt=mistake_excerpt[:1000],
        corrected_output=corrected_output[:3000],
        correction_method=correction_method,
        root_cause=root_cause,
        trigger_context=trigger_context,
        prevention_prompt=prevention_prompt,
        trigger_keywords=json.loads(trigger_keywords),
        negative_examples=json.loads(negative_examples),
        positive_examples=json.loads(positive_examples),
        related_mistake_ids=json.loads(related_mistake_ids)
    )

    mid = _registry.add(entry)
    return json.dumps({"status": "recorded", "mistake_id": mid, "category": category})


@mcp.tool()
def mistake_find_similar(query: str, task_type: str = None, category: str = None, top_k: int = 5) -> str:
    """Find past mistakes similar to a description.

    Args:
        query: Description of the current issue
        task_type: Filter by task type
        category: Filter by mistake category
        top_k: Number of results
    """
    results = _registry.find_similar(query, task_type, category, top_k)
    return json.dumps({"matches": results, "count": len(results)})


@mcp.tool()
def mistake_get_prevention_prompt(task_type: str, categories: str = None) -> str:
    """Get a prevention prompt for a task type.

    Args:
        task_type: The task about to be executed
        categories: Optional JSON array of categories to include
    """
    cat_filter = json.loads(categories) if categories else None
    prompt = _registry.get_prevention_prompt(task_type, cat_filter)
    return json.dumps({"prevention_prompt": prompt, "length": len(prompt)})


@mcp.tool()
def mistake_update_success(mistake_id: str, success: bool) -> str:
    """Update whether a fix worked.

    Args:
        mistake_id: The mistake ID
        success: True if the fix worked, False if it didn't
    """
    updated = _registry.update_success(mistake_id, success)
    return json.dumps({"status": "updated" if updated else "not_found", "mistake_id": mistake_id})


@mcp.tool()
def mistake_get_patterns() -> str:
    """Get global mistake patterns across all tasks."""
    patterns = _registry.get_global_patterns()
    return json.dumps({"patterns": patterns, "total_entries": len(_registry.entries)})


@mcp.tool()
def mistake_export_lessons() -> str:
    """Export a human-readable lessons learned document."""
    document = _registry.export_lessons_learned()

    # Also save to file
    lessons_path = Path("./LESSONS_LEARNED.md")
    with open(lessons_path, "w", encoding="utf-8") as f:
        f.write(document)

    return json.dumps({
        "status": "exported",
        "path": str(lessons_path),
        "document": document[:5000] + "..." if len(document) > 5000 else document
    })


@mcp.tool()
def mistake_get_by_category(category: str, limit: int = 10) -> str:
    """Get all mistakes in a category.

    Args:
        category: Mistake category
        limit: Max results
    """
    if category not in _registry.index:
        return json.dumps({"error": f"Unknown category: {category}"})

    ids = _registry.index[category][:limit]
    entries = [_registry.entries[mid].to_dict() for mid in ids if mid in _registry.entries]
    return json.dumps({"category": category, "entries": entries, "count": len(entries)})


@mcp.tool()
def mistake_get_stats() -> str:
    """Get overall registry statistics."""
    total = len(_registry.entries)
    by_severity = {"critical": 0, "major": 0, "minor": 0, "cosmetic": 0}
    by_model = {}

    for entry in _registry.entries.values():
        by_severity[entry.severity] = by_severity.get(entry.severity, 0) + 1
        by_model[entry.model_used] = by_model.get(entry.model_used, 0) + 1

    return json.dumps({
        "total_mistakes": total,
        "by_severity": by_severity,
        "by_model": by_model,
        "by_category": {cat: len(ids) for cat, ids in _registry.index.items() if ids},
        "storage_path": str(REGISTRY_PATH)
    })


@mcp.tool()
def mistake_batch_record(entries_json: str) -> str:
    """Record multiple mistakes at once.

    Args:
        entries_json: JSON array of mistake entry objects
    """
    entries = json.loads(entries_json)
    ids = []
    for data in entries:
        entry = MistakeEntry(
            mistake_id="",
            timestamp=time.time(),
            **{k: v for k, v in data.items() if k != "mistake_id"}
        )
        mid = _registry.add(entry)
        ids.append(mid)

    return json.dumps({"status": "recorded", "count": len(ids), "mistake_ids": ids})


if __name__ == "__main__":
    mcp.run()
