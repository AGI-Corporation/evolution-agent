# tests/conftest.py
# Shared pytest fixtures and configuration for the evolution-agent test suite.

import sys
import os

# Ensure the project root is on sys.path so that `evolution` is importable
# even when pytest is run from a subdirectory.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
