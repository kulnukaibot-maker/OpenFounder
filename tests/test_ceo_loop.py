"""Integration tests for the CEO Loop.

Uses mocked LLM responses to test the full pipeline:
state → prompt → (mock) LLM → process decisions → approvals → metrics → briefing.

Requires a running PostgreSQL database with the schema applied.
"""

import json
import os
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://openfounder:openfounder_dev@localhost:5433/openfounder",
)

from openfounder import state
from openfounder.ceo_loop import (
    _load_system_prompt,
    _needs_escalation,
    _process_decisions,
    _process_approvals,
    _process_metrics,
    _process_delegations,
    _build_briefing,
    run_ceo_loop,
)
from openfounder.config import config


# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_CEO_OUTPUT = {
    "summary": "MVP development on track. Prioritizing CEO loop and state manager.",
    "priorities": [
        {
            "title": "Complete CEO Loop implementation",
            "reasoning": "Core product feature, blocks everything else",
            "assigned_crew": "engineering",
            "urgency": "immediate",
        },
        {
            "title": "Write integration tests",
            "reasoning": "Need confidence before first real run",
            "assigned_crew": "engineering",
            "urgency": "today",
        },
    ],
    "decisions": [
        {
            "decision_type": "strategic",
            "title": "Focus on stability over features",
            "reasoning": "Too early for feature expansion, need solid foundation first",
            "outcome": "Freeze feature backlog until CEO loop is reliable",
            "confidence": 0.85,
        },
        {
            "decision_type": "feature",
            "title": "Add --dry-run flag to CEO loop",
            "reasoning": "Enables safe testing without DB side effects",
            "outcome": "Implemented in scripts/openfounder_ceo.py",
            "confidence": 0.95,
        },
    ],
    "delegations": [
        {
            "crew": "engineering",
            "task": "Add retry logic to LLM calls with exponential backoff",
            "context": "Current implementation has no retry on transient failures",
            "priority": "high",
        },
    ],
    "approvals_needed": [
        {
            "action_type": "post",
            "title": "Publish README to GitHub",
            "description": "Updated README with quick start guide and architecture diagram",
            "reasoning": "Need public docs before any external sharing",
        },
    ],
    "risks": [
        {
            "title": "No error handling on LLM JSON parse failures",
            "severity": "high",
            "mitigation": "Add try/catch with fallback to raw text logging",
        },
    ],
    "metrics_update": [
        {"name": "lines_of_code", "value": 2221, "unit": "count", "source": "calculated"},
    ],
    "morning_briefing": (
        "- **Status:** MVP Day 4 complete, core pipeline working end-to-end\n"
        "- **Focus today:** Integration tests and error handling\n"
        "- **Blocker:** None\n"
        "- **Decision:** Freezing feature backlog until CEO loop is stable\n"
        "- **Action needed:** Approve README publish to GitHub"
    ),
}


