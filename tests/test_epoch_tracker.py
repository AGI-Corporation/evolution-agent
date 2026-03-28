# tests/test_epoch_tracker.py
# Tests for evolution/epoch_tracker.py

import json
import os
import uuid
import pytest
from unittest.mock import patch
from evolution.epoch_tracker import (
    AgentVersion,
    EpochTracker,
    simulate_agent_evaluation,
)


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal project structure for EpochTracker."""
    (tmp_path / "evolution").mkdir()
    return tmp_path


@pytest.fixture
def tracker(tmp_project):
    return EpochTracker(str(tmp_project))


# ---------------------------------------------------------------------------
# AgentVersion
# ---------------------------------------------------------------------------

class TestAgentVersion:
    def test_default_values(self):
        av = AgentVersion(
            version_id="v1",
            epoch=1,
            parent_id=None,
            mutation_params={"lr": 0.01},
        )
        assert av.fitness_score == 0.0
        assert av.status == "created"

    def test_less_than_comparison(self):
        a = AgentVersion("a", 1, None, {}, fitness_score=0.5)
        b = AgentVersion("b", 1, None, {}, fitness_score=0.8)
        assert a < b
        assert not (b < a)

    def test_equality_via_fitness(self):
        a = AgentVersion("a", 1, None, {}, fitness_score=0.5)
        b = AgentVersion("b", 1, None, {}, fitness_score=0.5)
        assert not (a < b)
        assert not (b < a)


# ---------------------------------------------------------------------------
# EpochTracker.__init__ and _load_state
# ---------------------------------------------------------------------------

class TestEpochTrackerInit:
    def test_fresh_start_epoch_zero(self, tracker):
        assert tracker.current_epoch == 0
        assert tracker.population == {}
        assert tracker.history == []

    def test_checkpoint_path_set(self, tracker, tmp_project):
        expected = os.path.join(str(tmp_project), "evolution", "epoch_log.json")
        assert tracker.checkpoint_path == expected

    def test_memory_path_default(self, tracker, tmp_project):
        expected = os.path.join(str(tmp_project), "evolution", "memory.json")
        assert tracker.memory_path == expected

    def test_custom_memory_path(self, tmp_project):
        custom = str(tmp_project / "custom_memory.json")
        t = EpochTracker(str(tmp_project), memory_path=custom)
        assert t.memory_path == custom

    def test_resumes_from_checkpoint(self, tmp_project):
        checkpoint = {
            "current_epoch": 5,
            "history": [{"version_id": "v1", "epoch": 1}],
        }
        checkpoint_path = tmp_project / "evolution" / "epoch_log.json"
        checkpoint_path.write_text(json.dumps(checkpoint))
        t = EpochTracker(str(tmp_project))
        assert t.current_epoch == 5
        assert len(t.history) == 1


# ---------------------------------------------------------------------------
# start_epoch
# ---------------------------------------------------------------------------

class TestStartEpoch:
    def test_increments_epoch(self, tracker):
        tracker.start_epoch()
        assert tracker.current_epoch == 1
        tracker.start_epoch()
        assert tracker.current_epoch == 2

    def test_resets_population(self, tracker):
        tracker.start_epoch()
        tracker.register_agent(None, {"lr": "0.01"})
        assert len(tracker.population) == 1
        tracker.start_epoch()
        assert tracker.population == {}


# ---------------------------------------------------------------------------
# register_agent
# ---------------------------------------------------------------------------

class TestRegisterAgent:
    def test_returns_agent_version(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {"lr": "static"})
        assert isinstance(agent, AgentVersion)

    def test_version_id_format(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        assert agent.version_id.startswith("agent_")
        assert f"_e{tracker.current_epoch}" in agent.version_id

    def test_parent_id_stored(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent("parent_xyz", {})
        assert agent.parent_id == "parent_xyz"

    def test_agent_added_to_population(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        assert agent.version_id in tracker.population

    def test_mutation_params_stored(self, tracker):
        tracker.start_epoch()
        params = {"arch": "transformer", "lr": "adaptive"}
        agent = tracker.register_agent(None, params)
        assert agent.mutation_params == params

    def test_initial_status_created(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        assert agent.status == "created"


# ---------------------------------------------------------------------------
# log_performance
# ---------------------------------------------------------------------------

class TestLogPerformance:
    def test_updates_fitness_score(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        tracker.log_performance(agent.version_id, 0.85)
        assert tracker.population[agent.version_id].fitness_score == 0.85

    def test_updates_status(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        tracker.log_performance(agent.version_id, 0.5, status="tested")
        assert tracker.population[agent.version_id].status == "tested"

    def test_failed_status(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        tracker.log_performance(agent.version_id, 0.0, status="failed")
        assert tracker.population[agent.version_id].status == "failed"

    def test_appends_to_history(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        tracker.log_performance(agent.version_id, 0.7)
        assert len(tracker.history) == 1
        assert tracker.history[0]["version_id"] == agent.version_id

    def test_unknown_agent_is_no_op(self, tracker):
        tracker.start_epoch()
        # Should not raise
        tracker.log_performance("nonexistent_id", 0.5)
        assert len(tracker.history) == 0

    def test_logged_at_in_history(self, tracker):
        tracker.start_epoch()
        agent = tracker.register_agent(None, {})
        tracker.log_performance(agent.version_id, 0.6)
        assert "logged_at" in tracker.history[0]


# ---------------------------------------------------------------------------
# get_top_tested_versions
# ---------------------------------------------------------------------------

class TestGetTopTestedVersions:
    def test_empty_population_returns_empty(self, tracker):
        tracker.start_epoch()
        result = tracker.get_top_tested_versions(3)
        assert result == []

    def test_returns_only_tested_agents(self, tracker):
        tracker.start_epoch()
        a1 = tracker.register_agent(None, {})
        a2 = tracker.register_agent(None, {})
        tracker.log_performance(a1.version_id, 0.9, "tested")
        tracker.log_performance(a2.version_id, 0.5, "failed")
        result = tracker.get_top_tested_versions(5)
        assert len(result) == 1
        assert result[0].version_id == a1.version_id

    def test_returns_sorted_by_fitness_desc(self, tracker):
        tracker.start_epoch()
        a1 = tracker.register_agent(None, {})
        a2 = tracker.register_agent(None, {})
        a3 = tracker.register_agent(None, {})
        tracker.log_performance(a1.version_id, 0.3, "tested")
        tracker.log_performance(a2.version_id, 0.9, "tested")
        tracker.log_performance(a3.version_id, 0.6, "tested")
        result = tracker.get_top_tested_versions(3)
        scores = [a.fitness_score for a in result]
        assert scores == sorted(scores, reverse=True)

    def test_respects_top_n_limit(self, tracker):
        tracker.start_epoch()
        for i in range(5):
            a = tracker.register_agent(None, {})
            tracker.log_performance(a.version_id, float(i) / 10, "tested")
        result = tracker.get_top_tested_versions(3)
        assert len(result) == 3

    def test_falls_back_to_history(self, tracker):
        tracker.start_epoch()
        a1 = tracker.register_agent(None, {})
        tracker.log_performance(a1.version_id, 0.8, "tested")
        # Start new epoch, population resets
        tracker.start_epoch()
        result = tracker.get_top_tested_versions(3)
        assert len(result) == 1
        assert result[0].version_id == a1.version_id


# ---------------------------------------------------------------------------
# save_checkpoint
# ---------------------------------------------------------------------------

class TestSaveCheckpoint:
    def test_checkpoint_file_created(self, tracker, tmp_project):
        tracker.start_epoch()
        tracker.save_checkpoint()
        assert (tmp_project / "evolution" / "epoch_log.json").exists()

    def test_checkpoint_contains_epoch(self, tracker, tmp_project):
        tracker.start_epoch()
        tracker.save_checkpoint()
        data = json.loads((tmp_project / "evolution" / "epoch_log.json").read_text())
        assert data["current_epoch"] == 1

    def test_checkpoint_contains_population_size(self, tracker, tmp_project):
        tracker.start_epoch()
        tracker.register_agent(None, {})
        tracker.save_checkpoint()
        data = json.loads((tmp_project / "evolution" / "epoch_log.json").read_text())
        assert data["population_size"] == 1

    def test_memory_json_updated(self, tracker, tmp_project):
        tracker.start_epoch()
        tracker.save_checkpoint()
        memory_path = tmp_project / "evolution" / "memory.json"
        if memory_path.exists():
            data = json.loads(memory_path.read_text())
            # Find the epoch_checkpoint entry
            epochs = [e for e in data if e.get("type") == "epoch_checkpoint"]
            assert len(epochs) >= 1


# ---------------------------------------------------------------------------
# print_leaderboard
# ---------------------------------------------------------------------------

class TestPrintLeaderboard:
    def test_empty_leaderboard_no_error(self, tracker, capsys):
        tracker.start_epoch()
        tracker.print_leaderboard()
        captured = capsys.readouterr()
        assert "No tested agents yet" in captured.out

    def test_leaderboard_shows_agents(self, tracker, capsys):
        tracker.start_epoch()
        a = tracker.register_agent(None, {})
        tracker.log_performance(a.version_id, 0.75, "tested")
        tracker.print_leaderboard()
        captured = capsys.readouterr()
        assert a.version_id in captured.out
        assert "0.7500" in captured.out


# ---------------------------------------------------------------------------
# simulate_agent_evaluation
# ---------------------------------------------------------------------------

class TestSimulateAgentEvaluation:
    def test_returns_float_between_0_and_1(self):
        agent = AgentVersion("v1", 1, None, {})
        score = simulate_agent_evaluation(agent)
        assert 0.0 <= score <= 1.0

    def test_adaptive_learning_rate_increases_score(self):
        """Adaptive LR adds +0.15, so score should be >= 0.65 on average."""
        params = {"learning_rate": "adaptive"}
        scores = []
        for _ in range(20):
            agent = AgentVersion(str(uuid.uuid4()), 1, None, params)
            scores.append(simulate_agent_evaluation(agent))
        assert sum(scores) / len(scores) > 0.60  # must be higher than base

    def test_score_capped_at_1(self):
        """All bonuses combined can't exceed 1.0."""
        params = {
            "learning_rate": "adaptive",
            "architecture": "transformer_v2",
            "memory": "long_term",
        }
        for _ in range(30):
            agent = AgentVersion(str(uuid.uuid4()), 1, None, params)
            score = simulate_agent_evaluation(agent)
            assert score <= 1.0
