# tests/test_supervisor.py

import json
import os
import pytest
from unittest.mock import patch, MagicMock
from evolution.supervisor import Supervisor


def _make_supervisor(tmp_path):
    """
    Create a Supervisor with a real temporary project root.
    Git operations are mocked at the GitManager level to avoid
    requiring an actual git repository.
    """
    (tmp_path / "main_app.py").write_text("def main(): pass\n")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="main", stderr="")
        supervisor = Supervisor(str(tmp_path))
    return supervisor


class TestSupervisorInitFiles:
    def test_creates_logs_directory(self, tmp_path):
        _make_supervisor(tmp_path)
        assert (tmp_path / "logs").is_dir()

    def test_creates_evolution_directory(self, tmp_path):
        _make_supervisor(tmp_path)
        assert (tmp_path / "evolution").is_dir()

    def test_creates_log_file(self, tmp_path):
        _make_supervisor(tmp_path)
        assert (tmp_path / "logs" / "system.log").exists()

    def test_creates_feature_queue_json(self, tmp_path):
        _make_supervisor(tmp_path)
        queue_path = tmp_path / "evolution" / "feature_queue.json"
        assert queue_path.exists()
        assert json.loads(queue_path.read_text()) == []

    def test_creates_memory_json(self, tmp_path):
        _make_supervisor(tmp_path)
        memory_path = tmp_path / "evolution" / "memory.json"
        assert memory_path.exists()
        assert json.loads(memory_path.read_text()) == []

    def test_does_not_overwrite_existing_queue(self, tmp_path):
        (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
        (tmp_path / "logs" / "system.log").write_text("")
        evo_dir = tmp_path / "evolution"
        evo_dir.mkdir(parents=True, exist_ok=True)
        existing_queue = [{"name": "existing-feature"}]
        (evo_dir / "feature_queue.json").write_text(json.dumps(existing_queue))
        (evo_dir / "memory.json").write_text("[]")
        (tmp_path / "main_app.py").write_text("def main(): pass\n")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="main", stderr="")
            supervisor = Supervisor(str(tmp_path))
        data = json.loads((evo_dir / "feature_queue.json").read_text())
        assert data == existing_queue


