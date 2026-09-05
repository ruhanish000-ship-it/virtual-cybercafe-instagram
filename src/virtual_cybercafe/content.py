from __future__ import annotations

import hashlib
from pathlib import Path

from .settings import load_yaml


def load_services(path: Path) -> list[dict]:
    services = load_yaml(path).get("services", [])
    if not services:
        raise ValueError("No services found in config/services.yaml")
    return services


def evergreen_post(services: list[dict], service_index: int) -> dict:
    item = dict(services[service_index % len(services)])
    stable = f"evergreen:{service_index}:{item['title']}"
    item.update(
        {
            "id": hashlib.sha256(stable.encode()).hexdigest()[:16],
            "type": "evergreen",
            "source_name": None,
            "source_url": None,
        }
    )
    return item


def live_notice_post(notice: dict) -> dict:
    return {
        "id": notice["id"],
        "type": "live_notice",
        "category": f"LIVE • {notice['source_name']}",
        "title": notice["title"],
        "hook": "New official form or exam notice detected",
        "bullets": [
            "Official notice is now available",
            "Check eligibility, dates and instructions",
            "Form-filling and document assistance available",
        ],
        "documents": [
            "Official notification details",
            "Applicant identity/academic documents",
            "Correct photo and signature where required",
        ],
        "hashtags": [notice["source_name"].replace(" ", ""), "FormUpdate", "GovernmentJobs"],
        "source_name": notice["source_name"],
        "source_url": notice["url"],
    }

