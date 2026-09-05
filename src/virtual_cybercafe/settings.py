from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    meta_api_version: str = os.getenv("META_API_VERSION", "v26.0")
    ig_user_id: str = os.getenv("IG_USER_ID", "")
    publish_mode: str = os.getenv("PUBLISH_MODE", "dry-run").lower()
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    token_encryption_key: str = os.getenv("TOKEN_ENCRYPTION_KEY", "")
    direct_access_token: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def state_dir(self) -> Path:
        return self.root / "state"

    @property
    def output_dir(self) -> Path:
        return self.root / "output"

    @property
    def assets_dir(self) -> Path:
        return self.root / "assets"

    @property
    def live_publish_enabled(self) -> bool:
        return self.publish_mode == "live"

    def load_brand(self) -> dict:
        data = load_yaml(self.config_dir / "brand.yaml")
        overrides = {
            "brand_name": os.getenv("BRAND_NAME"),
            "handle": os.getenv("INSTAGRAM_HANDLE"),
            "service_area": os.getenv("SERVICE_AREA"),
            "cta_keyword": os.getenv("CTA_KEYWORD"),
        }
        for key, value in overrides.items():
            if value:
                data[key] = value
        return data


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}

