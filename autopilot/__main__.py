"""CLI: python -m autopilot {build,preview,publish,refresh-ig-token}"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import sys
import time
from pathlib import Path

import requests

from . import build as builder
from .config import ROOT, History, load_brand, load_topics, today_local
from .planner import plan_day, plan_range

log = logging.getLogger("autopilot")


def _date(s: str | None) -> dt.date:
    return dt.date.fromisoformat(s) if s else today_local()


def cmd_build(a) -> int:
    brand, topics, hist = load_brand(), load_topics(), History.load()
    d = _date(a.date)
    plan = plan_day(d, hist.posts, topics, brand)
    m = builder.build_day(plan, brand, Path(a.out), use_ai=not a.no_ai)
    log.info("gerado %s: tema=%s ig=%s yt=%s", d, m["topic"], plan.ig_format, plan.youtube)
    return 0


def cmd_preview(a) -> int:
    brand, topics, hist = load_brand(), load_topics(), History.load()
    out = Path(a.out)
    for p in plan_range(_date(a.date), a.days, hist.posts, topics, brand):
        builder.build_day(p, brand, out, use_ai=False)
        print(f"{p.date} {p.date.strftime('%a')}: {p.topic.id:<18} ig={p.ig_format or '-':<11} yt={'short' if p.youtube else '-'}")
    print(f"prévia em {out}/")
    return 0


def _wait_public(urls: list[str], timeout: int = 420) -> None:
    pending, start = set(urls), time.time()
    while pending and time.time() - start < timeout:
        for u in list(pending):
            try:
                if requests.head(u, timeout=20, allow_redirects=True).status_code == 200:
                    pending.discard(u)
            except requests.RequestException:
                pass
        if pending:
            time.sleep(10)
    if pending:
        raise RuntimeError(f"mídia não ficou pública no GitHub Pages: {sorted(pending)}")


def cmd_publish(a) -> int:
    brand, hist = load_brand(), History.load()
    d = _date(a.date)
    site = Path(a.site)
    m = builder.read_manifest(site, d)
    day = site / d.isoformat()
    base = a.base_url.rstrip("/") + f"/{d.isoformat()}/"
    errors: list[str] = []

    ig = m.get("instagram")
    token = os.environ.get("IG_ACCESS_TOKEN")
    if ig and not token:
        log.warning("Instagram não configurado (falta IG_ACCESS_TOKEN): pulando")
    elif ig:
        from .instagram import Instagram
        try:
            api = Instagram(token, os.environ.get("IG_USER_ID") or None)
            files = ig.get("slides", []) + [x for x in (ig.get("video"), ig.get("cover"), ig.get("story")) if x]
            _wait_public([base + f for f in files])
            if ig["format"] in {"reel", "carrossel"} and not hist.done(m["date"], "instagram"):
                if ig["format"] == "reel":
                    mid = api.reel(base + ig["video"], ig["caption"], base + ig["cover"])
                else:
                    mid = api.carousel([base + s for s in ig["slides"]], ig["caption"])
                api.comment(mid, ig["first_comment"])
                hist.record(m["date"], m["topic"], "instagram", {"ok": True, "id": mid, "format": ig["format"]})
                log.info("Instagram %s publicado: %s", ig["format"], mid)
            if ig.get("story") and not hist.done(m["date"], "instagram_story"):
                sid = api.story(base + ig["story"])
                hist.record(m["date"], m["topic"], "instagram_story", {"ok": True, "id": sid})
                log.info("story publicado: %s", sid)
        except Exception as e:
            log.error("Instagram falhou: %s", e)
            hist.record(m["date"], m["topic"], "instagram_erro", {"ok": False, "erro": str(e)[:500]})
            errors.append("instagram")

    yt = m.get("youtube")
    creds = [os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")]
    if yt and not all(creds):
        log.warning("YouTube não configurado (faltam YT_CLIENT_ID/YT_CLIENT_SECRET/YT_REFRESH_TOKEN): pulando")
    elif yt and not hist.done(m["date"], "youtube"):
        from .youtube import access_token, upload_short
        try:
            res = upload_short(day / yt["video"], yt, brand, access_token(*creds))
            hist.record(m["date"], m["topic"], "youtube", res)
            log.info("YouTube Short enviado: %s (%s)", res["url"], res["privacy"])
        except Exception as e:
            log.error("YouTube falhou: %s", e)
            hist.record(m["date"], m["topic"], "youtube_erro", {"ok": False, "erro": str(e)[:500]})
            errors.append("youtube")

    if hist.entry(m["date"]) is None:  # nada configurado: ainda assim registra o tema para o rodízio andar
        hist.record(m["date"], m["topic"], "gerado", {"ok": True})
    return 1 if errors else 0


def cmd_demos(a) -> int:
    import json

    from .demos import build_all

    res = build_all(Path(a.out))
    (Path(a.out) / "demos.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in res:
        print(f"{r['nome']}: narração IA = {r['narracao_ia']}")
    return 0


def cmd_refresh(a) -> int:
    from .instagram import refresh_token

    new = refresh_token(os.environ["IG_ACCESS_TOKEN"])
    print(f"::add-mask::{new}")
    Path(a.out).write_text(new, encoding="utf-8")
    log.info("token renovado (gravado em %s)", a.out)
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="autopilot")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--date"); b.add_argument("--out", default=str(ROOT / "site")); b.add_argument("--no-ai", action="store_true")
    v = sub.add_parser("preview"); v.add_argument("--date"); v.add_argument("--days", type=int, default=7); v.add_argument("--out", default=str(ROOT / "preview"))
    u = sub.add_parser("publish"); u.add_argument("--date"); u.add_argument("--site", default=str(ROOT / "site")); u.add_argument("--base-url", required=True)
    dm = sub.add_parser("demos"); dm.add_argument("--out", default=str(ROOT / "demos_out"))
    r = sub.add_parser("refresh-ig-token"); r.add_argument("--out", default="new_token.txt")
    a = p.parse_args(argv)
    return {"build": cmd_build, "preview": cmd_preview, "publish": cmd_publish, "refresh-ig-token": cmd_refresh, "demos": cmd_demos}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
