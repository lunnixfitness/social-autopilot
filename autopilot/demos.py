"""Shorts de demonstração do Velatrix com telas reais (assets/demos) e narração por IA."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .config import ROOT, load_brand
from .render import MARGIN, STORY_H, W, background, draw_block, encode_scenes, fit_text, font, hex2rgb

B = load_brand()
NAVY, GOLD, WHITE, SOFT = (hex2rgb(B["cores"][k]) for k in ("fundo", "destaque", "texto", "suave"))
M = ROOT / "assets" / "demos"
CTA_FALA = "O Velatrix está em fase beta. Siga o canal e acompanhe o lançamento."

def tela(nome, box, max_w=W - 2 * 60, max_h=860):
    im = Image.open(M / nome).convert("RGB").crop(box)
    s = min(max_w / im.width, max_h / im.height)
    return im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)


def cena(texto, shot=None, label="DEMONSTRAÇÃO · VELATRIX", rodape=None):
    im = background((W, STORY_H), B)
    d = ImageDraw.Draw(im)
    d.text((MARGIN, 250), label, font=font(36), fill=GOLD)
    f, lines, h = fit_text(d, texto, W - 2 * MARGIN, 330, 84)
    y = draw_block(d, (MARGIN, 310), lines, f, WHITE)
    if shot is not None:
        x = (W - shot.width) // 2
        top = max(y + 60, 720)
        sh = Image.new("RGBA", (shot.width + 80, shot.height + 80), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle((40, 50, shot.width + 40, shot.height + 50), 28, fill=(0, 0, 0, 150))
        im.paste(sh.filter(ImageFilter.GaussianBlur(18)), (x - 40, top - 40), sh.filter(ImageFilter.GaussianBlur(18)))
        mask = Image.new("L", shot.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, shot.width - 1, shot.height - 1), 22, fill=255)
        im.paste(shot, (x, top), mask)
        d.rounded_rectangle((x - 3, top - 3, x + shot.width + 2, top + shot.height + 2), 24, outline=GOLD, width=4)
    if rodape:
        f2, l2, _ = fit_text(d, rodape, W - 2 * MARGIN, 160, 40, bold=False)
        draw_block(d, (MARGIN, STORY_H - 470), l2, f2, SOFT)
    d.text((MARGIN, STORY_H - 330), "Ademilson Melo | Velatrix", font=font(36), fill=SOFT)
    return im


def zoom(nome, crop, largura=900):
    """Trecho da tela ampliado, como cartão flutuante."""
    src = Image.open(M / nome).convert("RGB").crop(crop)
    s = largura / src.width
    im = src.resize((largura, int(src.height * s)), Image.LANCZOS)
    b = 6
    ph = Image.new("RGBA", (im.width + 2 * b, im.height + 2 * b), (0, 0, 0, 0))
    ImageDraw.Draw(ph).rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), 30, fill=GOLD + (255,))
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), 26, fill=255)
    ph.paste(im, (b, b), mask)
    return ph


def celular(nome, crop=None, largura=560):
    """Tela capturada no modo celular, dentro de um aparelho."""
    src = Image.open(M / nome).convert("RGB")
    if crop:
        src = src.crop(crop)
    s = largura / 377
    tela_h = int(673 * s)
    screen = Image.new("RGB", (largura, tela_h), (255, 255, 255))
    im = src.resize((largura, int(src.height * s)), Image.LANCZOS)
    screen.paste(im, (0, 0))
    b = 18
    ph = Image.new("RGBA", (largura + 2 * b, tela_h + 2 * b), (0, 0, 0, 0))
    d = ImageDraw.Draw(ph)
    d.rounded_rectangle((0, 0, ph.width - 1, ph.height - 1), 64, fill=(12, 14, 20, 255), outline=GOLD + (255,), width=3)
    mask = Image.new("L", screen.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, largura - 1, tela_h - 1), 48, fill=255)
    ph.paste(screen, (b, b), mask)
    return ph


def cena_cel(texto, ph, label="DEMONSTRAÇÃO · VELATRIX"):
    im = background((W, STORY_H), B)
    d = ImageDraw.Draw(im)
    d.text((MARGIN, 200), label, font=font(36), fill=GOLD)
    f, lines, h = fit_text(d, texto, W - 2 * MARGIN, 300, 78)
    draw_block(d, (MARGIN, 255), lines, f, WHITE)
    x, y = (W - ph.width) // 2, 590 if ph.height > 900 else 780
    sh = Image.new("RGBA", (ph.width + 120, ph.height + 120), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((60, 75, ph.width + 60, ph.height + 75), 64, fill=(0, 0, 0, 170))
    sh = sh.filter(ImageFilter.GaussianBlur(26))
    im.paste(sh, (x - 60, y - 60), sh)
    im.paste(ph, (x, y), ph)
    return im


def cta():
    return cena("Tecnologia que trabalha pelo seu escritório.", None, "VELATRIX · EM BETA",
                rodape="Siga o canal para acompanhar o lançamento. Shorts novos de segunda a sábado.")



def demos() -> dict:
    """nome -> (título do Short, [(cena, duração mínima, fala)])"""
    return {
        "demo_tour": ("Tour do Velatrix: o sistema do escritório inteiro", [
            (cena_cel("Um sistema para o escritório inteiro", celular("inicio.png")), 3.5,
             "Este é o Velatrix, um sistema para o escritório inteiro."),
            (cena_cel("Cada área do escritório tem a sua esteira", celular("menu.png")), 3.5,
             "Cada área tem a sua esteira: tributário, perícia e previdenciário."),
            (cena_cel("Recuperação tributária em três etapas", celular("rt_pipeline.png")), 3.5,
             "Na recuperação tributária, o trabalho segue em três etapas."),
            (cena_cel("Marketplace de leads para escritórios parceiros", celular("mk_topo.png")), 3.5,
             "E no marketplace, leads de empresas chegam para escritórios parceiros."),
            (cta(), 3.0, CTA_FALA),
        ]),
        "demo_recuperacao": ("Recuperação tributária no Velatrix: do passivo ao acompanhamento", [
            (cena_cel("Recuperação tributária organizada do começo ao fim", zoom("rt_pipeline.png", (40, 150, 330, 340))), 3.5,
             "Recuperação tributária organizada do começo ao fim, começando pela auditoria do passivo."),
            (cena_cel("Auditoria do passivo, créditos de 5 anos e acompanhamento mensal", zoom("rt_pipeline.png", (40, 335, 330, 500))), 3.5,
             "Depois vêm os créditos dos últimos cinco anos e a transação, e por fim o acompanhamento mensal."),
            (cena_cel("Memória fiscal de 60 meses, cálculo pericial e linha do tempo", zoom("rt_ferramentas.png", (10, 360, 365, 610))), 3.5,
             "As ferramentas ficam lado a lado: memória fiscal de sessenta meses, cálculo pericial e linha do tempo."),
            (cta(), 3.0, CTA_FALA),
        ]),
        "demo_marketplace": ("Marketplace de leads do Velatrix para advogados e contadores", [
            (cena_cel("Leads de empresas para advogados e contadores", celular("mk_topo.png")), 3.5,
             "Advogado, contador: imagine receber leads de empresas prontos para atender."),
            (cena_cel("Caminho B: o comercial fecha e o escritório recebe a ação pronta", zoom("mk_caminho.png", (0, 210, 377, 445))), 4.0,
             "No caminho B, o comercial fecha o contrato e o escritório recebe a ação pronta para revisar e protocolar."),
            (cena_cel("Vitrine de oportunidades com rastreabilidade", celular("mk_vitrine.png")), 3.5,
             "Tudo numa vitrine de oportunidades com rastreabilidade."),
            (cta(), 3.0, CTA_FALA),
        ]),
    }


def build_all(out: Path) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    res = []
    for nome, (titulo, itens) in demos().items():
        scenes = [(img, d) for img, d, _ in itens]
        itens[0][0].save(out / f"{nome}_capa.jpg", quality=92)
        _, voiced = encode_scenes(scenes, out / f"{nome}.mp4", dt.date.today(), zoom=0.0005,
                                  brand=B, narration=[f for _, _, f in itens])
        res.append({"nome": nome, "titulo": titulo, "narracao_ia": voiced})
    return res
