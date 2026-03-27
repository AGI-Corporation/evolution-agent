# tests/test_version_control.py

import subprocess
import pytest
from unittest.mock import patch, MagicMock, call
from evolution.version_control import GitManager


def _make_manager(tmp_path):
    return GitManager(str(tmp_path))


def _ok(output=""):
    return MagicMock(returncode=0, stdout=output, stderr="")


def _fail(stderr="git error"):
    proc = MagicMock()
    proc.returncode = 1
    proc.stderr = stderr
    raise subprocess.CalledProcessError(1, "git", stderr=stderr)


class TestGitManagerRunGit:
    def test_success_returns_true_and_stdout(self, tmp_path):
        manager = _make_manager(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="output text", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            success, output = manager._run_git(["status"])
        assert success is True
        assert output == "output text"

    def test_called_process_error_returns_false(self, tmp_path):
        manager = _make_manager(tmp_path)
        err = subprocess.CalledProcessError(1, "git", stderr="fatal: not a git repo")
        with patch("subprocess.run", side_effect=err):
            success, output = manager._run_git(["status"])
        assert success is False
        assert "not a git repo" in output

    def test_timeout_returns_false(self, tmp_path):
        manager = _make_manager(tmp_path)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 60)):
            success, output = manager._run_git(["log"])
        assert success is False
        assert "timed out" in output.lower()

    def test_uses_repo_path_as_cwd(self, tmp_path):
        manager = _make_manager(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            manager._run_git(["status"])
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == str(tmp_path)


class TestGitManagerGetCurrentBranch:
    def test_returns_branch_name_on_success(self, tmp_path):
        manager = _make_manager(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="main", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            branch = manager.get_current_branch()
        assert branch == "main"

    def test_returns_unknown_on_failure(self, tmp_path):
        manager = _make_manager(tmp_path)
        err = subprocess.CalledProcessError(1, "git", stderr="")
        with patch("subprocess.run", side_effect=err):
            branch = manager.get_current_branch()
        assert branch == "unknown"


class TestGitManagerCreateBranch:
    def test_success_returns_true(self, tmp_path):
        manager = _make_manager(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = manager.create_branch("feature/test-branch")
        assert result is True

    def test_failure_returns_false(self, tmp_path):
        manager = _make_manager(tmp_path)
        err = subprocess.CalledProcessError(1, "git", stderr="already exists")
        with patch("subprocess.run", side_effect=err):
            result = manager.create_branch("feature/existing")
        assert result is False


class TestGitManagerCheckoutBranch:
    def test_success_returns_true(self, tmp_path):
        manager = _make_manager(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = manager.checkout_branch("main")
        assert result is True

    def test_failure_returns_false(self, tmp_path):
        manager = _make_manager(tmp_path)
        err = subprocess.CalledProcessError(1, "git", stderr="did not match any file")
        with patch("subprocess.run", side_effect=err):
            result = manager.checkout_branch("nonexistent")
        assert result is False


class TestGitManagerStageAll:
    def test_stage_all_success(self, tmp_path):
        manager = _make_manager(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = manager.stage_all()
        assert result is True

    def test_stage_all_failure(self, tmp_path):
        manager = _make_manager(tmp_path)
        err = subprocess.CalledProcessError(1, "git", stderr="error")
        with patch("subprocess.run", side_effect=err):
            result = manager.stage_all()
        assert result is False


class TestGitManagerCommitChanges:
    def test_commit_success(self, tmp_path):
        manager = _make_manager(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="[main abc123] fix: msg", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = manager.commit_changes("fix: some bug")
        assert result is True

    def test_nothing_to_commit_returns_true(self, tmp_path):
        manager = _make_manager(tmp_path)
        err = subprocess.CalledProcessError(1, "git", stderr="nothing to commit")
        with patch("subprocess.run", side_effect=err):
            result = manager.commit_changes("fix: nothing")
        assert result is True

    def test_commit_failure_returns_false(self, tmp_path):
        manager = _make_manager(tmp_path)

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # stage_all: success
                return MagicMock(returncode=0, stdout="", stderr="")
            # commit: failure
            raise subprocess.CalledProcessError(1, "git", stderr="commit failed")

        with patch("subprocess.run", side_effect=side_effect):
            result = manager.commit_changes("fix: failing commit")
        assert result is False


class TestGitManagerRollback:
    def test_rollback_success(self, tmp_path):
        manager = _make_manager(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="HEAD is now at abc", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = manager.rollback(steps=1)
        assert result is True

    def test_rollback_failure(self, tmp_path):
        manager = _make_manager(tmp_path)
        err = subprocess.CalledProcessError(1, "git", stderr="bad revision")
        with patch("subprocess.run", side_effect=err):
            result = manager.rollback()
        assert result is False

    def test_rollback_uses_correct_steps(self, tmp_path):
        manager = _make_manager(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            manager.rollback(steps=3)
        cmd = mock_run.call_args[0][0]
        assert "HEAD~3" in cmd


class TestGitManagerMergeToMain:
    def test_merge_success(self, tmp_path):
        manager = _make_manager(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="Merge made", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = manager.merge_to_main("fix/evolution-123")
        assert result is True

    def test_merge_failure_returns_false(self, tmp_path):
        manager = _make_manager(tmp_path)
        # checkout succeeds, merge fails
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return MagicMock(returncode=0, stdout="", stderr="")
            raise subprocess.CalledProcessError(1, "git", stderr="conflict")

        with patch("subprocess.run", side_effect=side_effect):
            result = manager.merge_to_main("feature/broken")
        assert result is False


class TestGitManagerCreateEvolutionBranch:
    def test_returns_branch_name_on_success(self, tmp_path):
        manager = _make_manager(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            name = manager.create_evolution_branch(prefix="fix")
        assert name is not None
        assert name.startswith("fix/evolution-")

    def test_returns_none_on_failure(self, tmp_path):
        manager = _make_manager(tmp_path)
        err = subprocess.CalledProcessError(1, "git", stderr="error")
        with patch("subprocess.run", side_effect=err):
            name = manager.create_evolution_branch(prefix="fix")
        assert name is None

    def test_prefix_used_in_branch_name(self, tmp_path):
        manager = _make_manager(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            name = manager.create_evolution_branch(prefix="feature")
        assert name.startswith("feature/evolution-")


class TestGitManagerGetLog:
    def test_returns_log_on_success(self, tmp_path):
        manager = _make_manager(tmp_path)
        log_output = "abc123 first commit\ndef456 second commit"
        mock_result = MagicMock(returncode=0, stdout=log_output, stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = manager.get_log(n=2)
        assert result == log_output

    def test_returns_empty_on_failure(self, tmp_path):
        manager = _make_manager(tmp_path)
        err = subprocess.CalledProcessError(1, "git", stderr="no commits")
        with patch("subprocess.run", side_effect=err):
            result = manager.get_log()
        assert result == ""


class TestGitManagerStatus:
    def test_returns_status_on_success(self, tmp_path):
        manager = _make_manager(tmp_path)
        mock_result = MagicMock(returncode=0, stdout="M  main_app.py", stderr="")
        with patch("subprocess.run", return_value=mock_result):
            result = manager.status()
        assert result == "M  main_app.py"

    def test_returns_empty_on_failure(self, tmp_path):
        manager = _make_manager(tmp_path)
        err = subprocess.CalledProcessError(1, "git", stderr="not a repo")
        with patch("subprocess.run", side_effect=err):
            result = manager.status()
        assert result == ""
