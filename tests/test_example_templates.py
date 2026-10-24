import pytest
from PIL import Image

from app.services import image_composer as ic

REAIS = {"exemplo_servico": (1080, 1920, 1), "exemplo_servico_preco": (1080, 1920, 1), "exemplo_antes_depois": (1080, 1920, 2), "exemplo_slide_antes": (1080, 1350, 1), "exemplo_slide_depois": (1080, 1350, 1)}


TEXTOS = {"exemplo_servico": {"titulo": "Escova blindada\ne modelada"},
          "exemplo_servico_preco": {"titulo": "Escova blindada\ne modelada", "preco": "R$ 70"}}


def fotos(t):
    return {p.id: Image.new("RGB", (1200, 1600), (255, 0, 0)) for p in t.photos}


@pytest.mark.parametrize("tid,spec", REAIS.items())
def test_example_template_composes(registry, tid, spec):
    t = registry.get(tid)
    assert (t.width, t.height, len(t.photos)) == spec
    out = ic.compose(t, fotos(t), TEXTOS.get(tid, {"servico": "Escova blindada"}))
    assert out.size == (t.width, t.height)
    p = t.photos[0]
    cx, cy = p.x + p.width // 2, p.y + p.height // 2
    r, g, b, _ = out.getpixel((cx, cy))
    assert r > 200 and g < 60 and b < 60            # foto aparece no centro do slot


@pytest.mark.parametrize("tid", REAIS)
def test_example_template_frame_is_above_photo(registry, tid):
    t = registry.get(tid)
    p = t.photos[0]
    out = ic.compose(t, fotos(t), TEXTOS.get(tid, {"servico": "Corte"})).convert("RGB")
    # borda do slot (meio do lado esquerdo): moldura branca do overlay por cima da foto vermelha
    r, g, b = out.getpixel((p.x + 2, p.y + p.height // 2))
    assert g > 245 and b > 245  # branco (moldura), não o vermelho da foto


def test_example_template_long_service_name(registry):
    t = registry.get("exemplo_slide_antes")
    with pytest.raises(ic.TextTooLongError):
        ic.compose(t, fotos(t), {"servico": "Progressiva orgânica com hidratação profunda e finalização"})


def test_static_cta_exists(registry):
    car = registry.get("exemplo_carrossel")
    assert Image.open(car.directory / "cta.png").size == (1080, 1350)


def test_price_badge_is_drawn_over_photo(registry):
    t = registry.get("exemplo_servico_preco")
    out = ic.compose(t, fotos(t), TEXTOS["exemplo_servico_preco"]).convert("RGB")
    assert out.getpixel((740, 1129)) == (195, 53, 119)          # selo magenta por cima da foto vermelha
    sem = registry.get("exemplo_servico")
    out2 = ic.compose(sem, fotos(sem), TEXTOS["exemplo_servico"]).convert("RGB")
    assert out2.getpixel((740, 1129)) != (195, 53, 119)         # modelo sem preço não tem selo


def test_price_required_in_price_template(registry):
    t = registry.get("exemplo_servico_preco")
    with pytest.raises(ic.MissingFieldError, match="Preço"):
        ic.compose(t, fotos(t), {"titulo": "Escova"})
