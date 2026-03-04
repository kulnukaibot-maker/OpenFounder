"""Base crew class — shared LLM calling and prompt loading for all crews."""

import json
import logging
from pathlib import Path

import anthropic

from openfounder.config import config
from openfounder.state import get_venture

logger = logging.getLogger("openfounder.crew")

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


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

    def run(self, task: str, context: str = "") -> dict:
        """Run the crew on a specific task.

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

        logger.info("[%s] Running task: %s", self.crew_name, task[:80])

        response = client.messages.create(
            model=config.CREW_MODEL,
            max_tokens=config.CEO_MAX_TOKENS,
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

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error("[%s] Failed to parse output: %s", self.crew_name, e)
            raise ValueError(f"{self.crew_name} output is not valid JSON: {e}") from e

        result["_crew"] = self.crew_name
        result["_usage"] = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model": config.CREW_MODEL,
        }

        logger.info(
            "[%s] Complete: %d in / %d out tokens",
            self.crew_name, response.usage.input_tokens, response.usage.output_tokens,
        )

        return result


def run_crew(crew_name: str, venture_name: str, task: str, context: str = "") -> dict:
    """Run a crew by name. Convenience function for the CEO loop."""
    from openfounder.crews import CREWS

    crew_class = CREWS.get(crew_name)
    if not crew_class:
        raise ValueError(f"Unknown crew: {crew_name}. Available: {list(CREWS.keys())}")

    crew = crew_class(venture_name)
    return crew.run(task, context)
