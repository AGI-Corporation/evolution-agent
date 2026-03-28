# tests/test_reporting.py
# Tests for evolution/reporting.py

import json
import os
import pytest
from evolution.reporting import EvolutionReporter


@pytest.fixture
def tmp_project(tmp_path):
    (tmp_path / "evolution").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path


@pytest.fixture
def reporter(tmp_project):
    return EvolutionReporter(str(tmp_project))


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestEvolutionReporterInit:
    def test_reports_dir_created(self, tmp_project):
        reporter = EvolutionReporter(str(tmp_project))
        assert os.path.isdir(reporter.reports_dir)

    def test_paths_set_correctly(self, tmp_project):
        reporter = EvolutionReporter(str(tmp_project))
        assert "memory.json" in reporter.memory_path
        assert "epoch_log.json" in reporter.epoch_log_path
        assert "reports" in reporter.reports_dir


# ---------------------------------------------------------------------------
# _save_report
# ---------------------------------------------------------------------------

class TestSaveReport:
    def test_saves_json_file(self, reporter, tmp_project):
        content = {"key": "value", "number": 42}
        reporter._save_report("test_report.json", content)
        path = os.path.join(reporter.reports_dir, "test_report.json")
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data["key"] == "value"
        assert data["number"] == 42


# ---------------------------------------------------------------------------
# generate_epoch_report
# ---------------------------------------------------------------------------

class TestGenerateEpochReport:
    def _write_epoch_log(self, tmp_project, history):
        data = {"current_epoch": 1, "history": history}
        path = tmp_project / "evolution" / "epoch_log.json"
        path.write_text(json.dumps(data))

    def test_no_data_for_epoch_returns_error(self, reporter, tmp_project):
        history = [
            {"version_id": "v1", "epoch": 1, "fitness_score": 0.8, "status": "tested"}
        ]
        self._write_epoch_log(tmp_project, history)
        result = reporter.generate_epoch_report(99)
        assert "error" in result

    def test_file_not_found_returns_error(self, reporter):
        result = reporter.generate_epoch_report(1)
        assert "error" in result

    def test_returns_metrics(self, reporter, tmp_project):
        history = [
            {"version_id": "v1", "epoch": 2, "fitness_score": 0.8, "status": "tested"},
            {"version_id": "v2", "epoch": 2, "fitness_score": 0.6, "status": "tested"},
            {"version_id": "v3", "epoch": 2, "fitness_score": 0.3, "status": "failed"},
        ]
        self._write_epoch_log(tmp_project, history)
        result = reporter.generate_epoch_report(2)
        assert "metrics" in result
        assert result["metrics"]["total_agents"] == 3
        assert result["metrics"]["success_rate"] == pytest.approx(2 / 3)
        assert result["metrics"]["failure_rate"] == pytest.approx(1 / 3)

    def test_average_fitness_calculated(self, reporter, tmp_project):
        history = [
            {"version_id": "v1", "epoch": 3, "fitness_score": 1.0, "status": "tested"},
            {"version_id": "v2", "epoch": 3, "fitness_score": 0.5, "status": "tested"},
        ]
        self._write_epoch_log(tmp_project, history)
        result = reporter.generate_epoch_report(3)
        assert result["metrics"]["average_fitness"] == pytest.approx(0.75)

    def test_peak_fitness(self, reporter, tmp_project):
        history = [
            {"version_id": "v1", "epoch": 4, "fitness_score": 0.3, "status": "tested"},
            {"version_id": "v2", "epoch": 4, "fitness_score": 0.95, "status": "tested"},
        ]
        self._write_epoch_log(tmp_project, history)
        result = reporter.generate_epoch_report(4)
        assert result["metrics"]["peak_fitness"] == pytest.approx(0.95)

    def test_top_agents_limited_to_3(self, reporter, tmp_project):
        history = [
            {"version_id": f"v{i}", "epoch": 5, "fitness_score": float(i) / 10, "status": "tested"}
            for i in range(1, 8)
        ]
        self._write_epoch_log(tmp_project, history)
        result = reporter.generate_epoch_report(5)
        assert len(result["top_agents"]) == 3

    def test_report_saved_to_disk(self, reporter, tmp_project):
        history = [
            {"version_id": "v1", "epoch": 6, "fitness_score": 0.8, "status": "tested"}
        ]
        self._write_epoch_log(tmp_project, history)
        reporter.generate_epoch_report(6)
        report_path = os.path.join(reporter.reports_dir, "epoch_6_report.json")
        assert os.path.exists(report_path)


# ---------------------------------------------------------------------------
# generate_system_summary
# ---------------------------------------------------------------------------

class TestGenerateSystemSummary:
    def _write_memory(self, tmp_project, data):
        path = tmp_project / "evolution" / "memory.json"
        path.write_text(json.dumps(data))

    def test_no_memory_file_returns_error(self, reporter):
        result = reporter.generate_system_summary()
        assert "error" in result

    def test_empty_memory_returns_summary(self, reporter, tmp_project):
        self._write_memory(tmp_project, [])
        result = reporter.generate_system_summary()
        assert result["total_cycles"] == 0

    def test_counts_bug_fixes(self, reporter, tmp_project):
        data = [
            {"type": "bug_fix", "timestamp": "2024-01-01"},
            {"type": "bug_fix", "timestamp": "2024-01-02"},
            {"type": "feature", "timestamp": "2024-01-03"},
        ]
        self._write_memory(tmp_project, data)
        result = reporter.generate_system_summary()
        assert result["evolution_metrics"]["total_bug_fixes"] == 2

    def test_counts_features(self, reporter, tmp_project):
        data = [
            {"type": "bug_fix", "timestamp": "2024-01-01"},
            {"type": "feature", "timestamp": "2024-01-02"},
            {"type": "feature", "timestamp": "2024-01-03"},
        ]
        self._write_memory(tmp_project, data)
        result = reporter.generate_system_summary()
        assert result["evolution_metrics"]["total_features"] == 2

    def test_counts_epoch_checkpoints(self, reporter, tmp_project):
        data = [
            {"type": "epoch_checkpoint", "epoch": 1},
            {"type": "epoch_checkpoint", "epoch": 2},
        ]
        self._write_memory(tmp_project, data)
        result = reporter.generate_system_summary()
        assert result["evolution_metrics"]["total_epochs"] == 2

    def test_recent_activity_limited_to_10(self, reporter, tmp_project):
        data = [{"type": "bug_fix", "timestamp": f"2024-01-{i:02d}"} for i in range(1, 21)]
        self._write_memory(tmp_project, data)
        result = reporter.generate_system_summary()
        assert len(result["recent_activity"]) == 10

    def test_uptime_since_first_entry(self, reporter, tmp_project):
        data = [
            {"type": "bug_fix", "timestamp": "2024-01-01T00:00:00"},
            {"type": "feature", "timestamp": "2024-01-02T00:00:00"},
        ]
        self._write_memory(tmp_project, data)
        result = reporter.generate_system_summary()
        assert result["evolution_metrics"]["uptime_since"] == "2024-01-01T00:00:00"

    def test_summary_saved_to_disk(self, reporter, tmp_project):
        self._write_memory(tmp_project, [])
        reporter.generate_system_summary()
        assert os.path.exists(os.path.join(reporter.reports_dir, "system_summary.json"))
