"""Cria os modelos de story de serviços a partir dos PNGs do Canva (com/sem preço).

Os PNGs vêm "achatados": fotos-exemplo e títulos já embutidos. Aqui o fundo é reconstruído
(área da foto e título repintados com o rosa do fundo) e as medidas foram extraídas dos próprios PNGs.
Uso: python tools/convert_png_servicos.py <Sem_preco.png>
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SIZE = (1080, 1920)
PINK = (252, 235, 243)
PHOTO = dict(x=232, y=412, width=616, height=816)     # medido: anel branco do PNG original
BORDER, RADIUS = 5, 59
TITLE_BOX = (250, 1250, 830, 1422)                     # área do título de exemplo (repintada)
BADGE_C, BADGE_R, BADGE_RING, BADGE_FILL = (819.5, 1129.5), 99, 8, (195, 53, 119)


def assert_pink_border(img: Image.Image, box) -> None:
    a = np.asarray(img.convert("RGB"))
    x0, y0, x1, y1 = box
    edge = np.concatenate([a[y0, x0:x1], a[y1 - 1, x0:x1], a[y0:y1, x0], a[y0:y1, x1 - 1]])
    if not (edge == PINK).all():
        raise SystemExit(f"A borda de {box} não é só fundo rosa; repintar apagaria algo.")


def ss_draw(size, draw_fn, s=4) -> Image.Image:
    big = Image.new("L", (size[0] * s, size[1] * s), 0)
    draw_fn(ImageDraw.Draw(big), s)
    return big.resize(size, Image.LANCZOS)


def layer(mask: Image.Image, rgb) -> Image.Image:
    out = Image.new("RGBA", mask.size, (*rgb, 0))
    out.putalpha(mask)
    return out


def build(src: Path) -> None:
    bg = Image.open(src).convert("RGB")
    assert bg.size == SIZE
    p = PHOTO
    photo_box = (p["x"], p["y"], p["x"] + p["width"], p["y"] + p["height"])
    d = ImageDraw.Draw(bg)
    d.rectangle((photo_box[0], photo_box[1], photo_box[2] - 1, photo_box[3] - 1), fill=PINK)
    assert_pink_border(bg, TITLE_BOX)
    d.rectangle((TITLE_BOX[0], TITLE_BOX[1], TITLE_BOX[2] - 1, TITLE_BOX[3] - 1), fill=PINK)

    def ring_fn(dr, s):
        x0, y0, x1, y1 = (v * s for v in photo_box)
        dr.rounded_rectangle((x0, y0, x1 - 1, y1 - 1), radius=RADIUS * s, fill=255)
        dr.rounded_rectangle((x0 + BORDER * s, y0 + BORDER * s, x1 - 1 - BORDER * s, y1 - 1 - BORDER * s),
                             radius=(RADIUS - BORDER) * s, fill=0)
    ring = layer(ss_draw(SIZE, ring_fn), (255, 255, 255))

    cx, cy = BADGE_C
    def disc(r):
        return lambda dr, s: dr.ellipse(((cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s), fill=255)
    badge = Image.alpha_composite(layer(ss_draw(SIZE, disc(BADGE_R)), (255, 255, 255)),
                                  layer(ss_draw(SIZE, disc(BADGE_R - BADGE_RING)), BADGE_FILL))

    photo = {"id": "foto", "label": "Foto do serviço", **PHOTO, "fit": "cover", "mask": "rounded", "radius": RADIUS}
    titulo = {"id": "titulo", "label": "Título (ex.: Escova blindada e modelada)", "x": 232, "y": 1250, "width": 616,
              "height": 172, "max_font_size": 68, "min_font_size": 38, "color": "#4D1439", "font": "Lora-Variable.ttf",
              "font_variation": "Bold", "max_lines": 2, "line_spacing": 0.93, "max_chars": 50}
    preco = {"id": "preco", "label": "Preço (ex.: R$ 70)", "x": 745, "y": 1094, "width": 149, "height": 71,
             "max_font_size": 44, "min_font_size": 24, "color": "#FFFFFF", "font": "Poppins-Bold.ttf", "max_chars": 10}
    for tid, name, ov, texts in (
        ("story_servico", "Story – Serviço", ring, [titulo]),
        ("story_servico_preco", "Story – Serviço com preço", Image.alpha_composite(ring, badge), [titulo, preco]),
    ):
        out = ROOT / "templates" / tid
        out.mkdir(parents=True, exist_ok=True)
        bg.save(out / "background.png")
        ov.save(out / "overlay.png")
        cfg = {"id": tid, "name": name, "description": "Story com uma foto, o título do serviço" + (", selo de preço" if "preco" in tid else "") + " e a chamada para agendar.",
               "canvas": {"width": SIZE[0], "height": SIZE[1]}, "background": "background.png", "overlay": "overlay.png",
               "photos": [photo], "texts": texts}
        (out / "template.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        print("OK", tid)


if __name__ == "__main__":
    build(Path(sys.argv[1]))
