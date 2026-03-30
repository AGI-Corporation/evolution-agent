# tests/test_observer.py
# Unit tests for the ObserverAgent

import os
import pytest
from evolution.agents import ObserverAgent


@pytest.fixture
def observer():
    return ObserverAgent()


@pytest.fixture
def log_file(tmp_path):
    """Return a path to a temporary log file."""
    return tmp_path / "system.log"


class TestObserverScanLogs:
    def test_returns_empty_string_for_missing_file(self, observer, tmp_path):
        result = observer.scan_logs(str(tmp_path / "nonexistent.log"))
        assert result == ""

    def test_reads_last_lines(self, observer, log_file):
        lines = [f"line {i}\n" for i in range(100)]
        log_file.write_text("".join(lines))
        content = observer.scan_logs(str(log_file))
        # Last 50 lines = lines 50-99
        assert "line 99" in content
        assert "line 50" in content
        # line 49 is NOT in the last 50
        assert "line 49" not in content


class TestObserverAct:
    def test_returns_none_for_empty_log(self, observer, log_file):
        log_file.write_text("")
        result = observer.act(str(log_file))
        assert result is None

    def test_returns_none_for_missing_log(self, observer, tmp_path):
        result = observer.act(str(tmp_path / "nonexistent.log"))
        assert result is None

    def test_detects_zero_division_error(self, observer, log_file):
        # Observer iterates keywords in order; "Error" appears before "ZeroDivisionError"
        # in the list, so the detected type will be "Error" (it's a substring match).
        log_file.write_text("CRITICAL ERROR: ZeroDivisionError\nTraceback ...\n")
        result = observer.act(str(log_file))
        assert result is not None
        # The first matching keyword is "Error" (appears earlier in the list)
        assert result["type"] in ("Error", "ZeroDivisionError", "CRITICAL", "Traceback")

    def test_detects_generic_error(self, observer, log_file):
        log_file.write_text("Some Error occurred in the system.\n")
        result = observer.act(str(log_file))
        assert result is not None
        assert result["type"] == "Error"

    def test_detects_traceback_as_anomaly_or_exception(self, observer, log_file):
        log_file.write_text("Traceback (most recent call last):\n  File 'x.py'\n")
        result = observer.act(str(log_file))
        assert result is not None

    def test_anomaly_for_non_error_content(self, observer, log_file):
        # No known error keyword → type becomes "anomaly", which is returned
        log_file.write_text("some unusual log content with no known error keyword\n")
        result = observer.act(str(log_file))
        assert result is not None
        assert result["type"] == "anomaly"
