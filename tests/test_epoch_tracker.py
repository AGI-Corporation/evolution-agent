# tests/test_epoch_tracker.py
# Unit tests for the EpochTracker component

import json
import pytest
from evolution.epoch_tracker import EpochTracker, AgentVersion


@pytest.fixture
def tracker(tmp_path):
    """Return a fresh EpochTracker using a temp directory."""
    return EpochTracker(str(tmp_path))


class TestEpochLifecycle:
    def test_initial_epoch_is_zero(self, tracker):
        assert tracker.current_epoch == 0

    def test_start_epoch_increments(self, tracker):
        tracker.start_epoch()
        assert tracker.current_epoch == 1
        tracker.start_epoch()
        assert tracker.current_epoch == 2

    def test_start_epoch_resets_population(self, tracker):
        tracker.start_epoch()
        tracker.register_agent(parent_id=None, mutation_params={"a": 1})
        assert len(tracker.population) == 1
        tracker.start_epoch()
        assert len(tracker.population) == 0


class TestRegisterAgent:
    def test_registers_agent(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(parent_id=None, mutation_params={"x": 1})
        assert isinstance(agent, AgentVersion)
        assert agent.version_id in tracker.population

    def test_version_id_contains_epoch(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(parent_id=None, mutation_params={})
        assert f"_e{tracker.current_epoch}" in agent.version_id

    def test_parent_id_is_stored(self, tracker):
        tracker.start_epoch()
        parent = tracker.register_agent(parent_id=None, mutation_params={})
        child = tracker.register_agent(parent_id=parent.version_id, mutation_params={})
        assert child.parent_id == parent.version_id


class TestLogPerformance:
    def test_records_fitness_score(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(parent_id=None, mutation_params={})
        tracker.log_performance(agent.version_id, 0.85, status="tested")
        assert tracker.population[agent.version_id].fitness_score == 0.85
        assert tracker.population[agent.version_id].status == "tested"

    def test_appends_to_history(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(parent_id=None, mutation_params={})
        tracker.log_performance(agent.version_id, 0.5)
        assert len(tracker.history) == 1

    def test_unknown_version_id_is_ignored(self, tracker):
        tracker.start_epoch()
        # Should not raise
        tracker.log_performance("nonexistent_id", 0.9)


class TestGetTopTestedVersions:
    def test_returns_top_n(self, tracker):
        tracker.start_epoch()
        scores = [0.3, 0.9, 0.6, 0.1, 0.8]
        for s in scores:
            agent = tracker.register_agent(parent_id=None, mutation_params={})
            tracker.log_performance(agent.version_id, s, status="tested")

        top = tracker.get_top_tested_versions(top_n=3)
        assert len(top) == 3
        assert top[0].fitness_score >= top[1].fitness_score >= top[2].fitness_score

    def test_excludes_failed_agents(self, tracker):
        tracker.start_epoch()
        good = tracker.register_agent(parent_id=None, mutation_params={})
        tracker.log_performance(good.version_id, 0.9, status="tested")
        bad = tracker.register_agent(parent_id=None, mutation_params={})
        tracker.log_performance(bad.version_id, 1.0, status="failed")

        top = tracker.get_top_tested_versions(top_n=5)
        ids = [a.version_id for a in top]
        assert good.version_id in ids
        assert bad.version_id not in ids


class TestCheckpoint:
    def test_save_checkpoint_creates_file(self, tracker, tmp_path):
        tracker.start_epoch()
        tracker.save_checkpoint()
        checkpoint_file = tmp_path / "evolution" / "epoch_log.json"
        assert checkpoint_file.exists()

    def test_checkpoint_contains_epoch(self, tracker, tmp_path):
        tracker.start_epoch()
        tracker.save_checkpoint()
        checkpoint_file = tmp_path / "evolution" / "epoch_log.json"
        data = json.loads(checkpoint_file.read_text())
        assert data["current_epoch"] == 1