class TestSupervisorReadSource:
    def test_reads_default_target_file(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        content = supervisor.read_source()
        assert content == "def main(): pass\n"

    def test_reads_explicit_filepath(self, tmp_path):
        other = tmp_path / "other.py"
        other.write_text("x = 1\n")
        supervisor = _make_supervisor(tmp_path)
        assert supervisor.read_source(str(other)) == "x = 1\n"

    def test_missing_file_returns_none(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        assert supervisor.read_source(str(tmp_path / "missing.py")) is None


class TestSupervisorSaveMemory:
    def test_appends_entry_to_memory(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        entry = {"type": "bug_fix", "status": "success"}
        supervisor.save_memory(entry)
        data = json.loads((tmp_path / "evolution" / "memory.json").read_text())
        assert len(data) == 1
        assert data[0] == entry

    def test_multiple_entries_accumulate(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        supervisor.save_memory({"type": "bug_fix"})
        supervisor.save_memory({"type": "feature"})
        data = json.loads((tmp_path / "evolution" / "memory.json").read_text())
        assert len(data) == 2


class TestSupervisorClearLog:
    def test_clears_log_content(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        log_file = tmp_path / "logs" / "system.log"
        log_file.write_text("ZeroDivisionError: division by zero\n")
        supervisor.clear_log()
        assert log_file.read_text() == ""


class TestSupervisorFeatureQueue:
    def test_load_feature_queue_returns_list(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        queue = [{"name": "feat1"}, {"name": "feat2"}]
        (tmp_path / "evolution" / "feature_queue.json").write_text(json.dumps(queue))
        assert supervisor.load_feature_queue() == queue

    def test_load_feature_queue_returns_empty_on_error(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        (tmp_path / "evolution" / "feature_queue.json").write_text("not-json")
        assert supervisor.load_feature_queue() == []

    def test_save_feature_queue_writes_list(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        queue = [{"name": "new-feat"}]
        supervisor.save_feature_queue(queue)
        data = json.loads((tmp_path / "evolution" / "feature_queue.json").read_text())
        assert data == queue


class TestSupervisorProcessBugFix:
    def test_no_issue_returns_false(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        with patch.object(supervisor.observer, "act", return_value=None):
            result = supervisor.process_bug_fix()
        assert result is False

    def test_missing_source_returns_false(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        supervisor.target_file = str(tmp_path / "missing.py")
        issue = {"type": "Error", "log_excerpt": "err"}
        with patch.object(supervisor.observer, "act", return_value=issue):
            result = supervisor.process_bug_fix()
        assert result is False

    def test_patch_rejected_by_auditor_returns_false(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        issue = {"type": "Error", "log_excerpt": "err"}
        with (
            patch.object(supervisor.observer, "act", return_value=issue),
            patch.object(supervisor.architect, "act", return_value="bad patch"),
            patch.object(supervisor.auditor, "act", return_value=False),
            patch.object(supervisor.git, "create_evolution_branch", return_value=None),
        ):
            result = supervisor.process_bug_fix()
        assert result is False

    def test_sandbox_failure_returns_false(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        issue = {"type": "Error", "log_excerpt": "err"}
        with (
            patch.object(supervisor.observer, "act", return_value=issue),
            patch.object(supervisor.architect, "act", return_value="patch"),
            patch.object(supervisor.auditor, "act", return_value=True),
            patch.object(supervisor.sandbox, "verify_and_apply", return_value=False),
            patch.object(supervisor.git, "create_evolution_branch", return_value=None),
        ):
            result = supervisor.process_bug_fix()
        assert result is False

    def test_tests_fail_after_patch_returns_false(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        issue = {"type": "Error", "log_excerpt": "err"}
        with (
            patch.object(supervisor.observer, "act", return_value=issue),
            patch.object(supervisor.architect, "act", return_value="patch"),
            patch.object(supervisor.auditor, "act", return_value=True),
            patch.object(supervisor.sandbox, "verify_and_apply", return_value=True),
            patch.object(supervisor.sandbox, "run_tests", return_value=False),
            patch.object(supervisor.git, "create_evolution_branch", return_value=None),
        ):
            result = supervisor.process_bug_fix()
        assert result is False

    def test_full_success_returns_true(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        issue = {"type": "ZeroDivisionError", "log_excerpt": "division by zero"}
        with (
            patch.object(supervisor.observer, "act", return_value=issue),
            patch.object(supervisor.architect, "act", return_value="def f(): pass\n"),
            patch.object(supervisor.auditor, "act", return_value=True),
            patch.object(supervisor.sandbox, "verify_and_apply", return_value=True),
            patch.object(supervisor.sandbox, "run_tests", return_value=True),
            patch.object(supervisor.git, "create_evolution_branch", return_value=None),
        ):
            result = supervisor.process_bug_fix()
        assert result is True

    def test_success_saves_memory_entry(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        issue = {"type": "TypeError", "log_excerpt": "type error"}
        with (
            patch.object(supervisor.observer, "act", return_value=issue),
            patch.object(supervisor.architect, "act", return_value="def f(): pass\n"),
            patch.object(supervisor.auditor, "act", return_value=True),
            patch.object(supervisor.sandbox, "verify_and_apply", return_value=True),
            patch.object(supervisor.sandbox, "run_tests", return_value=True),
            patch.object(supervisor.git, "create_evolution_branch", return_value=None),
        ):
            supervisor.process_bug_fix()
        data = json.loads((tmp_path / "evolution" / "memory.json").read_text())
        assert len(data) == 1
        assert data[0]["type"] == "bug_fix"
        assert data[0]["issue"] == "TypeError"

    def test_success_clears_log(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        log_file = tmp_path / "logs" / "system.log"
        log_file.write_text("TypeError: something failed\n")
        issue = {"type": "TypeError", "log_excerpt": "type error"}
        with (
            patch.object(supervisor.observer, "act", return_value=issue),
            patch.object(supervisor.architect, "act", return_value="def f(): pass\n"),
            patch.object(supervisor.auditor, "act", return_value=True),
            patch.object(supervisor.sandbox, "verify_and_apply", return_value=True),
            patch.object(supervisor.sandbox, "run_tests", return_value=True),
            patch.object(supervisor.git, "create_evolution_branch", return_value=None),
        ):
            supervisor.process_bug_fix()
        assert log_file.read_text() == ""

    def test_success_with_git_branch_commits_and_merges(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        issue = {"type": "Error", "log_excerpt": "err"}
        with (
            patch.object(supervisor.observer, "act", return_value=issue),
            patch.object(supervisor.architect, "act", return_value="def f(): pass\n"),
            patch.object(supervisor.auditor, "act", return_value=True),
            patch.object(supervisor.sandbox, "verify_and_apply", return_value=True),
            patch.object(supervisor.sandbox, "run_tests", return_value=True),
            patch.object(
                supervisor.git,
                "create_evolution_branch",
                return_value="fix/evolution-123",
            ),
            patch.object(supervisor.git, "commit_changes") as mock_commit,
            patch.object(supervisor.git, "merge_to_main") as mock_merge,
        ):
            supervisor.process_bug_fix()
        mock_commit.assert_called_once()
        mock_merge.assert_called_once_with("fix/evolution-123")


class TestSupervisorProcessFeatureRequest:
    def test_empty_queue_returns_false(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        with patch.object(supervisor, "load_feature_queue", return_value=[]):
            result = supervisor.process_feature_request()
        assert result is False

    def test_planner_failure_returns_false(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        queue = [{"name": "test-feature", "description": "do something"}]
        with (
            patch.object(supervisor, "load_feature_queue", return_value=list(queue)),
            patch.object(supervisor.planner, "implement_feature", return_value=None),
            patch.object(supervisor.git, "create_evolution_branch", return_value=None),
            patch.object(supervisor, "save_feature_queue") as mock_save,
        ):
            result = supervisor.process_feature_request()
        assert result is False
        # Failed feature should be removed from queue
        mock_save.assert_called()

    def test_feature_applied_successfully(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        feature = {"name": "logging", "description": "add logging"}
        feature_result = {
            "plan": "add a logger",
            "files_to_update": {},
            "new_files": {},
        }
        with (
            patch.object(supervisor, "load_feature_queue", return_value=[feature]),
            patch.object(
                supervisor.planner, "implement_feature", return_value=feature_result
            ),
            patch.object(supervisor.sandbox, "apply_feature_files", return_value=True),
            patch.object(supervisor.sandbox, "run_tests", return_value=True),
            patch.object(supervisor.git, "create_evolution_branch", return_value=None),
            patch.object(supervisor, "save_feature_queue"),
        ):
            result = supervisor.process_feature_request()
        assert result is True

    def test_failed_tests_requeues_feature(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        feature = {"name": "new-feature", "description": "desc"}
        feature_result = {"plan": "plan", "files_to_update": {}, "new_files": {}}
        saved_queues = []
        with (
            patch.object(supervisor, "load_feature_queue", return_value=[feature]),
            patch.object(
                supervisor.planner, "implement_feature", return_value=feature_result
            ),
            patch.object(supervisor.sandbox, "apply_feature_files", return_value=True),
            patch.object(supervisor.sandbox, "run_tests", return_value=False),
            patch.object(supervisor.git, "create_evolution_branch", return_value=None),
            patch.object(
                supervisor, "save_feature_queue", side_effect=lambda q: saved_queues.append(q)
            ),
        ):
            result = supervisor.process_feature_request()
        assert result is False
        # Feature should have been requeued
        assert any(len(q) > 0 for q in saved_queues)

    def test_feature_success_saves_memory(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        feature = {"name": "logging", "description": "add logging"}
        feature_result = {"plan": "add a logger", "files_to_update": {}, "new_files": {}}
        with (
            patch.object(supervisor, "load_feature_queue", return_value=[feature]),
            patch.object(
                supervisor.planner, "implement_feature", return_value=feature_result
            ),
            patch.object(supervisor.sandbox, "apply_feature_files", return_value=True),
            patch.object(supervisor.sandbox, "run_tests", return_value=True),
            patch.object(supervisor.git, "create_evolution_branch", return_value=None),
            patch.object(supervisor, "save_feature_queue"),
        ):
            supervisor.process_feature_request()
        data = json.loads((tmp_path / "evolution" / "memory.json").read_text())
        assert len(data) == 1
        assert data[0]["type"] == "feature"
        assert data[0]["name"] == "logging"

    def test_feature_success_with_git_commits(self, tmp_path):
        supervisor = _make_supervisor(tmp_path)
        feature = {"name": "logging", "description": "add logging"}
        feature_result = {"plan": "add a logger", "files_to_update": {}, "new_files": {}}
        with (
            patch.object(supervisor, "load_feature_queue", return_value=[feature]),
            patch.object(
                supervisor.planner, "implement_feature", return_value=feature_result
            ),
            patch.object(supervisor.sandbox, "apply_feature_files", return_value=True),
            patch.object(supervisor.sandbox, "run_tests", return_value=True),
            patch.object(
                supervisor.git,
                "create_evolution_branch",
                return_value="feature/evolution-999",
            ),
            patch.object(supervisor.git, "commit_changes") as mock_commit,
            patch.object(supervisor.git, "merge_to_main") as mock_merge,
            patch.object(supervisor, "save_feature_queue"),
        ):
            supervisor.process_feature_request()
        mock_commit.assert_called_once()
        mock_merge.assert_called_once_with("feature/evolution-999")
