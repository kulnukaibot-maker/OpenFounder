"""OpenFounder CEO Loop — nightly orchestrator.

Reads venture state, injects into CEO prompt, calls LLM,
writes decisions, submits approvals, and generates morning briefing.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import anthropic

from openfounder.config import config
from openfounder.state import (
    add_decision,
    add_metric,
    get_state,
    get_venture,
    submit_approval,
    update_feature,
    update_bug,
    list_decisions,
)
from openfounder.crews.base import run_crew
from openfounder.approval import DiscordApprovalNotifier, send_briefing_to_discord

logger = logging.getLogger("openfounder.ceo")

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_system_prompt(venture_state: dict, loop_number: int = 1) -> str:
    """Load and populate the CEO system prompt template."""
    template = (PROMPTS_DIR / "ceo_system.md").read_text()

    v = venture_state["venture"]
    replacements = {
        "{{venture_name}}": v["name"],
        "{{venture_description}}": v.get("description") or "No description",
        "{{venture_goal}}": v.get("goal") or "No goal set",
        "{{venture_stage}}": v.get("stage", "idea"),
        "{{current_date}}": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "{{loop_number}}": str(loop_number),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)

    return template


def _get_loop_number(venture_name: str) -> int:
    """Get the loop iteration number based on CEO decision count."""
    decisions = list_decisions(venture_name, days=365, decision_type=None)
    ceo_decisions = [d for d in decisions if d.get("source") == "ceo"]
    return len(ceo_decisions) + 1


def _call_llm(system_prompt: str, state_json: str) -> dict:
    """Call the LLM with the CEO prompt and venture state."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    user_message = (
        "Here is the current venture state. Analyze it and produce your CEO output.\n\n"
        f"```json\n{state_json}\n```"
    )

    logger.info("Calling %s (max_tokens=%d)", config.CEO_MODEL, config.CEO_MAX_TOKENS)

    response = client.messages.create(
        model=config.CEO_MODEL,
        max_tokens=config.CEO_MAX_TOKENS,
        temperature=config.CEO_TEMPERATURE,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text
    logger.debug("Raw LLM response: %s", raw[:500])

    # Parse JSON — strip any accidental markdown fences
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse CEO output as JSON: %s", e)
        logger.error("Raw text: %s", text[:1000])
        raise ValueError(f"CEO output is not valid JSON: {e}") from e

    # Record token usage
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "model": config.CEO_MODEL,
    }
    result["_usage"] = usage
    logger.info(
        "LLM response: %d input tokens, %d output tokens",
        usage["input_tokens"],
        usage["output_tokens"],
    )

    return result


def _process_decisions(venture_name: str, ceo_output: dict) -> list:
    """Write CEO decisions to the database."""
    recorded = []
    for d in ceo_output.get("decisions", []):
        result = add_decision(
            venture=venture_name,
            decision_type=d["decision_type"],
            title=d["title"],
            reasoning=d["reasoning"],
            outcome=d.get("outcome"),
            confidence=d.get("confidence", 0.5),
            source="ceo",
            metadata={"loop": ceo_output.get("_usage", {})},
        )
        recorded.append(result)
        logger.info("Decision recorded: [%s] %s (confidence: %.1f)",
                     d["decision_type"], d["title"], d.get("confidence", 0.5))
    return recorded


def _process_approvals(venture_name: str, ceo_output: dict) -> list:
    """Submit approval requests to the queue."""
    submitted = []
    for a in ceo_output.get("approvals_needed", []):
        result = submit_approval(
            venture=venture_name,
            action_type=a["action_type"],
            title=a["title"],
            description=a.get("description", ""),
            requested_by="ceo",
            metadata={"reasoning": a.get("reasoning", "")},
        )
        submitted.append(result)
        logger.info("Approval submitted: [%s] %s", a["action_type"], a["title"])
    return submitted


