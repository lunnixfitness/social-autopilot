from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
PKG = Path(__file__).resolve().parent
TZ = ZoneInfo("America/Sao_Paulo")
STATE_FILE = ROOT / "state" / "history.json"


@dataclass(frozen=True)
class Topic:
    id: str
    pilar: str
    gancho: str
    pontos: tuple[str, ...]
    base_legal: str
    hashtags: tuple[str, ...]
    titulo_yt: str

    @property
    def texto_banco(self) -> str:
        return " ".join([self.gancho, *self.pontos, self.base_legal, self.titulo_yt])


def load_brand(path: Path | None = None) -> dict:
    return yaml.safe_load((path or PKG / "brand.yaml").read_text(encoding="utf-8"))


def load_topics(path: Path | None = None) -> list[Topic]:
    raw = yaml.safe_load((path or PKG / "topics.yaml").read_text(encoding="utf-8"))["temas"]
    return [
        Topic(
            id=t["id"], pilar=t["pilar"], gancho=t["gancho"], pontos=tuple(t["pontos"]),
            base_legal=t["base_legal"], hashtags=tuple(t["hashtags"]), titulo_yt=t["titulo_yt"],
        )
        for t in raw
    ]


def today_local() -> dt.date:
    return dt.datetime.now(TZ).date()


@dataclass
class History:
    """Histórico persistido no repo (state/history.json). Fonte da rotação e da idempotência."""
    posts: list[dict] = field(default_factory=list)
    path: Path = STATE_FILE

    @classmethod
    def load(cls, path: Path = STATE_FILE) -> "History":
        if path.exists():
            return cls(posts=json.loads(path.read_text(encoding="utf-8")).get("posts", []), path=path)
        return cls(path=path)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"posts": self.posts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def entry(self, date: str) -> dict | None:
        return next((p for p in self.posts if p["date"] == date), None)

    def record(self, date: str, topic_id: str, channel: str, result: dict) -> None:
        e = self.entry(date)
        if e is None:
            e = {"date": date, "topic": topic_id, "channels": {}}
            self.posts.append(e)
        e["channels"][channel] = result
        self.save()

    def done(self, date: str, channel: str) -> bool:
        e = self.entry(date)
        return bool(e and e["channels"].get(channel, {}).get("ok"))
