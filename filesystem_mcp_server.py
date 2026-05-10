#!/usr/bin/env python3
"""
FileSystem MCP Server
Provides file I/O tools for NovelForge to save/load chapters and drafts.

Security features:
- Path traversal protection
- Input validation
- Safe file operations

Run: python filesystem_mcp_server.py
"""

import json
import os
import re
from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("FileSystemServer")
BASE_DIR = Path(os.getenv("NOVEL_OUTPUT_DIR", "./novel_output")).resolve()
BASE_DIR.mkdir(parents=True, exist_ok=True)

# Maximum file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024
# Allowed file extensions
ALLOWED_EXTENSIONS = {'.md', '.txt', '.json', '.yaml', '.yml'}


def _validate_path(filepath: str) -> tuple[bool, str]:
    """Validate file path to prevent path traversal attacks.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check for null bytes
    if '\x00' in filepath:
        return False, "Invalid characters in path"
    
    # Normalize path separators
    normalized = filepath.replace('\\', '/')
    
    # Check for path traversal attempts
    if '..' in normalized.split('/'):
        return False, "Path traversal not allowed"
    
    # Construct full path and resolve it
    try:
        full_path = (BASE_DIR / normalized).resolve()
        
        # Ensure resolved path is within BASE_DIR
        if not str(full_path).startswith(str(BASE_DIR)):
            return False, "Access denied: path outside allowed directory"
        
        return True, str(full_path)
    except Exception as e:
        return False, f"Invalid path: {str(e)}"


def _validate_extension(filepath: str) -> bool:
    """Check if file extension is allowed."""
    ext = Path(filepath).suffix.lower()
    return ext in ALLOWED_EXTENSIONS or ext == ''


@mcp.tool()
def filesystem_write(filepath: str, content: str, append: bool = False) -> str:
    """Write content to a file.

    Args:
        filepath: Relative path within novel_output/
        content: Text content to write
        append: If True, append instead of overwrite
    
    Security:
        - Prevents path traversal attacks
        - Validates file extensions
        - Limits file size
    """
    # Validate path
    is_valid, result = _validate_path(filepath)
    if not is_valid:
        return json.dumps({"status": "error", "message": result})
    
    path = Path(result)
    
    # Validate extension
    if not _validate_extension(filepath):
        return json.dumps({
            "status": "error", 
            "message": f"File extension not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        })
    
    # Check content size
    content_bytes = content.encode('utf-8')
    if len(content_bytes) > MAX_FILE_SIZE:
        return json.dumps({
            "status": "error",
            "message": f"Content exceeds maximum size of {MAX_FILE_SIZE // (1024*1024)}MB"
        })
    
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(path, mode, encoding="utf-8") as f:
            f.write(content)
        return json.dumps({"status": "written", "path": str(path.relative_to(BASE_DIR)), "bytes": len(content_bytes)})
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

@mcp.tool()
def filesystem_read(filepath: str, max_size: int = None) -> str:
    """Read content from a file.

    Args:
        filepath: Relative path within novel_output/
        max_size: Maximum bytes to read (default: MAX_FILE_SIZE)
    
    Security:
        - Prevents path traversal attacks
        - Limits file size to prevent memory exhaustion
    """
    # Validate path
    is_valid, result = _validate_path(filepath)
    if not is_valid:
        return json.dumps({"status": "error", "message": result})
    
    path = Path(result)
    
    if not path.exists():
        return json.dumps({"status": "error", "message": f"File not found: {filepath}"})
    
    if not path.is_file():
        return json.dumps({"status": "error", "message": "Not a file"})
    
    # Check file size
    file_size = path.stat().st_size
    limit = max_size if max_size else MAX_FILE_SIZE
    
    if file_size > limit:
        return json.dumps({
            "status": "error",
            "message": f"File too large ({file_size} bytes). Maximum: {limit} bytes"
        })
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read(limit)
        return json.dumps({
            "status": "read",
            "path": str(path.relative_to(BASE_DIR)),
            "content": content,
            "length": len(content),
            "total_size": file_size
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

@mcp.tool()
def filesystem_list(directory: str = ".", pattern: str = "*", recursive: bool = False) -> str:
    """List files in a directory.

    Args:
        directory: Subdirectory within novel_output/
        pattern: Glob pattern (e.g., "*.md", "chapter_*")
        recursive: If True, list files in subdirectories
    
    Security:
        - Prevents path traversal attacks
        - Validates glob patterns
    """
    # Validate directory path
    is_valid, result = _validate_path(directory)
    if not is_valid:
        return json.dumps({"status": "error", "message": result})
    
    path = Path(result)
    
    if not path.exists():
        return json.dumps({"status": "error", "message": f"Directory not found: {directory}"})
    
    if not path.is_dir():
        return json.dumps({"status": "error", "message": "Not a directory"})
    
    # Validate pattern (prevent dangerous glob patterns)
    if any(char in pattern for char in ['\x00', '\n', '\r']):
        return json.dumps({"status": "error", "message": "Invalid characters in pattern"})
    
    try:
        if recursive:
            files = [str(p.relative_to(BASE_DIR)) for p in path.rglob(pattern) if p.is_file()]
        else:
            files = [str(p.relative_to(BASE_DIR)) for p in path.glob(pattern) if p.is_file()]
        
        # Sort by name
        files.sort()
        
        return json.dumps({
            "status": "listed",
            "directory": directory,
            "files": files,
            "count": len(files),
            "recursive": recursive
        })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

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
