"""Textos de legenda, story e YouTube. Base = banco verificado; Gemini opcional só reescreve o tom."""
from __future__ import annotations

import json
import logging
import os

import requests

from .config import Topic
from .guard import ai_text_is_safe, check_forbidden

log = logging.getLogger(__name__)
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def hashtags(topic: Topic, brand: dict) -> list[str]:
    tags: list[str] = []
    for h in [*topic.hashtags, *brand.get("hashtags_fixas", [])]:
        if h.lower() not in (x.lower() for x in tags):
            tags.append(h)
    return tags[: brand.get("max_hashtags", 5)]


def base_caption(topic: Topic, brand: dict) -> str:
    cta = brand["cta"]["velatrix" if topic.pilar == "velatrix" else "padrao"]
    corpo = "\n\n".join(f"▪️ {p}" for p in topic.pontos)
    return (
        f"{topic.gancho}\n\n{corpo}\n\n📚 Base: {topic.base_legal}\n\n{cta}\n\n"
        f"{brand['aviso_legal']}"
    )


def _gemini_rewrite(topic: Topic, model: str, key: str) -> str | None:
    prompt = (
        "Reescreva em português do Brasil, tom direto e humano, a legenda de Instagram abaixo. "
        "Regras: mantenha o sentido exato; NÃO acrescente números, datas, leis, temas, artigos ou "
        "promessas; sem hashtags; sem emojis em excesso; máximo 900 caracteres; primeira linha é o gancho.\n\n"
        f"Gancho: {topic.gancho}\nPontos:\n- " + "\n- ".join(topic.pontos)
    )
    try:
        r = requests.post(
            GEMINI_URL.format(model=model), params={"key": key}, timeout=60,
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.7}},
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:  # IA é opcional: qualquer falha cai no texto do banco
        log.warning("Gemini indisponível (%s); usando o banco", e)
        return None


def caption(topic: Topic, brand: dict, use_ai: bool = True) -> tuple[str, str]:
    """Retorna (legenda, origem). A origem vai para o plan.json para auditoria."""
    base = base_caption(topic, brand)
    key = os.environ.get("GEMINI_API_KEY")
    if use_ai and key:
        ai = _gemini_rewrite(topic, os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"), key)
        if ai:
            ok, why = ai_text_is_safe(ai, topic.texto_banco, brand["termos_proibidos"])
            if ok:
                cta = brand["cta"]["velatrix" if topic.pilar == "velatrix" else "padrao"]
                text = f"{ai}\n\n📚 Base: {topic.base_legal}\n\n{cta}\n\n{brand['aviso_legal']}"
                check_forbidden(text, brand["termos_proibidos"])
                return text[:2200], "gemini"
            log.warning("texto da IA descartado: %s", why)
    check_forbidden(base, brand["termos_proibidos"])
    return base[:2200], "banco"


def youtube_meta(topic: Topic, brand: dict, voiced: bool = False) -> dict:
    title = topic.titulo_yt
    if "#shorts" not in title.lower() and len(title) + 8 <= 100:
        title = f"{title} #Shorts"
    desc = (
        f"{topic.gancho}\n\n" + "\n".join(f"• {p}" for p in topic.pontos)
        + f"\n\nBase: {topic.base_legal}\n\n{brand['aviso_legal']}"
        + ("\nNarração com voz gerada por IA." if voiced else "") + "\n\n"
        f"Instagram: {brand['perfil']['instagram']} | {brand['perfil']['site']}\n\n"
        + " ".join(["#Shorts", *hashtags(topic, brand)[:3]])
    )
    check_forbidden(title + desc, brand["termos_proibidos"])
    tags = [h.lstrip("#") for h in hashtags(topic, brand)]
    return {"title": title[:100], "description": desc[:5000], "tags": tags}


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
