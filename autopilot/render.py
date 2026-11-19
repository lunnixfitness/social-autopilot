"""Arte: carrossel 1080x1350, story 1080x1920 e reel/Short 1080x1920 (H.264 + AAC)."""
from __future__ import annotations

import datetime as dt
import hashlib
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from .config import ROOT, Topic

W = 1080
FEED_H, STORY_H = 1350, 1920
FPS = 30
MARGIN = 96
FONT_CANDIDATES = {
    True: ["/usr/share/fonts/opentype/inter/Inter-Bold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    False: ["/usr/share/fonts/opentype/inter/Inter-Regular.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
}


@lru_cache(maxsize=None)
def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES[bold]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    out = subprocess.run(["fc-match", "-f", "%{file}", "sans:bold" if bold else "sans"], capture_output=True, text=True)
    return ImageFont.truetype(out.stdout.strip(), size)


def hex2rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=f) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_text(draw, text, width, max_h, start, minimum=34, bold=True, spacing=1.18):
    size = start
    while True:
        f = font(size, bold)
        lines = wrap(draw, text, f, width)
        h = int(len(lines) * size * spacing)
        if h <= max_h or size <= minimum:
            return f, lines, h
        size -= 4


def draw_block(draw, xy, lines, f, fill, spacing=1.18):
    x, y = xy
    for ln in lines:
        draw.text((x, y), ln, font=f, fill=fill)
        y += int(f.size * spacing)
    return y


def photos() -> list[Path]:
    d = ROOT / "assets" / "fotos"
    return sorted(p for p in d.glob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})


def pick_photo(date: dt.date, salt: str = "") -> Path | None:
    ps = photos()
    if not ps:
        return None
    i = int(hashlib.sha1(f"{date}{salt}".encode()).hexdigest(), 16) % len(ps)
    return ps[i]


