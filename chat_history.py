"""
Chat conversation persistence. Stores conversations as JSON files in a local conversations folder.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).parent
CONVERSATIONS_DIR = PROJECT_ROOT / "conversations"


def _ensure_dir() -> Path:
    CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
    return CONVERSATIONS_DIR


def _preview(messages: List[dict], max_len: int = 60) -> str:
    """First user message content, truncated."""
    for m in messages:
        if m.get("role") == "user":
            content = m.get("content") or ""
            if isinstance(content, str):
                text = content.strip()
                return (text[: max_len] + "…") if len(text) > max_len else text
    return "New conversation"


def save_conversation(conversation_id: str, messages: List[dict]) -> Dict[str, Any]:
    """Save or update a conversation by id. Creates file conversations/{id}.json."""
    _ensure_dir()
    path = CONVERSATIONS_DIR / f"{conversation_id}.json"
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "id": conversation_id,
        "timestamp": now,
        "messages": messages,
    }
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)
    return {"id": conversation_id, "timestamp": now, "preview": _preview(messages)}


def load_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Load a conversation by id. Returns None if not found."""
    path = CONVERSATIONS_DIR / f"{conversation_id}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def list_conversations() -> List[Dict[str, Any]]:
    """List all conversations: id, timestamp, preview. Newest first."""
    _ensure_dir()
    out = []
    for path in sorted(CONVERSATIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(path) as f:
                data = json.load(f)
            out.append({
                "id": data.get("id", path.stem),
                "timestamp": data.get("timestamp", ""),
                "preview": _preview(data.get("messages", [])),
            })
        except (json.JSONDecodeError, OSError):
            continue
    return out


def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation by id. Returns True if deleted."""
    path = CONVERSATIONS_DIR / f"{conversation_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def new_conversation_id() -> str:
    """Generate a new unique conversation id."""
    return str(uuid.uuid4())
