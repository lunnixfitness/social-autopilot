"""Upload de Shorts pela YouTube Data API v3 (OAuth com refresh token, upload resumable)."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import requests

log = logging.getLogger(__name__)
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


class YTError(RuntimeError):
    pass


def access_token(client_id: str, client_secret: str, refresh: str) -> str:
    r = requests.post(TOKEN_URL, timeout=60, data={
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh, "grant_type": "refresh_token",
    })
    body = r.json()
    if "access_token" not in body:
        hint = " (refresh token expirou: o app OAuth está em modo Teste? publique-o em Produção)" \
            if body.get("error") == "invalid_grant" else ""
        raise YTError(f"token Google: {body.get('error')}{hint}")
    return body["access_token"]


def upload_short(video: Path, meta: dict, brand: dict, token: str) -> dict:
    yt = brand["youtube"]
    privacy = os.environ.get("YT_PRIVACY", yt.get("privacidade", "public"))
    resource = {
        "snippet": {
            "title": meta["title"], "description": meta["description"], "tags": meta["tags"],
            "categoryId": yt.get("categoria", "27"), "defaultLanguage": yt.get("idioma", "pt-BR"),
            "defaultAudioLanguage": yt.get("idioma", "pt-BR"),
        },
        "status": {
            "privacyStatus": privacy, "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": False, "embeddable": True,
        },
    }
    size = video.stat().st_size
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
         "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)}
    r = requests.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"},
                      headers=h, data=json.dumps(resource), timeout=60)
    if r.status_code >= 400 or "Location" not in r.headers:
        raise YTError(f"início do upload: {r.status_code} {r.text[:400]}")
    with video.open("rb") as fh:
        up = requests.put(r.headers["Location"], data=fh, timeout=900,
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "video/mp4",
                                   "Content-Length": str(size)})
    if up.status_code not in (200, 201):
        raise YTError(f"upload: {up.status_code} {up.text[:400]}")
    body = up.json()
    got = body.get("status", {}).get("privacyStatus")
    result = {"ok": True, "id": body["id"], "url": f"https://youtube.com/shorts/{body['id']}", "privacy": got}
    if got != privacy:
        result["aviso"] = ("YouTube travou como privado: o projeto Google ainda não passou na auditoria "
                           "da YouTube API. Veja o README, seção YouTube.")
        log.warning(result["aviso"])
    return result
