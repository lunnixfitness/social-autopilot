"""LinkedIn pela API oficial (Posts API, w_member_social).

Fluxo: content/linkedin/queue.yaml -> travas -> POST /rest/posts -> link no 1º comentário.
Idempotente (state/linkedin_posted.json), no máximo 1 post a cada 20 h, DRY_RUN grava a prévia.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import requests
import yaml

from .config import ROOT, TZ, load_brand
from .guard import GuardError, check_forbidden

log = logging.getLogger("autopilot.linkedin")

API = "https://api.linkedin.com/rest"
QUEUE = ROOT / "content" / "linkedin" / "queue.yaml"
STATE = ROOT / "state" / "linkedin_posted.json"
PREVIEW = ROOT / "preview" / "linkedin"
MIN_INTERVAL_H = 20
TOKEN_DAYS = 60
TOKEN_WARN_DAYS = 50

# Dado real sempre: nada de caso inventado, depoimento ou promessa de ganho.
FICCAO = [
    r"\b(ficou|ficaram|tornou-se|tornaram-se|virou|viraram) milion[áa]ri[oa]s?\b",
    r"\b(depoimento|caso real|nosso cliente|cliente nosso)\b",
    r"\bfatur(e|ar[áa]?) R\$ ?[\d.,]+ (por m[eê]s|mensais)\b",
    r"\blunnix\b",
]
_ESCAPE = re.compile(r"([\\|{}@\[\]()<>#*_~])")
_HASHTAG = re.compile(r"#[0-9A-Za-zÀ-ÿ_]+")


class TokenError(RuntimeError):
    """401: token vencido ou revogado. Para tudo e abre issue."""


class SkipPost(RuntimeError):
    """422 ou outro erro de conteúdo: pula o item, não repete."""


def escape_commentary(text: str) -> str:
    """Formato "little text": escapa os caracteres reservados, preservando as hashtags."""
    out, last = [], 0
    for m in _HASHTAG.finditer(text):
        out.append(_ESCAPE.sub(r"\\\1", text[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(_ESCAPE.sub(r"\\\1", text[last:]))
    return "".join(out)


@dataclass
class Item:
    id: str
    pilar: str
    texto: str
    hashtags: list[str]
    primeiro_comentario: str
    fonte: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        return cls(
            id=str(d["id"]), pilar=d["pilar"], texto=d["texto"].strip(),
            hashtags=list(d.get("hashtags", [])), primeiro_comentario=d.get("primeiro_comentario", "").strip(),
            fonte=d.get("fonte", ""),
        )


def load_queue(path: Path = QUEUE) -> list[Item]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [Item.from_dict(d) for d in raw.get("posts", [])]


def compose(item: Item, brand: dict) -> str:
    li = brand.get("linkedin", {})
    tags = " ".join(item.hashtags[: li.get("max_hashtags", 5)])
    partes = [item.texto, brand["aviso_legal"], tags]
    return "\n\n".join(p for p in partes if p)


def check_item(item: Item, brand: dict) -> None:
    """Travas antes de publicar. Levanta GuardError se algo não puder ir ao ar."""
    texto = f"{item.texto}\n{item.primeiro_comentario}"
    check_forbidden(texto, brand["termos_proibidos"])
    for pat in FICCAO:
        if re.search(pat, texto, re.IGNORECASE):
            raise GuardError(f"conteúdo não permitido (dado real sempre): /{pat}/")
    li = brand.get("linkedin", {})
    n = len(compose(item, brand))
    if not (li.get("min_chars", 600) <= n <= li.get("max_chars", 2800)):
        raise GuardError(f"tamanho fora da faixa: {n} caracteres")
    if not item.hashtags or len(item.hashtags) > li.get("max_hashtags", 5):
        raise GuardError("de 1 a 5 hashtags")
    if any(not h.startswith("#") or " " in h for h in item.hashtags):
        raise GuardError(f"hashtag inválida: {item.hashtags}")
    if "http" in item.texto:
        raise GuardError("link vai no 1º comentário, não no corpo")


class State:
    def __init__(self, path: Path = STATE):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"posts": {}}

    def posted(self, item_id: str) -> bool:
        return item_id in self.data["posts"]

    def last_time(self) -> dt.datetime | None:
        ts = [dt.datetime.fromisoformat(p["em"]) for p in self.data["posts"].values() if p.get("em")]
        return max(ts) if ts else None

    def record(self, item_id: str, urn: str, comment: str | None, now: dt.datetime | None = None) -> None:
        em = (now or dt.datetime.now(TZ)).isoformat(timespec="seconds")
        self.data["posts"][item_id] = {"urn": urn, "comentario": comment, "em": em}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class LinkedIn:
    def __init__(self, token: str, author: str | None = None, version: str | None = None,
                 session: requests.Session | None = None, sleep=time.sleep):
        self.token = token
        self.version = version or os.environ.get("LINKEDIN_API_VERSION") or "202609"
        self.s = session or requests.Session()
        self.sleep = sleep
        self.author = author or self.whoami()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "LinkedIn-Version": self.version,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, url: str, **kw) -> requests.Response:
        for tentativa in range(5):
            r = self.s.request(method, url, headers=self._headers(), timeout=60, **kw)
            if r.status_code == 401:
                raise TokenError("LinkedIn recusou o token (401): renove o token")
            if r.status_code == 422:
                raise SkipPost(f"LinkedIn recusou o conteúdo (422): {r.text[:500]}")
            if r.status_code == 429 or r.status_code >= 500:
                espera = 2 ** tentativa * 5
                log.warning("LinkedIn %s, nova tentativa em %ss", r.status_code, espera)
                self.sleep(espera)
                continue
            if r.status_code >= 400:
                raise SkipPost(f"LinkedIn {r.status_code}: {r.text[:500]}")
            return r
        raise RuntimeError("LinkedIn indisponível depois de 5 tentativas")

    def whoami(self) -> str:
        r = self.s.get("https://api.linkedin.com/v2/userinfo", headers={"Authorization": f"Bearer {self.token}"}, timeout=30)
        if r.status_code == 401:
            raise TokenError("LinkedIn recusou o token (401): renove o token")
        r.raise_for_status()
        return f"urn:li:person:{r.json()['sub']}"

    def post_text(self, commentary: str) -> str:
        body = {
            "author": self.author,
            "commentary": escape_commentary(commentary),
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        r = self._request("POST", f"{API}/posts", json=body)
        urn = r.headers.get("x-restli-id")
        if not urn:
            raise RuntimeError("post criado sem x-restli-id")
        return urn

    def comment(self, post_urn: str, text: str) -> str:
        enc = requests.utils.quote(post_urn, safe="")
        body = {"actor": self.author, "object": post_urn, "message": {"text": escape_commentary(text)}}
        r = self._request("POST", f"{API}/socialActions/{enc}/comments", json=body)
        return r.headers.get("x-restli-id", "")


def next_item(queue: list[Item], state: State) -> Item | None:
    return next((i for i in queue if not state.posted(i.id)), None)


def publish_next(dry_run: bool = False, now: dt.datetime | None = None, api: LinkedIn | None = None,
                 queue: list[Item] | None = None, state: State | None = None, brand: dict | None = None) -> str:
    brand = brand or load_brand()
    queue = queue if queue is not None else load_queue()
    state = state or State()
    now = now or dt.datetime.now(TZ)

    last = state.last_time()
    if last and not dry_run and now - last < dt.timedelta(hours=MIN_INTERVAL_H):
        log.info("último post há menos de %sh: nada a fazer", MIN_INTERVAL_H)
        return "intervalo"
    item = next_item(queue, state)
    if not item:
        log.info("fila do LinkedIn vazia")
        return "vazia"
    check_item(item, brand)
    texto = compose(item, brand)

    if dry_run:
        PREVIEW.mkdir(parents=True, exist_ok=True)
        (PREVIEW / f"{item.id}.txt").write_text(f"{texto}\n\n--- 1º comentário ---\n{item.primeiro_comentario}\n", encoding="utf-8")
        log.info("prévia gravada: preview/linkedin/%s.txt (%s caracteres)", item.id, len(texto))
        return "previa"

    api = api or LinkedIn(os.environ["LINKEDIN_ACCESS_TOKEN"], os.environ.get("LINKEDIN_AUTHOR_URN") or None)
    urn = api.post_text(texto)
    cid = None
    if item.primeiro_comentario:
        try:
            cid = api.comment(urn, item.primeiro_comentario)
        except (SkipPost, RuntimeError) as e:  # o post já saiu: registra mesmo sem o comentário
            log.error("comentário falhou: %s", e)
    state.record(item.id, urn, cid, now)
    log.info("LinkedIn publicado: %s (%s)", urn, item.id)
    return "publicado"


def preview_all(brand: dict | None = None, queue: list[Item] | None = None) -> list[tuple[str, int, str]]:
    """Valida e grava a prévia de toda a fila. Retorna (id, caracteres, status)."""
    brand = brand or load_brand()
    PREVIEW.mkdir(parents=True, exist_ok=True)
    res = []
    for item in queue if queue is not None else load_queue():
        try:
            check_item(item, brand)
            texto = compose(item, brand)
            (PREVIEW / f"{item.id}.txt").write_text(f"{texto}\n\n--- 1º comentário ---\n{item.primeiro_comentario}\n", encoding="utf-8")
            res.append((item.id, len(texto), "ok"))
        except GuardError as e:
            res.append((item.id, 0, f"bloqueado: {e}"))
    return res


def token_age_days(created_at: str, today: dt.date | None = None) -> int:
    today = today or dt.datetime.now(TZ).date()
    return (today - dt.date.fromisoformat(created_at[:10])).days
