"""Marketing crew — content creation, campaigns, and audience strategy."""

import logging

from openfounder.config import config
from openfounder.crews.base import BaseCrew
from openfounder.state import add_content, list_content, submit_approval

logger = logging.getLogger("openfounder.crew")


class MarketingCrew(BaseCrew):
    crew_name = "marketing"
    prompt_file = "marketing_crew.md"

    def _get_model(self) -> str:
        return config.MARKETING_MODEL

    def _get_max_tokens(self) -> int:
        return config.MARKETING_MAX_TOKENS

    def _load_prompt(self) -> str:
        """Override to inject venture context and content calendar."""
        template = super()._load_prompt()

        # Inject venture details
        v = self.venture
        template = template.replace("{{venture_description}}", v.get("description") or "No description")
        template = template.replace("{{venture_goal}}", v.get("goal") or "No goal set")
        template = template.replace("{{venture_stage}}", v.get("stage", "idea"))

        # Inject recent content calendar
        try:
            recent = list_content(self.venture_name, days=14)
            if recent:
                calendar_lines = []
                for c in recent[:20]:
                    calendar_lines.append(
                        f"[{c.get('status', '?')}] {c.get('channel', '?')}: {c.get('title', '?')}"
                    )
                template = template.replace("{{content_calendar}}", "\n".join(calendar_lines))
            else:
                template = template.replace("{{content_calendar}}", "(no content yet)")
        except Exception:
            template = template.replace("{{content_calendar}}", "(unable to load)")

        return template

    def run(self, task: str, context: str = "") -> dict:
        """Run marketing crew and persist content pieces to calendar."""
        result = super().run(task, context)

        # Persist content pieces to content_calendar table
        content_pieces = result.get("content_pieces", [])
        saved_content = []
        for piece in content_pieces:
            try:
                saved = add_content(
                    venture=self.venture_name,
                    channel=piece.get("channel", "unknown"),
                    title=piece.get("title", "Untitled"),
                    body=piece.get("body", ""),
                    cta=piece.get("cta"),
                    status="pending_approval" if piece.get("requires_approval") else "draft",
                    scheduled_for=piece.get("scheduled_for"),
                    metadata={
                        "hashtags": piece.get("hashtags", []),
                        "strategy": result.get("strategy", {}),
                    },
                )
                saved_content.append(saved)
                logger.info("[marketing] Content saved: [%s] %s",
                            piece.get("channel"), piece.get("title", "?")[:50])

                # Submit approval request if needed
                if piece.get("requires_approval"):
                    try:
                        submit_approval(
                            venture=self.venture_name,
                            action_type="post",
                            title=f"Publish: {piece.get('title', 'Untitled')[:60]}",
                            description=f"Channel: {piece.get('channel')}\n\n{piece.get('body', '')[:500]}",
                            requested_by="marketing_crew",
                            metadata={"content_id": saved.get("id"), "channel": piece.get("channel")},
                        )
                    except Exception as e:
                        logger.error("[marketing] Failed to submit approval: %s", e)

            except Exception as e:
                logger.error("[marketing] Failed to save content piece '%s': %s",
                             piece.get("title", "?"), e)

        result["_content_saved"] = len(saved_content)
        result["_content_ids"] = [c.get("id") for c in saved_content]

        return result
