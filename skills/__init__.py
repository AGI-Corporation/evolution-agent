# skills/__init__.py
"""
Evolution Agent Skills System.

Provides a registry and CLI for pluggable agent skills.  Skills extend the
supervisor with new capabilities (e.g. trading on Bitrefill).

Quick start::

    python -m skills add bitrefill/agents
    python -m skills list

Programmatic usage::

    from skills.registry import load_skill_agent
    agent = load_skill_agent("bitrefill/agents")
    result = agent.act({"action": "search", "query": "amazon", "country": "US"})
"""
