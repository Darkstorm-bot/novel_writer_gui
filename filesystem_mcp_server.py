#!/usr/bin/env python3
"""
FileSystem MCP Server
Provides file I/O tools for NovelForge to save/load chapters and drafts.

Run: python filesystem_mcp_server.py
"""

import json
from pathlib import Path
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("FileSystemServer")
BASE_DIR = Path("./novel_output")
BASE_DIR.mkdir(exist_ok=True)

@mcp.tool()
def filesystem_write(filepath: str, content: str, append: bool = False) -> str:
    """Write content to a file.

    Args:
        filepath: Relative path within novel_output/
        content: Text content to write
        append: If True, append instead of overwrite
    """
    path = BASE_DIR / filepath
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with open(path, mode, encoding="utf-8") as f:
        f.write(content)
    return json.dumps({"status": "written", "path": str(path), "bytes": len(content.encode())})

@mcp.tool()
def filesystem_read(filepath: str) -> str:
    """Read content from a file.

    Args:
        filepath: Relative path within novel_output/
    """
    path = BASE_DIR / filepath
    if not path.exists():
        return json.dumps({"status": "error", "message": f"File not found: {filepath}"})
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return json.dumps({"status": "read", "path": str(path), "content": content, "length": len(content)})

@mcp.tool()
def filesystem_list(directory: str = ".", pattern: str = "*") -> str:
    """List files in a directory.

    Args:
        directory: Subdirectory within novel_output/
        pattern: Glob pattern (e.g., "*.md", "chapter_*")
    """
    path = BASE_DIR / directory
    if not path.exists():
        return json.dumps({"status": "error", "message": f"Directory not found: {directory}"})
    files = [str(p.relative_to(BASE_DIR)) for p in path.rglob(pattern) if p.is_file()]
    return json.dumps({"status": "listed", "directory": directory, "files": files, "count": len(files)})

@mcp.tool()
def filesystem_chapter_save(novel_name: str, chapter: str, content: str, draft_version: int = 1) -> str:
    """Save a chapter with proper naming and versioning.

    Args:
        novel_name: Novel project name
        chapter: Chapter name/number
        content: Chapter content
        draft_version: Draft version number
    """
    safe_chapter = chapter.replace(" ", "_").replace("/", "_")
    filepath = f"{novel_name}/chapters/{safe_chapter}_v{draft_version}.md"
    header = f"# {chapter}\n\n**Novel:** {novel_name} | **Draft:** v{draft_version}\n\n---\n\n"
    return filesystem_write(filepath, header + content)

@mcp.tool()
def filesystem_chapter_load(novel_name: str, chapter: str, draft_version: int = None) -> str:
    """Load a specific chapter or latest draft.

    Args:
        novel_name: Novel project name
        chapter: Chapter name
        draft_version: Specific version, or None for latest
    """
    safe_chapter = chapter.replace(" ", "_").replace("/", "_")

    if draft_version:
        filepath = f"{novel_name}/chapters/{safe_chapter}_v{draft_version}.md"
        return filesystem_read(filepath)

    # Find latest version
    chapter_dir = BASE_DIR / novel_name / "chapters"
    if not chapter_dir.exists():
        return json.dumps({"status": "error", "message": f"No chapters found for {novel_name}"})

    matching = sorted(chapter_dir.glob(f"{safe_chapter}_v*.md"))
    if not matching:
        return json.dumps({"status": "error", "message": f"No drafts found for {chapter}"})

    latest = matching[-1]
    with open(latest, "r", encoding="utf-8") as f:
        content = f.read()
    return json.dumps({
        "status": "read",
        "path": str(latest.relative_to(BASE_DIR)),
        "content": content,
        "version": len(matching)
    })

@mcp.tool()
def filesystem_project_init(novel_name: str, genre: str = "", premise: str = "") -> str:
    """Initialize a new novel project with directory structure.

    Args:
        novel_name: Project name
        genre: Genre tag
        premise: One-line premise
    """
    dirs = [
        f"{novel_name}/chapters",
        f"{novel_name}/outlines",
        f"{novel_name}/characters",
        f"{novel_name}/research",
        f"{novel_name}/notes"
    ]
    for d in dirs:
        (BASE_DIR / d).mkdir(parents=True, exist_ok=True)

    # Create project manifest
    manifest = {
        "name": novel_name,
        "genre": genre,
        "premise": premise,
        "created": str(Path.cwd()),
        "chapters": [],
        "characters": []
    }
    filesystem_write(
        f"{novel_name}/manifest.json",
        json.dumps(manifest, indent=2)
    )

    return json.dumps({"status": "initialized", "novel": novel_name, "directories": dirs})

if __name__ == "__main__":
    mcp.run()
