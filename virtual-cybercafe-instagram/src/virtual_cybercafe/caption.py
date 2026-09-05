from __future__ import annotations

import json
import logging
import re

import requests


LOGGER = logging.getLogger(__name__)
MAX_CAPTION = 2200


def _tag(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", value)
    return f"#{cleaned}" if cleaned else ""


def fallback_caption(post: dict, brand: dict) -> str:
    bullets = "\n".join(f"✅ {item}" for item in post["bullets"])
    documents = "\n".join(f"• {item}" for item in post["documents"])
    tags = [
        "VirtualCyberCafe",
        "DelhiCyberCafe",
        "OnlineFormFilling",
        "DigitalSeva",
        *post.get("hashtags", []),
    ]
    hashtags = " ".join(dict.fromkeys(filter(None, (_tag(item) for item in tags))))
    source = ""
    if post.get("source_name"):
        source = f"\n\nOfficial source: {post['source_name']}\n{post['source_url']}"

    caption = (
        f"{post['hook']}\n\n"
        f"{post['title']}\n\n"
        "In services ke liye clear, professional assistance available hai:\n"
        f"{bullets}\n\n"
        "Aam taur par yeh documents ready rakhein:\n"
        f"{documents}\n\n"
        f"📩 DM “{brand['cta_keyword']}” for the correct checklist and assistance.\n"
        "Is post ko save karein aur zaruratmand person ke saath share karein.\n"
        f"📍 {brand['service_area']}"
        f"{source}\n\n"
        f"Important: {brand['disclaimer']}. Eligibility, fees, dates and approval are controlled by the relevant authority.\n\n"
        f"{hashtags}"
    )
    return caption[:MAX_CAPTION].rstrip()


def static_post_caption(post: dict, brand: dict) -> str:
    points = "\n".join(f"• {item}" for item in post["bullets"])
    tags = ["VirtualCyberCafe", "DelhiCyberCafe", "DigitalServices", *post.get("hashtags", [])]
    hashtags = " ".join(dict.fromkeys(filter(None, (_tag(item) for item in tags))))
    source = ""
    if post.get("source_name"):
        source = f"\n\nOfficial source: {post['source_name']}\n{post['source_url']}"
    caption = (
        f"{post['title']} — quick information post 📌\n\n"
        f"{points}\n\n"
        "Sahi documents ready rakhne se application process simple ho jata hai. "
        "Post save karein aur kisi zaruratmand person ke saath share karein.\n\n"
        f"📩 DM “{brand['cta_keyword']}” for form and document assistance.\n"
        f"📍 {brand['service_area']}"
        f"{source}\n\n"
        f"Important: {brand['disclaimer']}. Eligibility, fees, dates and approval are controlled by the relevant authority.\n\n"
        f"{hashtags}"
    )
    return caption[:MAX_CAPTION].rstrip()


def _gemini_caption(post: dict, brand: dict, api_key: str, model: str) -> str:
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    prompt = f"""
Write one Instagram Reel caption for {brand['brand_name']}, a private digital assistance service in India.
Audience: Delhi residents, students, job applicants and vehicle owners.
Topic JSON: {json.dumps(post, ensure_ascii=False)}
Rules:
- Natural Hinglish written in Roman script; maximum 1,650 characters before the compliance footer.
- Strong first-line hook, short paragraphs, 3 useful bullets, one save/share prompt and a DM {brand['cta_keyword']} CTA.
- Use 7-11 highly relevant hashtags; do not keyword-stuff.
- Never invent a date, fee, eligibility rule, deadline, vacancy count or government affiliation.
- If this is a live notice, repeat only facts present in the exact official title.
- Do not add a disclaimer; the software adds it.
Return only the caption text.
""".strip()
    response = requests.post(
        endpoint,
        params={"key": api_key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.65, "maxOutputTokens": 700},
        },
        timeout=45,
    )
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def build_caption(post: dict, brand: dict, api_key: str = "", model: str = "") -> str:
    if not api_key:
        return fallback_caption(post, brand)
    try:
        generated = _gemini_caption(post, brand, api_key, model)
        footer = (
            f"\n\nImportant: {brand['disclaimer']}. Eligibility, fees, dates and approval are controlled "
            "by the relevant authority."
        )
        if post.get("source_name"):
            footer += f"\nOfficial source: {post['source_name']} — {post['source_url']}"
        return (generated[: MAX_CAPTION - len(footer)] + footer).strip()
    except (requests.RequestException, KeyError, IndexError, TypeError) as exc:
        LOGGER.warning("Gemini caption unavailable; using permanent template fallback (%s)", exc)
        return fallback_caption(post, brand)
