"""OpenFounder State Manager — Postgres-backed company state with CLI interface."""

import argparse
import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone

import logging
import time

import psycopg2
import psycopg2.extras

from openfounder.config import config

logger = logging.getLogger("openfounder.state")

# Use RealDictCursor for JSON-friendly output
psycopg2.extras.register_default_jsonb(globally=True, loads=json.loads)

DB_MAX_RETRIES = 2
DB_RETRY_DELAY = 1  # seconds


@contextmanager
def get_db():
    """Get a database connection with auto-commit on success and retry on transient failures."""
    last_error = None
    for attempt in range(DB_MAX_RETRIES + 1):
        try:
            conn = psycopg2.connect(config.DATABASE_URL, connect_timeout=10)
            break
        except psycopg2.OperationalError as e:
            last_error = e
            if attempt < DB_MAX_RETRIES:
                delay = DB_RETRY_DELAY * (2 ** attempt)
                logger.warning("DB connection failed (attempt %d/%d): %s — retrying in %ds",
                               attempt + 1, DB_MAX_RETRIES + 1, e, delay)
                time.sleep(delay)
            else:
                logger.error("DB connection failed after %d attempts: %s", DB_MAX_RETRIES + 1, e)
                raise ConnectionError(f"Cannot connect to database after {DB_MAX_RETRIES + 1} attempts: {e}") from e
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_dict(row):
    """Convert a psycopg2 RealDictRow to a plain dict with serializable values."""
    if row is None:
        return None
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def _rows_to_list(rows):
    return [_row_to_dict(r) for r in rows]


# ── Ventures ──────────────────────────────────────────────────────────────────

def create_venture(name, description=None, goal=None, stage="idea", config_json=None):
    """Create a new venture."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """INSERT INTO ventures (name, description, goal, stage, config)
               VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (name, description, goal, stage, json.dumps(config_json or {})),
        )
        return _row_to_dict(cur.fetchone())


def get_venture(name_or_id):
    """Get a venture by name or ID."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if isinstance(name_or_id, int) or name_or_id.isdigit():
            cur.execute("SELECT * FROM ventures WHERE id = %s", (int(name_or_id),))
        else:
            cur.execute("SELECT * FROM ventures WHERE name = %s", (name_or_id,))
        return _row_to_dict(cur.fetchone())


def list_ventures():
    """List all active ventures."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM ventures WHERE status = 'active' ORDER BY created_at")
        return _rows_to_list(cur.fetchall())


def _resolve_venture_id(name_or_id):
    """Resolve a venture name or ID to an integer ID."""
    v = get_venture(name_or_id)
    if not v:
        raise ValueError(f"Venture not found: {name_or_id}")
    return v["id"]


# ── Features ──────────────────────────────────────────────────────────────────

def add_feature(venture, title, description=None, priority="medium"):
    """Add a feature to a venture."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """INSERT INTO features (venture_id, title, description, priority)
               VALUES (%s, %s, %s, %s) RETURNING *""",
            (vid, title, description, priority),
        )
        return _row_to_dict(cur.fetchone())


def list_features(venture, status=None):
    """List features for a venture, optionally filtered by status."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if status:
            cur.execute(
                "SELECT * FROM features WHERE venture_id = %s AND status = %s ORDER BY priority, created_at",
                (vid, status),
            )
        else:
            cur.execute(
                "SELECT * FROM features WHERE venture_id = %s ORDER BY priority, created_at",
                (vid,),
            )
        return _rows_to_list(cur.fetchall())


