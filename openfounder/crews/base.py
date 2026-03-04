"""Base crew class — shared LLM calling and prompt loading for all crews."""

import json
import logging
import time
from pathlib import Path

import anthropic

from openfounder.config import config
from openfounder.state import get_venture

logger = logging.getLogger("openfounder.crew")

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

CREW_MAX_RETRIES = 2
CREW_RETRY_DELAY = 3


def _extract_json(text: str) -> dict:
    """Extract the first JSON object from text, ignoring trailing commentary."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the first { and use a decoder to grab just that object
    start = text.find("{")
    if start == -1:
        raise json.JSONDecodeError("No JSON object found", text, 0)

    decoder = json.JSONDecoder()
    result, _ = decoder.raw_decode(text, start)
    return result


class BaseCrew:
    """Base class for all specialist crews."""

    crew_name: str = "base"
    prompt_file: str = ""  # e.g. "research_crew.md"

    def __init__(self, venture_name: str):
        self.venture_name = venture_name
        self.venture = get_venture(venture_name)
        if not self.venture:
            raise ValueError(f"Venture not found: {venture_name}")

    def _load_prompt(self) -> str:
        """Load and populate the crew system prompt."""
        template = (PROMPTS_DIR / self.prompt_file).read_text()
        template = template.replace("{{venture_name}}", self.venture["name"])
        return template

    def _get_model(self) -> str:
        """Return the model to use. Override in subclasses for per-crew models."""
        return config.CREW_MODEL

    def _get_max_tokens(self) -> int:
        """Return max tokens. Override in subclasses for per-crew limits."""
        return config.CREW_MAX_TOKENS

    def run(self, task: str, context: str = "") -> dict:
        """Run the crew on a specific task with retry on transient failures.

        Args:
            task: The task description from the CEO.
            context: Additional context the CEO provided.

        Returns:
            Parsed JSON output from the crew.
        """
        system_prompt = self._load_prompt()

        user_message = f"## Task\n{task}"
        if context:
            user_message += f"\n\n## Context\n{context}"

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

        last_error = None
        for attempt in range(CREW_MAX_RETRIES + 1):
            try:
                logger.info("[%s] Running task (attempt %d/%d): %s",
                            self.crew_name, attempt + 1, CREW_MAX_RETRIES + 1, task[:80])

                model = self._get_model()
                response = client.messages.create(
                    model=model,
                    max_tokens=self._get_max_tokens(),
                    temperature=config.CEO_TEMPERATURE,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )

                raw = response.content[0].text.strip()

                # Strip markdown fences if present
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1]
                if raw.endswith("```"):
                    raw = raw.rsplit("```", 1)[0]
                raw = raw.strip()

                # Extract first JSON object — LLMs often append commentary
                result = _extract_json(raw)

                result["_crew"] = self.crew_name
                result["_usage"] = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "model": model,
                }

                logger.info(
                    "[%s] Complete: %d in / %d out tokens",
                    self.crew_name, response.usage.input_tokens, response.usage.output_tokens,
                )

                return result

            except (anthropic.APIConnectionError, anthropic.RateLimitError,
                    anthropic.InternalServerError) as e:
                last_error = e
                if attempt < CREW_MAX_RETRIES:
                    delay = CREW_RETRY_DELAY * (2 ** attempt)
                    logger.warning("[%s] LLM call failed (attempt %d/%d): %s — retrying in %ds",
                                   self.crew_name, attempt + 1, CREW_MAX_RETRIES + 1, e, delay)
                    time.sleep(delay)

            except json.JSONDecodeError as e:
                last_error = e
                if attempt < CREW_MAX_RETRIES:
                    logger.warning("[%s] Invalid JSON (attempt %d/%d): %s — retrying",
                                   self.crew_name, attempt + 1, CREW_MAX_RETRIES + 1, e)
                    time.sleep(CREW_RETRY_DELAY)

            except anthropic.AuthenticationError:
                raise

        raise RuntimeError(
            f"[{self.crew_name}] Failed after {CREW_MAX_RETRIES + 1} attempts: {last_error}"
        )


def run_crew(crew_name: str, venture_name: str, task: str, context: str = "") -> dict:
    """Run a crew by name. Convenience function for the CEO loop."""
    from openfounder.crews import CREWS

    crew_class = CREWS.get(crew_name)
    if not crew_class:
        raise ValueError(f"Unknown crew: {crew_name}. Available: {list(CREWS.keys())}")

    crew = crew_class(venture_name)
    return crew.run(task, context)
