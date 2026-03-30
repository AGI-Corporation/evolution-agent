# tests/test_version_control.py
# Unit tests for the GitManager component

import pytest
from unittest.mock import patch, MagicMock
from evolution.version_control import GitManager


@pytest.fixture
def git(tmp_path):
    """Return a GitManager pointing at a temp directory."""
    with patch.object(GitManager, "_detect_default_branch", return_value="main"):
        return GitManager(str(tmp_path))


class TestGitManagerInit:
    def test_default_branch_set(self, git):
        assert git._default_branch == "main"

    def test_custom_default_branch(self, tmp_path):
        with patch.object(GitManager, "_detect_default_branch", return_value="master"):
            gm = GitManager(str(tmp_path))
        assert gm._default_branch == "master"


class TestRunGit:
    def test_returns_false_on_error(self, git):
        success, _ = git._run_git(["this-command-does-not-exist"])
        assert success is False

    def test_returns_true_on_success(self, git):
        # `git --version` always works
        success, output = git._run_git(["--version"])
        assert success is True
        assert "git version" in output


class TestGitManagerBranchName:
    def test_create_evolution_branch_prefix_fix(self, git):
        with patch.object(git, "create_branch", return_value=True):
            branch = git.create_evolution_branch(prefix="fix")
        assert branch is not None
        assert branch.startswith("fix/evolution-")

    def test_create_evolution_branch_prefix_feature(self, git):
        with patch.object(git, "create_branch", return_value=True):
            branch = git.create_evolution_branch(prefix="feature")
        assert branch.startswith("feature/evolution-")

    def test_returns_none_if_create_fails(self, git):
        with patch.object(git, "create_branch", return_value=False):
            branch = git.create_evolution_branch()
        assert branch is None


class TestMergeToMain:
    def test_merges_into_default_branch(self, git):
        calls = []

        def fake_run_git(cmd):
            calls.append(cmd)
            return True, "ok"

        git._run_git = fake_run_git
        git.merge_to_main("fix/evolution-123")

        # First call should be checkout of the default branch
        assert calls[0] == ["checkout", "main"]
