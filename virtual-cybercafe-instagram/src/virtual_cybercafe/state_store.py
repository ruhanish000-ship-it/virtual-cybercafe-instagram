from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_STATE = {"service_index": 0, "seen_notice_ids": [], "monitored_sources": [], "published": []}


def load_state(path: Path) -> dict:
    if not path.exists():
        return DEFAULT_STATE.copy()
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return {**DEFAULT_STATE, **data}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def record_publish(state: dict, post: dict) -> dict:
    updated = dict(state)
    updated["published"] = list(updated.get("published", []))[-89:]
    updated["published"].append(
        {
            "id": post["id"],
            "type": post["type"],
            "title": post["title"],
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    if post["type"] == "live_notice":
        seen = list(updated.get("seen_notice_ids", []))
        if post["id"] not in seen:
            seen.append(post["id"])
        updated["seen_notice_ids"] = seen[-1000:]
    else:
        updated["service_index"] = int(updated.get("service_index", 0)) + 1
    updated.pop("partial_publish", None)
    return updated
