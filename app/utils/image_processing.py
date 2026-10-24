"""Funções puras de imagem: validação, EXIF, recorte, máscaras."""
from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 50_000_000
MIN_SIDE = 200


class InvalidImageError(ValueError):
    """Foto recebida não pode ser usada (mensagem segura para o usuário)."""


def load_photo(data: bytes) -> Image.Image:
    """Valida bytes de uma foto e devolve RGB já com orientação EXIF corrigida."""
    if len(data) > MAX_BYTES:
        raise InvalidImageError("A foto é muito grande. Envie uma de até 15 MB.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            w, h = probe.size
        if fmt not in ALLOWED_FORMATS:
            raise InvalidImageError("Formato não suportado. Envie JPG, PNG ou WEBP.")
        if w * h > MAX_PIXELS:
            raise InvalidImageError("A foto tem resolução muito alta. Envie uma menor.")
        if min(w, h) < MIN_SIDE:
            raise InvalidImageError("A foto é muito pequena. Envie uma com mais qualidade.")
        img = Image.open(io.BytesIO(data))
        img.load()
    except InvalidImageError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise InvalidImageError("Não consegui abrir essa foto. Tente enviar outra.") from e
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        bg.alpha_composite(rgba)
        return bg.convert("RGB")
    return img.convert("RGB")


def fit_image(
    img: Image.Image, size: tuple[int, int], fit: str = "cover",
    focus: tuple[float, float] = (0.5, 0.5),
) -> Image.Image:
    """Ajusta `img` a `size` sem distorcer. cover = corta o excedente; contain = letterbox transparente."""
    tw, th = size
    if fit == "cover":
        return ImageOps.fit(img.convert("RGBA"), size, method=Image.LANCZOS, centering=focus)
    if fit == "contain":
        scale = min(tw / img.width, th / img.height)
        nw, nh = max(1, round(img.width * scale)), max(1, round(img.height * scale))
        resized = img.convert("RGBA").resize((nw, nh), Image.LANCZOS)
        out = Image.new("RGBA", size, (0, 0, 0, 0))
        out.paste(resized, ((tw - nw) // 2, (th - nh) // 2))
        return out
    raise ValueError(f"fit desconhecido: {fit}")


def make_mask(size: tuple[int, int], kind: str, radius: int = 0) -> Image.Image | None:
    """Máscara 'L' com antialiasing (supersampling 4x). None quando não há máscara."""
    if kind == "none":
        return None
    s = 4
    big = Image.new("L", (size[0] * s, size[1] * s), 0)
    d = ImageDraw.Draw(big)
    if kind == "circle":
        d.ellipse((0, 0, size[0] * s - 1, size[1] * s - 1), fill=255)
    elif kind == "rounded":
        d.rounded_rectangle((0, 0, size[0] * s - 1, size[1] * s - 1), radius=radius * s, fill=255)
    else:
        raise ValueError(f"máscara desconhecida: {kind}")
    return big.resize(size, Image.LANCZOS)


def apply_mask(img: Image.Image, mask: Image.Image | None) -> Image.Image:
    if mask is None:
        return img
    out = img.convert("RGBA")
    alpha = Image.composite(out.getchannel("A"), Image.new("L", out.size, 0), mask)
    out.putalpha(alpha)
    return out
