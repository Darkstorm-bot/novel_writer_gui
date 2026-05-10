#!/usr/bin/env python3
"""
Crawl4AI MCP Server
Provides web research and style analysis tools for NovelForge.

Supports two modes:
1. Docker mode (recommended): docker run -d -p 11235:11235 unclecode/crawl4ai:latest
2. Direct mode: Uses crawl4ai Python library if installed

Run: python crawl4ai_mcp_server.py
"""

import json
import time
import httpx
import os
from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Crawl4AIServer")
CRAWL4AI_ENDPOINT = os.getenv("CRAWL4AI_ENDPOINT", "http://localhost:11235")
CRAWL4AI_MODE = os.getenv("CRAWL4AI_MODE", "auto")  # "auto", "docker", "direct"

# Try to import crawl4ai for direct mode
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False

def _crawl_with_docker(url_list: list, query: str, mode: str = "fit_markdown") -> dict:
    """Crawl using Docker-based Crawl4AI API."""
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

    try:
        response = httpx.post(f"{CRAWL4AI_ENDPOINT}/crawl", json=payload, timeout=120)
        task_id = response.json()["task_id"]

        # Poll for completion
        for _ in range(60):
            result = httpx.get(f"{CRAWL4AI_ENDPOINT}/task/{task_id}", timeout=30)
            data = result.json()
            if data.get("status") == "completed":
                return {
                    "status": "success",
                    "markdown": data.get("result", {}).get("markdown", ""),
                    "sources": data.get("result", {}).get("links", []),
                    "images": data.get("result", {}).get("media", []),
                    "citations": data.get("result", {}).get("citations", [])
                }
            time.sleep(2)

        return {"status": "timeout", "task_id": task_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def _crawl_direct_async(url_list: list, query: str, mode: str = "fit_markdown") -> dict:
    """Crawl using direct crawl4ai library."""
    if not CRAWL4AI_AVAILABLE:
        return {"status": "error", "message": "crawl4ai library not installed"}
    
    try:
        browser_config = BrowserConfig(headless=True)
        crawler_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
        
        all_content = []
        all_links = []
        all_media = []
        
        async with AsyncWebCrawler(config=browser_config) as crawler:
            for url in url_list:
                result = await crawler.arun(url=url, config=crawler_config)
                if result.success:
                    all_content.append(result.markdown or "")
                    all_links.extend(result.links.get("external", []) + result.links.get("internal", []))
                    all_media.extend(result.media.get("images", []) + result.media.get("videos", []))
        
        return {
            "status": "success",
            "markdown": "\n\n---\n\n".join(all_content),
            "sources": list(set(all_links))[:50],
            "images": list(set(all_media))[:50],
            "citations": []
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def crawl4ai_research(urls: str, query: str, mode: str = "fit_markdown", max_pages: int = 5) -> str:
    """Crawl URLs for research with BM25 content filtering.

    Args:
        urls: JSON array of URLs to crawl
        query: Research query for BM25 filtering
        mode: "fit_markdown" (default), "clean_markdown", or "raw"
        max_pages: Maximum pages to crawl
    """
    url_list = json.loads(urls)[:max_pages]
    
    # Determine mode
    use_docker = CRAWL4AI_MODE == "docker" or (CRAWL4AI_MODE == "auto" and not CRAWL4AI_AVAILABLE)
    
    if use_docker:
        result = _crawl_with_docker(url_list, query, mode)
    else:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_crawl_direct_async(url_list, query, mode))
    
    return json.dumps(result)

@mcp.tool()
def crawl4ai_style_analysis(author_url: str, focus: str = "tone voice style") -> str:
    """Analyze an author's writing style from their website or blog.

    Args:
        author_url: URL of author's website
        focus: What aspects to analyze (default: "tone voice style")
    """
    return crawl4ai_research(json.dumps([author_url]), focus, "fit_markdown")

@mcp.tool()
def crawl4ai_fact_check(claim: str, sources: str) -> str:
    """Fact-check a claim against provided sources.

    Args:
        claim: The claim to verify
        sources: JSON array of source URLs
    """
    source_list = json.loads(sources)
    research = crawl4ai_research(json.dumps(source_list), claim, "fit_markdown")
    research_data = json.loads(research)

    return json.dumps({
        "claim": claim,
        "sources_crawled": len(source_list),
        "research_excerpts": research_data.get("markdown", "")[:3000],
        "verification_status": "manual_review_required"
    })

@mcp.tool()
def crawl4ai_market_research(genre: str, comp_titles: str = "") -> str:
    """Research genre trends and comparable titles.

    Args:
        genre: Genre to research (e.g., "cyberpunk", "romance")
        comp_titles: JSON array of comparable title names
    """
    # This would typically search Goodreads, Amazon, etc.
    # For now, returns a structured request for manual research
    titles = json.loads(comp_titles) if comp_titles else []
    return json.dumps({
        "genre": genre,
        "comp_titles": titles,
        "suggested_research_urls": [
            f"https://www.goodreads.com/search?q={genre}",
            f"https://www.amazon.com/s?k={genre}+books",
        ],
        "note": "Use crawl4ai_research with these URLs for actual data"
    })

@mcp.tool()
def crawl4ai_setting_research(setting_description: str, historical_era: str = "") -> str:
    """Research a story setting for historical/cultural accuracy.

    Args:
        setting_description: Description of the setting
        historical_era: Optional historical time period
    """
    query = f"{setting_description} {historical_era}".strip()
    # Would typically search Wikipedia, historical archives
    return json.dumps({
        "setting": setting_description,
        "era": historical_era,
        "suggested_sources": [
            f"https://en.wikipedia.org/wiki/Special:Search?search={query.replace(' ', '+')}",
        ],
        "note": "Use crawl4ai_research with these URLs"
    })

if __name__ == "__main__":
    mcp.run()
