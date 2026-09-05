from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone

from .caption import build_caption, static_post_caption
from .content import evergreen_post, live_notice_post, load_services
from .instagram import InstagramPublisher
from .live_monitor import discover_notices
from .render import render_reel
from .settings import Settings
from .state_store import load_state, record_publish, save_state
from .token_store import load_access_token, refresh_encrypted_token


LOGGER = logging.getLogger(__name__)


def _paths(settings: Settings) -> dict:
    return {
        "state": settings.state_dir / "content_state.json",
        "pending_state": settings.output_dir / "pending_state.json",
        "post": settings.output_dir / "post.json",
        "caption": settings.output_dir / "caption.txt",
        "static_caption": settings.output_dir / "static-caption.txt",
    }


def prepare(settings: Settings, skip_live: bool = False) -> dict:
    paths = _paths(settings)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    state = load_state(paths["state"])
    notices: list[dict] = []
    baseline_created = False
    partial = state.get("partial_publish")
    if partial and partial.get("post"):
        post = partial["post"]
    elif not skip_live:
        notices, baseline_created = discover_notices(settings.config_dir / "sources.yaml", state)
        if notices:
            post = live_notice_post(notices[0])
        else:
            services = load_services(settings.config_dir / "services.yaml")
            post = evergreen_post(services, int(state.get("service_index", 0)))
    else:
        services = load_services(settings.config_dir / "services.yaml")
        post = evergreen_post(services, int(state.get("service_index", 0)))

    brand = settings.load_brand()
    caption = build_caption(post, brand, settings.gemini_api_key, settings.gemini_model)
    feed_caption = static_post_caption(post, brand)
    reel, cover, static_post = render_reel(post, brand, settings.output_dir, settings.assets_dir)
    post["generated_at"] = datetime.now(timezone.utc).isoformat()
    post["caption"] = caption
    post["static_caption"] = feed_caption
    post["reel_file"] = reel.name
    post["cover_file"] = cover.name
    post["static_post_file"] = static_post.name
    post["hook_seconds"] = 3.65
    post["official_monitor_baseline_created"] = baseline_created
    paths["post"].write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["caption"].write_text(caption + "\n", encoding="utf-8")
    paths["static_caption"].write_text(feed_caption + "\n", encoding="utf-8")
    paths["pending_state"].write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return post


def publish(settings: Settings, video_url: str, image_url: str | None = None) -> dict:
    if not settings.live_publish_enabled:
        raise RuntimeError("Publishing is locked. Set repository variable PUBLISH_MODE=live after testing.")
    paths = _paths(settings)
    if not paths["post"].exists() or not paths["pending_state"].exists():
        raise RuntimeError("No prepared post found; run the prepare command first")
    post = json.loads(paths["post"].read_text(encoding="utf-8"))
    state = json.loads(paths["pending_state"].read_text(encoding="utf-8"))
    refresh_encrypted_token(settings)
    token = load_access_token(settings)
    publisher = InstagramPublisher(settings.ig_user_id, token, settings.meta_api_version)
    partial = state.get("partial_publish", {})
    static_media_id = None
    if image_url:
        if partial.get("post_id") == post["id"] and partial.get("static_media_id"):
            static_media_id = partial["static_media_id"]
        else:
            static_media_id = publisher.publish_image(image_url, post["static_caption"])
            state["partial_publish"] = {
                "post_id": post["id"],
                "static_media_id": static_media_id,
                "post": post,
            }
            save_state(paths["state"], state)
    media_id = publisher.publish_reel(video_url, post["caption"])
    updated = record_publish(state, post)
    updated["last_instagram_media_id"] = media_id
    if static_media_id:
        updated["last_static_media_id"] = static_media_id
    save_state(paths["state"], updated)
    return {
        "reel_media_id": media_id,
        "static_media_id": static_media_id,
        "post_id": post["id"],
        "title": post["title"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Virtual Cyber Cafe Instagram Reel automation")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare", help="Create today's Reel, cover and caption")
    prepare_parser.add_argument("--skip-live", action="store_true", help="Skip official-notice monitoring")
    publish_parser = sub.add_parser("publish", help="Publish the prepared Reel")
    publish_parser.add_argument("--video-url", required=True, help="Public URL that Meta can download")
    publish_parser.add_argument("--image-url", help="Optional public URL for the matching 4:5 feed post")
    refresh_parser = sub.add_parser("refresh-token", help="Refresh the encrypted Instagram token")
    refresh_parser.add_argument("--force", action="store_true")
    return parser


def cli() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()
    settings = Settings()
    if args.command == "prepare":
        result = prepare(settings, skip_live=args.skip_live)
    elif args.command == "publish":
        result = publish(settings, args.video_url, args.image_url)
    else:
        result = {"refreshed": refresh_encrypted_token(settings, force=args.force)}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cli()
