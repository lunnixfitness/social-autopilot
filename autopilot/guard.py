"""Travas de conteúdo. Tudo que vai ao ar passa por aqui."""
from __future__ import annotations

import re
import unicodedata

_NUM = re.compile(r"\d+(?:[.,/]\d+)*")
_LEI = re.compile(
    r"\b(?:art(?:igo)?\.?|lei|lc|ec|tema|re|resp|are|cpc|ctn|provimento|decreto|s[úu]mula)\s*[\w.\-/º°]*",
    re.IGNORECASE,
)


class GuardError(ValueError):
    pass


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in _NUM.findall(text)}


def forbidden_hits(text: str, termos: list[str]) -> list[str]:
    t = _norm(text)
    return [w for w in termos if _norm(w) in t]


def check_forbidden(text: str, termos: list[str]) -> None:
    hits = forbidden_hits(text, termos)
    if hits:
        raise GuardError(f"termos proibidos (Provimento 205/OAB): {hits}")


def ai_text_is_safe(ai_text: str, banco: str, termos: list[str]) -> tuple[bool, str]:
    """A versão da IA só passa se não trouxer número, norma ou termo proibido fora do banco."""
    if forbidden_hits(ai_text, termos):
        return False, "termo proibido"
    extra = numbers(ai_text) - numbers(banco)
    if extra:
        return False, f"números fora do banco: {sorted(extra)}"
    banco_n = _norm(banco)
    for m in _LEI.finditer(ai_text):
        ref = _norm(m.group(0)).strip(" .")
        if any(ch.isdigit() for ch in ref) and ref not in banco_n:
            return False, f"norma fora do banco: {m.group(0)!r}"
    return True, "ok"
