"""Tests for the approval system and Discord notification formatting."""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://openfounder:openfounder_dev@localhost:5433/openfounder",
)

from openfounder import state
from openfounder.approval import DiscordApprovalNotifier, send_briefing_to_discord


@pytest.fixture(autouse=True)
def clean_db():
    with state.get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM approvals")
        cur.execute("DELETE FROM campaigns")
        cur.execute("DELETE FROM metrics")
        cur.execute("DELETE FROM decisions")
        cur.execute("DELETE FROM bugs")
        cur.execute("DELETE FROM features")
        cur.execute("DELETE FROM ventures")
    yield


@pytest.fixture
def test_venture():
    return state.create_venture("ApprovalCo", description="Test approvals")


class TestDiscordFormatting:
    def test_format_approval_post(self, test_venture):
        approval = state.submit_approval(
            "ApprovalCo", "post", "Tweet launch",
            "Post launch announcement on Twitter",
            metadata={"reasoning": "Need visibility"},
        )
        notifier = DiscordApprovalNotifier(webhook_url="https://example.com/webhook")
        embed = notifier._format_approval(approval)

        assert embed["title"] == "Approval Needed: Tweet launch"
        assert embed["color"] == 0x3498DB  # blue for "post"
        assert any(f["value"] == "post" for f in embed["fields"])
        assert any(f["name"] == "Approval ID" for f in embed["fields"])

    def test_format_approval_spend(self, test_venture):
        approval = state.submit_approval(
            "ApprovalCo", "spend", "Buy ads",
            "$500 on Google Ads",
        )
        notifier = DiscordApprovalNotifier(webhook_url="https://example.com/webhook")
        embed = notifier._format_approval(approval)

        assert embed["color"] == 0xE74C3C  # red for "spend"

    def test_format_approval_with_reasoning(self, test_venture):
        approval = state.submit_approval(
            "ApprovalCo", "deploy", "Ship v1",
            "Deploy to production",
            metadata={"reasoning": "All tests pass, ready for launch"},
        )
        notifier = DiscordApprovalNotifier(webhook_url="https://example.com/webhook")
        embed = notifier._format_approval(approval)

        reasoning_fields = [f for f in embed["fields"] if f["name"] == "Reasoning"]
        assert len(reasoning_fields) == 1
        assert "All tests pass" in reasoning_fields[0]["value"]


class TestDiscordNotifications:
    @patch("openfounder.approval.httpx.post")
    def test_send_approval_notification(self, mock_post, test_venture):
        mock_post.return_value = MagicMock(status_code=204)
        mock_post.return_value.raise_for_status = MagicMock()

        approval = state.submit_approval(
            "ApprovalCo", "post", "Test post", "Test description",
        )
        notifier = DiscordApprovalNotifier(webhook_url="https://example.com/webhook")
        result = notifier.send_approval_notification(approval)

        assert result is True
        mock_post.assert_called_once()

        # Verify payload structure
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "embeds" in payload
        assert len(payload["embeds"]) == 1

    def test_send_notification_no_webhook(self, test_venture):
        approval = state.submit_approval(
            "ApprovalCo", "post", "Test", "Test",
        )
        notifier = DiscordApprovalNotifier(webhook_url="")
        result = notifier.send_approval_notification(approval)
        assert result is False

    @patch("openfounder.approval.httpx.post")
    def test_send_pending_summary(self, mock_post, test_venture):
        mock_post.return_value = MagicMock(status_code=204)
        mock_post.return_value.raise_for_status = MagicMock()

        state.submit_approval("ApprovalCo", "post", "P1", "D1")
        state.submit_approval("ApprovalCo", "send", "P2", "D2")

        notifier = DiscordApprovalNotifier(webhook_url="https://example.com/webhook")
        result = notifier.send_pending_summary("ApprovalCo")

        assert result is True
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert "2 pending" in payload["content"]
        assert len(payload["embeds"]) == 2

    @patch("openfounder.approval.httpx.post")
    def test_send_pending_summary_none_pending(self, mock_post, test_venture):
        notifier = DiscordApprovalNotifier(webhook_url="https://example.com/webhook")
        result = notifier.send_pending_summary("ApprovalCo")
        assert result is True
        mock_post.assert_not_called()


class TestBriefingNotification:
    @patch("openfounder.approval.httpx.post")
    def test_send_briefing(self, mock_post):
        mock_post.return_value = MagicMock(status_code=204)
        mock_post.return_value.raise_for_status = MagicMock()

        result = send_briefing_to_discord(
            "TestCo",
            "- Status: All good\n- Focus: Ship it",
            webhook_url="https://example.com/webhook",
        )

        assert result is True
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["embeds"][0]["title"] == "Morning Briefing — TestCo"
        assert "All good" in payload["embeds"][0]["description"]

    def test_send_briefing_no_webhook(self):
        result = send_briefing_to_discord("TestCo", "Briefing text", webhook_url="")
        assert result is False
