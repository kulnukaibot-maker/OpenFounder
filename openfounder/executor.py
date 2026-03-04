"""Code executor — applies engineering crew output to the filesystem.

Creates a feature branch, writes/modifies/deletes files, runs tests,
and commits changes. Never touches main directly.
"""

import logging
import re
import subprocess
import time
from pathlib import Path

from openfounder.config import config

logger = logging.getLogger("openfounder.executor")


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a branch-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-")


class CodeExecutor:
    """Applies code changes from engineering crew output to the filesystem."""

    def __init__(self, repo_path: str, venture_name: str, dry_run: bool = False):
        self.repo_path = Path(repo_path).resolve()
        self.venture_name = venture_name
        self.dry_run = dry_run
        self.branch_name = None
        self.original_branch = None
        self.changes_applied = []
        self.test_results = []

    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
        """Run a git command in the repo directory."""
        return subprocess.run(
            ["git"] + list(args),
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _validate_path(self, file_path: str) -> Path:
        """Validate that a file path is under the repo root. Prevents traversal."""
        resolved = (self.repo_path / file_path).resolve()
        if not str(resolved).startswith(str(self.repo_path)):
            raise ValueError(f"Path traversal blocked: {file_path} resolves outside repo")
        return resolved

    def create_branch(self, task_summary: str) -> str:
        """Create and checkout a feature branch from current HEAD."""
        # Save current branch
        result = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        self.original_branch = result.stdout.strip() or "main"

        # Generate branch name
        from datetime import datetime, timezone
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        slug = _slugify(task_summary)
        self.branch_name = f"eng/{_slugify(self.venture_name, 20)}/{date_str}-{slug}"

        # Stash any uncommitted changes
        self._run_git("stash", "--include-untracked")

        # Create and checkout branch
        result = self._run_git("checkout", "-b", self.branch_name)
        if result.returncode != 0:
            # Branch might already exist, try switching to it
            result = self._run_git("checkout", self.branch_name)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to create branch {self.branch_name}: {result.stderr}")

        logger.info("Created branch: %s", self.branch_name)
        return self.branch_name

    def apply_changes(self, code_changes: list) -> list:
        """Apply code_changes from engineering crew output.

        Returns list of {file, action, status, error?}
        """
        results = []
        for change in code_changes:
            file_path = change.get("file", "")
            action = change.get("action", "")
            content = change.get("content", "")

            if not file_path or not action:
                results.append({"file": file_path, "action": action, "status": "skipped", "error": "missing file or action"})
                continue

            try:
                full_path = self._validate_path(file_path)

                if action == "create":
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content)
                    logger.info("Created: %s", file_path)
                    results.append({"file": file_path, "action": "create", "status": "ok"})

                elif action == "modify":
                    if not full_path.exists():
                        logger.warning("File to modify doesn't exist, creating: %s", file_path)
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content)
                    logger.info("Modified: %s", file_path)
                    results.append({"file": file_path, "action": "modify", "status": "ok"})

                elif action == "delete":
                    if full_path.exists():
                        full_path.unlink()
                        logger.info("Deleted: %s", file_path)
                        results.append({"file": file_path, "action": "delete", "status": "ok"})
                    else:
                        results.append({"file": file_path, "action": "delete", "status": "skipped", "error": "file not found"})

                else:
                    results.append({"file": file_path, "action": action, "status": "skipped", "error": f"unknown action: {action}"})

            except Exception as e:
                logger.error("Failed to apply change to %s: %s", file_path, e)
                results.append({"file": file_path, "action": action, "status": "error", "error": str(e)})

        self.changes_applied = results
        return results

    def run_tests(self, test_commands: list) -> list:
        """Run test commands and capture results."""
        results = []
        timeout = config.ENGINEERING_TEST_TIMEOUT

        for cmd in test_commands:
            # Only allow pytest commands
            if not (cmd.startswith("pytest") or cmd.startswith("python3 -m pytest") or cmd.startswith("python -m pytest")):
                results.append({"command": cmd, "exit_code": -1, "stdout": "", "stderr": "Blocked: only pytest commands allowed", "duration_s": 0})
                continue

            start = time.time()
            try:
                proc = subprocess.run(
                    cmd.split(),
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                duration = time.time() - start
                results.append({
                    "command": cmd,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout[-2000:] if len(proc.stdout) > 2000 else proc.stdout,
                    "stderr": proc.stderr[-1000:] if len(proc.stderr) > 1000 else proc.stderr,
                    "duration_s": round(duration, 1),
                })
                logger.info("Test '%s': exit %d (%.1fs)", cmd, proc.returncode, duration)
            except subprocess.TimeoutExpired:
                duration = time.time() - start
                results.append({"command": cmd, "exit_code": -1, "stdout": "", "stderr": f"Timed out after {timeout}s", "duration_s": round(duration, 1)})
                logger.warning("Test timed out: %s", cmd)
            except Exception as e:
                results.append({"command": cmd, "exit_code": -1, "stdout": "", "stderr": str(e), "duration_s": 0})

        self.test_results = results
        return results

    def commit_changes(self, message: str) -> str | None:
        """Stage all changes and commit. Returns commit SHA or None on failure."""
        self._run_git("add", "-A")

        # Check if there are changes to commit
        status = self._run_git("status", "--porcelain")
        if not status.stdout.strip():
            logger.info("No changes to commit")
            return None

        result = self._run_git("commit", "-m", message)
        if result.returncode != 0:
            logger.error("Commit failed: %s", result.stderr)
            return None

        # Get commit SHA
        sha_result = self._run_git("rev-parse", "HEAD")
        sha = sha_result.stdout.strip()
        logger.info("Committed: %s", sha[:8])
        return sha

    def get_diff(self) -> str:
        """Return git diff of all staged/unstaged changes."""
        result = self._run_git("diff", "HEAD~1", "--stat")
        return result.stdout if result.returncode == 0 else ""

    def rollback(self):
        """Return to original branch and delete the feature branch."""
        if self.original_branch:
            self._run_git("checkout", self.original_branch)
            # Pop stash if we stashed earlier
            self._run_git("stash", "pop")
            if self.branch_name:
                self._run_git("branch", "-D", self.branch_name)
                logger.info("Rolled back: deleted branch %s", self.branch_name)

    def execute(self, crew_output: dict) -> dict:
        """Full pipeline: branch -> apply -> test -> commit -> return to original branch.

        Returns execution result dict.
        """
        if self.dry_run:
            return {
                "status": "dry_run",
                "branch": None,
                "changes": [],
                "test_results": [],
                "commit_sha": None,
                "diff": "",
            }

        code_changes = crew_output.get("code_changes", [])
        if not code_changes:
            return {
                "status": "no_changes",
                "branch": None,
                "changes": [],
                "test_results": [],
                "commit_sha": None,
                "diff": "",
            }

        task_summary = crew_output.get("summary", crew_output.get("task", "engineering-task"))

        try:
            # 1. Create branch
            branch = self.create_branch(task_summary)

            # 2. Apply changes
            changes = self.apply_changes(code_changes)
            failed = [c for c in changes if c["status"] == "error"]
            if failed:
                logger.error("Apply failed for %d file(s), rolling back", len(failed))
                self.rollback()
                return {
                    "status": "apply_failed",
                    "branch": branch,
                    "changes": changes,
                    "test_results": [],
                    "commit_sha": None,
                    "diff": "",
                    "error": f"{len(failed)} file(s) failed to apply",
                }

            # 3. Commit (before tests, so tests run against committed code)
            commit_msg = f"eng: {task_summary[:60]}\n\nAutomated by OpenFounder engineering crew."
            commit_sha = self.commit_changes(commit_msg)

            # 4. Run tests
            test_commands = crew_output.get("test_commands", [])
            test_results = self.run_tests(test_commands) if test_commands else []
            tests_passed = all(t["exit_code"] == 0 for t in test_results) if test_results else True

            # 5. Get diff
            diff = self.get_diff()

            # 6. Return to original branch (leave feature branch intact)
            if self.original_branch:
                self._run_git("checkout", self.original_branch)
                self._run_git("stash", "pop")

            status = "success" if tests_passed else "tests_failed"

            return {
                "status": status,
                "branch": branch,
                "changes": changes,
                "test_results": test_results,
                "commit_sha": commit_sha,
                "diff": diff,
            }

        except Exception as e:
            logger.error("Executor failed: %s", e)
            try:
                self.rollback()
            except Exception:
                pass
            return {
                "status": "error",
                "branch": self.branch_name,
                "changes": self.changes_applied,
                "test_results": self.test_results,
                "commit_sha": None,
                "diff": "",
                "error": str(e),
            }