def _mock_anthropic_response(output_dict: dict):
    """Create a mock Anthropic API response."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(output_dict))]
    mock_response.usage.input_tokens = 1500
    mock_response.usage.output_tokens = 800
    return mock_response


@pytest.fixture(autouse=True)
def clean_db():
    """Clean all tables and create a test venture."""
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
    """Create a test venture with some initial data."""
    v = state.create_venture(
        "TestVenture",
        description="A test venture for integration tests",
        goal="Validate the CEO loop pipeline",
    )
    state.add_feature("TestVenture", "Feature A", priority="high")
    state.add_feature("TestVenture", "Feature B", priority="medium")
    state.add_bug("TestVenture", "Bug X", severity="critical")
    state.add_metric("TestVenture", "users", 0, unit="count")
    return v


# ── Prompt Tests ──────────────────────────────────────────────────────────────

class TestPromptLoading:
    def test_load_system_prompt(self, test_venture):
        venture_state = state.get_state("TestVenture")
        prompt = _load_system_prompt(venture_state, loop_number=1)

        assert "TestVenture" in prompt
        assert "A test venture for integration tests" in prompt
        assert "Validate the CEO loop pipeline" in prompt
        assert "Loop number:" in prompt

    def test_prompt_has_output_format(self, test_venture):
        venture_state = state.get_state("TestVenture")
        prompt = _load_system_prompt(venture_state)

        assert '"summary"' in prompt
        assert '"decisions"' in prompt
        assert '"delegations"' in prompt
        assert '"morning_briefing"' in prompt


# ── Escalation Tests ──────────────────────────────────────────────────────────

class TestEscalation:
    def test_no_escalation_high_confidence(self):
        output = {
            "decisions": [
                {"decision_type": "feature", "title": "X", "confidence": 0.9},
            ],
            "risks": [],
        }
        assert _needs_escalation(output) is None

    def test_escalate_to_sonnet_low_confidence(self):
        output = {
            "decisions": [
                {"decision_type": "feature", "title": "X", "confidence": 0.3},
            ],
            "risks": [],
        }
        result = _needs_escalation(output)
        assert result == config.ESCALATION_MODEL

    def test_escalate_to_opus_strategic_low_confidence(self):
        output = {
            "decisions": [
                {"decision_type": "strategic", "title": "Pivot", "confidence": 0.5},
            ],
            "risks": [],
        }
        result = _needs_escalation(output)
        assert result == config.MAX_MODEL

    def test_escalate_to_sonnet_critical_risk(self):
        output = {
            "decisions": [],
            "risks": [
                {"title": "Data loss possible", "severity": "critical"},
            ],
        }
        result = _needs_escalation(output)
        assert result == config.ESCALATION_MODEL

    def test_no_escalation_medium_risk(self):
        output = {
            "decisions": [],
            "risks": [
                {"title": "Minor delay", "severity": "medium"},
            ],
        }
        assert _needs_escalation(output) is None


# ── Processing Tests ──────────────────────────────────────────────────────────

class TestProcessing:
    def test_process_decisions(self, test_venture):
        recorded = _process_decisions("TestVenture", MOCK_CEO_OUTPUT)
        assert len(recorded) == 2
        assert recorded[0]["decision_type"] == "strategic"
        assert recorded[1]["decision_type"] == "feature"

        # Verify they're in the database
        decisions = state.list_decisions("TestVenture")
        assert len(decisions) == 2

    def test_process_approvals(self, test_venture):
        submitted = _process_approvals("TestVenture", MOCK_CEO_OUTPUT)
        assert len(submitted) == 1
        assert submitted[0]["action_type"] == "post"
        assert submitted[0]["status"] == "pending"

        # Verify in database
        pending = state.list_pending_approvals("TestVenture")
        assert len(pending) == 1

    def test_process_metrics(self, test_venture):
        recorded = _process_metrics("TestVenture", MOCK_CEO_OUTPUT)
        assert len(recorded) == 1
        assert recorded[0]["name"] == "lines_of_code"
        assert recorded[0]["value"] == 2221

    def test_process_empty_outputs(self, test_venture):
        empty = {"decisions": [], "approvals_needed": [], "metrics_update": []}
        assert _process_decisions("TestVenture", empty) == []
        assert _process_approvals("TestVenture", empty) == []
        assert _process_metrics("TestVenture", empty) == []


# ── Briefing Tests ────────────────────────────────────────────────────────────

class TestBriefing:
    def test_build_briefing_from_output(self):
        briefing = _build_briefing(MOCK_CEO_OUTPUT)
        assert "MVP Day 4" in briefing
        assert "Integration tests" in briefing

    def test_build_briefing_fallback(self):
        output = {
            "summary": "Things are going well",
            "priorities": [
                {"title": "Ship it", "urgency": "immediate", "assigned_crew": "engineering"},
            ],
        }
        briefing = _build_briefing(output)
        assert "Things are going well" in briefing
        assert "Ship it" in briefing

    def test_build_briefing_empty(self):
        briefing = _build_briefing({})
        assert briefing == "No briefing generated."


# ── Full Loop Tests ───────────────────────────────────────────────────────────

class TestFullLoop:
    @patch("openfounder.ceo_loop.anthropic.Anthropic")
    @patch("openfounder.ceo_loop.send_briefing_to_discord")
    @patch("openfounder.ceo_loop.DiscordApprovalNotifier")
    @patch("openfounder.ceo_loop.run_crew")
    def test_full_loop_dry_run(self, mock_run_crew, mock_notifier, mock_briefing,
                                mock_anthropic_cls, test_venture):
        """Dry run: calls LLM but doesn't write to DB or send notifications."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_CEO_OUTPUT)

        result = run_ceo_loop("TestVenture", dry_run=True)

        assert result["dry_run"] is True
        assert result["venture"] == "TestVenture"
        assert result["decisions_recorded"] == 0
        assert result["approvals_submitted"] == 0
        assert result["metrics_recorded"] == 0
        assert "MVP Day 4" in result["briefing"]

        # LLM was called
        mock_client.messages.create.assert_called_once()

        # DB was NOT written to
        assert state.list_decisions("TestVenture") == []

        # Discord was NOT notified
        mock_briefing.assert_not_called()

    @patch("openfounder.ceo_loop.anthropic.Anthropic")
    @patch("openfounder.ceo_loop.send_briefing_to_discord")
    @patch("openfounder.ceo_loop.DiscordApprovalNotifier")
    @patch("openfounder.ceo_loop.run_crew")
    def test_full_loop_live(self, mock_run_crew, mock_notifier_cls, mock_briefing,
                             mock_anthropic_cls, test_venture):
        """Live run: writes decisions, submits approvals, sends notifications."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_CEO_OUTPUT)

        mock_run_crew.return_value = {"_crew": "engineering", "summary": "Done"}

        result = run_ceo_loop("TestVenture", dry_run=False)

        assert result["dry_run"] is False
        assert result["decisions_recorded"] == 2
        assert result["approvals_submitted"] == 1
        assert result["metrics_recorded"] == 1
        assert result["delegations_run"] == 1

        # Verify DB state
        decisions = state.list_decisions("TestVenture")
        assert len(decisions) == 2

        pending = state.list_pending_approvals("TestVenture")
        assert len(pending) == 1

        # Verify crew was called
        mock_run_crew.assert_called_once_with(
            "engineering", "TestVenture",
            "Add retry logic to LLM calls with exponential backoff",
            "Current implementation has no retry on transient failures",
        )

        # Verify Discord was notified
        mock_briefing.assert_called_once()

    @patch("openfounder.ceo_loop.anthropic.Anthropic")
    @patch("openfounder.ceo_loop.send_briefing_to_discord")
    @patch("openfounder.ceo_loop.DiscordApprovalNotifier")
    @patch("openfounder.ceo_loop.run_crew")
    def test_full_loop_with_escalation(self, mock_run_crew, mock_notifier_cls,
                                        mock_briefing, mock_anthropic_cls, test_venture):
        """Test that low-confidence output triggers escalation."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # First call returns low-confidence strategic decision → triggers Opus escalation
        low_confidence_output = dict(MOCK_CEO_OUTPUT)
        low_confidence_output["decisions"] = [
            {
                "decision_type": "strategic",
                "title": "Maybe pivot?",
                "reasoning": "Not sure about this",
                "outcome": "Possibly change direction",
                "confidence": 0.3,
            },
        ]

        mock_client.messages.create.side_effect = [
            _mock_anthropic_response(low_confidence_output),
            _mock_anthropic_response(MOCK_CEO_OUTPUT),  # escalated response
        ]

        result = run_ceo_loop("TestVenture", dry_run=True)

        # LLM should have been called twice (initial + escalation)
        assert mock_client.messages.create.call_count == 2

        # Second call should use MAX_MODEL
        second_call = mock_client.messages.create.call_args_list[1]
        assert second_call.kwargs.get("model") == config.MAX_MODEL or \
               second_call[1].get("model") == config.MAX_MODEL

    @patch("openfounder.ceo_loop.anthropic.Anthropic")
    @patch("openfounder.ceo_loop.send_briefing_to_discord")
    @patch("openfounder.ceo_loop.DiscordApprovalNotifier")
    @patch("openfounder.ceo_loop.run_crew")
    def test_full_loop_venture_not_found(self, mock_run_crew, mock_notifier,
                                          mock_briefing, mock_anthropic_cls):
        """Should raise ValueError for unknown venture."""
        with pytest.raises(ValueError, match="not found"):
            run_ceo_loop("NonExistent")

    @patch("openfounder.ceo_loop.anthropic.Anthropic")
    @patch("openfounder.ceo_loop.send_briefing_to_discord")
    @patch("openfounder.ceo_loop.DiscordApprovalNotifier")
    @patch("openfounder.ceo_loop.run_crew")
    def test_output_is_json_serializable(self, mock_run_crew, mock_notifier,
                                          mock_briefing, mock_anthropic_cls, test_venture):
        """Full loop result must be JSON-serializable (for logging/storage)."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_anthropic_response(MOCK_CEO_OUTPUT)

        result = run_ceo_loop("TestVenture", dry_run=True)
        serialized = json.dumps(result, default=str)
        assert len(serialized) > 100
