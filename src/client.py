"""Anthropic API client abstraction."""
import asyncio
import json
import os
from anthropic import AsyncAnthropic
from dotenv import load_dotenv


load_dotenv()
API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not API_KEY:
    raise ValueError("ANTHROPIC_API_KEY environment variable is required")


class APIClient:
    """Wrapper around Anthropic API with retry and timeout handling."""

    def __init__(self, model: str = "claude-haiku-4-5", max_retries: int = 3):
        self.client = AsyncAnthropic(api_key=API_KEY)
        self.model = model
        self.max_retries = max_retries

    async def call(
        self,
        prompt: str,
        max_tokens: int = 1024,
        timeout: float = 60.0,
        semaphore: asyncio.Semaphore | None = None
    ) -> str:
        """Call the API with automatic retry and timeout handling."""
        for attempt in range(self.max_retries):
            try:
                if semaphore:
                    async with semaphore:
                        response = await asyncio.wait_for(
                            self.client.messages.create(
                                model=self.model,
                                max_tokens=max_tokens,
                                messages=[{"role": "user", "content": prompt}]
                            ),
                            timeout=timeout
                        )
                else:
                    response = await asyncio.wait_for(
                        self.client.messages.create(
                            model=self.model,
                            max_tokens=max_tokens,
                            messages=[{"role": "user", "content": prompt}]
                        ),
                        timeout=timeout
                    )

                return response.content[0].text.strip()

            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise
            except Exception:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise


def parse_json(content: str) -> dict:
    """Parse JSON from LLM response, handling code blocks and malformed JSON."""
    content = content.strip()

    # Extract from code block if present
    if content.startswith("```"):
        parts = content.split("```")
        if len(parts) >= 2:
            content = parts[1]
            if content.startswith(("json", "JSON")):
                content = content[4:]
            content = content.strip()

    # Try parsing as-is first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try truncating at last closing brace/bracket
    last_brace = content.rfind('}')
    last_bracket = content.rfind(']')
    last_close = max(last_brace, last_bracket)

    if last_close > 0:
        truncated = content[:last_close + 1]
        try:
            return json.loads(truncated)
        except json.JSONDecodeError:
            pass

    # Try counting braces to find structure boundaries
    open_braces = 0
    open_brackets = 0
    in_string = False
    escape_next = False

    for i, char in enumerate(content):
        if escape_next:
            escape_next = False
            continue

        if char == '\\' and in_string:
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if not in_string:
            if char == '{':
                open_braces += 1
            elif char == '}':
                open_braces -= 1
            elif char == '[':
                open_brackets += 1
            elif char == ']':
                open_brackets -= 1

            if open_braces == 0 and open_brackets == 0 and char in ('}', ']'):
                truncated = content[:i + 1]
                try:
                    return json.loads(truncated)
                except json.JSONDecodeError:
                    pass

    raise json.JSONDecodeError(
        f"Could not parse JSON. Last 500 chars: {content[-500:]}",
        content,
        len(content) - 1
    )
