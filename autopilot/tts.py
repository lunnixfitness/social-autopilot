"""Narração por IA (Gemini TTS). Opcional: sem GEMINI_API_KEY, os vídeos saem só com música."""
from __future__ import annotations

import base64
import logging
import os
import re
import subprocess
from pathlib import Path

import requests

log = logging.getLogger(__name__)
URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Do mais novo para o mais antigo; o primeiro que responder é usado.
MODELOS = ["gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"]


def enabled(brand: dict) -> bool:
    return bool(os.environ.get("GEMINI_API_KEY")) and brand.get("voz", {}).get("ativa", True)


def _rate(mime: str) -> int:
    m = re.search(r"rate=(\d+)", mime or "")
    return int(m.group(1)) if m else 24000


def synth(text: str, dst: Path, brand: dict) -> Path | None:
    """Gera um .m4a com a fala. Retorna None se a voz não estiver disponível (o vídeo sai sem narração)."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    voz = brand.get("voz", {})
    estilo = voz.get("estilo", "")
    modelos = [os.environ["GEMINI_TTS_MODEL"]] if os.environ.get("GEMINI_TTS_MODEL") else MODELOS
    for model in modelos:
        part: dict = {"text": text}
        if estilo and "3.8" in model:
            part["speech_metadata"] = {"style": estilo}
        elif estilo:
            part = {"text": f"{estilo}: {text}"}
        body = {
            "contents": [{"role": "user", "parts": [part]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voz.get("nome", "Charon")}}},
            },
        }
        try:
            r = requests.post(URL.format(model=model), headers={"x-goog-api-key": key}, json=body, timeout=120)
            if r.status_code >= 400:
                log.warning("TTS %s: %s %s", model, r.status_code, r.text[:200])
                continue
            inline = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
        except Exception as e:  # rede, formato inesperado
            log.warning("TTS %s falhou: %s", model, e)
            continue
        pcm = base64.b64decode(inline["data"])
        raw = dst.with_suffix(".pcm")
        raw.write_bytes(pcm)
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(_rate(inline.get("mimeType", ""))), "-ac", "1",
             "-i", str(raw), "-af", "silenceremove=start_periods=1:start_threshold=-50dB,loudnorm=I=-16:TP=-1.5",
             "-c:a", "aac", "-b:a", "128k", "-ar", "48000", str(dst)],
            check=True,
        )
        raw.unlink(missing_ok=True)
        return dst
    log.warning("nenhum modelo de voz respondeu; vídeo sem narração")
    return None


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout.strip())
