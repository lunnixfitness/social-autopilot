"""Gera tudo de um dia em site/<data>/ + plan.json. A publicação só lê o que foi gerado aqui."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from . import render, writer
from .planner import DayPlan


def build_day(plan: DayPlan, brand: dict, out_root: Path, use_ai: bool = True) -> dict:
    out = out_root / plan.date.isoformat()
    out.mkdir(parents=True, exist_ok=True)
    t = plan.topic
    manifest: dict = {
        "date": plan.date.isoformat(), "topic": t.id, "pilar": t.pilar, "seq": plan.seq,
        "instagram": None, "youtube": None,
    }
    need_video = plan.ig_format == "reel" or plan.youtube
    video, voiced = render.reel(t, brand, out, plan.date) if need_video else (None, False)
    manifest["narracao_ia"] = voiced
    cover = render.cover(t, brand, out, plan.date) if need_video else None

    if plan.ig_format:
        cap, origem = writer.caption(t, brand, use_ai=use_ai)
        if voiced and plan.ig_format == "reel":
            cap = f"{cap}\n\nNarração com voz gerada por IA."
        ig: dict = {
            "format": plan.ig_format, "caption": cap, "caption_origin": origem,
            "first_comment": " ".join(writer.hashtags(t, brand)),
        }
        if plan.ig_format == "carrossel":
            ig["slides"] = [p.name for p in render.carousel(t, brand, out, plan.date)]
        elif plan.ig_format == "reel":
            ig["video"], ig["cover"] = video.name, cover.name
        story_kind = "dica" if plan.ig_format == "dica_story" else "chamada"
        ig["story"] = render.story(t, brand, out, plan.date, story_kind).name
        manifest["instagram"] = ig

    if plan.youtube:
        manifest["youtube"] = {"video": video.name, **writer.youtube_meta(t, brand, voiced)}

    (out / "plan.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_root / ".nojekyll").touch()
    return manifest


def read_manifest(site: Path, date: dt.date) -> dict:
    return json.loads((site / date.isoformat() / "plan.json").read_text(encoding="utf-8"))
