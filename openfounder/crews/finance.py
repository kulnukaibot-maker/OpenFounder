"""Finance crew — revenue tracking, budget enforcement, and financial analysis."""

import json
import logging

from openfounder.config import config
from openfounder.crews.base import BaseCrew
from openfounder.state import add_metric, get_latest_metrics, submit_approval

logger = logging.getLogger("openfounder.crew")


class FinanceCrew(BaseCrew):
    crew_name = "finance"
    prompt_file = "finance_crew.md"

    def _get_model(self) -> str:
        return config.FINANCE_MODEL

    def _get_max_tokens(self) -> int:
        return config.FINANCE_MAX_TOKENS

    def _load_prompt(self) -> str:
        """Override to inject venture context and financial summary."""
        template = super()._load_prompt()

        v = self.venture
        template = template.replace("{{venture_description}}", v.get("description") or "No description")
        template = template.replace("{{venture_goal}}", v.get("goal") or "No goal set")
        template = template.replace("{{venture_stage}}", v.get("stage", "idea"))

        # Inject current financial metrics
        try:
            metrics = get_latest_metrics(self.venture_name)
            if metrics:
                financial_lines = []
                for m in metrics:
                    unit = m.get("unit", "")
                    financial_lines.append(f"{m['name']}: {m['value']} {unit} (source: {m.get('source', '?')})")
                template = template.replace("{{financial_summary}}", "\n".join(financial_lines))
            else:
                template = template.replace("{{financial_summary}}", "(no financial data yet)")
        except Exception:
            template = template.replace("{{financial_summary}}", "(unable to load)")

        return template

    def run(self, task: str, context: str = "") -> dict:
        """Run finance crew and persist metrics + budget alerts."""
        result = super().run(task, context)

        # Persist metrics updates
        metrics_update = result.get("metrics_update", [])
        saved_metrics = 0
        for m in metrics_update:
            try:
                if not m.get("name") or m.get("value") is None:
                    continue
                add_metric(
                    venture=self.venture_name,
                    name=m["name"],
                    value=float(m["value"]),
                    unit=m.get("unit"),
                    source=m.get("source", "finance_crew"),
                )
                saved_metrics += 1
                logger.info("[finance] Metric saved: %s = %s %s",
                            m["name"], m["value"], m.get("unit", ""))
            except Exception as e:
                logger.error("[finance] Failed to save metric '%s': %s", m.get("name", "?"), e)

        # Submit approval requests for spending recommendations
        recommendations = result.get("recommendations", [])
        for rec in recommendations:
            if rec.get("requires_approval"):
                try:
                    submit_approval(
                        venture=self.venture_name,
                        action_type="spend",
                        title=f"Finance: {rec.get('action', 'Spending change')[:60]}",
                        description=f"Reasoning: {rec.get('reasoning', '')}\nImpact: {rec.get('impact', '')}",
                        requested_by="finance_crew",
                        metadata={"priority": rec.get("priority"), "impact": rec.get("impact")},
                    )
                except Exception as e:
                    logger.error("[finance] Failed to submit approval: %s", e)

        result["_metrics_saved"] = saved_metrics

        return result
