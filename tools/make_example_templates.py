"""Gera os modelos de EXEMPLO (examples/templates): sintéticos, sem marca, logo, telefone ou fotos reais.

Têm a mesma estrutura dos modelos de produção (fotos, textos, overlay, carrossel), então servem para
rodar o bot, a CLI e os testes sem nenhum arquivo privado.   Uso: python tools/make_example_templates.py
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "templates"
FONTS = ROOT / "fonts"

PINK, SOFT = (252, 235, 243), (250, 221, 235)
WINE, MAGENTA, PILL = (77, 20, 57), (195, 53, 119), (158, 33, 96)
WHITE = (255, 255, 255)


def font(name: str, size: int, variation: str | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / name), size)
    if variation:
        f.set_variation_by_name(variation)
    return f


def mask(size, draw_fn, s=4) -> Image.Image:
    big = Image.new("L", (size[0] * s, size[1] * s), 0)
    draw_fn(ImageDraw.Draw(big), s)
    return big.resize(size, Image.LANCZOS)


def layer(m: Image.Image, rgb) -> Image.Image:
    out = Image.new("RGBA", m.size, (*rgb, 0))
    out.putalpha(m)
    return out


def ring(size, box, border, radius) -> Image.Image:
    x0, y0, x1, y1 = box

    def fn(d, s):
        d.rounded_rectangle((x0 * s, y0 * s, x1 * s - 1, y1 * s - 1), radius=radius * s, fill=255)
        d.rounded_rectangle(((x0 + border) * s, (y0 + border) * s, (x1 - border) * s - 1, (y1 - border) * s - 1),
                            radius=max(1, radius - border) * s, fill=0)
    return layer(mask(size, fn), WHITE)


def disc(size, center, r, rgb) -> Image.Image:
    cx, cy = center
    return layer(mask(size, lambda d, s: d.ellipse(((cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s), fill=255)), rgb)


def pill(size, box, rgb) -> Image.Image:
    x0, y0, x1, y1 = box
    return layer(mask(size, lambda d, s: d.rounded_rectangle((x0 * s, y0 * s, x1 * s, y1 * s), radius=(y1 - y0) * s // 2, fill=255)), rgb)


def say(img: Image.Image, xy, text, f, fill, anchor="mm") -> None:
    ImageDraw.Draw(img).text(xy, text, font=f, fill=fill, anchor=anchor)


def brand_header(img, y, size=64) -> None:
    say(img, (img.width // 2, y), "SUA MARCA", font("Lora-Variable.ttf", size, "Bold"), WINE)
    say(img, (img.width // 2, y + size // 2 + 22), "seu nome | sua profissão", font("Poppins-Regular.ttf", 26), PILL)


def story_base() -> Image.Image:
    img = Image.new("RGBA", (1080, 1920), (*PINK, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((1040 - 261, 191 - 261, 1040 + 261, 191 + 261), fill=SOFT)
    d.ellipse((-330, 1428, 330, 2088), fill=SOFT)
    brand_header(img, 225)
    img.alpha_composite(pill(img.size, (140, 1444, 940, 1544), PILL))
    say(img, (540, 1473), "Agende pelo WhatsApp", font("Poppins-Regular.ttf", 36), WHITE)
    say(img, (540, 1518), "00 00000-0000", font("Poppins-Bold.ttf", 40), WHITE)
    return img


def feed_base() -> Image.Image:
    img = Image.new("RGBA", (1080, 1350), (*PINK, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((1000 - 250, 90 - 250, 1000 + 250, 90 + 250), fill=SOFT)
    d.ellipse((-300, 1000, 300, 1600), fill=SOFT)
    brand_header(img, 80, 56)
    say(img, (540, 1300), "Agende pelo WhatsApp 00 00000-0000", font("Poppins-Regular.ttf", 32), PILL)
    return img


def badge(size, box, rgb, label) -> Image.Image:
    out = pill(size, box, rgb)
    say(out, ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2), label, font("Poppins-Bold.ttf", 28), WHITE)
    return out


def photo(pid, label, x, y, w, h, radius) -> dict:
    return {"id": pid, "label": label, "x": x, "y": y, "width": w, "height": h, "fit": "cover", "mask": "rounded", "radius": radius}


TITLE = {"id": "titulo", "label": "Título (ex.: Escova blindada e modelada)", "x": 232, "y": 1250, "width": 616, "height": 172,
         "max_font_size": 68, "min_font_size": 38, "color": "#4D1439", "font": "Lora-Variable.ttf", "font_variation": "Bold",
         "max_lines": 2, "line_spacing": 0.93, "max_chars": 50}
PRICE = {"id": "preco", "label": "Preço (ex.: R$ 70)", "x": 745, "y": 1094, "width": 149, "height": 71, "max_font_size": 44,
         "min_font_size": 24, "color": "#FFFFFF", "font": "Poppins-Bold.ttf", "max_chars": 10}


def save(tid: str, cfg: dict, bg: Image.Image, overlay: Image.Image | None = None) -> None:
    d = OUT / tid
    d.mkdir(parents=True, exist_ok=True)
    bg.convert("RGB").save(d / "background.png")
    cfg = {"id": tid, "background": "background.png", **cfg}
    if overlay is not None:
        overlay.save(d / "overlay.png")
        cfg["overlay"] = "overlay.png"
    (d / "template.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def build() -> None:
    S, F = (1080, 1920), (1080, 1350)
    box = (232, 412, 848, 1228)
    story_ring = ring(S, box, 5, 59)
    ph = photo("foto", "Foto do serviço", 232, 412, 616, 816, 59)

    # 1) serviço (1 foto + título)
    save("exemplo_servico", {"name": "Exemplo – Serviço", "description": "Story com uma foto, título do serviço e chamada para agendar.",
                             "canvas": {"width": 1080, "height": 1920}, "photos": [ph], "texts": [TITLE]}, story_base(), story_ring)
    # 2) serviço com selo de preço (sobre a foto)
    ov = Image.alpha_composite(story_ring, disc(S, (819.5, 1129.5), 99, WHITE))
    ov = Image.alpha_composite(ov, disc(S, (819.5, 1129.5), 91, MAGENTA))
    save("exemplo_servico_preco", {"name": "Exemplo – Serviço com preço", "description": "Story com uma foto, título, selo de preço e chamada para agendar.",
                                   "canvas": {"width": 1080, "height": 1920}, "photos": [ph], "texts": [TITLE, PRICE]}, story_base(), ov)
    # 3) antes e depois (2 fotos lado a lado)
    bg = story_base()
    say(bg, (540, 500), "Antes e depois", font("Lora-Variable.ttf", 88, "Bold"), WINE)
    a, b = (32, 682, 538, 1238), (542, 682, 1048, 1238)
    ov = Image.alpha_composite(ring(S, a, 8, 47), ring(S, b, 8, 47))
    ov.alpha_composite(badge(S, (a[0] + 24, a[1] + 24, a[0] + 224, a[1] + 86), WINE, "ANTES"))
    ov.alpha_composite(badge(S, (b[0] + 24, b[1] + 24, b[0] + 224, b[1] + 86), MAGENTA, "DEPOIS"))
    save("exemplo_antes_depois", {"name": "Exemplo – Antes e depois", "description": "Story com duas fotos lado a lado e o serviço realizado.",
                                  "canvas": {"width": 1080, "height": 1920},
                                  "photos": [photo("antes", "Foto ANTES", 32, 682, 506, 556, 47), photo("depois", "Foto DEPOIS", 542, 682, 506, 556, 47)],
                                  "texts": [{"id": "servico", "label": "Qual serviço foi feito? (ex.: Corte)", "x": 32, "y": 560, "width": 1016, "height": 80,
                                             "max_font_size": 44, "min_font_size": 26, "color": "#9E2160", "max_lines": 1, "max_chars": 40}]}, bg, ov)
    # 4) carrossel: slides internos (ocultos) + imagem fixa + definição do carrossel
    fbox = (52, 207, 1028, 1183)
    for tid, label, rgb, word in (("exemplo_slide_antes", "Foto ANTES", WINE, "ANTES"), ("exemplo_slide_depois", "Foto DEPOIS", MAGENTA, "DEPOIS")):
        ov = ring(F, fbox, 8, 51)
        ov.alpha_composite(badge(F, (82, 237, 282, 299), rgb, word))
        save(tid, {"name": f"Exemplo – Slide {word.lower()}", "description": "Uso interno do carrossel.", "hidden": True,
                   "canvas": {"width": 1080, "height": 1350}, "photos": [photo("foto", label, 52, 207, 976, 976, 51)],
                   "texts": [{"id": "servico", "label": "Qual serviço foi feito? (ex.: Corte)", "x": 52, "y": 1195, "width": 976, "height": 70,
                              "max_font_size": 50, "min_font_size": 30, "color": "#4D1439", "font": "Lora-Variable.ttf",
                              "font_variation": "Bold", "max_lines": 1, "max_chars": 40}]}, feed_base(), ov)
    cta = Image.new("RGBA", F, (*PINK, 255))
    ImageDraw.Draw(cta).ellipse((700, -200, 1300, 400), fill=SOFT)
    brand_header(cta, 230, 90)
    say(cta, (540, 640), "Quer o seu depois?", font("Lora-Variable.ttf", 70, "Bold"), WINE)
    say(cta, (540, 730), "Vem fazer um horário comigo", font("Poppins-Regular.ttf", 36), (57, 35, 47))
    cta.alpha_composite(pill(F, (140, 830, 940, 950), PILL))
    say(cta, (540, 868), "Agende pelo WhatsApp", font("Poppins-Regular.ttf", 36), WHITE)
    say(cta, (540, 915), "00 00000-0000", font("Poppins-Bold.ttf", 42), WHITE)
    d = OUT / "exemplo_carrossel"
    d.mkdir(parents=True, exist_ok=True)
    cta.convert("RGB").save(d / "cta.png")
    (d / "template.json").write_text(json.dumps({
        "type": "carousel", "id": "exemplo_carrossel", "name": "Exemplo – Carrossel antes e depois",
        "description": "Carrossel de 3 imagens: antes, depois e o convite para agendar.",
        "photos": [{"id": "antes", "label": "Foto ANTES"}, {"id": "depois", "label": "Foto DEPOIS"}],
        "texts": [{"id": "servico", "label": "Qual serviço foi feito? (ex.: Corte)", "max_chars": 40}],
        "slides": [{"template": "exemplo_slide_antes", "photos": {"foto": "antes"}, "texts": {"servico": "servico"}},
                   {"template": "exemplo_slide_depois", "photos": {"foto": "depois"}, "texts": {"servico": "servico"}},
                   {"static": "cta.png"}]}, ensure_ascii=False, indent=2), encoding="utf-8")

    # 5) demonstrativo simples usado nos testes do motor (oculto no menu do bot)
    bg = Image.new("RGB", (1080, 1350), "#FBEAF1")
    d = ImageDraw.Draw(bg)
    d.ellipse((760, -120, 1200, 320), fill="#E8B8CC")
    d.ellipse((-200, 1050, 260, 1510), fill="#E8B8CC")
    d.rounded_rectangle((140, 1170, 940, 1260), radius=45, fill="#B52D68")
    ov = Image.new("RGBA", (1080, 1350), (0, 0, 0, 0))
    ImageDraw.Draw(ov).rounded_rectangle((90, 300, 990, 880), radius=40, outline="#FFFFFF", width=14)
    save("exemplo_demo", {"name": "EXEMPLO – modelo demonstrativo", "hidden": True, "description": "Modelo sintético só para testes do motor.",
                          "canvas": {"width": 1080, "height": 1350},
                          "photos": [{"id": "foto_principal", "label": "Foto principal", "x": 100, "y": 310, "width": 880, "height": 560,
                                      "fit": "cover", "mask": "rounded", "radius": 30}],
                          "texts": [{"id": "titulo", "label": "Título", "x": 100, "y": 110, "width": 880, "height": 150, "max_font_size": 84,
                                     "min_font_size": 36, "color": "#4A082D", "font": "Lora-Variable.ttf", "max_lines": 2, "max_chars": 60},
                                    {"id": "descricao", "label": "Descrição", "x": 100, "y": 910, "width": 880, "height": 230, "max_font_size": 44,
                                     "min_font_size": 24, "color": "#39232F", "max_lines": 4, "max_chars": 200, "required": False},
                                    {"id": "chamada", "label": "Chamada para agendamento", "x": 160, "y": 1180, "width": 760, "height": 70,
                                     "max_font_size": 38, "min_font_size": 22, "color": "#FFFFFF", "font": "Poppins-Bold.ttf", "max_chars": 50}]},
         bg, ov)
    print("Modelos de exemplo gerados em", OUT)


if __name__ == "__main__":
    build()
