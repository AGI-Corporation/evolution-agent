# tests/test_supervisor.py
# Tests for evolution/supervisor.py

import json
import os
import pytest
from unittest.mock import MagicMock, patch
from evolution.supervisor import Supervisor


@pytest.fixture
def tmp_project(tmp_path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "evolution").mkdir()
    (tmp_path / "logs" / "system.log").write_text("")
    (tmp_path / "main_app.py").write_text("def main(): pass\n")
    return tmp_path


@pytest.fixture
def supervisor(tmp_project):
    with patch("evolution.supervisor.ObserverAgent"), \
         patch("evolution.supervisor.ArchitectAgent"), \
         patch("evolution.supervisor.AuditorAgent"), \
         patch("evolution.supervisor.PlannerAgent"), \
         patch("evolution.supervisor.Sandbox"), \
         patch("evolution.supervisor.GitManager"):
        sup = Supervisor(str(tmp_project))
    return sup


# ---------------------------------------------------------------------------
# __init__ and _init_files
# ---------------------------------------------------------------------------

class TestSupervisorInit:
    def test_directories_created(self, tmp_path):
        with patch("evolution.supervisor.ObserverAgent"), \
             patch("evolution.supervisor.ArchitectAgent"), \
             patch("evolution.supervisor.AuditorAgent"), \
             patch("evolution.supervisor.PlannerAgent"), \
             patch("evolution.supervisor.Sandbox"), \
             patch("evolution.supervisor.GitManager"):
            sup = Supervisor(str(tmp_path))
        assert os.path.isdir(os.path.join(str(tmp_path), "logs"))
        assert os.path.isdir(os.path.join(str(tmp_path), "evolution"))

    def test_log_file_created(self, tmp_path):
        with patch("evolution.supervisor.ObserverAgent"), \
             patch("evolution.supervisor.ArchitectAgent"), \
             patch("evolution.supervisor.AuditorAgent"), \
             patch("evolution.supervisor.PlannerAgent"), \
             patch("evolution.supervisor.Sandbox"), \
             patch("evolution.supervisor.GitManager"):
            sup = Supervisor(str(tmp_path))
        log_path = os.path.join(str(tmp_path), "logs", "system.log")
        assert os.path.exists(log_path)

    def test_queue_file_created_with_empty_list(self, tmp_path):
        with patch("evolution.supervisor.ObserverAgent"), \
             patch("evolution.supervisor.ArchitectAgent"), \
             patch("evolution.supervisor.AuditorAgent"), \
             patch("evolution.supervisor.PlannerAgent"), \
             patch("evolution.supervisor.Sandbox"), \
             patch("evolution.supervisor.GitManager"):
            sup = Supervisor(str(tmp_path))
        queue_path = os.path.join(str(tmp_path), "evolution", "feature_queue.json")
        assert os.path.exists(queue_path)
        with open(queue_path) as f:
            assert json.load(f) == []

    def test_memory_file_created_with_empty_list(self, tmp_path):
        with patch("evolution.supervisor.ObserverAgent"), \
             patch("evolution.supervisor.ArchitectAgent"), \
             patch("evolution.supervisor.AuditorAgent"), \
             patch("evolution.supervisor.PlannerAgent"), \
             patch("evolution.supervisor.Sandbox"), \
             patch("evolution.supervisor.GitManager"):
            sup = Supervisor(str(tmp_path))
        memory_path = os.path.join(str(tmp_path), "evolution", "memory.json")
        assert os.path.exists(memory_path)
        with open(memory_path) as f:
            assert json.load(f) == []


# ---------------------------------------------------------------------------
# read_source
# ---------------------------------------------------------------------------

class TestReadSource:
    def test_reads_default_target(self, supervisor, tmp_project):
        (tmp_project / "main_app.py").write_text("x = 1\n")
        result = supervisor.read_source()
        assert result == "x = 1\n"

    def test_reads_custom_path(self, supervisor, tmp_project):
        custom = tmp_project / "custom.py"
        custom.write_text("y = 2\n")
        result = supervisor.read_source(str(custom))
        assert result == "y = 2\n"

    def test_missing_file_returns_none(self, supervisor):
        result = supervisor.read_source("/nonexistent/file.py")
        assert result is None


