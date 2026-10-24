import io

import pytest
from PIL import Image

from app.utils import image_processing as ip
from tests.conftest import make_photo_bytes


def test_load_valid_formats():
    for fmt in ("JPEG", "PNG", "WEBP"):
        assert ip.load_photo(make_photo_bytes(fmt=fmt)).mode == "RGB"


def test_invalid_file_rejected():
    with pytest.raises(ip.InvalidImageError):
        ip.load_photo(b"isto nao e uma imagem")


def test_unsupported_format_rejected():
    buf = io.BytesIO()
    Image.new("RGB", (400, 400)).save(buf, format="GIF")
    with pytest.raises(ip.InvalidImageError, match="Formato"):
        ip.load_photo(buf.getvalue())


def test_too_small_and_too_big(monkeypatch):
    with pytest.raises(ip.InvalidImageError, match="pequena"):
        ip.load_photo(make_photo_bytes(size=(100, 100)))
    monkeypatch.setattr(ip, "MAX_PIXELS", 1000)
    with pytest.raises(ip.InvalidImageError, match="resolução"):
        ip.load_photo(make_photo_bytes(size=(400, 400)))
    monkeypatch.setattr(ip, "MAX_BYTES", 10)
    with pytest.raises(ip.InvalidImageError, match="grande"):
        ip.load_photo(make_photo_bytes())


def test_exif_orientation_applied():
    # orientação 6 = rotacionar 90° → 1600x900 vira 900x1600
    img = ip.load_photo(make_photo_bytes(size=(1600, 900), exif_orientation=6))
    assert img.size == (900, 1600)


def test_cover_horizontal_and_vertical_fill_exactly():
    for size in ((1600, 900), (900, 1600)):
        out = ip.fit_image(Image.new("RGB", size, "red"), (500, 300), "cover")
        assert out.size == (500, 300)
        assert out.getchannel("A").getextrema() == (255, 255)  # sem bordas vazias


def test_cover_preserves_aspect_ratio():
    # imagem com círculo: após cover num quadrado, o círculo continua circular (sem esticar)
    src = Image.new("RGB", (1600, 800), "white")
    from PIL import ImageDraw
    ImageDraw.Draw(src).ellipse((600, 0, 1000, 400), fill="black")
    out = ip.fit_image(src, (400, 400), "cover").convert("L").point(lambda v: 255 if v < 128 else 0)
    bbox = out.getbbox()
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    assert abs(w - h) <= 2


def test_cover_focus_changes_crop():
    src = Image.open(io.BytesIO(make_photo_bytes(size=(1600, 900)))).convert("RGB")
    left = ip.fit_image(src, (300, 300), "cover", (0.0, 0.5)).convert("RGB").getpixel((150, 150))
    right = ip.fit_image(src, (300, 300), "cover", (1.0, 0.5)).convert("RGB").getpixel((150, 150))
    assert left[0] > 150 and right[2] > 150  # esquerda avermelhada, direita azulada


def test_contain_keeps_whole_image_with_transparent_bars():
    out = ip.fit_image(Image.new("RGB", (1600, 800), "red"), (400, 400), "contain")
    assert out.size == (400, 400)
    assert out.getpixel((200, 5))[3] == 0      # barra superior transparente
    assert out.getpixel((200, 200))[3] == 255  # centro preenchido
    assert out.getpixel((5, 200))[3] == 255    # largura total preservada


def test_circle_mask_transparent_corners():
    img = ip.apply_mask(ip.fit_image(Image.new("RGB", (400, 400), "red"), (200, 200)), ip.make_mask((200, 200), "circle"))
    assert img.getpixel((0, 0))[3] == 0 and img.getpixel((100, 100))[3] == 255


def test_rounded_mask_and_none():
    m = ip.make_mask((200, 100), "rounded", 30)
    assert m.getpixel((0, 0)) == 0 and m.getpixel((100, 50)) == 255
    assert ip.make_mask((10, 10), "none") is None
    with pytest.raises(ValueError):
        ip.make_mask((10, 10), "triangulo")
