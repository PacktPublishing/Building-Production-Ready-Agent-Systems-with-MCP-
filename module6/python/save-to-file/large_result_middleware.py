"""Save-to-File Middleware — Module 6.

When an MCP tool returns a result larger than a configurable threshold,
this middleware saves the full output to a file and replaces it with a
compact summary + file reference. The agent can then selectively read
from the file if it needs more detail.

Why this matters:
- Tool results are included in the model's context on every subsequent turn
- A 10K-token tool result in a 5-turn conversation costs 50K input tokens
- Saving to file and returning a 200-token summary saves ~49K tokens/turn

This is an emerging pattern that's especially valuable with MCP servers
that return large payloads (full API responses, log dumps, search results).

Usage:
    from large_result_middleware import LargeResultSaverMiddleware

    agent = Agent(
        client=client,
        tools=mcp_tool,
        middleware=[LargeResultSaverMiddleware(token_threshold=500)],
    )
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Awaitable, Callable

from agent_framework import Content, FunctionMiddleware, FunctionInvocationContext

logger = logging.getLogger(__name__)

# ~4 chars per token — rough but useful for threshold checks
CHARS_PER_TOKEN = 4


class LargeResultSaverMiddleware(FunctionMiddleware):
    """Intercept large tool results and save them to files.

    When a tool returns text content exceeding ``token_threshold`` estimated
    tokens, the full result is written to ``output_dir`` and the context
    receives a compact summary instead.

    The summary includes:
    - File path for the full result
    - Result size in characters and estimated tokens
    - A preview of the first ``preview_chars`` characters

    The agent can then use a file-reading tool to access specific parts
    of the result if needed, rather than carrying the entire payload
    through every subsequent turn.
    """

    def __init__(
        self,
        token_threshold: int = 500,
        output_dir: str | None = None,
        preview_chars: int = 300,
    ):
        self.token_threshold = token_threshold
        self.output_dir = Path(output_dir or os.path.join(os.getcwd(), ".tool_results"))
        self.preview_chars = preview_chars
        self._files_saved = 0

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        # Execute the tool
        await call_next()

        # Inspect the result
        result = context.result
        if not isinstance(result, list):
            return

        modified = []
        for item in result:
            if item.type == "text" and item.text:
                estimated_tokens = len(item.text) // CHARS_PER_TOKEN

                if estimated_tokens > self.token_threshold:
                    # Save to file
                    self.output_dir.mkdir(parents=True, exist_ok=True)
                    content_hash = hashlib.sha256(item.text.encode()).hexdigest()[:12]
                    filename = f"{context.function.name}_{content_hash}.txt"
                    filepath = self.output_dir / filename

                    filepath.write_text(item.text, encoding="utf-8")
                    self._files_saved += 1

                    logger.info(
                        "Tool '%s' result saved to %s (%d chars, ~%d tokens)",
                        context.function.name,
                        filepath,
                        len(item.text),
                        estimated_tokens,
                    )

                    # Replace with summary
                    preview = item.text[: self.preview_chars]
                    if len(item.text) > self.preview_chars:
                        preview += "..."

                    summary = (
                        f"[Large result saved to file]\n"
                        f"File: {filepath}\n"
                        f"Size: {len(item.text):,} chars (~{estimated_tokens:,} tokens)\n"
                        f"Tool: {context.function.name}\n"
                        f"\n"
                        f"Preview:\n{preview}"
                    )
                    modified.append(Content.from_text(summary))
                else:
                    modified.append(item)
            else:
                modified.append(item)

        context.result = modified

    @property
    def files_saved(self) -> int:
        return self._files_saved
