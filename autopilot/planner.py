"""Decide o que sai em cada dia: formato por rede e tema (rodízio de pilares, sem repetir)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .config import Topic


@dataclass(frozen=True)
class DayPlan:
    date: dt.date
    topic: Topic
    ig_format: str | None     # reel | carrossel | dica_story | None
    youtube: bool
    seq: int                  # índice do post na sequência (para o rodízio)


def pick_topic(seq: int, used: list[str], topics: list[Topic], rodizio: list[str]) -> Topic:
    pilar = rodizio[seq % len(rodizio)]
    pool = [t for t in topics if t.pilar == pilar] or topics
    # o menos usado recentemente; nunca usado vem primeiro, em ordem do banco
    last = {tid: i for i, tid in enumerate(used)}
    return min(pool, key=lambda t: (last.get(t.id, -1), pool.index(t)))


def plan_day(date: dt.date, history_posts: list[dict], topics: list[Topic], brand: dict) -> DayPlan:
    cal = brand["calendario"]
    wd = date.weekday()
    ig = cal["instagram"].get(wd) or cal["instagram"].get(str(wd))
    yt = wd in cal["youtube_shorts"]
    prior = [p for p in history_posts if p["date"] < date.isoformat()]
    existing = next((p for p in history_posts if p["date"] == date.isoformat()), None)
    seq = len(prior)
    if existing:  # rerun do mesmo dia: mantém o tema já escolhido
        topic = next(t for t in topics if t.id == existing["topic"])
    else:
        topic = pick_topic(seq, [p["topic"] for p in prior], topics, brand["rodizio_pilares"])
    return DayPlan(date=date, topic=topic, ig_format=ig, youtube=yt, seq=seq)


def plan_range(start: dt.date, days: int, history_posts: list[dict], topics: list[Topic], brand: dict) -> list[DayPlan]:
    posts = list(history_posts)
    out = []
    for i in range(days):
        d = start + dt.timedelta(days=i)
        p = plan_day(d, posts, topics, brand)
        out.append(p)
        if not any(x["date"] == d.isoformat() for x in posts):
            posts.append({"date": d.isoformat(), "topic": p.topic.id, "channels": {}})
    return out
