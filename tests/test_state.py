"""Tests for OpenFounder State Manager.

Requires a running PostgreSQL database with the schema applied.
Set DATABASE_URL env var or use defaults (localhost:5433).
"""

import json
import os
import pytest

# Point at test database if not already set
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://openfounder:openfounder_dev@localhost:5433/openfounder",
)

from openfounder import state


@pytest.fixture(autouse=True)
def clean_db():
    """Clean all tables before each test."""
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


# ── Ventures ──────────────────────────────────────────────────────────────────

class TestVentures:
    def test_create_venture(self):
        v = state.create_venture("TestCo", description="A test company", goal="Ship MVP")
        assert v["name"] == "TestCo"
        assert v["description"] == "A test company"
        assert v["goal"] == "Ship MVP"
        assert v["stage"] == "idea"
        assert v["status"] == "active"
        assert v["id"] is not None

    def test_create_venture_duplicate_name(self):
        state.create_venture("UniqueCo")
        with pytest.raises(Exception):
            state.create_venture("UniqueCo")

    def test_get_venture_by_name(self):
        state.create_venture("FindMe")
        v = state.get_venture("FindMe")
        assert v is not None
        assert v["name"] == "FindMe"

    def test_get_venture_by_id(self):
        created = state.create_venture("ByID")
        v = state.get_venture(str(created["id"]))
        assert v["name"] == "ByID"

    def test_get_venture_not_found(self):
        v = state.get_venture("DoesNotExist")
        assert v is None

    def test_list_ventures(self):
        state.create_venture("V1")
        state.create_venture("V2")
        vs = state.list_ventures()
        assert len(vs) == 2

    def test_list_ventures_empty(self):
        vs = state.list_ventures()
        assert vs == []


# ── Features ──────────────────────────────────────────────────────────────────

class TestFeatures:
    def test_add_feature(self):
        state.create_venture("FCo")
        f = state.add_feature("FCo", "Login page", description="OAuth login", priority="high")
        assert f["title"] == "Login page"
        assert f["priority"] == "high"
        assert f["status"] == "backlog"

    def test_list_features(self):
        state.create_venture("FCo2")
        state.add_feature("FCo2", "Feature A")
        state.add_feature("FCo2", "Feature B")
        fs = state.list_features("FCo2")
        assert len(fs) == 2

    def test_list_features_by_status(self):
        state.create_venture("FCo3")
        state.add_feature("FCo3", "F1")
        f2 = state.add_feature("FCo3", "F2")
        state.update_feature(f2["id"], status="in_progress")
        assert len(state.list_features("FCo3", status="backlog")) == 1
        assert len(state.list_features("FCo3", status="in_progress")) == 1

    def test_update_feature(self):
        state.create_venture("FCo4")
        f = state.add_feature("FCo4", "Old Title")
        updated = state.update_feature(f["id"], title="New Title", status="done")
        assert updated["title"] == "New Title"
        assert updated["status"] == "done"


# ── Bugs ──────────────────────────────────────────────────────────────────────

class TestBugs:
    def test_add_bug(self):
        state.create_venture("BCo")
        b = state.add_bug("BCo", "Crash on login", severity="critical")
        assert b["title"] == "Crash on login"
        assert b["severity"] == "critical"
        assert b["status"] == "open"

    def test_list_bugs(self):
        state.create_venture("BCo2")
        state.add_bug("BCo2", "Bug 1")
        state.add_bug("BCo2", "Bug 2")
        bs = state.list_bugs("BCo2")
        assert len(bs) == 2

    def test_update_bug(self):
        state.create_venture("BCo3")
        b = state.add_bug("BCo3", "Flaky test")
        updated = state.update_bug(b["id"], status="resolved")
        assert updated["status"] == "resolved"


# ── Decisions ─────────────────────────────────────────────────────────────────

class TestDecisions:
    def test_add_decision(self):
        state.create_venture("DCo")
        d = state.add_decision(
            "DCo", "strategic", "Pivot to B2B",
            reasoning="B2C CAC too high, B2B has 3x LTV",
            outcome="Focus on enterprise features",
            confidence=0.8,
        )
        assert d["decision_type"] == "strategic"
        assert d["title"] == "Pivot to B2B"
        assert d["reasoning"] == "B2C CAC too high, B2B has 3x LTV"
        assert d["confidence"] == 0.8
        assert d["source"] == "ceo"

    def test_list_decisions(self):
        state.create_venture("DCo2")
        state.add_decision("DCo2", "feature", "Add auth", "Security requirement")
        state.add_decision("DCo2", "bug", "Fix crash", "Users affected")
        ds = state.list_decisions("DCo2")
        assert len(ds) == 2

    def test_list_decisions_by_type(self):
        state.create_venture("DCo3")
        state.add_decision("DCo3", "feature", "F1", "R1")
        state.add_decision("DCo3", "strategic", "S1", "R2")
        ds = state.list_decisions("DCo3", decision_type="strategic")
        assert len(ds) == 1
        assert ds[0]["decision_type"] == "strategic"


