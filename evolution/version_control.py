# evolution/version_control.py
# Git integration for safe rollback and evolution tracking

import subprocess
import os
from datetime import datetime


class GitManager:
    """
    Manages Git operations for safe evolution tracking.
    Every code change is committed to a branch, making all evolutions
    permanent, auditable, and reversible.
    """

    def __init__(self, repo_path):
        self.repo_path = repo_path

    def _run_git(self, command):
        """
        Execute a git command in the repo directory.
        Returns (success: bool, output: str)
        """
        try:
            result = subprocess.run(
                ["git"] + command,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "Git command timed out."

    def get_current_branch(self):
        """Return the name of the current git branch."""
        success, output = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return output if success else "unknown"

    def create_branch(self, branch_name):
        """Create and checkout a new branch for a fix evolution."""
        print(f"[Git] Creating safety branch: {branch_name}")
        success, msg = self._run_git(["checkout", "-b", branch_name])
        if not success:
            print(f"[Git] Failed to create branch: {msg}")
        return success

    def checkout_branch(self, branch_name):
        """Checkout an existing branch."""
        success, msg = self._run_git(["checkout", branch_name])
        if not success:
            print(f"[Git] Failed to checkout branch {branch_name}: {msg}")
        return success

    def stage_all(self):
        """Stage all changes."""
        success, msg = self._run_git(["add", "."])
        return success

    def commit_changes(self, message):
        """
        Stage and commit all current changes.
        Returns True if commit was successful.
        """
        self.stage_all()
        success, msg = self._run_git(["commit", "-m", message, "--no-verify"])
        if success:
            print(f"[Git] Committed: {message}")
        else:
            # Check if there's nothing to commit
            if "nothing to commit" in msg:
                print(f"[Git] Nothing to commit.")
                return True
            print(f"[Git] Commit failed: {msg}")
        return success

    def rollback(self, steps=1):
        """
        Roll back the last N commits.
        Used when an evolution causes critical failures.
        """
        print(f"[Git] Rolling back {steps} commit(s)...")
        success, msg = self._run_git(["reset", "--hard", f"HEAD~{steps}"])
        if success:
            print(f"[Git] Rollback successful.")
        else:
            print(f"[Git] Rollback failed: {msg}")
        return success

    def merge_to_main(self, branch_name):
        """
        Merge a fix/feature branch back to main after successful evolution.
        """
        print(f"[Git] Merging {branch_name} into main...")
        self.checkout_branch("main")
        success, msg = self._run_git(["merge", branch_name, "--no-ff", "-m", f"Merge evolution branch: {branch_name}"])
        if success:
            print(f"[Git] Merge successful.")
            # Clean up the fix branch
            self._run_git(["branch", "-d", branch_name])
        else:
            print(f"[Git] Merge failed: {msg}")
        return success

    def create_evolution_branch(self, prefix="fix"):
        """
        Create a uniquely named evolution branch.
        Returns the branch name.
        """
        timestamp = int(datetime.now().timestamp())
        branch_name = f"{prefix}/evolution-{timestamp}"
        success = self.create_branch(branch_name)
        return branch_name if success else None

    def get_log(self, n=10):
        """Return the last N commit messages."""
        success, output = self._run_git(["log", f"--oneline", f"-{n}"])
        return output if success else ""

    def status(self):
        """Return the current git status."""
        success, output = self._run_git(["status", "--short"])
        return output if success else ""
