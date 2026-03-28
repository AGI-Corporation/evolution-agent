# tests/test_version_control.py
# Tests for evolution/version_control.py

import subprocess
import pytest
from unittest.mock import MagicMock, patch, call
from evolution.version_control import GitManager


@pytest.fixture
def git(tmp_path):
    return GitManager(str(tmp_path))


# ---------------------------------------------------------------------------
# _run_git
# ---------------------------------------------------------------------------

class TestRunGit:
    def test_success_returns_true_and_output(self, git):
        mock_result = MagicMock()
        mock_result.stdout = "  main  "
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            mock_run.return_value = mock_result
            # CalledProcessError not raised means check=True passed
            success, output = git._run_git(["status"])
        assert success is True
        assert output == "main"

    def test_called_process_error_returns_false(self, git):
        err = subprocess.CalledProcessError(1, "git")
        err.stderr = "fatal: not a git repository"
        with patch("subprocess.run", side_effect=err):
            success, output = git._run_git(["status"])
        assert success is False
        assert "not a git repository" in output

    def test_timeout_returns_false(self, git):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 60)):
            success, output = git._run_git(["status"])
        assert success is False
        assert "timed out" in output.lower()


# ---------------------------------------------------------------------------
# get_current_branch
# ---------------------------------------------------------------------------

class TestGetCurrentBranch:
    def test_returns_branch_name(self, git):
        with patch.object(git, "_run_git", return_value=(True, "main")):
            assert git.get_current_branch() == "main"

    def test_failure_returns_unknown(self, git):
        with patch.object(git, "_run_git", return_value=(False, "error")):
            assert git.get_current_branch() == "unknown"


# ---------------------------------------------------------------------------
# create_branch
# ---------------------------------------------------------------------------

class TestCreateBranch:
    def test_success_returns_true(self, git):
        with patch.object(git, "_run_git", return_value=(True, "")):
            assert git.create_branch("feature/test") is True

    def test_failure_returns_false(self, git):
        with patch.object(git, "_run_git", return_value=(False, "already exists")):
            assert git.create_branch("feature/test") is False


# ---------------------------------------------------------------------------
# checkout_branch
# ---------------------------------------------------------------------------

class TestCheckoutBranch:
    def test_success_returns_true(self, git):
        with patch.object(git, "_run_git", return_value=(True, "")):
            assert git.checkout_branch("main") is True

    def test_failure_returns_false(self, git):
        with patch.object(git, "_run_git", return_value=(False, "error")):
            assert git.checkout_branch("main") is False


# ---------------------------------------------------------------------------
# stage_all
# ---------------------------------------------------------------------------

class TestStageAll:
    def test_success_returns_true(self, git):
        with patch.object(git, "_run_git", return_value=(True, "")):
            assert git.stage_all() is True

    def test_failure_returns_false(self, git):
        with patch.object(git, "_run_git", return_value=(False, "error")):
            assert git.stage_all() is False


# ---------------------------------------------------------------------------
# commit_changes
# ---------------------------------------------------------------------------

class TestCommitChanges:
    def test_successful_commit_returns_true(self, git):
        with patch.object(git, "_run_git", return_value=(True, "committed")):
            result = git.commit_changes("fix: something")
        assert result is True

    def test_nothing_to_commit_returns_true(self, git):
        # stage_all succeeds, commit returns "nothing to commit"
        responses = [(True, ""), (False, "nothing to commit")]
        with patch.object(git, "_run_git", side_effect=responses):
            result = git.commit_changes("fix: nothing")
        assert result is True

    def test_commit_failure_returns_false(self, git):
        responses = [(True, ""), (False, "real error")]
        with patch.object(git, "_run_git", side_effect=responses):
            result = git.commit_changes("fix: something")
        assert result is False


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------

class TestRollback:
    def test_success_returns_true(self, git):
        with patch.object(git, "_run_git", return_value=(True, "")):
            assert git.rollback() is True

    def test_failure_returns_false(self, git):
        with patch.object(git, "_run_git", return_value=(False, "error")):
            assert git.rollback() is False

    def test_uses_head_tilde_steps(self, git):
        with patch.object(git, "_run_git", return_value=(True, "")) as mock:
            git.rollback(steps=3)
        args = mock.call_args[0][0]
        assert "HEAD~3" in args


# ---------------------------------------------------------------------------
# merge_to_main
# ---------------------------------------------------------------------------

class TestMergeToMain:
    def test_successful_merge_returns_true(self, git):
        with patch.object(git, "_run_git", return_value=(True, "")) as mock_git, \
             patch.object(git, "checkout_branch", return_value=True):
            result = git.merge_to_main("feature/test")
        assert result is True

    def test_failed_merge_returns_false(self, git):
        responses = [(False, "conflict")]
        with patch.object(git, "checkout_branch", return_value=True), \
             patch.object(git, "_run_git", side_effect=responses):
            result = git.merge_to_main("feature/test")
        assert result is False

    def test_checks_out_main_first(self, git):
        with patch.object(git, "checkout_branch", return_value=True) as mock_co, \
             patch.object(git, "_run_git", return_value=(True, "")):
            git.merge_to_main("feature/test")
        mock_co.assert_called_once_with("main")


# ---------------------------------------------------------------------------
# create_evolution_branch
# ---------------------------------------------------------------------------

class TestCreateEvolutionBranch:
    def test_returns_branch_name_on_success(self, git):
        with patch.object(git, "create_branch", return_value=True):
            name = git.create_evolution_branch(prefix="fix")
        assert name is not None
        assert name.startswith("fix/evolution-")

    def test_returns_none_on_failure(self, git):
        with patch.object(git, "create_branch", return_value=False):
            name = git.create_evolution_branch()
        assert name is None

    def test_custom_prefix(self, git):
        with patch.object(git, "create_branch", return_value=True):
            name = git.create_evolution_branch(prefix="feature")
        assert name.startswith("feature/evolution-")


# ---------------------------------------------------------------------------
# get_log and status
# ---------------------------------------------------------------------------

class TestGetLogAndStatus:
    def test_get_log_success(self, git):
        with patch.object(git, "_run_git", return_value=(True, "abc123 commit msg")):
            result = git.get_log(n=5)
        assert "commit msg" in result

    def test_get_log_failure(self, git):
        with patch.object(git, "_run_git", return_value=(False, "error")):
            result = git.get_log()
        assert result == ""

    def test_status_success(self, git):
        with patch.object(git, "_run_git", return_value=(True, "M main_app.py")):
            result = git.status()
        assert "main_app.py" in result

    def test_status_failure(self, git):
        with patch.object(git, "_run_git", return_value=(False, "error")):
            result = git.status()
        assert result == ""