# ── Metrics ───────────────────────────────────────────────────────────────────

class TestMetrics:
    def test_add_metric(self):
        state.create_venture("MCo")
        m = state.add_metric("MCo", "users", 100, unit="count", source="manual")
        assert m["name"] == "users"
        assert m["value"] == 100
        assert m["unit"] == "count"

    def test_get_latest_metrics(self):
        state.create_venture("MCo2")
        state.add_metric("MCo2", "revenue", 1000)
        state.add_metric("MCo2", "revenue", 1500)  # newer value
        state.add_metric("MCo2", "users", 50)
        ms = state.get_latest_metrics("MCo2")
        assert len(ms) == 2
        revenue = next(m for m in ms if m["name"] == "revenue")
        assert revenue["value"] == 1500  # should be the latest


# ── Campaigns ─────────────────────────────────────────────────────────────────

class TestCampaigns:
    def test_add_campaign(self):
        state.create_venture("CCo")
        c = state.add_campaign("CCo", "Launch Post", "hn", description="Show HN post")
        assert c["title"] == "Launch Post"
        assert c["channel"] == "hn"
        assert c["status"] == "draft"

    def test_list_campaigns(self):
        state.create_venture("CCo2")
        state.add_campaign("CCo2", "C1", "twitter")
        state.add_campaign("CCo2", "C2", "reddit")
        cs = state.list_campaigns("CCo2")
        assert len(cs) == 2


# ── Approvals ─────────────────────────────────────────────────────────────────

class TestApprovals:
    def test_submit_approval(self):
        state.create_venture("ACo")
        a = state.submit_approval(
            "ACo", "post", "Publish blog post",
            "Draft blog post about launch strategy",
        )
        assert a["action_type"] == "post"
        assert a["status"] == "pending"

    def test_resolve_approval_approved(self):
        state.create_venture("ACo2")
        a = state.submit_approval("ACo2", "send", "Email blast", "Send to 500 users")
        resolved = state.resolve_approval(a["id"], "approved", resolved_by="Sir Abhi")
        assert resolved["status"] == "approved"
        assert resolved["resolved_by"] == "Sir Abhi"
        assert resolved["resolved_at"] is not None

    def test_resolve_approval_rejected(self):
        state.create_venture("ACo3")
        a = state.submit_approval("ACo3", "spend", "Buy ads", "$500 on Google Ads")
        resolved = state.resolve_approval(a["id"], "rejected")
        assert resolved["status"] == "rejected"

    def test_resolve_already_resolved(self):
        state.create_venture("ACo4")
        a = state.submit_approval("ACo4", "deploy", "Push v1", "Deploy to prod")
        state.resolve_approval(a["id"], "approved")
        with pytest.raises(ValueError):
            state.resolve_approval(a["id"], "rejected")

    def test_list_pending_approvals(self):
        state.create_venture("ACo5")
        state.submit_approval("ACo5", "post", "P1", "D1")
        state.submit_approval("ACo5", "send", "P2", "D2")
        a3 = state.submit_approval("ACo5", "spend", "P3", "D3")
        state.resolve_approval(a3["id"], "approved")
        pending = state.list_pending_approvals("ACo5")
        assert len(pending) == 2

    def test_invalid_resolve_status(self):
        with pytest.raises(ValueError, match="must be 'approved' or 'rejected'"):
            state.resolve_approval(999, "maybe")


# ── Full State ────────────────────────────────────────────────────────────────

class TestFullState:
    def test_get_state(self):
        state.create_venture("StateCo", description="Full state test", goal="Test everything")
        state.add_feature("StateCo", "Feature X")
        state.add_bug("StateCo", "Bug Y")
        state.add_decision("StateCo", "strategic", "Do Z", "Because reasons")
        state.add_metric("StateCo", "users", 42)
        state.add_campaign("StateCo", "Launch", "twitter")
        state.submit_approval("StateCo", "post", "Tweet", "Launch tweet")

        s = state.get_state("StateCo")
        assert s["venture"]["name"] == "StateCo"
        assert len(s["features"]) == 1
        assert len(s["bugs"]) == 1
        assert len(s["recent_decisions"]) == 1
        assert len(s["metrics"]) == 1
        assert len(s["campaigns"]) == 1
        assert len(s["pending_approvals"]) == 1

        # Verify it's JSON-serializable
        json.dumps(s, default=str)

    def test_get_state_not_found(self):
        with pytest.raises(ValueError, match="not found"):
            state.get_state("Ghost")
