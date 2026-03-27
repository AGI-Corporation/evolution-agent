# tests/conftest.py
# Set a dummy API key so the OpenAI client can be instantiated during imports.

import os

os.environ.setdefault("OPENAI_API_KEY", "fake-key-for-testing")
