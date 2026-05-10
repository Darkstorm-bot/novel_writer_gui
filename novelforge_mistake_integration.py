
# ═══════════════════════════════════════════════════════════════════════════════
# NOVELFORGE v2.1 — MISTAKE REGISTRY INTEGRATION
# Add these methods/classes to novelforge_v2.py
# ═══════════════════════════════════════════════════════════════════════════════

"""
MISTAKE REGISTRY INTEGRATION
==============================

The Mistake Registry is the "head file" that records every error the system
makes and how it was fixed. Before executing ANY task, the orchestrator:

1. QUERIES the registry for similar past mistakes
2. INJECTS prevention prompts into the system prompt
3. EXECUTES the task with mistake-awareness
4. RECORDS any new mistakes found by the critic
5. UPDATES success rates when fixes work
6. LEARNS from patterns across all tasks

This creates a self-improving writing system that gets better over time.
"""

import json

# ─────────────────────────────────────────────────────────────────────────────
# ADD TO IntelligentOrchestrator.__init__:
# ─────────────────────────────────────────────────────────────────────────────

# In __init__, add:
# self.mistake_registry_enabled = True
# self.mistake_prevention_threshold = 0.5  # Only inject if success rate > 50%
# self.mistake_learning_aggressive = True  # Record ALL issues, not just failures

# ─────────────────────────────────────────────────────────────────────────────
# NEW: MistakeAwarenessMixin
# ─────────────────────────────────────────────────────────────────────────────

