"""User profile persistence for the tax advisor app."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).parent
PROFILE_PATH = PROJECT_ROOT / "user_profile.json"

DEFAULT_PROFILE: Dict[str, Any] = {
    "filing_status": "single",
    "state": None,
    "dependents": 0,
    "annual_income": None,
    "w2_data": None,
    "ten99_data": None,
    "additional_income": None,
    "notes": [],
    "age": None,
    "self_employment_income": None,
    "last_updated": None,
}


def _ensure_defaults(data: Dict[str, Any]) -> Dict[str, Any]:
    """Merge stored profile with defaults and normalize types."""
    profile = {**DEFAULT_PROFILE, **data}
    # Ensure notes is a list
    if not isinstance(profile.get("notes"), list):
        profile["notes"] = list(profile.get("notes") or [])
    return profile


def load_profile() -> Dict[str, Any]:
    """Read user_profile.json from project root, returning defaults if missing."""
    if PROFILE_PATH.exists():
        with open(PROFILE_PATH) as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
        # Backwards compatibility with older keys
        if "state_of_residence" in data and "state" not in data:
            data["state"] = data.get("state_of_residence")
        if "number_of_dependents" in data and "dependents" not in data:
            data["dependents"] = data.get("number_of_dependents")
        return _ensure_defaults(data)
    return dict(DEFAULT_PROFILE)


def save_profile(data: Dict[str, Any]) -> Dict[str, Any]:
    """Write updated profile to user_profile.json and return normalized profile."""
    profile = _ensure_defaults(data)
    profile["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(PROFILE_PATH, "w") as f:
        json.dump(profile, f, indent=2)
    return profile


def update_profile_field(field: str, value: Any) -> Dict[str, Any]:
    """
    Update a single profile field and save.

    Expected fields include:
      - filing_status (str)
      - state (str or null)
      - dependents (int)
      - annual_income (number or null)
      - w2_data (object or null)
      - ten99_data (object or null)
      - additional_income (number or null)
      - notes (list or null)
      - age (int or null)
      - self_employment_income (number or null)
    """
    profile = load_profile()
    if field not in DEFAULT_PROFILE:
        # Silently ignore unknown fields rather than crashing the agent
        return save_profile(profile)
    if field == "notes" and isinstance(value, str):
        # Append note strings instead of replacing the list
        profile.setdefault("notes", [])
        if not isinstance(profile["notes"], list):
            profile["notes"] = [str(profile["notes"])]
        profile["notes"].append(value)
    else:
        profile[field] = value
    return save_profile(profile)


