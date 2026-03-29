# skills/registry.py
# Manages the registry of installed skill packages for the Evolution Agent.

import json
import os
from typing import Any, Dict, List, Optional

_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "installed.json")

# Built-in skills that ship with this repository and are always available.
_BUILTIN_SKILLS: Dict[str, Dict[str, Any]] = {
    "bitrefill/agents": {
        "id": "bitrefill/agents",
        "name": "Bitrefill Trading Agent",
        "module": "skills.bitrefill.agents",
        "class": "BitrefillTradingAgent",
        "description": (
            "Trade on Bitrefill: search gift cards and mobile top-ups, "
            "place orders, and track payments using Bitcoin and other "
            "cryptocurrencies."
        ),
        "capabilities": [
            "product_search",
            "order_creation",
            "order_tracking",
            "balance_check",
        ],
        "builtin": True,
    }
}


def _load_registry() -> Dict[str, Dict[str, Any]]:
    """Load the installed-skills registry from disk, merged with builtins."""
    registry = dict(_BUILTIN_SKILLS)
    if os.path.exists(_REGISTRY_PATH):
        try:
            with open(_REGISTRY_PATH, "r") as fh:
                data = json.load(fh)
            registry.update(data)
        except (json.JSONDecodeError, OSError) as exc:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "Could not load skills registry from %s: %s", _REGISTRY_PATH, exc
            )
    return registry


def _save_registry(registry: Dict[str, Dict[str, Any]]) -> None:
    """Persist the non-builtin entries of the registry to disk."""
    custom = {k: v for k, v in registry.items() if not v.get("builtin")}
    with open(_REGISTRY_PATH, "w") as fh:
        json.dump(custom, fh, indent=4)


def list_skills() -> List[Dict[str, Any]]:
    """Return all registered skills (builtins + installed)."""
    return list(_load_registry().values())


def get_skill(skill_id: str) -> Optional[Dict[str, Any]]:
    """Return the registry entry for *skill_id*, or ``None`` if not found."""
    return _load_registry().get(skill_id)


def register_skill(entry: Dict[str, Any]) -> None:
    """
    Add or update a skill entry in the registry.

    *entry* must contain at least the keys ``"id"``, ``"module"``, and
    ``"class"``.
    """
    skill_id = entry.get("id")
    if not skill_id:
        raise ValueError("Skill entry must contain an 'id' field.")
    registry = _load_registry()
    registry[skill_id] = entry
    _save_registry(registry)


def unregister_skill(skill_id: str) -> bool:
    """
    Remove a skill from the registry.

    Returns ``True`` if the skill was removed, ``False`` if it was not found.
    Builtin skills cannot be unregistered.
    """
    registry = _load_registry()
    entry = registry.get(skill_id)
    if entry is None:
        return False
    if entry.get("builtin"):
        raise ValueError(f"Built-in skill '{skill_id}' cannot be removed.")
    del registry[skill_id]
    _save_registry(registry)
    return True


def load_skill_agent(skill_id: str, **kwargs):
    """
    Instantiate and return the agent class for *skill_id*.

    Extra keyword arguments are forwarded to the agent constructor.

    Raises
    ------
    KeyError
        If the skill is not in the registry.
    ImportError
        If the skill module cannot be imported.
    """
    entry = get_skill(skill_id)
    if entry is None:
        raise KeyError(f"Skill '{skill_id}' is not installed.")
    module_path = entry["module"]
    class_name = entry["class"]
    import importlib
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(**kwargs)
