"""
file_tools.py — File Export Tools for AutoCrew AI
---------------------------------------------------
Utilities for saving agent outputs to Markdown, text, and PDF files.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default output directory (relative to project root)
DEFAULT_OUTPUT_DIR = Path("outputs")


def _ensure_dir(directory: Path) -> None:
    """Create the output directory if it does not exist."""
    directory.mkdir(parents=True, exist_ok=True)


def _timestamped_filename(prefix: str, extension: str) -> str:
    """Generate a filename with an ISO timestamp."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.{extension}"


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def save_markdown(
    content: str,
    filename: Optional[str] = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """
    Save content to a Markdown file.

    Args:
        content (str): The Markdown content to write.
        filename (str, optional): Custom filename. Auto-generated if not provided.
        output_dir (Path): Directory to write the file to.

    Returns:
        Path: Absolute path of the saved file.
    """
    _ensure_dir(output_dir)
    filename = filename or _timestamped_filename("output", "md")
    filepath = output_dir / filename

    filepath.write_text(content, encoding="utf-8")
    logger.info("[file_tools] Saved Markdown → %s", filepath.resolve())
    return filepath.resolve()


# ---------------------------------------------------------------------------
# Plain Text
# ---------------------------------------------------------------------------


def save_text(
    content: str,
    filename: Optional[str] = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """
    Save content to a plain-text (.txt) file.

    Args:
        content (str): The text content to write.
        filename (str, optional): Custom filename. Auto-generated if not provided.
        output_dir (Path): Directory to write the file to.

    Returns:
        Path: Absolute path of the saved file.
    """
    _ensure_dir(output_dir)
    filename = filename or _timestamped_filename("output", "txt")
    filepath = output_dir / filename

    filepath.write_text(content, encoding="utf-8")
    logger.info("[file_tools] Saved text → %s", filepath.resolve())
    return filepath.resolve()


# ---------------------------------------------------------------------------
# PDF (requires weasyprint or fpdf2 — optional dependency)
# ---------------------------------------------------------------------------


def save_pdf(
    content: str,
    filename: Optional[str] = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """
    Save content to a PDF file. Converts Markdown to HTML first, then to PDF.

    Requires:
        pip install markdown weasyprint

    Args:
        content (str): Markdown content to convert and save as PDF.
        filename (str, optional): Custom filename. Auto-generated if not provided.
        output_dir (Path): Directory to write the file to.

    Returns:
        Path: Absolute path of the saved PDF file.

    Raises:
        ImportError: If ``markdown`` or ``weasyprint`` are not installed.
        RuntimeError: If PDF conversion fails.
    """
    try:
        import markdown as md_lib
        from weasyprint import HTML
    except ImportError as exc:
        raise ImportError(
            "PDF export requires 'markdown' and 'weasyprint'. "
            "Install them with: pip install markdown weasyprint"
        ) from exc

    _ensure_dir(output_dir)
    filename = filename or _timestamped_filename("output", "pdf")
    filepath = output_dir / filename

    # Convert Markdown → HTML → PDF
    html_content = md_lib.markdown(content, extensions=["tables", "fenced_code"])
    styled_html = f"""
    <html><head><style>
      body {{ font-family: Arial, sans-serif; margin: 2cm; line-height: 1.6; }}
      h1, h2, h3 {{ color: #2c3e50; }} table {{ border-collapse: collapse; width: 100%; }}
      th, td {{ border: 1px solid #ddd; padding: 8px; }} th {{ background: #f2f2f2; }}
      code {{ background: #f4f4f4; padding: 2px 4px; border-radius: 3px; }}
    </style></head><body>{html_content}</body></html>
    """

    try:
        HTML(string=styled_html).write_pdf(str(filepath))
        logger.info("[file_tools] Saved PDF → %s", filepath.resolve())
    except Exception as exc:
        raise RuntimeError(f"PDF generation failed: {exc}") from exc

    return filepath.resolve()


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------


def save_output(
    content: str,
    format: str = "markdown",
    filename: Optional[str] = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """
    Save agent output in the requested format.

    Args:
        content (str): Content to save.
        format (str): One of "markdown", "text", or "pdf".
        filename (str, optional): Custom filename.
        output_dir (Path): Target directory.

    Returns:
        Path: Path to the saved file.

    Raises:
        ValueError: If an unsupported format is requested.
    """
    fmt = format.lower()
    if fmt in ("markdown", "md"):
        return save_markdown(content, filename, output_dir)
    elif fmt in ("text", "txt"):
        return save_text(content, filename, output_dir)
    elif fmt == "pdf":
        return save_pdf(content, filename, output_dir)
    else:
        raise ValueError(f"Unsupported format '{format}'. Use: markdown, text, or pdf.")
