import io

import pytest
from PIL import Image, ImageDraw

from app.models.template_schema import parse_template
from app.services import image_composer as ic
from app.utils.image_processing import load_photo
from tests.conftest import make_photo_bytes

TEXTS = {"titulo": "Escova blindada", "descricao": "Brilho e maciez por mais tempo", "chamada": "Agende pelo WhatsApp"}


def photo(color=(200, 30, 30), size=(1600, 900)):
    return {"foto_principal": load_photo(make_photo_bytes(size=size, color=color))}


def test_compose_output_size_and_png(demo):
    out = ic.compose(demo, photo(), TEXTS)
    assert out.size == (1080, 1350)
    png = ic.to_png_bytes(out)
    assert Image.open(io.BytesIO(png)).format == "PNG"


def test_layer_order_photo_then_overlay_then_text(demo):
    out = ic.compose(demo, photo(color=(255, 0, 0)), {**TEXTS, "titulo": "A"}).convert("RGB")
    assert out.getpixel((300, 600))[0] > 200 and out.getpixel((300, 600))[2] < 80   # foto dentro da área
    assert out.getpixel((10, 10)) == (251, 234, 241)                                # fundo rosa claro
    assert out.getpixel((97, 590)) == (255, 255, 255)                               # moldura do overlay sobre a foto


def test_text_actually_drawn(demo):
    with_text = ic.compose(demo, photo(), TEXTS).convert("RGB")
    without = ic.compose(demo, photo(), {**TEXTS, "descricao": ""}).convert("RGB")
    box = (100, 910, 980, 1140)
    assert with_text.crop(box).tobytes() != without.crop(box).tobytes()


def test_accents_and_special_chars(demo):
    out = ic.compose(demo, photo(), {**TEXTS, "titulo": "Coloração à moda", "descricao": "Hidratação, ação & ñ – R$ 80"})
    assert out.size == (1080, 1350)


def test_long_text_shrinks_font_then_fits(demo):
    slot = demo.texts[0]
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    short_font, _, _ = ic.fit_text(d, slot, "Corte")
    long_font, lines, _ = ic.fit_text(d, slot, "Progressiva orgânica com hidratação profunda")
    assert long_font.size < short_font.size and len(lines) <= slot.max_lines


def test_text_too_long_raises(demo):
    with pytest.raises(ic.TextTooLongError):
        ic.compose(demo, photo(), {**TEXTS, "titulo": "palavra " * 9})  # 71 > max_chars=60
    with pytest.raises(ic.TextTooLongError):
        ic.compose(demo, photo(), {**TEXTS, "titulo": "Supercalifragilisticoexpialidosamentelongo" * 3})


def test_missing_required_fields(demo):
    with pytest.raises(ic.MissingFieldError, match="foto"):
        ic.compose(demo, {}, TEXTS)
    with pytest.raises(ic.MissingFieldError, match="Título"):
        ic.compose(demo, photo(), {**TEXTS, "titulo": "  "})
    ic.compose(demo, photo(), {k: v for k, v in TEXTS.items() if k != "descricao"})  # opcional: ok


def test_multiple_photos_template(tmp_path):
    Image.new("RGB", (1000, 1000), "#FBEAF1").save(tmp_path / "bg.png")
    cfg = {"id": "dois", "name": "Antes e depois", "canvas": {"width": 1000, "height": 1000}, "background": "bg.png",
           "photos": [{"id": "antes", "label": "Antes", "x": 0, "y": 0, "width": 500, "height": 500},
                      {"id": "depois", "label": "Depois", "x": 500, "y": 500, "width": 500, "height": 500, "mask": "circle"}]}
    t = parse_template(cfg, tmp_path)
    red = load_photo(make_photo_bytes(color=(255, 0, 0), size=(800, 800)))
    out = ic.compose(t, {"antes": red, "depois": load_photo(make_photo_bytes(color=(0, 255, 0), size=(800, 800)))}, {}).convert("RGB")
    assert out.getpixel((100, 100))[0] > 200
    assert out.getpixel((500 + 5, 500 + 5)) == (251, 234, 241)   # canto do círculo = fundo
    with pytest.raises(ic.MissingFieldError, match="Depois"):
        ic.compose(t, {"antes": red}, {})


def test_background_size_mismatch_is_clear_error(tmp_path):
    Image.new("RGB", (500, 500)).save(tmp_path / "bg.png")
    cfg = {"id": "x", "name": "X", "canvas": {"width": 1000, "height": 1000}, "background": "bg.png",
           "texts": [{"id": "t", "label": "T", "x": 0, "y": 0, "width": 100, "height": 50, "max_font_size": 20, "min_font_size": 10}]}
    with pytest.raises(ic.CompositionError, match="fundo"):
        ic.compose(parse_template(cfg, tmp_path), {}, {"t": "oi"})


def test_composition_is_deterministic(demo):
    a = ic.compose(demo, photo(), TEXTS).tobytes()
    b = ic.compose(demo, photo(), TEXTS).tobytes()
    assert a == b
