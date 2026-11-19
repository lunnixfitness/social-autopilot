"""Publicação pela API oficial do Instagram (Instagram API com login do Instagram)."""
from __future__ import annotations

import logging
import os
import time

import requests

log = logging.getLogger(__name__)
VERSION = os.environ.get("IG_API_VERSION", "v25.0")
BASE = f"https://graph.instagram.com/{VERSION}"


class IGError(RuntimeError):
    pass


class Instagram:
    def __init__(self, token: str, user_id: str | None = None, session: requests.Session | None = None):
        self.token = token
        self.s = session or requests.Session()
        self.user_id = user_id or self.me()["user_id"]

    def _req(self, method: str, path: str, **params) -> dict:
        url = path if path.startswith("http") else f"{BASE}/{path.lstrip('/')}"
        params["access_token"] = self.token
        r = self.s.request(method, url, params=params if method == "GET" else None,
                           data=params if method != "GET" else None, timeout=60)
        try:
            body = r.json()
        except ValueError:
            body = {"raw": r.text[:300]}
        if r.status_code >= 400 or "error" in body:
            err = body.get("error", body)
            raise IGError(f"{method} {path} -> {r.status_code}: {err.get('message', err) if isinstance(err, dict) else err}")
        return body

    def me(self) -> dict:
        return self._req("GET", "me", fields="user_id,username")

    def _container(self, **fields) -> str:
        return self._req("POST", f"{self.user_id}/media", **fields)["id"]

    def _wait(self, cid: str, timeout: int = 600) -> None:
        start = time.time()
        while True:
            st = self._req("GET", cid, fields="status_code,status").get("status_code")
            if st == "FINISHED":
                return
            if st in {"ERROR", "EXPIRED"}:
                raise IGError(f"container {cid}: {st}")
            if time.time() - start > timeout:
                raise IGError(f"container {cid}: timeout ({st})")
            time.sleep(10)

    def _publish(self, cid: str) -> str:
        self._wait(cid)
        return self._req("POST", f"{self.user_id}/media_publish", creation_id=cid)["id"]

    def comment(self, media_id: str, text: str) -> None:
        if text:
            try:
                self._req("POST", f"{media_id}/comments", message=text)
            except IGError as e:  # comentário é bônus: não derruba o post
                log.warning("primeiro comentário falhou: %s", e)

    def carousel(self, image_urls: list[str], caption: str) -> str:
        if not 2 <= len(image_urls) <= 10:
            raise IGError("carrossel precisa de 2 a 10 imagens")
        children = [self._container(image_url=u, is_carousel_item="true") for u in image_urls]
        for c in children:
            self._wait(c, 180)
        parent = self._container(media_type="CAROUSEL", children=",".join(children), caption=caption)
        return self._publish(parent)

    def reel(self, video_url: str, caption: str, cover_url: str | None = None) -> str:
        fields = dict(media_type="REELS", video_url=video_url, caption=caption, share_to_feed="true")
        if cover_url:
            fields["cover_url"] = cover_url
        return self._publish(self._container(**fields))

    def story(self, image_url: str) -> str:
        return self._publish(self._container(media_type="STORIES", image_url=image_url))


def refresh_token(token: str) -> str:
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60)
    body = r.json()
    if "access_token" not in body:
        raise IGError(f"refresh falhou: {body}")
    return body["access_token"]