def update_feature(feature_id, **kwargs):
    """Update a feature's fields."""
    allowed = {"title", "description", "priority", "status", "assigned_crew"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return None
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [feature_id]
        cur.execute(f"UPDATE features SET {set_clause} WHERE id = %s RETURNING *", values)
        return _row_to_dict(cur.fetchone())


# ── Bugs ──────────────────────────────────────────────────────────────────────

def add_bug(venture, title, description=None, severity="medium"):
    """Add a bug to a venture."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """INSERT INTO bugs (venture_id, title, description, severity)
               VALUES (%s, %s, %s, %s) RETURNING *""",
            (vid, title, description, severity),
        )
        return _row_to_dict(cur.fetchone())


def list_bugs(venture, status=None):
    """List bugs for a venture, optionally filtered by status."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if status:
            cur.execute(
                "SELECT * FROM bugs WHERE venture_id = %s AND status = %s ORDER BY severity, created_at",
                (vid, status),
            )
        else:
            cur.execute(
                "SELECT * FROM bugs WHERE venture_id = %s ORDER BY severity, created_at",
                (vid,),
            )
        return _rows_to_list(cur.fetchall())


def update_bug(bug_id, **kwargs):
    """Update a bug's fields."""
    allowed = {"title", "description", "severity", "status", "assigned_crew"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return None
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [bug_id]
        cur.execute(f"UPDATE bugs SET {set_clause} WHERE id = %s RETURNING *", values)
        return _row_to_dict(cur.fetchone())


# ── Decisions ─────────────────────────────────────────────────────────────────

def add_decision(venture, decision_type, title, reasoning, outcome=None,
                 confidence=0.5, source="ceo", metadata=None):
    """Record a decision with reasoning."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """INSERT INTO decisions (venture_id, decision_type, title, reasoning,
               outcome, confidence, source, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            (vid, decision_type, title, reasoning, outcome, confidence,
             source, json.dumps(metadata or {})),
        )
        return _row_to_dict(cur.fetchone())


def list_decisions(venture, days=7, decision_type=None):
    """List recent decisions for a venture."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        query = """SELECT * FROM decisions WHERE venture_id = %s
                   AND created_at > NOW() - INTERVAL '%s days'"""
        params = [vid, days]
        if decision_type:
            query += " AND decision_type = %s"
            params.append(decision_type)
        query += " ORDER BY created_at DESC"
        cur.execute(query, params)
        return _rows_to_list(cur.fetchall())


# ── Metrics ───────────────────────────────────────────────────────────────────

def add_metric(venture, name, value, unit=None, source=None):
    """Record a metric data point."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """INSERT INTO metrics (venture_id, name, value, unit, source)
               VALUES (%s, %s, %s, %s, %s) RETURNING *""",
            (vid, name, value, unit, source),
        )
        return _row_to_dict(cur.fetchone())


def get_latest_metrics(venture):
    """Get the most recent value of each metric for a venture."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT DISTINCT ON (name) name, value, unit, source, recorded_at
               FROM metrics WHERE venture_id = %s
               ORDER BY name, recorded_at DESC""",
            (vid,),
        )
        return _rows_to_list(cur.fetchall())


# ── Campaigns ─────────────────────────────────────────────────────────────────

def add_campaign(venture, title, channel, description=None):
    """Create a marketing campaign."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """INSERT INTO campaigns (venture_id, title, channel, description)
               VALUES (%s, %s, %s, %s) RETURNING *""",
            (vid, title, channel, description),
        )
        return _row_to_dict(cur.fetchone())


def list_campaigns(venture, status=None):
    """List campaigns for a venture."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if status:
            cur.execute(
                "SELECT * FROM campaigns WHERE venture_id = %s AND status = %s ORDER BY created_at",
                (vid, status),
            )
        else:
            cur.execute(
                "SELECT * FROM campaigns WHERE venture_id = %s ORDER BY created_at",
                (vid,),
            )
        return _rows_to_list(cur.fetchall())


# ── Approvals ─────────────────────────────────────────────────────────────────

def submit_approval(venture, action_type, title, description, decision_id=None,
                    requested_by="ceo", metadata=None):
    """Submit an action for human approval."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """INSERT INTO approvals (venture_id, decision_id, action_type, title,
               description, requested_by, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            (vid, decision_id, action_type, title, description,
             requested_by, json.dumps(metadata or {})),
        )
        return _row_to_dict(cur.fetchone())


def resolve_approval(approval_id, status, resolved_by="human"):
    """Approve or reject a pending approval."""
    if status not in ("approved", "rejected"):
        raise ValueError(f"Status must be 'approved' or 'rejected', got: {status}")
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """UPDATE approvals SET status = %s, resolved_by = %s, resolved_at = NOW()
               WHERE id = %s AND status = 'pending' RETURNING *""",
            (status, resolved_by, approval_id),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Approval {approval_id} not found or already resolved")
        return _row_to_dict(row)


def list_pending_approvals(venture):
    """List pending approvals for a venture."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT * FROM approvals WHERE venture_id = %s AND status = 'pending'
               ORDER BY created_at""",
            (vid,),
        )
        return _rows_to_list(cur.fetchall())


# ── Content Calendar ─────────────────────────────────────────────────────────

def add_content(venture, channel, title, body, cta=None, status="draft",
                scheduled_for=None, campaign_id=None, crew_output_id=None, metadata=None):
    """Add a content piece to the calendar."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """INSERT INTO content_calendar (venture_id, channel, title, body, cta,
               status, scheduled_for, campaign_id, crew_output_id, metadata)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            (vid, channel, title, body, cta, status, scheduled_for,
             campaign_id, crew_output_id, json.dumps(metadata or {})),
        )
        return _row_to_dict(cur.fetchone())


