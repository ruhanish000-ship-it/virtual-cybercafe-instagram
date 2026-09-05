from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .settings import load_yaml


LOGGER = logging.getLogger(__name__)
USER_AGENT = "VirtualCyberCafe-OfficialNoticeMonitor/1.0 (+private assistance service)"


@dataclass(frozen=True)
class Notice:
    id: str
    source_name: str
    title: str
    url: str

    def as_dict(self) -> dict:
        return {"id": self.id, "source_name": self.source_name, "title": self.title, "url": self.url}


def _normalise_space(value: str) -> str:
    return " ".join(value.split())


def _is_allowed(url: str, allowed_hosts: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == allowed or host.endswith("." + allowed) for allowed in allowed_hosts)


def _matches(title: str, includes: list[str], excludes: list[str]) -> bool:
    lowered = title.casefold()
    return any(word.casefold() in lowered for word in includes) and not any(
        word.casefold() in lowered for word in excludes
    )


def scrape_source(source: dict, includes: list[str], excludes: list[str], timeout: int = 25) -> list[Notice]:
    response = requests.get(
        source["url"], headers={"User-Agent": USER_AGENT, "Accept-Language": "en-IN,en;q=0.8"}, timeout=timeout
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    found: list[Notice] = []
    seen_titles: set[str] = set()
    allowed_hosts = [host.lower() for host in source["allowed_hosts"]]

    for anchor in soup.find_all("a", href=True):
        title = _normalise_space(anchor.get_text(" ", strip=True))
        if not 12 <= len(title) <= 280 or title.casefold() in seen_titles:
            continue
        url = urljoin(source["url"], anchor["href"])
        if not _is_allowed(url, allowed_hosts) or not _matches(title, includes, excludes):
            continue
        digest = hashlib.sha256(f"{source['name']}|{title}|{url}".encode("utf-8")).hexdigest()[:20]
        found.append(Notice(digest, source["name"], title, url))
        seen_titles.add(title.casefold())
    return found[:40]


def discover_notices(config_path, state: dict) -> tuple[list[dict], bool]:
    config = load_yaml(config_path)
    includes = config.get("include_keywords", [])
    excludes = config.get("exclude_keywords", [])
    sources = config.get("sources", [])
    results: dict[str, list[Notice]] = {}
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(sources)))) as pool:
        futures = {pool.submit(scrape_source, source, includes, excludes): source for source in sources}
        for future in as_completed(futures):
            source = futures[future]
            try:
                results[source["name"]] = future.result()
            except (requests.RequestException, ValueError) as exc:
                LOGGER.warning("Official source unavailable: %s (%s)", source.get("name", "unknown"), exc)

    seen = set(state.get("seen_notice_ids", []))
    monitored = set(state.get("monitored_sources", []))
    new_notices: list[dict] = []
    baseline_created = False
    # Preserve the configured source order even though downloads run concurrently.
    for source in sources:
        name = source["name"]
        if name not in results:
            continue
        source_notices = results[name]
        if name not in monitored:
            seen.update(item.id for item in source_notices)
            monitored.add(name)
            baseline_created = True
            continue
        new_notices.extend(item.as_dict() for item in source_notices if item.id not in seen)
    state["seen_notice_ids"] = list(seen)[-1000:]
    state["monitored_sources"] = sorted(monitored)
    return new_notices, baseline_created
