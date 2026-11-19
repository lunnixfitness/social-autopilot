"""Publicação na Página do Facebook (Graph API oficial). Grupos não têm API: ficam fora do automático."""
from __future__ import annotations

import json
import logging
import os
import time

import requests

log = logging.getLogger(__name__)
VERSION = os.environ.get("FB_API_VERSION", "v25.0")
BASE = f"https://graph.facebook.com/{VERSION}"


class FBError(RuntimeError):
    pass


class FacebookPage:
    def __init__(self, page_id: str, token: str, session: requests.Session | None = None):
        self.page_id, self.token = page_id, token
        self.s = session or requests.Session()

    def _req(self, method: str, endpoint: str, headers: dict | None = None, **params) -> dict:
        url = endpoint if endpoint.startswith("http") else f"{BASE}/{endpoint.lstrip('/')}"
        if headers is None:
            params["access_token"] = self.token
        r = self.s.request(method, url, params=params if method == "GET" else None,
                           data=params if method != "GET" else None, headers=headers, timeout=120)
        try:
            body = r.json()
        except ValueError:
            body = {"raw": r.text[:300]}
        if r.status_code >= 400 or (isinstance(body, dict) and "error" in body):
            err = body.get("error", body) if isinstance(body, dict) else body
            raise FBError(f"{method} {url.split('?')[0]} -> {r.status_code}: {err.get('message', err) if isinstance(err, dict) else err}")
        return body

    def reel(self, video_url: str, description: str) -> str:
        """Fluxo oficial de Reels: start -> upload por URL -> finish (publicado)."""
        start = self._req("POST", f"{self.page_id}/video_reels", upload_phase="start")
        vid = start["video_id"]
        self._req("POST", start.get("upload_url") or f"https://rupload.facebook.com/video-upload/{VERSION}/{vid}",
                  headers={"Authorization": f"OAuth {self.token}", "file_url": video_url})
        self._req("POST", f"{self.page_id}/video_reels", upload_phase="finish", video_id=vid,
                  video_state="PUBLISHED", description=description)
        for _ in range(30):  # o processamento é assíncrono; não bloqueia se demorar
            st = self._req("GET", vid, fields="status").get("status", {})
            if st.get("video_status") in {"ready", "published"} or st.get("publishing_phase", {}).get("status") == "complete":
                break
            if st.get("video_status") == "error":
                raise FBError(f"reel {vid}: erro no processamento")
            time.sleep(10)
        return vid

    def album(self, image_urls: list[str], message: str) -> str:
        """Post com várias fotos (equivalente ao carrossel)."""
        ids = [self._req("POST", f"{self.page_id}/photos", url=u, published="false")["id"] for u in image_urls]
        media = {f"attached_media[{i}]": json.dumps({"media_fbid": m}) for i, m in enumerate(ids)}
        return self._req("POST", f"{self.page_id}/feed", message=message, **media)["id"]


def fb_text(caption: str, tags: list[str], brand: dict) -> str:
    """Legenda do Facebook: a mesma do Instagram, até 3 hashtags e convite para o grupo."""
    fb = brand.get("facebook", {})
    extra = f"\n\n👥 {fb['convite_grupo']} {fb['grupo_url']}" if fb.get("grupo_url") else ""
    return f"{caption}{extra}\n\n{' '.join(tags[:3])}".strip()
