"""OpenFounder CEO Loop — nightly orchestrator.

Reads venture state, injects into CEO prompt, calls LLM,
writes decisions, submits approvals, and generates morning briefing.
"""

import json
import logging
import time
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

# Retry config
LLM_MAX_RETRIES = 2
LLM_RETRY_DELAY = 3  # seconds, doubles each retry


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


def _parse_llm_json(raw: str) -> dict:
    """Parse JSON from LLM response, handling common formatting issues."""
    text = raw.strip()

    # Strip markdown fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON object from surrounding text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from LLM response ({len(text)} chars): {text[:200]}...")


def _call_llm(system_prompt: str, state_json: str, model: str = None) -> dict:
    """Call the LLM with retry on transient failures."""
    model = model or config.CEO_MODEL
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    user_message = (
        "Here is the current venture state. Analyze it and produce your CEO output.\n\n"
        f"```json\n{state_json}\n```"
    )

    last_error = None
    for attempt in range(LLM_MAX_RETRIES + 1):
        try:
            logger.info("Calling %s (attempt %d/%d, max_tokens=%d)",
                        model, attempt + 1, LLM_MAX_RETRIES + 1, config.CEO_MAX_TOKENS)

            response = client.messages.create(
                model=model,
                max_tokens=config.CEO_MAX_TOKENS,
                temperature=config.CEO_TEMPERATURE,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            raw = response.content[0].text
            logger.debug("Raw LLM response: %s", raw[:500])

            result = _parse_llm_json(raw)

            # Validate required fields
            if not isinstance(result, dict):
                raise ValueError(f"CEO output is not a JSON object, got {type(result).__name__}")

            # Record token usage
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "model": model,
            }
            result["_usage"] = usage
            logger.info(
                "LLM response (%s): %d input tokens, %d output tokens",
                model, usage["input_tokens"], usage["output_tokens"],
            )

            return result

        except (anthropic.APIConnectionError, anthropic.RateLimitError,
                anthropic.InternalServerError) as e:
            last_error = e
            if attempt < LLM_MAX_RETRIES:
                delay = LLM_RETRY_DELAY * (2 ** attempt)
                logger.warning("LLM call failed (attempt %d/%d): %s — retrying in %ds",
                               attempt + 1, LLM_MAX_RETRIES + 1, e, delay)
                time.sleep(delay)
            else:
                logger.error("LLM call failed after %d attempts: %s", LLM_MAX_RETRIES + 1, e)

        except ValueError as e:
            # JSON parse failure — retry once (LLM might produce valid JSON on second try)
            last_error = e
            if attempt < LLM_MAX_RETRIES:
                logger.warning("LLM returned invalid JSON (attempt %d/%d): %s — retrying",
                               attempt + 1, LLM_MAX_RETRIES + 1, e)
                time.sleep(LLM_RETRY_DELAY)
            else:
                logger.error("LLM returned invalid JSON after %d attempts", LLM_MAX_RETRIES + 1)

        except anthropic.AuthenticationError as e:
            # Don't retry auth errors
            logger.error("Authentication failed — check ANTHROPIC_API_KEY: %s", e)
            raise

    raise RuntimeError(f"LLM call failed after {LLM_MAX_RETRIES + 1} attempts: {last_error}")


def _needs_escalation(ceo_output: dict) -> str | None:
    """Check if the CEO output needs re-evaluation with a stronger model.

    Returns the model to escalate to, or None if no escalation needed.

    Escalation triggers:
    - Any decision with confidence < 0.4 → escalate to Sonnet
    - Any critical risk identified → escalate to Sonnet
    - Any strategic decision with confidence < 0.6 → escalate to Opus
    """
    decisions = ceo_output.get("decisions", [])
    risks = ceo_output.get("risks", [])

    # Check for strategic decisions with low confidence → Opus
    for d in decisions:
        if d.get("decision_type") == "strategic" and d.get("confidence", 0.5) < 0.6:
            logger.info("Escalation → Opus: strategic decision '%s' has low confidence (%.1f)",
                        d["title"], d.get("confidence", 0.5))
            return config.MAX_MODEL

    # Check for any decision with very low confidence → Sonnet
    for d in decisions:
        if d.get("confidence", 0.5) < 0.4:
            logger.info("Escalation → Sonnet: decision '%s' has very low confidence (%.1f)",
                        d["title"], d.get("confidence", 0.5))
            return config.ESCALATION_MODEL

    # Check for critical risks → Sonnet
    for r in risks:
        if r.get("severity") == "critical":
            logger.info("Escalation → Sonnet: critical risk '%s'", r["title"])
            return config.ESCALATION_MODEL

    return None


