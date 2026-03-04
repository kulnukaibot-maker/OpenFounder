"""Approval system — human-in-the-loop via Discord.

Sends approval requests to Discord and processes responses.
Phase 1: Discord notifications with reaction-based approve/reject.
Phase 2: Dashboard UI with full approval workflow.
"""

import json
import logging
from datetime import datetime, timezone

import httpx

from openfounder.config import config
from openfounder.state import (
    list_pending_approvals,
    resolve_approval,
    submit_approval,
)

logger = logging.getLogger("openfounder.approval")


class DiscordApprovalNotifier:
    """Send approval notifications to Discord via webhook."""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or config.DISCORD_WEBHOOK_URL

    def _format_approval(self, approval: dict) -> dict:
        """Format an approval as a Discord embed."""
        color_map = {
            "post": 0x3498DB,    # blue
            "send": 0x2ECC71,    # green
            "spend": 0xE74C3C,   # red
            "deploy": 0xF39C12,  # orange
            "delete": 0x992D22,  # dark red
        }
        color = color_map.get(approval.get("action_type"), 0x95A5A6)

        embed = {
            "title": f"Approval Needed: {approval['title']}",
            "description": approval.get("description", ""),
            "color": color,
            "fields": [
                {"name": "Action Type", "value": approval.get("action_type", "?"), "inline": True},
                {"name": "Requested By", "value": approval.get("requested_by", "?"), "inline": True},
                {"name": "Approval ID", "value": str(approval.get("id", "?")), "inline": True},
            ],
            "footer": {"text": "Reply: !approve <id> or !reject <id>"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Add reasoning from metadata if present
        meta = approval.get("metadata", {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        if meta.get("reasoning"):
            embed["fields"].append({
                "name": "Reasoning",
                "value": meta["reasoning"][:1024],
                "inline": False,
            })

        return embed

    def send_approval_notification(self, approval: dict) -> bool:
        """Send a single approval notification to Discord."""
        if not self.webhook_url:
            logger.warning("No Discord webhook configured — skipping notification")
            return False

        embed = self._format_approval(approval)
        payload = {
            "embeds": [embed],
            "content": "New approval request from the CEO Loop:",
        }

        try:
            resp = httpx.post(self.webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info("Discord notification sent for approval #%s", approval.get("id"))
            return True
        except httpx.HTTPError as e:
            logger.error("Failed to send Discord notification: %s", e)
            return False

    def send_pending_summary(self, venture_name: str) -> bool:
        """Send a summary of all pending approvals."""
        pending = list_pending_approvals(venture_name)
        if not pending:
            logger.info("No pending approvals for %s", venture_name)
            return True

        embeds = [self._format_approval(a) for a in pending[:10]]  # Discord max 10 embeds
        payload = {
            "content": f"**{len(pending)} pending approval(s)** for {venture_name}:",
            "embeds": embeds,
        }

        if not self.webhook_url:
            logger.warning("No Discord webhook configured — skipping notification")
            return False

        try:
            resp = httpx.post(self.webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error("Failed to send pending summary: %s", e)
            return False


def send_briefing_to_discord(venture_name: str, briefing: str, webhook_url: str = None) -> bool:
    """Send the morning briefing to Discord."""
    url = webhook_url or config.DISCORD_WEBHOOK_URL
    if not url:
        logger.warning("No Discord webhook configured — skipping briefing")
        return False

    payload = {
        "embeds": [{
            "title": f"Morning Briefing — {venture_name}",
            "description": briefing[:4096],  # Discord embed limit
            "color": 0x5865F2,  # Discord blurple
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }],
    }

    try:
        resp = httpx.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Morning briefing sent to Discord for %s", venture_name)
        return True
    except httpx.HTTPError as e:
        logger.error("Failed to send briefing: %s", e)
        return False