class MistakeAwarenessMixin:
    """Mixin that adds mistake registry awareness to the orchestrator."""

    async def _load_mistake_prevention(self, task: TaskNode) -> str:
        """Query the mistake registry for prevention prompts before executing."""

        if not hasattr(self, 'mistake_registry_enabled') or not self.mistake_registry_enabled:
            return ""

        try:
            # Query prevention prompt for this task type
            result = await self.mcp.call_tool("mistake_get_prevention_prompt", {
                "task_type": task.task_type,
                "categories": json.dumps([
                    "hallucination", "continuity_error", "cringe", "style_drift",
                    "character_voice_loss", "pacing_break", "pov_slip", "repetition",
                    "over_description", "under_description", "dialogue_tag_abuse",
                    "motivation_gap", "emotional_tell", "worldbuild_dump"
                ])
            })

            data = json.loads(result)
            prevention = data.get("prevention_prompt", "")

            if prevention and len(prevention) > 50:
                logger.info(f"📚 Loaded mistake prevention guide for {task.task_type} ({len(prevention)} chars)")
                return prevention

            return ""

        except Exception as e:
            logger.warning(f"Could not load mistake prevention: {e}")
            return ""

    async def _check_for_known_mistakes(self, draft: str, task: TaskNode) -> list[dict]:
        """Check if the draft contains known mistake patterns."""

        if not hasattr(self, 'mistake_registry_enabled') or not self.mistake_registry_enabled:
            return []

        try:
            # Search for similar mistakes
            result = await self.mcp.call_tool("mistake_find_similar", {
                "query": draft[:2000],  # Check first 2K chars
                "task_type": task.task_type,
                "top_k": 5
            })

            data = json.loads(result)
            matches = data.get("matches", [])

            # Filter to high-confidence matches
            known_issues = []
            for match in matches:
                if match.get("success_rate", 0) > self.mistake_prevention_threshold:
                    known_issues.append(match)

            if known_issues:
                logger.info(f"⚠️  Found {len(known_issues)} known mistake patterns in draft")

            return known_issues

        except Exception as e:
            logger.warning(f"Could not check for known mistakes: {e}")
            return []

    async def _record_mistake(self, 
                              task: TaskNode, 
                              draft: str, 
                              critique: dict,
                              correction: str) -> Optional[str]:
        """Record a mistake found by the critic to the registry."""

        if not hasattr(self, 'mistake_learning_aggressive') or not self.mistake_learning_aggressive:
            return None

        # Extract issues from critique
        issues = critique.get("issues", [])
        if not issues:
            return None

        mistake_ids = []
        for issue in issues:
            # Classify the issue
            category = self._classify_issue(issue)
            severity = self._score_severity(issue, critique.get("score", 0.5))

            # Build the entry
            try:
                result = await self.mcp.call_tool("mistake_record", {
                    "task_type": task.task_type,
                    "task_description": task.description,
                    "model_used": task.preferred_model,
                    "category": category,
                    "severity": severity,
                    "mistake_description": issue,
                    "original_output": draft[:3000],
                    "mistake_excerpt": self._extract_mistake_excerpt(draft, issue),
                    "corrected_output": correction[:3000],
                    "correction_method": "critic_feedback",
                    "root_cause": self._infer_root_cause(issue, task),
                    "trigger_context": task.description[:500],
                    "prevention_prompt": self._build_prevention_prompt(category, issue),
                    "trigger_keywords": json.dumps(self._extract_keywords(issue)),
                    "negative_examples": json.dumps([self._extract_mistake_excerpt(draft, issue)]),
                    "positive_examples": json.dumps([correction[:500]])
                })

                data = json.loads(result)
                if data.get("status") == "recorded":
                    mistake_ids.append(data.get("mistake_id"))
                    logger.info(f"📝 Recorded mistake: {category} ({severity})")

            except Exception as e:
                logger.warning(f"Failed to record mistake: {e}")

        return mistake_ids[0] if mistake_ids else None

    async def _record_success_or_failure(self, mistake_id: str, success: bool):
        """Update whether a recorded fix actually worked."""
        if not mistake_id:
            return

        try:
            await self.mcp.call_tool("mistake_update_success", {
                "mistake_id": mistake_id,
                "success": success
            })
        except Exception as e:
            logger.warning(f"Could not update mistake success: {e}")

    def _classify_issue(self, issue: str) -> str:
        """Classify a critic issue into a mistake category."""
        issue_lower = issue.lower()

        classification_map = {
            "hallucination": ["invented", "made up", "nonexistent", "never established", "no evidence"],
            "continuity_error": ["contradict", "inconsistent", "earlier you said", "previously", "timeline"],
            "cringe": ["purple prose", "cliché", "overwrought", "melodramatic", "cheesy"],
            "grammar_syntax": ["grammar", "syntax", "tense", "comma", "fragment", "run-on"],
            "style_drift": ["voice", "tone shift", "sounds different", "style change"],
            "character_voice_loss": ["sound the same", "indistinguishable", "same voice", "identical speech"],
            "pacing_break": ["too fast", "too slow", "rushed", "dragging", "info dump"],
            "pov_slip": ["head hop", "pov", "perspective", "filtering", "omniscient"],
            "research_fail": ["inaccurate", "wrong century", "anachronism", "didn't exist"],
            "repetition": ["repeated", "same word", "echo", "redundant"],
            "over_description": ["too much description", "overwrought", "unnecessary detail"],
            "under_description": ["white room", "no setting", "vague", "under-described"],
            "dialogue_tag_abuse": ["ejaculated", "hissed", "dialogue tag", "said bookism"],
            "anachronism": ["anachronism", "wrong era", "didn't exist yet", "modern"],
            "motivation_gap": ["motivation", "why would", "unclear reason", "no cause"],
            "foreshadow_fail": ["foreshadow", "too obvious", "too subtle", "hint"],
            "emotional_tell": ["telling", "show don't tell", "was angry", "felt sad"],
            "worldbuild_dump": ["exposition", "info dump", "too much backstory"],
            "theme_contradiction": ["contradicts theme", "undermines", "mixed message"],
            "structural_error": ["scene doesn't", "no purpose", "doesn't advance"]
        }

        for category, keywords in classification_map.items():
            for kw in keywords:
                if kw in issue_lower:
                    return category

        return "style_drift"  # Default fallback

    def _score_severity(self, issue: str, quality_score: float) -> str:
        """Score issue severity based on issue text and quality score."""
        issue_lower = issue.lower()

        critical_keywords = ["contradict", "hallucination", "pov slip", "timeline", "major plot"]
        major_keywords = ["cringe", "voice loss", "pacing", "motivation gap", "continuity"]

        for kw in critical_keywords:
            if kw in issue_lower:
                return "critical"
        for kw in major_keywords:
            if kw in issue_lower:
                return "major"

        if quality_score < 0.4:
            return "major"
        elif quality_score < 0.6:
            return "minor"

        return "cosmetic"

    def _extract_mistake_excerpt(self, draft: str, issue: str) -> str:
        """Extract the specific text around the mistake."""
        # Simple heuristic: find sentences containing keywords from the issue
        issue_words = [w for w in issue.lower().split() if len(w) > 4]
        sentences = draft.replace("!", ".").replace("?", ".").split(".")

        for sent in sentences:
            for word in issue_words:
                if word in sent.lower():
                    return sent.strip()[:500]

        return draft[:500]  # Fallback

    def _infer_root_cause(self, issue: str, task: TaskNode) -> str:
        """Infer why the mistake happened."""
        causes = []

        if task.temperature > 0.9:
            causes.append("High temperature caused creative drift")
        if task.temperature < 0.4:
            causes.append("Low temperature caused robotic prose")
        if len(task.description) < 50:
            causes.append("Vague prompt lacked constraints")
        if task.preferred_model == "head":
            causes.append("Head model prioritized creativity over accuracy")
        if "outline" not in str(task.dependencies):
            causes.append("Missing outline led to structural issues")

        return "; ".join(causes) if causes else "Unknown — insufficient context"

    def _build_prevention_prompt(self, category: str, issue: str) -> str:
        """Build a prevention prompt snippet for this mistake category."""

        prevention_templates = {
            "hallucination": "Only use established facts from the context. If uncertain, imply rather than state.",
            "continuity_error": "Cross-check all character actions and timeline against previous scenes before writing.",
            "cringe": "Avoid purple prose, clichés, and melodrama. Keep descriptions grounded and specific.",
            "grammar_syntax": "Vary sentence structure. Check subject-verb agreement and tense consistency.",
            "style_drift": "Maintain the established voice and tone throughout. Reference the style guide.",
            "character_voice_loss": "Each character must have distinct vocabulary, rhythm, and speech patterns.",
            "pacing_break": "Alternate action, dialogue, and reflection. No info-dumps longer than 2 paragraphs.",
            "pov_slip": "Stay in the designated POV. No head-hopping. Use sensory details from that character only.",
            "research_fail": "Verify all historical/technical details. When uncertain, use vague but plausible details.",
            "repetition": "Use a thesaurus. No word should appear more than twice per paragraph unless intentional.",
            "over_description": "One vivid detail beats five adequate ones. Trust the reader's imagination.",
            "under_description": "Ground every scene in at least 3 sensory details and spatial orientation.",
            "dialogue_tag_abuse": "Use 'said' 90% of the time. Let actions and context carry emotion.",
            "anachronism": "Double-check era-appropriate language, technology, and social norms.",
            "motivation_gap": "Every significant action must have a clear, established motivation.",
            "foreshadow_fail": "Plant hints subtly. One explicit, two implicit per major plot point.",
            "emotional_tell": "Show emotion through action, dialogue, and physical sensation. Never name emotions directly.",
            "worldbuild_dump": "Weave worldbuilding into action and dialogue. No exposition longer than 3 sentences.",
            "theme_contradiction": "Ensure every scene reinforces or complicates the central theme.",
            "structural_error": "Every scene must advance plot, reveal character, or escalate conflict."
        }

        return prevention_templates.get(category, f"Be careful about: {issue[:100]}")

    def _extract_keywords(self, issue: str) -> list[str]:
        """Extract trigger keywords from an issue description."""
        # Simple keyword extraction
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                      "have", "has", "had", "do", "does", "did", "will", "would", "could",
                      "should", "may", "might", "must", "shall", "can", "need", "dare",
                      "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
                      "from", "as", "into", "through", "during", "before", "after", "above",
                      "below", "between", "under", "and", "but", "or", "yet", "so", "if",
                      "because", "although", "though", "while", "where", "when", "that",
                      "which", "who", "whom", "whose", "what", "this", "these", "those"}

        words = [w.strip(".,;:!?()[]{}"'") for w in issue.lower().split()]
        keywords = [w for w in words if len(w) > 4 and w not in stop_words]
        return list(set(keywords))[:10]  # Max 10 unique keywords

    async def _get_mistake_enriched_prompt(self, task: TaskNode, base_system_prompt: str) -> str:
        """Enhance system prompt with mistake prevention knowledge."""

        prevention = await self._load_mistake_prevention(task)

        if not prevention:
            return base_system_prompt

        # Combine base prompt with prevention knowledge
        enriched = f"""{base_system_prompt}

{prevention}

REMEMBER: These are mistakes the system has made before. Do NOT repeat them."""

        return enriched

    async def _meta_reflect_with_mistakes(self, results: list[dict]) -> dict:
        """Enhanced meta-reflection that includes mistake pattern analysis."""

        # Get base reflection
        base_reflection = await self._meta_reflect(results)

        try:
            # Get global mistake patterns
            patterns_result = await self.mcp.call_tool("mistake_get_patterns", {})
            patterns_data = json.loads(patterns_result)
            patterns = patterns_data.get("patterns", {})

            # Add mistake insights
            base_reflection["mistake_patterns"] = patterns
            base_reflection["mistake_suggestions"] = []

            # Identify recurring high-impact mistakes
            for category, data in patterns.items():
                if data.get("total_occurrences", 0) > 5 and data.get("avg_success_rate", 1.0) < 0.6:
                    base_reflection["mistake_suggestions"].append(
                        f"High-recurrence issue: {category} ({data['total_occurrences']} occurrences, "
                        f"{data['avg_success_rate']:.0%} fix rate). Consider adjusting prompts or model settings."
                    )

            # Export lessons learned periodically
            if len(base_reflection.get("mistake_suggestions", [])) > 3:
                try:
                    await self.mcp.call_tool("mistake_export_lessons", {})
                    base_reflection["lessons_exported"] = True
                except:
                    pass

        except Exception as e:
            logger.warning(f"Could not analyze mistake patterns: {e}")

        return base_reflection


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION: Modified _run_task method
# ─────────────────────────────────────────────────────────────────────────────

"""
Replace the existing _run_task method in IntelligentOrchestrator with this version:
"""

async def _run_task(self, task: TaskNode, novel_state: "NovelState"):
    """Execute a single task with full mistake-awareness."""
    logger.info(f"▶️  Executing {task.task_type}: {task.description[:60]}...")

    # Track if we recorded a mistake for this task
    recorded_mistake_id = None

    try:
        # Step 1: Intelligent context loading
        context = await self._load_context(task, novel_state)

        # Step 1.5: Load mistake prevention knowledge
        prevention_enriched = False
        if hasattr(self, 'mistake_registry_enabled') and self.mistake_registry_enabled:
            prevention = await self._load_mistake_prevention(task)
            if prevention:
                context["mistake_prevention"] = prevention
                prevention_enriched = True
                logger.info(f"🛡️  Loaded mistake prevention for {task.task_type}")

        # Step 2: Decide if tools needed
        tool_plan = await self._decide_tools(task, context)

        # Step 3: Execute tool calls if needed
        tool_results = await self._execute_tools(tool_plan)

        # Step 4: Build enriched system prompt with mistake prevention
        system_prompt = self._build_system_prompt(task, "creative")
        if prevention_enriched and hasattr(self, '_get_mistake_enriched_prompt'):
            system_prompt = await self._get_mistake_enriched_prompt(task, system_prompt)

        # Step 5: Route to appropriate model
        if task.preferred_model == "head":
            output = await self._run_head(task, context, tool_results, system_prompt)
        elif task.preferred_model == "critic":
            output = await self._run_critic(task, context, tool_results, system_prompt)
        else:  # both
            draft = await self._run_head(task, context, tool_results, system_prompt)
            output = await self._run_critic_review(task, draft, context)

        task.output = output
        task.actual_tokens = len(output.split()) * 1.3
        self.tokens_used_this_hour += task.actual_tokens

        # Step 6: Quality gate with mistake recording
        if task.preferred_model in ("head", "both"):
            task.quality_score = await self._assess_quality(task)

            if task.quality_score < 0.7 and task.revision_count < task.max_revisions:
                logger.info(f"🔄 Quality {task.quality_score:.2f} < 0.7, triggering revision")
                task.status = TaskStatus.REVISION
                task.revision_count += 1

                # Get critic feedback for mistake recording
                critique = task.critique if task.critique else {}

                revised = await self._revise_task(task, novel_state)

                # Record the mistake if we have critique data
                if hasattr(self, 'mistake_learning_aggressive') and self.mistake_learning_aggressive:
                    if critique:
                        recorded_mistake_id = await self._record_mistake(
                            task, task.output, critique, revised
                        )

                task.output = revised
                task.quality_score = await self._assess_quality(task)

                # Update whether the fix worked
                if hasattr(self, '_record_success_or_failure') and recorded_mistake_id:
                    fix_worked = task.quality_score >= 0.7
                    await self._record_success_or_failure(recorded_mistake_id, fix_worked)

        # Step 7: Check for known mistake patterns even if quality is good
        if hasattr(self, 'mistake_registry_enabled') and self.mistake_registry_enabled:
            known_issues = await self._check_for_known_mistakes(task.output, task)
            if known_issues:
                logger.warning(f"⚠️  Known mistake patterns detected post-generation, consider review")
                task.metadata["known_issues_flagged"] = len(known_issues)

        # Step 8: Store to memory
        await self._store_result(task, novel_state)

        task.status = TaskStatus.COMPLETED
        task.completed_at = time.time()

    except Exception as e:
        logger.error(f"❌ Task {task.task_id} failed: {e}")
        task.status = TaskStatus.FAILED
        task.metadata["error"] = str(e)


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION: Modified _run_head method signature
# ─────────────────────────────────────────────────────────────────────────────

"""
Update _run_head to accept optional system_prompt override:
"""

async def _run_head(self, task: TaskNode, context: dict, tool_results: dict, system_prompt: str = None) -> str:
    """Execute creative task with head model, optionally using enriched system prompt."""

    if system_prompt is None:
        system_prompt = self._build_system_prompt(task, "creative")

    user_prompt = self._build_user_prompt(task, context, tool_results)

    return await self.head.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=task.temperature,
        rep_pen=task.rep_penalty,
        max_tokens=min(task.estimated_tokens * 2, 8000)
    )


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION: Modified NovelForge.__init__
# ─────────────────────────────────────────────────────────────────────────────

"""
Add mistake_registry_mcp_server.py to the MCP servers list:
"""

# In NovelForge.__init__:
# self.mcp_server_paths = mcp_servers + ["mistake_registry_mcp_server.py"]

# Or better, just include it in the default list:
# mcp_servers=[
#     "mempalace_mcp_server.py",
#     "crawl4ai_mcp_server.py",
#     "filesystem_mcp_server.py",
#     "mistake_registry_mcp_server.py"  # <-- ADD THIS
# ]


# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION: Modified execute_goal to use mistake-aware meta-reflection
# ─────────────────────────────────────────────────────────────────────────────

"""
In IntelligentOrchestrator.execute_goal, replace:
    reflection = await self._meta_reflect(results)
With:
    reflection = await self._meta_reflect_with_mistakes(results)
"""


# ─────────────────────────────────────────────────────────────────────────────
# NEW: NovelForge convenience methods for mistake management
# ─────────────────────────────────────────────────────────────────────────────

class NovelForge:
    # ... existing methods ...

    async def review_and_learn(self, novel_name: str, chapter: str) -> dict:
        """Review a chapter and record all mistakes found for future prevention."""

        self.state.current_novel = novel_name
        self.state.current_chapter = chapter

        # First, do a normal review
        review_result = await self.review_chapter(novel_name, chapter)

        # Then, export lessons
        try:
            lessons = await self.orchestrator.mcp.call_tool("mistake_export_lessons", {})
            review_result["lessons_exported"] = True
        except:
            review_result["lessons_exported"] = False

        return review_result

    async def get_mistake_stats(self) -> dict:
        """Get overall mistake statistics."""
        try:
            stats = await self.orchestrator.mcp.call_tool("mistake_get_stats", {})
            return json.loads(stats)
        except Exception as e:
            return {"error": str(e)}

    async def find_similar_mistakes(self, query: str, task_type: str = None) -> list:
        """Find past mistakes similar to a query."""
        try:
            result = await self.orchestrator.mcp.call_tool("mistake_find_similar", {
                "query": query,
                "task_type": task_type,
                "top_k": 5
            })
            return json.loads(result).get("matches", [])
        except Exception as e:
            return []