def list_content(venture, status=None, channel=None, days=30):
    """List content calendar entries for a venture."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        query = """SELECT * FROM content_calendar WHERE venture_id = %s
                   AND created_at > NOW() - INTERVAL '%s days'"""
        params = [vid, days]
        if status:
            query += " AND status = %s"
            params.append(status)
        if channel:
            query += " AND channel = %s"
            params.append(channel)
        query += " ORDER BY COALESCE(scheduled_for, created_at)"
        cur.execute(query, params)
        return _rows_to_list(cur.fetchall())


def update_content(content_id, **kwargs):
    """Update a content calendar entry."""
    allowed = {"title", "body", "cta", "status", "channel",
               "scheduled_for", "published_at", "published_url"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return None
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        set_clause = ", ".join(f"{k} = %s" for k in updates)
        values = list(updates.values()) + [content_id]
        cur.execute(f"UPDATE content_calendar SET {set_clause} WHERE id = %s RETURNING *", values)
        return _row_to_dict(cur.fetchone())


def get_pending_content(venture):
    """Get content pieces ready to publish (status=approved, scheduled_for <= now)."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """SELECT * FROM content_calendar WHERE venture_id = %s
               AND status = 'approved'
               AND (scheduled_for IS NULL OR scheduled_for <= NOW())
               ORDER BY scheduled_for NULLS LAST""",
            (vid,),
        )
        return _rows_to_list(cur.fetchall())


# ── Crew Outputs ─────────────────────────────────────────────────────────────

def save_crew_output(venture, crew_name, task, context=None, status="completed",
                     output=None, execution=None, branch_name=None, commit_sha=None,
                     model=None, input_tokens=None, output_tokens=None, duration_s=None):
    """Persist a crew output to the database."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """INSERT INTO crew_outputs (venture_id, crew_name, task, context, status,
               output, execution, branch_name, commit_sha, model,
               input_tokens, output_tokens, duration_s)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *""",
            (vid, crew_name, task, context, status,
             json.dumps(output or {}), json.dumps(execution) if execution else None,
             branch_name, commit_sha, model,
             input_tokens, output_tokens, duration_s),
        )
        return _row_to_dict(cur.fetchone())


def list_crew_outputs(venture, crew_name=None, days=7):
    """List recent crew outputs for a venture."""
    vid = _resolve_venture_id(venture)
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        query = """SELECT id, crew_name, task, status, branch_name, commit_sha,
                   model, input_tokens, output_tokens, duration_s, created_at
                   FROM crew_outputs WHERE venture_id = %s
                   AND created_at > NOW() - INTERVAL '%s days'"""
        params = [vid, days]
        if crew_name:
            query += " AND crew_name = %s"
            params.append(crew_name)
        query += " ORDER BY created_at DESC"
        cur.execute(query, params)
        return _rows_to_list(cur.fetchall())


def get_crew_output(output_id):
    """Get a single crew output by ID (includes full output JSON)."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM crew_outputs WHERE id = %s", (output_id,))
        return _row_to_dict(cur.fetchone())


# ── Full State Snapshot ───────────────────────────────────────────────────────

