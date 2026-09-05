from __future__ import annotations

import json
import wave
from pathlib import Path

from PIL import Image

from virtual_cybercafe.caption import MAX_CAPTION, fallback_caption, static_post_caption
from virtual_cybercafe.content import evergreen_post, load_services
from virtual_cybercafe.live_monitor import _is_allowed, _matches
from virtual_cybercafe.music import SAMPLE_RATE, generate_original_music
from virtual_cybercafe.render import POST_HEIGHT, POST_WIDTH, create_static_post
from virtual_cybercafe.settings import ROOT, load_yaml
from virtual_cybercafe.state_store import record_publish


def test_catalog_is_broad_and_rotates() -> None:
    services = load_services(ROOT / "config" / "services.yaml")
    assert len(services) >= 45
    first = evergreen_post(services, 0)
    wrapped = evergreen_post(services, len(services))
    assert first["title"] == wrapped["title"]
    assert first["id"] != wrapped["id"]


def test_caption_is_compliant_and_within_instagram_limit() -> None:
    services = load_services(ROOT / "config" / "services.yaml")
    post = evergreen_post(services, 0)
    brand = load_yaml(ROOT / "config" / "brand.yaml")
    caption = fallback_caption(post, brand)
    assert len(caption) <= MAX_CAPTION
    assert "Not a government authority" in caption
    assert "#VirtualCyberCafe" in caption
    assert "DM “HELP”" in caption
    feed_caption = static_post_caption(post, brand)
    assert len(feed_caption) <= MAX_CAPTION
    assert feed_caption != caption
    assert "Not a government authority" in feed_caption


def test_official_domain_guard_rejects_lookalikes() -> None:
    allowed = ["ssc.gov.in"]
    assert _is_allowed("https://ssc.gov.in/home/notice", allowed)
    assert _is_allowed("https://www.ssc.gov.in/home/notice", allowed)
    assert not _is_allowed("https://ssc.gov.in.example.com/fake", allowed)
    assert not _is_allowed("https://ssc-gov.in/fake", allowed)


def test_notice_filter() -> None:
    assert _matches("New online application notification", ["application"], ["tender"])
    assert not _matches("Tender application notice", ["application"], ["tender"])


def test_state_moves_only_after_publish() -> None:
    services = load_services(ROOT / "config" / "services.yaml")
    post = evergreen_post(services, 0)
    state = {
        "service_index": 0,
        "seen_notice_ids": [],
        "published": [],
        "partial_publish": {"post_id": post["id"], "static_media_id": "123"},
    }
    updated = record_publish(state, post)
    assert state["service_index"] == 0
    assert updated["service_index"] == 1
    assert updated["published"][0]["id"] == post["id"]
    assert "partial_publish" not in updated


def test_static_post_is_instagram_4_by_5(tmp_path: Path) -> None:
    services = load_services(ROOT / "config" / "services.yaml")
    post = evergreen_post(services, 0)
    brand = load_yaml(ROOT / "config" / "brand.yaml")
    path = create_static_post(post, brand, tmp_path)
    with Image.open(path) as image:
        assert image.size == (POST_WIDTH, POST_HEIGHT)


def test_original_music_has_instagram_audio_rate(tmp_path: Path) -> None:
    destination = generate_original_music(tmp_path / "music.wav", duration=1.2)
    with wave.open(str(destination), "rb") as audio:
        assert audio.getframerate() == SAMPLE_RATE
        assert audio.getnchannels() == 2
        assert audio.getsampwidth() == 2


def test_initial_state_is_valid_json() -> None:
    state = json.loads((ROOT / "state" / "content_state.json").read_text(encoding="utf-8"))
    assert state["service_index"] == 0
