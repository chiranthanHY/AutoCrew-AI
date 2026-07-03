"""
tools/__init__.py — AutoCrew AI tools package.

Exports:
    TavilySearchTool   — Web search via Tavily API
    save_markdown      — Save content as a Markdown file
    save_text          — Save content as a plain-text file
    save_pdf           — Save content as a PDF (requires weasyprint)
    save_output        — Convenience dispatcher for all export formats
"""

from app.tools.file_tools import save_markdown, save_output, save_pdf, save_text
from app.tools.tavily import TavilySearchTool

__all__ = [
    "TavilySearchTool",
    "save_markdown",
    "save_text",
    "save_pdf",
    "save_output",
]
