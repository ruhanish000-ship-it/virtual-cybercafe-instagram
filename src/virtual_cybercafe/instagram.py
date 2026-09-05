from __future__ import annotations

import time

import requests


class InstagramPublisher:
    def __init__(self, user_id: str, access_token: str, api_version: str = "v26.0") -> None:
        if not user_id:
            raise ValueError("IG_USER_ID is missing")
        if not access_token:
            raise ValueError("Instagram access token is missing")
        self.user_id = user_id
        self.access_token = access_token
        self.base = f"https://graph.instagram.com/{api_version}"

    @staticmethod
    def _error(response: requests.Response, action: str) -> RuntimeError:
        try:
            detail = response.json().get("error", {}).get("message", response.text[:400])
        except ValueError:
            detail = response.text[:400]
        return RuntimeError(f"Instagram {action} failed ({response.status_code}): {detail}")

    def wait_for_public_video(self, video_url: str, attempts: int = 12) -> None:
        for attempt in range(attempts):
            try:
                response = requests.get(video_url, headers={"Range": "bytes=0-2047"}, timeout=25)
                if response.status_code in {200, 206} and response.content:
                    return
            except requests.RequestException:
                pass
            if attempt < attempts - 1:
                time.sleep(10)
        raise RuntimeError("Public Reel URL did not become readable by Instagram")

    def create_image_container(self, image_url: str, caption: str) -> str:
        response = requests.post(
            f"{self.base}/{self.user_id}/media",
            data={"image_url": image_url, "caption": caption, "access_token": self.access_token},
            timeout=60,
        )
        if not response.ok:
            raise self._error(response, "image container creation")
        return response.json()["id"]

    def create_reel_container(self, video_url: str, caption: str) -> str:
        response = requests.post(
            f"{self.base}/{self.user_id}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "share_to_feed": "true",
                "access_token": self.access_token,
            },
            timeout=60,
        )
        if not response.ok:
            raise self._error(response, "container creation")
        return response.json()["id"]

    def wait_for_container(self, container_id: str, attempts: int = 20) -> None:
        for attempt in range(attempts):
            response = requests.get(
                f"{self.base}/{container_id}",
                params={"fields": "status_code,status", "access_token": self.access_token},
                timeout=35,
            )
            if not response.ok:
                raise self._error(response, "container status check")
            payload = response.json()
            status = payload.get("status_code")
            if status == "FINISHED":
                return
            if status in {"ERROR", "EXPIRED"}:
                raise RuntimeError(f"Instagram rejected the Reel container: {payload.get('status', status)}")
            if attempt < attempts - 1:
                time.sleep(12)
        raise RuntimeError("Instagram did not finish processing the Reel in time")

    def publish_container(self, container_id: str) -> str:
        response = requests.post(
            f"{self.base}/{self.user_id}/media_publish",
            data={"creation_id": container_id, "access_token": self.access_token},
            timeout=60,
        )
        if not response.ok:
            raise self._error(response, "publish")
        return response.json()["id"]

    def publish_reel(self, video_url: str, caption: str) -> str:
        self.wait_for_public_video(video_url)
        container = self.create_reel_container(video_url, caption)
        self.wait_for_container(container)
        return self.publish_container(container)

    def publish_image(self, image_url: str, caption: str) -> str:
        self.wait_for_public_video(image_url)
        container = self.create_image_container(image_url, caption)
        return self.publish_container(container)
