import os
from pathlib import Path
from typing import Optional

from chainlit.logger import logger

from ._utils import is_path_inside

# Default chainlit.md file created if none exists
DEFAULT_MARKDOWN_STR = """# Welcome to Fujifilm MCP Chatbot! 

FujiFilm Business Innovation has a long-standing history in imaging and information technology with continuous innovation. The Hong Kong branch is committed to providing leading business solutions for local enterprises.

## 🔧 Model Context Protocol (MCP)

- MCP = a standard for LLMs to use external tools and context.

- Allows models to dynamically call tools (e.g. web search, APIs, 3D engines).

- Enables multi-step, tool-augmented reasoning.

- Makes LLMs more interactive, powerful, and autonomous.

## 🤖 A2A (Agent-to-Agent)

- A design pattern where multiple specialized agents collaborate.

- Each agent handles a distinct capability or domain (e.g., web search, database access, MCP tools).

- Agents communicate with each other via messages or task passing.

- Enables scalable, multi-step reasoning by delegating subtasks.
"""


def init_markdown(root: str):
    """Initialize the chainlit.md file if it doesn't exist."""
    chainlit_md_file = os.path.join(root, "chainlit.md")

    if not os.path.exists(chainlit_md_file):
        with open(chainlit_md_file, "w", encoding="utf-8") as f:
            f.write(DEFAULT_MARKDOWN_STR)
            logger.info(f"Created default chainlit markdown file at {chainlit_md_file}")


def get_markdown_str(root: str, language: str) -> Optional[str]:
    """Get the chainlit.md file as a string."""
    root_path = Path(root)
    translated_chainlit_md_path = root_path / f"chainlit_{language}.md"
    default_chainlit_md_path = root_path / "chainlit.md"

    if (
        is_path_inside(translated_chainlit_md_path, root_path)
        and translated_chainlit_md_path.is_file()
    ):
        chainlit_md_path = translated_chainlit_md_path
    else:
        chainlit_md_path = default_chainlit_md_path
        logger.warning(
            f"Translated markdown file for {language} not found. Defaulting to chainlit.md."
        )

    if chainlit_md_path.is_file():
        return chainlit_md_path.read_text(encoding="utf-8")
    else:
        return None