def background(size: tuple[int, int], brand: dict, photo: Path | None = None, darken: float = 0.62) -> Image.Image:
    w, h = size
    navy = hex2rgb(brand["cores"]["fundo"])
    if photo:
        im = Image.open(photo).convert("RGB")
        scale = max(w / im.width, h / im.height)
        im = im.resize((int(im.width * scale) + 1, int(im.height * scale) + 1), Image.LANCZOS)
        left, top = (im.width - w) // 2, max(0, (im.height - h) // 3)
        im = im.crop((left, top, left + w, top + h))
        grad = Image.new("L", (1, h))
        for y in range(h):  # escurece mais embaixo, onde vai o texto
            grad.putpixel((0, y), int(255 * min(1, darken * 0.55 + darken * 0.8 * y / h)))
        overlay = Image.new("RGB", (w, h), navy)
        return Image.composite(overlay, im, grad.resize((w, h)))
    base = Image.new("RGB", (w, h), navy)
    glow = Image.new("RGB", (w, h), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gold = hex2rgb(brand["cores"]["destaque"])
    gd.ellipse((w * 0.45, -h * 0.25, w * 1.5, h * 0.45), fill=tuple(int(c * 0.35) for c in gold))
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    return ImageChops.add(base, glow)


def chrome(draw: ImageDraw.ImageDraw, size, brand, page: str | None = None):
    """Faixa dourada, @perfil e numeração."""
    w, h = size
    gold = hex2rgb(brand["cores"]["destaque"])
    soft = hex2rgb(brand["cores"]["suave"])
    draw.rectangle((MARGIN, MARGIN - 30, MARGIN + 120, MARGIN - 22), fill=gold)
    f = font(30, False)
    draw.text((MARGIN, h - MARGIN + 6), brand["perfil"]["instagram"], font=f, fill=soft)
    if page:
        tw = draw.textlength(page, font=f)
        draw.text((w - MARGIN - tw, h - MARGIN + 6), page, font=f, fill=soft)


PILAR_LABEL = {"tributario": "TRIBUTÁRIO", "previdenciario": "PREVIDENCIÁRIO", "pericia": "PERÍCIA", "escritorios": "PARA ESCRITÓRIOS", "velatrix": "VELATRIX"}


def _label(draw, xy, text, brand):
    gold = hex2rgb(brand["cores"]["destaque"])
    draw.text(xy, text, font=font(32), fill=gold)


# ---------- carrossel ----------
def carousel(topic: Topic, brand: dict, out: Path, date: dt.date) -> list[Path]:
    size = (W, FEED_H)
    white, gold, soft = (hex2rgb(brand["cores"][k]) for k in ("texto", "destaque", "suave"))
    slides: list[Image.Image] = []
    inner = W - 2 * MARGIN

    im = background(size, brand)
    d = ImageDraw.Draw(im)
    _label(d, (MARGIN, MARGIN + 10), PILAR_LABEL.get(topic.pilar, ""), brand)
    f, lines, h = fit_text(d, topic.gancho, inner, 700, 104)
    draw_block(d, (MARGIN, (FEED_H - h) // 2 - 40), lines, f, white)
    d.text((MARGIN, FEED_H - MARGIN - 90), "Arraste para o lado  →", font=font(38), fill=gold)
    slides.append(im)

    for i, p in enumerate(topic.pontos, 1):
        im = background(size, brand)
        d = ImageDraw.Draw(im)
        d.text((MARGIN, MARGIN + 40), f"{i:02d}", font=font(150), fill=gold)
        f, lines, h = fit_text(d, p, inner, 640, 76)
        draw_block(d, (MARGIN, 470), lines, f, white)
        slides.append(im)

    im = background(size, brand)
    d = ImageDraw.Draw(im)
    _label(d, (MARGIN, MARGIN + 10), "BASE", brand)
    f, lines, h = fit_text(d, topic.base_legal, inner, 520, 64)
    y = draw_block(d, (MARGIN, 300), lines, f, white)
    f2, l2, _ = fit_text(d, brand["aviso_legal"], inner, 200, 36, bold=False)
    draw_block(d, (MARGIN, y + 60), l2, f2, soft)
    slides.append(im)

    im = background(size, brand)
    d = ImageDraw.Draw(im)
    cta = brand["cta"]["velatrix" if topic.pilar == "velatrix" else "padrao"]
    f, lines, h = fit_text(d, cta, inner, 500, 84)
    y = draw_block(d, (MARGIN, (FEED_H - h) // 2 - 80), lines, f, white)
    d.text((MARGIN, y + 50), f"Siga {brand['perfil']['instagram']}", font=font(46), fill=gold)
    slides.append(im)

    slides = slides[:10]
    paths = []
    for i, s in enumerate(slides, 1):
        chrome(ImageDraw.Draw(s), size, brand, f"{i}/{len(slides)}")
        p = out / f"slide_{i:02d}.jpg"
        s.save(p, "JPEG", quality=92)
        paths.append(p)
    return paths


# ---------- story ----------
def story(topic: Topic, brand: dict, out: Path, date: dt.date, kind: str) -> Path:
    size = (W, STORY_H)
    white, gold, soft = (hex2rgb(brand["cores"][k]) for k in ("texto", "destaque", "suave"))
    im = background(size, brand, pick_photo(date, "story"), darken=0.7)
    d = ImageDraw.Draw(im)
    inner = W - 2 * MARGIN
    top = 300  # zona segura: topo e base ficam sob a interface do Instagram
    if kind == "dica":
        _label(d, (MARGIN, top), "DICA DE DOMINGO", brand)
        f, lines, h = fit_text(d, topic.gancho, inner, 420, 86)
        y = draw_block(d, (MARGIN, top + 80), lines, f, white)
        f2, l2, _ = fit_text(d, topic.pontos[0], inner, 500, 54, bold=False)
        y = draw_block(d, (MARGIN, y + 50), l2, f2, white)
        f3, l3, _ = fit_text(d, f"Base: {topic.base_legal}", inner, 220, 34, bold=False)
        draw_block(d, (MARGIN, y + 40), l3, f3, soft)
    else:
        _label(d, (MARGIN, top), "POST NOVO", brand)
        f, lines, h = fit_text(d, topic.gancho, inner, 700, 96)
        y = draw_block(d, (MARGIN, top + 80), lines, f, white)
        d.text((MARGIN, y + 60), brand["cta"]["story"], font=font(44), fill=gold)
    d.text((MARGIN, STORY_H - 330), brand["perfil"]["instagram"], font=font(40), fill=soft)
    p = out / "story.jpg"
    im.save(p, "JPEG", quality=92)
    return p


# ---------- reel / Short ----------
def _scene(text: str, brand: dict, photo: Path | None, label: str | None, big: bool, footer: str | None = None) -> Image.Image:
    size = (W, STORY_H)
    white, gold, soft = (hex2rgb(brand["cores"][k]) for k in ("texto", "destaque", "suave"))
    im = background(size, brand, photo, darken=0.72)
    d = ImageDraw.Draw(im)
    inner = W - 2 * MARGIN
    f, lines, h = fit_text(d, text, inner, 760, 104 if big else 78)
    y0 = 1020 - h // 2 if photo is None else 1180 - h // 2
    if label:
        d.text((MARGIN, y0 - 90), label, font=font(40), fill=gold)
    y = draw_block(d, (MARGIN, y0), lines, f, white)
    if footer:
        f2, l2, _ = fit_text(d, footer, inner, 200, 36, bold=False)
        draw_block(d, (MARGIN, y + 40), l2, f2, soft)
    d.text((MARGIN, STORY_H - 330), brand["perfil"]["instagram"], font=font(36), fill=soft)
    return im


def reel_scenes(topic: Topic, brand: dict, date: dt.date) -> list[tuple[Image.Image, float]]:
    cta = brand["cta"]["velatrix" if topic.pilar == "velatrix" else "padrao"]
    sc = [(_scene(topic.gancho, brand, pick_photo(date, "reel"), PILAR_LABEL.get(topic.pilar), True), 3.5)]
    for i, p in enumerate(topic.pontos, 1):
        sc.append((_scene(p, brand, None, f"{i:02d}", False), max(3.5, min(6.0, len(p) / 16))))
    sc.append((_scene(cta, brand, None, None, True, footer=f"Base: {topic.base_legal}. {brand['aviso_legal']}"), 4.0))
    return sc


def cover(topic: Topic, brand: dict, out: Path, date: dt.date) -> Path:
    im = _scene(topic.gancho, brand, pick_photo(date, "reel"), PILAR_LABEL.get(topic.pilar), True)
    p = out / "cover.jpg"
    im.save(p, "JPEG", quality=92)
    return p


def audio_track(date: dt.date) -> Path | None:
    tracks = sorted((ROOT / "assets" / "audio").glob("*.mp3"))
    if not tracks:
        return None
    return tracks[date.toordinal() % len(tracks)]


def reel_narration(topic: Topic, brand: dict) -> list[str]:
    """Fala de cada cena do reel: sai do banco verificado, nada inventado."""
    cta = "Conheça o Velatrix." if topic.pilar == "velatrix" else "Salve e mande para quem precisa ver."
    return [topic.gancho, *topic.pontos, f"{cta} {brand['aviso_legal']}"]


def reel(topic: Topic, brand: dict, out: Path, date: dt.date) -> tuple[Path, bool]:
    return encode_scenes(reel_scenes(topic, brand, date), out / "reel.mp4", date,
                         brand=brand, narration=reel_narration(topic, brand))


def encode_scenes(scenes: list[tuple[Image.Image, float]], dst: Path, date: dt.date, zoom: float = 0.0009,
                  brand: dict | None = None, narration: list[str | None] | None = None) -> tuple[Path, bool]:
    """Cenas (imagem 1080x1920, duração) -> MP4 vertical com zoom lento, transições, voz (opcional) e música.
    Retorna (arquivo, tem_narração)."""
    from . import tts

    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg não encontrado")
    xf, lead = 0.4, 0.25
    with tempfile.TemporaryDirectory() as td:
        clips: list[Path | None] = [None] * len(scenes)
        if narration and brand and tts.enabled(brand):
            for i, txt in enumerate(narration[: len(scenes)]):
                if txt:
                    clips[i] = tts.synth(txt, Path(td) / f"v{i}.m4a", brand)
        durs = []
        for (img, dur), c in zip(scenes, clips):
            durs.append(max(dur, tts.duration(c) + lead + 0.5) if c else dur)
        voiced = any(clips)

        inputs, filters = [], []
        for i, (img, _) in enumerate(scenes):
            p = Path(td) / f"s{i}.png"
            img.resize((int(W * 1.1), int(STORY_H * 1.1)), Image.LANCZOS).save(p)
            inputs += ["-i", str(p)]
            filters.append(
                f"[{i}:v]zoompan=z='min(1+on*{zoom},1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={int(durs[i] * FPS)}:s={W}x{STORY_H}:fps={FPS},format=yuv420p,setsar=1[v{i}]"
            )
        last, t, starts = "v0", durs[0], [0.0]
        for i in range(1, len(scenes)):
            off = t - xf
            starts.append(off)
            filters.append(f"[{last}][v{i}]xfade=transition=fade:duration={xf}:offset={off:.2f}[x{i}]")
            last, t = f"x{i}", t + durs[i] - xf
        total = t
        idx = len(scenes)

        track = audio_track(date)
        if track:
            inputs += ["-i", str(track)]
            vol = 0.12 if voiced else 1.0
            filters.append(f"[{idx}:a]atrim=0:{total:.2f},volume={vol},afade=t=out:st={total - 1.2:.2f}:d=1.2,"
                           f"aresample=48000,aformat=channel_layouts=stereo[bg]")
        else:
            inputs += ["-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=r=48000:cl=stereo"]
            filters.append(f"[{idx}:a]anull[bg]")
        idx += 1
        mix = ["[bg]"]
        for i, c in enumerate(clips):
            if c:
                inputs += ["-i", str(c)]
                ms = int((starts[i] + lead) * 1000)
                filters.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[n{i}]")
                mix.append(f"[n{i}]")
                idx += 1
        if len(mix) > 1:
            filters.append(f"{''.join(mix)}amix=inputs={len(mix)}:duration=first:normalize=0[a]")
        else:
            filters.append("[bg]anull[a]")
        cmd = [
            "ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filters),
            "-map", f"[{last}]", "-map", "[a]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-profile:v", "high", "-crf", "21", "-pix_fmt", "yuv420p",
            "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-movflags", "+faststart", str(dst),
        ]
        subprocess.run(cmd, check=True)
    return dst, voiced
