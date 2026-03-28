# tests/test_reporting.py
# Tests for evolution/reporting.py

import json
import os
import pytest
from evolution.reporting import EvolutionReporter


@pytest.fixture()
def project_root(tmp_path):
    os.makedirs(tmp_path / "evolution", exist_ok=True)
    os.makedirs(tmp_path / "logs", exist_ok=True)
    return str(tmp_path)


@pytest.fixture()
def reporter(project_root):
    return EvolutionReporter(project_root)


def write_memory(project_root, data):
    with open(os.path.join(project_root, "evolution", "memory.json"), "w") as f:
        json.dump(data, f)


def write_epoch_log(project_root, data):
    with open(os.path.join(project_root, "evolution", "epoch_log.json"), "w") as f:
        json.dump(data, f)


class TestGenerateSystemSummary:
    def test_returns_error_when_memory_missing(self, reporter):
        result = reporter.generate_system_summary()
        assert "error" in result

    def test_counts_events_correctly(self, reporter, project_root):
        write_memory(project_root, [
            {"type": "bug_fix", "timestamp": "2026-01-01T00:00:00"},
            {"type": "bug_fix", "timestamp": "2026-01-02T00:00:00"},
            {"type": "feature", "timestamp": "2026-01-03T00:00:00"},
            {"type": "epoch_checkpoint", "timestamp": "2026-01-04T00:00:00", "epoch": 1},
        ])
        result = reporter.generate_system_summary()
        assert result["evolution_metrics"]["total_bug_fixes"] == 2
        assert result["evolution_metrics"]["total_features"] == 1
        assert result["evolution_metrics"]["total_epochs"] == 1

    def test_empty_memory_returns_valid_summary(self, reporter, project_root):
        write_memory(project_root, [])
        result = reporter.generate_system_summary()
        assert result["total_cycles"] == 0
        assert result["system_status"] == "active"

    def test_recent_activity_limited_to_ten(self, reporter, project_root):
        events = [{"type": "bug_fix", "timestamp": f"2026-01-{i:02d}T00:00:00"} for i in range(1, 21)]
        write_memory(project_root, events)
        result = reporter.generate_system_summary()
        assert len(result["recent_activity"]) == 10

    def test_saves_report_to_disk(self, reporter, project_root):
        write_memory(project_root, [])
        reporter.generate_system_summary()
        report_path = os.path.join(project_root, "logs", "reports", "system_summary.json")
        assert os.path.exists(report_path)


class TestGenerateEpochReport:
    def test_returns_error_when_epoch_log_missing(self, reporter):
        result = reporter.generate_epoch_report(1)
        assert "error" in result

    def test_returns_error_for_unknown_epoch(self, reporter, project_root):
        write_epoch_log(project_root, {"current_epoch": 1, "history": []})
        result = reporter.generate_epoch_report(99)
        assert "error" in result

    def test_correct_metrics_for_epoch(self, reporter, project_root):
        history = [
            {"epoch": 1, "version_id": "a1", "status": "tested", "fitness_score": 0.8,
             "parent_id": None, "mutation_params": {}, "logged_at": "2026-01-01"},
            {"epoch": 1, "version_id": "a2", "status": "failed", "fitness_score": 0.1,
             "parent_id": None, "mutation_params": {}, "logged_at": "2026-01-02"},
        ]
        write_epoch_log(project_root, {"current_epoch": 1, "history": history})
        result = reporter.generate_epoch_report(1)
        assert result["epoch"] == 1
        assert result["metrics"]["total_agents"] == 2
        assert result["metrics"]["success_rate"] == pytest.approx(0.5)
        assert result["metrics"]["peak_fitness"] == pytest.approx(0.8)

    def test_saves_epoch_report_to_disk(self, reporter, project_root):
        history = [
            {"epoch": 2, "version_id": "b1", "status": "tested", "fitness_score": 0.6,
             "parent_id": None, "mutation_params": {}, "logged_at": "2026-01-01"},
        ]
        write_epoch_log(project_root, {"current_epoch": 2, "history": history})
        reporter.generate_epoch_report(2)
        report_path = os.path.join(project_root, "logs", "reports", "epoch_2_report.json")
        assert os.path.exists(report_path)