def _process_metrics(venture_name: str, ceo_output: dict) -> list:
    """Record any metric updates from the CEO."""
    recorded = []
    for m in ceo_output.get("metrics_update", []):
        result = add_metric(
            venture=venture_name,
            name=m["name"],
            value=m["value"],
            unit=m.get("unit"),
            source=m.get("source", "ceo_estimate"),
        )
        recorded.append(result)
        logger.info("Metric recorded: %s = %s %s", m["name"], m["value"], m.get("unit", ""))
    return recorded


def _process_delegations(venture_name: str, ceo_output: dict) -> list:
    """Execute crew delegations from the CEO output."""
    results = []
    for d in ceo_output.get("delegations", []):
        crew_name = d.get("crew")
        task = d.get("task", "")
        context = d.get("context", "")

        try:
            result = run_crew(crew_name, venture_name, task, context)
            results.append({"crew": crew_name, "task": task, "status": "success", "output": result})
            logger.info("Delegation complete: %s → %s", crew_name, task[:60])
        except Exception as e:
            logger.error("Delegation failed: %s → %s: %s", crew_name, task[:60], e)
            results.append({"crew": crew_name, "task": task, "status": "error", "error": str(e)})

    return results


def _build_briefing(ceo_output: dict) -> str:
    """Extract or build the morning briefing."""
    briefing = ceo_output.get("morning_briefing", "")
    if not briefing:
        # Fallback: build from summary + priorities
        parts = []
        if ceo_output.get("summary"):
            parts.append(f"**Summary:** {ceo_output['summary']}")
        for p in ceo_output.get("priorities", [])[:5]:
            parts.append(f"- [{p.get('urgency', '?')}] {p['title']} → {p.get('assigned_crew', '?')}")
        briefing = "\n".join(parts) if parts else "No briefing generated."
    return briefing


def run_ceo_loop(venture_name: str, dry_run: bool = False) -> dict:
    """Run the full CEO loop for a venture.

    Args:
        venture_name: Name or ID of the venture.
        dry_run: If True, call the LLM but don't write to the database.

    Returns:
        Dict with: ceo_output, decisions, approvals, metrics, briefing.
    """
    logger.info("Starting CEO loop for: %s", venture_name)

    # 1. Read state
    venture_state = get_state(venture_name)
    state_json = json.dumps(venture_state, indent=2, default=str)
    logger.info("State loaded: %d features, %d bugs, %d recent decisions",
                len(venture_state["features"]),
                len(venture_state["bugs"]),
                len(venture_state["recent_decisions"]))

    # 2. Build prompt
    loop_number = _get_loop_number(venture_name)
    system_prompt = _load_system_prompt(venture_state, loop_number)
    logger.info("Loop #%d — prompt loaded (%d chars)", loop_number, len(system_prompt))

    # 3. Call LLM
    ceo_output = _call_llm(system_prompt, state_json)

    # 4. Process outputs
    if dry_run:
        logger.info("Dry run — skipping database writes")
        decisions = []
        approvals = []
        metrics = []
    else:
        decisions = _process_decisions(venture_name, ceo_output)
        approvals = _process_approvals(venture_name, ceo_output)
        metrics = _process_metrics(venture_name, ceo_output)

    # 5. Run crew delegations
    delegation_results = []
    if not dry_run:
        delegation_results = _process_delegations(venture_name, ceo_output)

    # 6. Build briefing and notify
    briefing = _build_briefing(ceo_output)

    if not dry_run:
        # Send approval notifications to Discord
        notifier = DiscordApprovalNotifier()
        for a in approvals:
            notifier.send_approval_notification(a)

        # Send morning briefing to Discord
        send_briefing_to_discord(venture_name, briefing)

    result = {
        "venture": venture_name,
        "loop_number": loop_number,
        "ceo_output": ceo_output,
        "decisions_recorded": len(decisions),
        "approvals_submitted": len(approvals),
        "metrics_recorded": len(metrics),
        "delegations_run": len(delegation_results),
        "delegation_results": delegation_results,
        "briefing": briefing,
        "dry_run": dry_run,
    }

    logger.info(
        "CEO loop complete: %d decisions, %d approvals, %d metrics",
        len(decisions), len(approvals), len(metrics),
    )

    return result