def get_state(venture):
    """Get the full state of a venture as a single JSON-serializable dict.

    This is what gets injected into the CEO system prompt.
    """
    v = get_venture(venture)
    if not v:
        raise ValueError(f"Venture not found: {venture}")

    return {
        "venture": v,
        "features": list_features(venture),
        "bugs": list_bugs(venture),
        "recent_decisions": list_decisions(venture, days=7),
        "metrics": get_latest_metrics(venture),
        "campaigns": list_campaigns(venture),
        "pending_approvals": list_pending_approvals(venture),
        "content_calendar": list_content(venture, days=14),
        "recent_crew_outputs": list_crew_outputs(venture, days=7),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def _output(data):
    """Print JSON output."""
    print(json.dumps(data, indent=2, default=str))


def _confidence_bar(confidence: float) -> str:
    """Render a confidence score as a visual bar."""
    filled = int(confidence * 10)
    return "█" * filled + "░" * (10 - filled) + f" {confidence:.0%}"


def _pretty_decisions(venture: str, decisions: list, days: int):
    """Print decisions in a human-readable formatted view."""
    print(f"\n{'═' * 70}")
    print(f"  Decision Log — {venture} (last {days} days)")
    print(f"  {len(decisions)} decision(s)")
    print(f"{'═' * 70}")

    if not decisions:
        print("  No decisions found.\n")
        return

    for d in decisions:
        dtype = d.get("decision_type", "?").upper()
        conf = d.get("confidence", 0.5)
        source = d.get("source", "?")
        created = d.get("created_at", "?")
        if isinstance(created, str) and len(created) > 16:
            created = created[:16]

        print(f"\n  [{dtype}] {d.get('title', '?')}")
        print(f"  {'─' * 66}")
        print(f"  Reasoning:  {d.get('reasoning', 'N/A')}")
        if d.get("outcome"):
            print(f"  Outcome:    {d['outcome']}")
        print(f"  Confidence: {_confidence_bar(conf)}")
        print(f"  Source:     {source}  |  Date: {created}")

    # Summary stats
    types = {}
    total_conf = 0
    for d in decisions:
        t = d.get("decision_type", "?")
        types[t] = types.get(t, 0) + 1
        total_conf += d.get("confidence", 0.5)

    avg_conf = total_conf / len(decisions) if decisions else 0
    type_summary = ", ".join(f"{v} {k}" for k, v in sorted(types.items(), key=lambda x: -x[1]))

    print(f"\n{'─' * 70}")
    print(f"  Types:          {type_summary}")
    print(f"  Avg confidence: {_confidence_bar(avg_conf)}")
    print(f"{'═' * 70}\n")


def cli():
    parser = argparse.ArgumentParser(
        prog="openfounder-state",
        description="OpenFounder State Manager — manage ventures, features, bugs, decisions, and more.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # create-venture
    p = sub.add_parser("create-venture", help="Create a new venture")
    p.add_argument("name")
    p.add_argument("--description", "-d")
    p.add_argument("--goal", "-g")
    p.add_argument("--stage", default="idea", choices=["idea", "mvp", "growth", "scale"])

    # list-ventures
    sub.add_parser("list-ventures", help="List all active ventures")

    # get-state
    p = sub.add_parser("get-state", help="Get full state of a venture")
    p.add_argument("venture", help="Venture name or ID")

    # add-feature
    p = sub.add_parser("add-feature", help="Add a feature to a venture")
    p.add_argument("venture")
    p.add_argument("title")
    p.add_argument("--description", "-d")
    p.add_argument("--priority", "-p", default="medium", choices=["critical", "high", "medium", "low"])

    # list-features
    p = sub.add_parser("list-features", help="List features for a venture")
    p.add_argument("venture")
    p.add_argument("--status", "-s")

    # update-feature
    p = sub.add_parser("update-feature", help="Update a feature")
    p.add_argument("id", type=int)
    p.add_argument("--title")
    p.add_argument("--status", "-s")
    p.add_argument("--priority", "-p")
    p.add_argument("--assigned-crew")

    # add-bug
    p = sub.add_parser("add-bug", help="Add a bug to a venture")
    p.add_argument("venture")
    p.add_argument("title")
    p.add_argument("--description", "-d")
    p.add_argument("--severity", default="medium", choices=["critical", "high", "medium", "low"])

    # list-bugs
    p = sub.add_parser("list-bugs", help="List bugs for a venture")
    p.add_argument("venture")
    p.add_argument("--status", "-s")

    # add-decision
    p = sub.add_parser("add-decision", help="Record a decision")
    p.add_argument("venture")
    p.add_argument("type", choices=["strategic", "feature", "bug", "marketing", "resource", "delegation"])
    p.add_argument("title")
    p.add_argument("reasoning")
    p.add_argument("--outcome", "-o")
    p.add_argument("--confidence", "-c", type=float, default=0.5)
    p.add_argument("--source", default="ceo")

    # decisions
    p = sub.add_parser("decisions", help="List recent decisions")
    p.add_argument("venture")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--type", dest="decision_type")
    p.add_argument("--source")
    p.add_argument("--pretty", action="store_true", help="Formatted table output")

    # add-metric
    p = sub.add_parser("add-metric", help="Record a metric")
    p.add_argument("venture")
    p.add_argument("name")
    p.add_argument("value", type=float)
    p.add_argument("--unit", "-u")
    p.add_argument("--source", "-s")

    # metrics
    p = sub.add_parser("metrics", help="Get latest metrics")
    p.add_argument("venture")

    # add-campaign
    p = sub.add_parser("add-campaign", help="Create a campaign")
    p.add_argument("venture")
    p.add_argument("title")
    p.add_argument("channel", choices=["twitter", "reddit", "hn", "email", "blog", "discord"])
    p.add_argument("--description", "-d")

    # submit-approval
    p = sub.add_parser("submit-approval", help="Submit an action for approval")
    p.add_argument("venture")
    p.add_argument("action_type", choices=["post", "send", "spend", "deploy", "delete"])
    p.add_argument("title")
    p.add_argument("description")
    p.add_argument("--decision-id", type=int)
    p.add_argument("--requested-by", default="ceo")

    # resolve-approval
    p = sub.add_parser("resolve-approval", help="Approve or reject an approval")
    p.add_argument("id", type=int)
    p.add_argument("status", choices=["approved", "rejected"])
    p.add_argument("--resolved-by", default="human")

    # pending-approvals
    p = sub.add_parser("pending-approvals", help="List pending approvals")
    p.add_argument("venture")

    args = parser.parse_args()

    try:
        if args.command == "create-venture":
            _output(create_venture(args.name, args.description, args.goal, args.stage))

        elif args.command == "list-ventures":
            _output(list_ventures())

        elif args.command == "get-state":
            _output(get_state(args.venture))

        elif args.command == "add-feature":
            _output(add_feature(args.venture, args.title, args.description, args.priority))

        elif args.command == "list-features":
            _output(list_features(args.venture, args.status))

        elif args.command == "update-feature":
            result = update_feature(args.id, title=args.title, status=args.status,
                                    priority=args.priority, assigned_crew=args.assigned_crew)
            _output(result or {"error": "No fields to update"})

        elif args.command == "add-bug":
            _output(add_bug(args.venture, args.title, args.description, args.severity))

        elif args.command == "list-bugs":
            _output(list_bugs(args.venture, args.status))

        elif args.command == "add-decision":
            _output(add_decision(args.venture, args.type, args.title, args.reasoning,
                                 args.outcome, args.confidence, args.source))

        elif args.command == "decisions":
            decisions = list_decisions(args.venture, args.days, args.decision_type)
            if args.source:
                decisions = [d for d in decisions if d.get("source") == args.source]
            if args.pretty:
                _pretty_decisions(args.venture, decisions, args.days)
            else:
                _output(decisions)

        elif args.command == "add-metric":
            _output(add_metric(args.venture, args.name, args.value, args.unit, args.source))

        elif args.command == "metrics":
            _output(get_latest_metrics(args.venture))

        elif args.command == "add-campaign":
            _output(add_campaign(args.venture, args.title, args.channel, args.description))

        elif args.command == "submit-approval":
            _output(submit_approval(args.venture, args.action_type, args.title,
                                    args.description, args.decision_id, args.requested_by))

        elif args.command == "resolve-approval":
            _output(resolve_approval(args.id, args.status, args.resolved_by))

        elif args.command == "pending-approvals":
            _output(list_pending_approvals(args.venture))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    cli()
