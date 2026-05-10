#!/usr/bin/env python3
"""
MemPalace MCP Server
Provides memory storage/retrieval tools for NovelForge via MCP protocol.

Run: python mempalace_mcp_server.py
"""

import json
import time
from pathlib import Path
from mcp.server.fastmcp import FastMCP

try:
    from mempalace import Palace
except (ImportError, ModuleNotFoundError):
    class _LocalKG:
        def __init__(self, root: Path):
            self.root = root
            self.path = root / "kg.json"
            self.root.mkdir(parents=True, exist_ok=True)
            self.facts = self._load()

        def _load(self):
            if self.path.exists():
                try:
                    return json.loads(self.path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    return []
            return []

        def _save(self):
            self.path.write_text(json.dumps(self.facts, indent=2), encoding="utf-8")

        def add_fact(self, subject: str, predicate: str, object: str, valid_from: float = None):
            self.facts.append({
                "subject": subject,
                "predicate": predicate,
                "object": object,
                "valid_from": valid_from,
            })
            self._save()

        def query(self, subject: str = None, relation_type: str = None, object: str = None):
            results = self.facts
            if subject is not None:
                results = [fact for fact in results if fact.get("subject") == subject]
            if relation_type is not None:
                results = [fact for fact in results if fact.get("predicate") == relation_type]
            if object is not None:
                results = [fact for fact in results if fact.get("object") == object]
            return results

    class Palace:
        def __init__(self, root_path: str):
            self.root = Path(root_path)
            self.root.mkdir(parents=True, exist_ok=True)
            self.docs_path = self.root / "documents.json"
            self.wings_path = self.root / "wings.json"
            self.documents = self._load_json(self.docs_path, [])
            self.wings = self._load_json(self.wings_path, {})
            self.kg = _LocalKG(self.root / "kg")

        def _load_json(self, path: Path, default):
            if path.exists():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    return default
            return default

        def _save_json(self, path: Path, payload):
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        def add_batch(self, documents, metadatas, ids):
            for document, metadata, doc_id in zip(documents, metadatas, ids):
                self.documents = [item for item in self.documents if item.get("id") != doc_id]
                self.documents.append({"id": doc_id, "document": document, "metadata": metadata})
            self._save_json(self.docs_path, self.documents)

        def search(self, query: str, wing: str, room: str = None, top_k: int = 5, mode: str = "hybrid_v4"):
            query_lower = query.lower()
            matches = []
            for item in self.documents:
                metadata = item.get("metadata", {})
                if metadata.get("wing") != wing:
                    continue
                if room is not None and metadata.get("room") != room:
                    continue

                haystack = f"{item.get('document', '')} {json.dumps(metadata, ensure_ascii=False)}".lower()
                score = haystack.count(query_lower)
                if query_lower in haystack:
                    score += 1
                if score:
                    matches.append({
                        "id": item.get("id"),
                        "document": item.get("document"),
                        "metadata": metadata,
                        "score": score,
                    })

            return matches[:top_k]

        def create_wing(self, wing_name: str):
            self.wings.setdefault(wing_name, {"rooms": []})
            self._save_json(self.wings_path, self.wings)

        def create_room(self, wing: str, room_name: str):
            wing_entry = self.wings.setdefault(wing, {"rooms": []})
            if room_name not in wing_entry["rooms"]:
                wing_entry["rooms"].append(room_name)
                self._save_json(self.wings_path, self.wings)

mcp = FastMCP("MemPalaceServer")
palace = Palace("./novels_db")

@mcp.tool()
def mempalace_store(content: str, wing: str, room: str, hall: str, metadata: str = "{}") -> str:
    """Store content in the memory palace.

    Args:
        content: The text content to store
        wing: Novel/project name (e.g., "cyberpunk_novel")
        room: Chapter or section (e.g., "chapter_3")
        hall: Content type (e.g., "drafts", "research", "characters")
        metadata: JSON string with additional metadata
    """
    meta = json.loads(metadata)
    drawer_id = f"{wing}/{room}/{hall}/{time.time()}"
    palace.add_batch(
        documents=[content],
        metadatas=[{"wing": wing, "room": room, "hall": hall, "drawer": drawer_id, **meta}],
        ids=[drawer_id]
    )
    return json.dumps({"status": "stored", "drawer_id": drawer_id, "length": len(content)})

@mcp.tool()
def mempalace_retrieve(query: str, wing: str, room: str = None, top_k: int = 5) -> str:
    """Retrieve relevant memories using hybrid vector + BM25 search.

    Args:
        query: Search query
        wing: Novel/project name
        room: Optional room filter
        top_k: Number of results
    """
    results = palace.search(query=query, wing=wing, room=room, top_k=top_k, mode="hybrid_v4")
    return json.dumps({"results": results, "count": len(results)})

@mcp.tool()
def mempalace_kg_query(subject: str, relation_type: str = None, object_filter: str = None) -> str:
    """Query the temporal knowledge graph for character/plot consistency.

    Args:
        subject: Entity name (character, location, etc.)
        relation_type: Optional relation filter (e.g., "appears_in", "motivation")
        object_filter: Optional object filter
    """
    results = palace.kg.query(subject=subject, relation_type=relation_type, object=object_filter)
    return json.dumps({"facts": results, "subject": subject})

@mcp.tool()
def mempalace_create_wing(wing_name: str) -> str:
    """Create a new wing (novel project)."""
    palace.create_wing(wing_name)
    return json.dumps({"status": "created", "wing": wing_name})

@mcp.tool()
def mempalace_create_room(wing: str, room_name: str) -> str:
    """Create a new room (chapter/arc) within a wing."""
    palace.create_room(wing, room_name)
    return json.dumps({"status": "created", "wing": wing, "room": room_name})

@mcp.tool()
def mempalace_character_update(wing: str, character_name: str, attributes: str) -> str:
    """Update character bible in the knowledge graph.

    Args:
        wing: Novel name
        character_name: Character name
        attributes: JSON string of character attributes
    """
    attrs = json.loads(attributes)
    for key, value in attrs.items():
        palace.kg.add_fact(
            subject=character_name,
            predicate=key,
            object=str(value),
            valid_from=time.time()
        )
    return json.dumps({"status": "updated", "character": character_name, "fields": list(attrs.keys())})

@mcp.tool()
def mempalace_timeline_check(wing: str, character: str, event_time: str) -> str:
    """Check if a character was at a specific time/place (continuity check).

    Args:
        wing: Novel name
        character: Character name
        event_time: Timestamp or chapter reference
    """
    facts = palace.kg.query(subject=character, relation_type="appears_in")
    locations = [f for f in facts if "location" in str(f).lower()]
    return json.dumps({"character": character, "timeline_facts": facts, "locations": locations})

if __name__ == "__main__":
    mcp.run()
