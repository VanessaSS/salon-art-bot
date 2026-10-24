"""Motor de composição determinístico (sem IA generativa)."""
from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.models.template_schema import Carousel, PhotoSlot, Template, TextSlot
from app.utils.image_processing import apply_mask, fit_image, make_mask

FONTS_DIR = Path(__file__).resolve().parents[2] / "fonts"
FALLBACK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


class CompositionError(RuntimeError):
    """Falha ao montar a arte."""


class MissingFieldError(CompositionError):
    """Foto ou texto obrigatório não informado."""


class TextTooLongError(CompositionError):
    """O texto não cabe na área mesmo com a fonte mínima."""

    def __init__(self, slot: TextSlot):
        super().__init__(f"O texto de “{slot.label}” é longo demais para esse espaço. Tente algo mais curto.")
        self.slot = slot


@lru_cache(maxsize=64)
def _font(name: str, size: int, variation: str | None = None, fonts_dir: Path = FONTS_DIR) -> ImageFont.FreeTypeFont:
    path = fonts_dir / name
    try:
        font = ImageFont.truetype(str(path), size)
        if variation:
            font.set_variation_by_name(variation)
        return font
    except OSError:
        try:
            return ImageFont.truetype(FALLBACK_FONT, size)
        except OSError:
            return ImageFont.load_default(size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str] | None:
    """Quebra por palavras. None se alguma palavra sozinha excede a largura."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            if draw.textlength(word, font=font) > max_w:
                return None
            trial = f"{current} {word}".strip()
            if draw.textlength(trial, font=font) <= max_w:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def fit_text(draw: ImageDraw.ImageDraw, slot: TextSlot, text: str) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    """Maior fonte (max->min) em que o texto cabe em largura, altura e max_lines."""
    for size in range(slot.max_font_size, slot.min_font_size - 1, -1):
        font = _font(slot.font, size, slot.font_variation)
        lines = _wrap(draw, text, font, slot.width)
        if lines is None or len(lines) > slot.max_lines:
            continue
        asc, desc = font.getmetrics()
        line_h = round((asc + desc) * slot.line_spacing)
        if line_h * len(lines) - (line_h - asc - desc) <= slot.height:
            return font, lines, line_h
    raise TextTooLongError(slot)


def _draw_text(canvas: Image.Image, slot: TextSlot, text: str) -> None:
    layer = ImageDraw.Draw(canvas)
    font, lines, line_h = fit_text(layer, slot, text)
    asc, desc = font.getmetrics()
    block_h = line_h * (len(lines) - 1) + asc + desc
    y0 = {"top": slot.y, "middle": slot.y + (slot.height - block_h) // 2,
          "bottom": slot.y + slot.height - block_h}[slot.valign]
    for i, line in enumerate(lines):
        w = layer.textlength(line, font=font)
        x = {"left": slot.x, "center": slot.x + (slot.width - w) / 2, "right": slot.x + slot.width - w}[slot.align]
        layer.text((x, y0 + i * line_h), line, font=font, fill=slot.color)


def _place_photo(canvas: Image.Image, slot: PhotoSlot, photo: Image.Image) -> None:
    fitted = fit_image(photo, (slot.width, slot.height), slot.fit, (slot.focus_x, slot.focus_y))
    fitted = apply_mask(fitted, make_mask(fitted.size, slot.mask, slot.radius))
    canvas.alpha_composite(fitted, (slot.x, slot.y))


def compose(template: Template, photos: dict[str, Image.Image], texts: dict[str, str]) -> Image.Image:
    """Camadas: background -> fotos -> overlay -> textos. Retorna RGBA no tamanho do canvas."""
    for p in template.photos:
        if p.id not in photos:
            raise MissingFieldError(f"Falta a foto “{p.label}”.")
    clean: dict[str, str] = {}
    for t in template.texts:
        value = (texts.get(t.id) or "").strip()
        if not value and t.required:
            raise MissingFieldError(f"Falta o texto “{t.label}”.")
        if len(value) > t.max_chars:
            raise TextTooLongError(t)
        clean[t.id] = value
    try:
        canvas = Image.open(template.background_path).convert("RGBA")
        if canvas.size != (template.width, template.height):
            raise CompositionError("O fundo não tem o mesmo tamanho do canvas configurado.")
        for p in template.photos:
            _place_photo(canvas, p, photos[p.id])
        if template.overlay_path:
            overlay = Image.open(template.overlay_path).convert("RGBA")
            if overlay.size != canvas.size:
                raise CompositionError("O overlay não tem o mesmo tamanho do canvas.")
            canvas.alpha_composite(overlay)
        for t in template.texts:
            if clean[t.id]:
                _draw_text(canvas, t, clean[t.id])
    except CompositionError:
        raise
    except Exception as e:  # noqa: BLE001 - qualquer falha vira erro de domínio
        raise CompositionError("Não consegui montar a arte. Tente novamente.") from e
    return canvas


def to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def compose_item(item: Template | Carousel, registry, photos: dict[str, Image.Image],
                 texts: dict[str, str]) -> list[Image.Image]:
    """Gera as imagens de um item do menu: 1 para modelo simples, N para carrossel (na ordem dos slides)."""
    if isinstance(item, Template):
        return [compose(item, photos, texts)]
    for p in item.photos:
        if p.id not in photos:
            raise MissingFieldError(f"Falta a foto “{p.label}”.")
    for t in item.texts:
        value = (texts.get(t.id) or "").strip()
        if not value and t.required:
            raise MissingFieldError(f"Falta o texto “{t.label}”.")
        if len(value) > t.max_chars:
            raise CompositionError(f"O texto de “{t.label}” é longo demais. Tente algo mais curto.")
    out: list[Image.Image] = []
    for ref in item.slides:
        if ref.static:
            try:
                out.append(Image.open(item.directory / ref.static).convert("RGBA"))
            except OSError as e:
                raise CompositionError("Não consegui abrir uma imagem fixa do carrossel.") from e
            continue
        sub = registry.get(ref.template_id)
        out.append(compose(sub, {sid: photos[cid] for sid, cid in ref.photos.items()},
                           {sid: texts.get(cid, "") for sid, cid in ref.texts.items()}))
    return out


def to_jpeg_bytes(img: Image.Image, quality: int = 95) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality, subsampling=0, optimize=True)
    return buf.getvalue()