# ---------------------------------------------------------------------------
# save_memory
# ---------------------------------------------------------------------------

class TestSaveMemory:
    def test_appends_entry(self, supervisor):
        entry = {"type": "bug_fix", "status": "success"}
        supervisor.save_memory(entry)
        with open(supervisor.memory_path) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["type"] == "bug_fix"

    def test_multiple_entries_accumulate(self, supervisor):
        for i in range(3):
            supervisor.save_memory({"id": i})
        with open(supervisor.memory_path) as f:
            data = json.load(f)
        assert len(data) == 3


# ---------------------------------------------------------------------------
# clear_log
# ---------------------------------------------------------------------------

class TestClearLog:
    def test_clears_log_content(self, supervisor, tmp_project):
        (tmp_project / "logs" / "system.log").write_text("previous errors")
        supervisor.clear_log()
        assert (tmp_project / "logs" / "system.log").read_text() == ""


# ---------------------------------------------------------------------------
# load_feature_queue / save_feature_queue
# ---------------------------------------------------------------------------

class TestFeatureQueue:
    def test_load_empty_queue(self, supervisor):
        result = supervisor.load_feature_queue()
        assert result == []

    def test_load_populated_queue(self, supervisor, tmp_project):
        data = [{"name": "feat-a"}, {"name": "feat-b"}]
        (tmp_project / "evolution" / "feature_queue.json").write_text(json.dumps(data))
        result = supervisor.load_feature_queue()
        assert len(result) == 2

    def test_save_feature_queue(self, supervisor, tmp_project):
        queue = [{"name": "new-feat"}]
        supervisor.save_feature_queue(queue)
        with open(supervisor.queue_path) as f:
            data = json.load(f)
        assert data[0]["name"] == "new-feat"


# ---------------------------------------------------------------------------
# process_bug_fix
# ---------------------------------------------------------------------------

class TestProcessBugFix:
    def test_no_issue_returns_false(self, supervisor):
        supervisor.observer.act.return_value = None
        assert supervisor.process_bug_fix() is False

    def test_no_source_returns_false(self, supervisor):
        supervisor.observer.act.return_value = {"type": "Error", "log_excerpt": "err"}
        supervisor.target_file = "/nonexistent.py"
        assert supervisor.process_bug_fix() is False

    def test_patch_rejected_returns_false(self, supervisor):
        supervisor.observer.act.return_value = {"type": "Error", "log_excerpt": "err"}
        supervisor.architect.act.return_value = None  # no patch generated
        supervisor.git.create_evolution_branch.return_value = "fix/branch"
        supervisor.git.checkout_branch.return_value = True
        assert supervisor.process_bug_fix() is False

    def test_auditor_rejects_returns_false(self, supervisor):
        supervisor.observer.act.return_value = {"type": "Error", "log_excerpt": "err"}
        supervisor.architect.act.return_value = "bad_code"
        supervisor.auditor.act.return_value = False
        supervisor.git.create_evolution_branch.return_value = None
        assert supervisor.process_bug_fix() is False

    def test_sandbox_fails_returns_false(self, supervisor):
        supervisor.observer.act.return_value = {"type": "Error", "log_excerpt": "err"}
        supervisor.architect.act.return_value = "def fixed(): pass"
        supervisor.auditor.act.return_value = True
        supervisor.sandbox.verify_and_apply.return_value = False
        supervisor.git.create_evolution_branch.return_value = None
        assert supervisor.process_bug_fix() is False

    def test_tests_fail_returns_false(self, supervisor):
        supervisor.observer.act.return_value = {"type": "Error", "log_excerpt": "err"}
        supervisor.architect.act.return_value = "def fixed(): pass"
        supervisor.auditor.act.return_value = True
        supervisor.sandbox.verify_and_apply.return_value = True
        supervisor.sandbox.run_tests.return_value = False
        supervisor.git.create_evolution_branch.return_value = "fix/branch"
        supervisor.git.rollback.return_value = True
        supervisor.git.checkout_branch.return_value = True
        assert supervisor.process_bug_fix() is False

    def test_full_success_returns_true(self, supervisor, tmp_project):
        supervisor.observer.act.return_value = {"type": "ZeroDivisionError", "log_excerpt": "err"}
        supervisor.architect.act.return_value = "def fixed(): pass"
        supervisor.auditor.act.return_value = True
        supervisor.sandbox.verify_and_apply.return_value = True
        supervisor.sandbox.run_tests.return_value = True
        supervisor.git.create_evolution_branch.return_value = "fix/branch"
        supervisor.git.commit_changes.return_value = True
        supervisor.git.merge_to_main.return_value = True
        result = supervisor.process_bug_fix()
        assert result is True

    def test_full_success_saves_memory(self, supervisor, tmp_project):
        supervisor.observer.act.return_value = {"type": "TypeError", "log_excerpt": "err"}
        supervisor.architect.act.return_value = "def fixed(): pass"
        supervisor.auditor.act.return_value = True
        supervisor.sandbox.verify_and_apply.return_value = True
        supervisor.sandbox.run_tests.return_value = True
        supervisor.git.create_evolution_branch.return_value = None
        supervisor.process_bug_fix()
        with open(supervisor.memory_path) as f:
            data = json.load(f)
        assert any(e.get("type") == "bug_fix" for e in data)


