# tests/test_epoch_tracker.py
# Tests for evolution/epoch_tracker.py

import json
import os
import pytest
from evolution.epoch_tracker import EpochTracker, AgentVersion, simulate_agent_evaluation


@pytest.fixture()
def project_root(tmp_path):
    os.makedirs(tmp_path / "evolution", exist_ok=True)
    return str(tmp_path)


@pytest.fixture()
def tracker(project_root):
    return EpochTracker(project_root)


class TestEpochTrackerInit:
    def test_starts_at_epoch_zero(self, tracker):
        assert tracker.current_epoch == 0

    def test_empty_population(self, tracker):
        assert tracker.population == {}

    def test_no_checkpoint_starts_fresh(self, tracker):
        assert tracker.history == []

    def test_checkpoint_path_exists_after_save(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {"lr": "static"})
        tracker.log_performance(agent.version_id, 0.7)
        tracker.save_checkpoint()
        assert os.path.exists(tracker.checkpoint_path)


class TestEpochLifecycle:
    def test_start_epoch_increments_counter(self, tracker):
        tracker.start_epoch()
        assert tracker.current_epoch == 1
        tracker.start_epoch()
        assert tracker.current_epoch == 2

    def test_start_epoch_clears_population(self, tracker):
        tracker.start_epoch()
        tracker.register_agent(None, {})
        assert len(tracker.population) == 1
        tracker.start_epoch()
        assert len(tracker.population) == 0

    def test_register_agent_adds_to_population(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {"lr": "static"})
        assert agent.version_id in tracker.population

    def test_register_agent_version_id_format(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        assert f"_e{tracker.current_epoch}" in agent.version_id

    def test_register_agent_with_parent(self, tracker):
        tracker.start_epoch()
        parent = tracker.register_agent(None, {})
        child = tracker.register_agent(parent.version_id, {})
        assert child.parent_id == parent.version_id


class TestLogPerformance:
    def test_log_updates_fitness_score(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        tracker.log_performance(agent.version_id, 0.85)
        assert tracker.population[agent.version_id].fitness_score == pytest.approx(0.85)

    def test_log_updates_status(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        tracker.log_performance(agent.version_id, 0.5, status="tested")
        assert tracker.population[agent.version_id].status == "tested"

    def test_log_failed_status(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        tracker.log_performance(agent.version_id, 0.0, status="failed")
        assert tracker.population[agent.version_id].status == "failed"

    def test_log_unknown_agent_does_not_raise(self, tracker):
        tracker.start_epoch()
        # Should print an error but not raise
        tracker.log_performance("nonexistent_id", 0.5)

    def test_log_appends_to_history(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        tracker.log_performance(agent.version_id, 0.9)
        assert len(tracker.history) == 1
        assert tracker.history[0]["version_id"] == agent.version_id


class TestGetTopTestedVersions:
    def test_returns_sorted_by_score_descending(self, tracker):
        tracker.start_epoch()
        scores = [0.3, 0.9, 0.6]
        for s in scores:
            agent = tracker.register_agent(None, {})
            tracker.log_performance(agent.version_id, s)

        top = tracker.get_top_tested_versions(top_n=3)
        assert [a.fitness_score for a in top] == sorted(scores, reverse=True)

    def test_only_tested_status_included(self, tracker):
        tracker.start_epoch()
        a_good = tracker.register_agent(None, {})
        tracker.log_performance(a_good.version_id, 0.9, status="tested")
        a_bad = tracker.register_agent(None, {})
        tracker.log_performance(a_bad.version_id, 0.8, status="failed")

        top = tracker.get_top_tested_versions(top_n=5)
        ids = [a.version_id for a in top]
        assert a_good.version_id in ids
        assert a_bad.version_id not in ids

    def test_falls_back_to_history(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        tracker.log_performance(agent.version_id, 0.75)
        tracker.save_checkpoint()

        # Start new epoch (clears population)
        tracker.start_epoch()
        top = tracker.get_top_tested_versions(top_n=3)
        assert len(top) == 1
        assert top[0].fitness_score == pytest.approx(0.75)

    def test_returns_empty_when_no_tested(self, tracker):
        tracker.start_epoch()
        top = tracker.get_top_tested_versions()
        assert top == []


class TestCheckpointPersistence:
    def test_reload_resumes_epoch(self, project_root):
        t1 = EpochTracker(project_root)
        t1.start_epoch()
        t1.start_epoch()
        agent = t1.register_agent(None, {})
        t1.log_performance(agent.version_id, 0.8)
        t1.save_checkpoint()

        t2 = EpochTracker(project_root)
        assert t2.current_epoch == 2

    def test_checkpoint_written_to_disk(self, tracker, project_root):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        tracker.log_performance(agent.version_id, 0.5)
        tracker.save_checkpoint()

        with open(os.path.join(project_root, "evolution", "epoch_log.json")) as f:
            data = json.load(f)
        assert data["current_epoch"] == 1

    def test_checkpoint_appends_to_memory(self, tracker, project_root):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        tracker.log_performance(agent.version_id, 0.5)
        tracker.save_checkpoint()

        with open(os.path.join(project_root, "evolution", "memory.json")) as f:
            memory = json.load(f)
        assert any(e.get("type") == "epoch_checkpoint" for e in memory)


class TestSimulateAgentEvaluation:
    def test_score_between_zero_and_one(self):
        agent = AgentVersion(
            version_id="test_agent",
            epoch=1,
            parent_id=None,
            mutation_params={"learning_rate": "static"},
        )
        for _ in range(10):
            score = simulate_agent_evaluation(agent)
            assert 0.0 <= score <= 1.0

    def test_adaptive_lr_boosts_score(self):
        # Run many trials to verify the adaptive param produces higher average
        import statistics

        def avg_score(params, n=100):
            scores = []
            for _ in range(n):
                a = AgentVersion("x", 1, None, params)
                scores.append(simulate_agent_evaluation(a))
            return statistics.mean(scores)

        adaptive_avg = avg_score({"learning_rate": "adaptive"})
        static_avg = avg_score({"learning_rate": "static"})
        assert adaptive_avg > static_avg
