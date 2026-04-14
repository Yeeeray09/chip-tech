"""
publisher.py — Upload images to Cloudinary and publish a carousel to Instagram
via the Facebook Graph API v19.0.
"""

import logging
import os
import time
from pathlib import Path

import cloudinary
import cloudinary.uploader
import requests
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

GRAPH_API_VERSION = "v19.0"
GRAPH_BASE        = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


# ── Cloudinary ────────────────────────────────────────────────────────────────

def _configure_cloudinary() -> None:
    cloudinary.config(
        cloud_name = os.environ["CLOUDINARY_CLOUD_NAME"],
        api_key    = os.environ["CLOUDINARY_API_KEY"],
        api_secret = os.environ["CLOUDINARY_API_SECRET"],
        secure     = True,
    )


def upload_images(image_paths: list[Path]) -> list[str]:
    """
    Upload PNG files to Cloudinary.
    Returns a list of secure HTTPS URLs.
    """
    _configure_cloudinary()
    urls: list[str] = []

    for path in image_paths:
        log.info("  Uploading %s to Cloudinary…", path.name)
        result = cloudinary.uploader.upload(
            str(path),
            folder     = "chip-tech",
            use_filename = True,
            unique_filename = True,
            resource_type = "image",
        )
        url = result["secure_url"]
        log.info("    → %s", url)
        urls.append(url)

    return urls


# ── Instagram Graph API ───────────────────────────────────────────────────────

def _ig_request(method: str, endpoint: str, **kwargs) -> dict:
    """Thin wrapper around requests for Graph API calls."""
    url = f"{GRAPH_BASE}/{endpoint}"
    params = kwargs.pop("params", {})
    params["access_token"] = os.environ["FACEBOOK_ACCESS_TOKEN"]

    response = getattr(requests, method)(url, params=params, **kwargs)

    try:
        data = response.json()
    except Exception:
        response.raise_for_status()
        raise

    if "error" in data:
        raise RuntimeError(f"Graph API error: {data['error']}")

    return data


def _create_image_container(ig_user_id: str, image_url: str, is_carousel_item: bool = True) -> str:
    """Create an IG media container for a single image. Returns container ID."""
    payload = {
        "image_url":          image_url,
        "is_carousel_item":   str(is_carousel_item).lower(),
    }
    data = _ig_request("post", f"{ig_user_id}/media", data=payload)
    container_id = data["id"]
    log.info("    Image container: %s", container_id)
    return container_id


def _create_carousel_container(
    ig_user_id: str,
    children_ids: list[str],
    caption: str,
) -> str:
    """Create the parent carousel container. Returns container ID."""
    payload = {
        "media_type": "CAROUSEL",
        "children":   ",".join(children_ids),
        "caption":    caption,
    }
    data = _ig_request("post", f"{ig_user_id}/media", data=payload)
    container_id = data["id"]
    log.info("  Carousel container: %s", container_id)
    return container_id


def _wait_for_container(ig_user_id: str, container_id: str, max_wait: int = 120) -> None:
    """Poll until the container is FINISHED processing."""
    waited = 0
    while waited < max_wait:
        data   = _ig_request("get", container_id, params={"fields": "status_code"})
        status = data.get("status_code", "IN_PROGRESS")
        log.info("  Container %s status: %s", container_id, status)
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(f"Container {container_id} encountered an error")
        time.sleep(5)
        waited += 5
    raise TimeoutError(f"Container {container_id} did not finish in {max_wait}s")


def _publish_container(ig_user_id: str, container_id: str) -> str:
    """Publish a finished container. Returns the published media ID."""
    data = _ig_request("post", f"{ig_user_id}/media_publish", data={"creation_id": container_id})
    media_id = data["id"]
    log.info("Published! Media ID: %s", media_id)
    return media_id


def publish_carousel(image_paths: list[Path], caption: str) -> str:
    """
    Full pipeline: upload → create containers → publish carousel.
    Returns the Instagram media ID of the published post.
    """
    ig_user_id = os.environ["INSTAGRAM_USER_ID"]

    # 1. Upload to Cloudinary
    log.info("Step 1/4 — Uploading images to Cloudinary…")
    urls = upload_images(image_paths)

    # 2. Create individual image containers
    log.info("Step 2/4 — Creating image containers…")
    child_ids: list[str] = []
    for url in urls:
        cid = _create_image_container(ig_user_id, url)
        child_ids.append(cid)

    # 3. Create carousel container
    log.info("Step 3/4 — Creating carousel container…")
    carousel_id = _create_carousel_container(ig_user_id, child_ids, caption)
    _wait_for_container(ig_user_id, carousel_id)

    # 4. Publish
    log.info("Step 4/4 — Publishing…")
    media_id = _publish_container(ig_user_id, carousel_id)

    return media_id
