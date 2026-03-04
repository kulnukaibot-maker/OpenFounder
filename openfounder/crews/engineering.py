"""Engineering crew — code generation and execution."""

import logging
import os
import subprocess
from pathlib import Path

from openfounder.config import config
from openfounder.crews.base import BaseCrew
from openfounder.executor import CodeExecutor

logger = logging.getLogger("openfounder.crew")


class EngineeringCrew(BaseCrew):
    crew_name = "engineering"
    prompt_file = "engineering_crew.md"

    def _get_model(self) -> str:
        return config.ENGINEERING_MODEL

    def _get_max_tokens(self) -> int:
        return config.ENGINEERING_MAX_TOKENS

    def _get_repo_path(self) -> str | None:
        """Get repo path from venture config or env var."""
        venture_config = self.venture.get("config", {}) or {}
        return venture_config.get("repo_path") or config.ENGINEERING_REPO_PATH or None

    def _list_repo_files(self, repo_path: str) -> str:
        """List tracked files in the repo using git ls-files."""
        try:
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                files = result.stdout.strip().split("\n")
                # Truncate to 200 files to keep prompt manageable
                if len(files) > 200:
                    return "\n".join(files[:200]) + f"\n... and {len(files) - 200} more files"
                return "\n".join(files)
        except Exception:
            pass
        return "(unable to list files)"

    def _load_prompt(self) -> str:
        """Override to inject repo context."""
        template = super()._load_prompt()
        repo_path = self._get_repo_path()
        if repo_path:
            template = template.replace("{{repo_path}}", repo_path)
            template = template.replace("{{existing_files}}", self._list_repo_files(repo_path))
        else:
            template = template.replace("{{repo_path}}", "(not configured)")
            template = template.replace("{{existing_files}}", "(no repo path configured)")
        return template

    def run(self, task: str, context: str = "") -> dict:
        """Run engineering crew with optional code execution."""
        # 1. Call LLM to generate code (uses Sonnet via _get_model)
        result = super().run(task, context)

        # 2. Execute code changes if auto-apply is enabled
        repo_path = self._get_repo_path()
        if not config.ENGINEERING_AUTO_APPLY:
            result["_execution"] = {"status": "skipped", "reason": "auto-apply disabled"}
            return result

        if not repo_path:
            result["_execution"] = {"status": "skipped", "reason": "no repo_path configured"}
            return result

        if not result.get("code_changes"):
            result["_execution"] = {"status": "no_changes"}
            return result

        try:
            executor = CodeExecutor(repo_path, self.venture_name)
            execution = executor.execute(result)
            result["_execution"] = execution
            logger.info("[engineering] Code execution: %s (branch: %s)",
                        execution.get("status"), execution.get("branch"))
        except Exception as e:
            logger.error("[engineering] Executor failed: %s", e)
            result["_execution"] = {"status": "error", "error": str(e)}

        return result