# ---------------------------------------------------------------------------
# process_feature_request
# ---------------------------------------------------------------------------

class TestProcessFeatureRequest:
    def test_empty_queue_returns_false(self, supervisor):
        assert supervisor.process_feature_request() is False

    def test_planner_fails_removes_from_queue(self, supervisor, tmp_project):
        queue = [{"name": "feat-x", "description": "add x"}]
        (tmp_project / "evolution" / "feature_queue.json").write_text(json.dumps(queue))
        supervisor.planner.implement_feature.return_value = None
        supervisor.git.create_evolution_branch.return_value = None
        supervisor.git.checkout_branch.return_value = True
        result = supervisor.process_feature_request()
        assert result is False
        # Queue should be empty (feature removed on failure)
        remaining = supervisor.load_feature_queue()
        assert remaining == []

    def test_feature_applied_successfully(self, supervisor, tmp_project):
        queue = [{"name": "feat-y", "description": "add y"}]
        (tmp_project / "evolution" / "feature_queue.json").write_text(json.dumps(queue))
        (tmp_project / "main_app.py").write_text("def main(): pass\n")
        supervisor.planner.implement_feature.return_value = {
            "plan": "add function",
            "files_to_update": {},
            "new_files": {},
        }
        supervisor.sandbox.apply_feature_files.return_value = True
        supervisor.sandbox.run_tests.return_value = True
        supervisor.git.create_evolution_branch.return_value = "feature/branch"
        supervisor.git.commit_changes.return_value = True
        supervisor.git.merge_to_main.return_value = True
        result = supervisor.process_feature_request()
        assert result is True

    def test_feature_tests_fail_re_adds_to_queue(self, supervisor, tmp_project):
        queue = [{"name": "failing-feat", "description": "will fail"}]
        (tmp_project / "evolution" / "feature_queue.json").write_text(json.dumps(queue))
        (tmp_project / "main_app.py").write_text("def main(): pass\n")
        supervisor.planner.implement_feature.return_value = {
            "plan": "plan",
            "files_to_update": {},
            "new_files": {},
        }
        supervisor.sandbox.apply_feature_files.return_value = True
        supervisor.sandbox.run_tests.return_value = False
        supervisor.git.create_evolution_branch.return_value = "feature/branch"
        supervisor.git.rollback.return_value = True
        supervisor.git.checkout_branch.return_value = True
        result = supervisor.process_feature_request()
        assert result is False
        # Feature should be re-inserted at front of queue for retry
        remaining = supervisor.load_feature_queue()
        assert len(remaining) == 1
        assert remaining[0]["name"] == "failing-feat"