def _process_decisions(venture_name: str, ceo_output: dict) -> list:
    """Write CEO decisions to the database. Skips malformed entries."""
    recorded = []
    for i, d in enumerate(ceo_output.get("decisions", [])):
        try:
            if not d.get("decision_type") or not d.get("title") or not d.get("reasoning"):
                logger.warning("Skipping malformed decision #%d: missing required fields", i)
                continue
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
        except Exception as e:
            logger.error("Failed to record decision #%d '%s': %s",
                         i, d.get("title", "?"), e)
    return recorded


def _process_approvals(venture_name: str, ceo_output: dict) -> list:
    """Submit approval requests to the queue. Skips malformed entries."""
    submitted = []
    for i, a in enumerate(ceo_output.get("approvals_needed", [])):
        try:
            if not a.get("action_type") or not a.get("title"):
                logger.warning("Skipping malformed approval #%d: missing required fields", i)
                continue
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
        except Exception as e:
            logger.error("Failed to submit approval #%d '%s': %s",
                         i, a.get("title", "?"), e)
    return submitted


def _process_metrics(venture_name: str, ceo_output: dict) -> list:
    """Record any metric updates from the CEO. Skips malformed entries."""
    recorded = []
    for i, m in enumerate(ceo_output.get("metrics_update", [])):
        try:
            if not m.get("name") or m.get("value") is None:
                logger.warning("Skipping malformed metric #%d: missing name or value", i)
                continue
            result = add_metric(
                venture=venture_name,
                name=m["name"],
                value=float(m["value"]),
                unit=m.get("unit"),
                source=m.get("source", "ceo_estimate"),
            )
            recorded.append(result)
            logger.info("Metric recorded: %s = %s %s", m["name"], m["value"], m.get("unit", ""))
        except (ValueError, TypeError) as e:
            logger.error("Failed to record metric #%d '%s': %s", i, m.get("name", "?"), e)
        except Exception as e:
            logger.error("Failed to record metric #%d '%s': %s", i, m.get("name", "?"), e)
    return recorded


def _process_delegations(venture_name: str, ceo_output: dict) -> list:
    """Execute crew delegations from the CEO output."""
    results = []
    for d in ceo_output.get("delegations", []):
        crew_name = d.get("crew")
        task = d.get("task", "")
        context = d.get("context", "")

        if not crew_name or not task:
            logger.warning("Skipping malformed delegation: missing crew or task")
            continue

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
    errors = []

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

    # 3. Call LLM (starts with Haiku, escalates if needed)
    ceo_output = _call_llm(system_prompt, state_json)

    # 3b. Check if escalation is needed
    escalate_to = _needs_escalation(ceo_output)
    if escalate_to:
        initial_model = ceo_output.get("_usage", {}).get("model", "?")
        logger.info("Escalating from %s → %s", initial_model, escalate_to)
        try:
            ceo_output = _call_llm(system_prompt, state_json, model=escalate_to)
            ceo_output["_escalated_from"] = initial_model
        except RuntimeError as e:
            logger.error("Escalation failed, using original output: %s", e)
            errors.append(f"Escalation to {escalate_to} failed: {e}")

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
        # Send approval notifications to Discord (non-fatal)
        try:
            notifier = DiscordApprovalNotifier()
            for a in approvals:
                notifier.send_approval_notification(a)
        except Exception as e:
            logger.error("Discord approval notifications failed: %s", e)
            errors.append(f"Discord approval notify failed: {e}")

        # Send morning briefing to Discord (non-fatal)
        try:
            send_briefing_to_discord(venture_name, briefing)
        except Exception as e:
            logger.error("Discord briefing delivery failed: %s", e)
            errors.append(f"Discord briefing failed: {e}")

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
        "errors": errors,
    }

    if errors:
        logger.warning("CEO loop completed with %d error(s): %s", len(errors), errors)
    else:
        logger.info(
            "CEO loop complete: %d decisions, %d approvals, %d metrics",
            len(decisions), len(approvals), len(metrics),
        )

    return result
