import copy
import json

import pytest
from PIL import Image

from app import cli
from app.models.template_schema import Carousel, TemplateError, parse_carousel
from app.services import image_composer as ic
from app.services.template_service import TemplateRegistry
from app.config import EXAMPLES_DIR
from tests.conftest import make_photo_bytes


def solid(rgb):
    return Image.new("RGB", (1200, 1600), rgb)


def test_menu_shows_one_feed_option(registry):
    ids = [t.id for t in registry.all()]
    assert "exemplo_carrossel" in ids and "exemplo_slide_antes" not in ids and "exemplo_slide_depois" not in ids
    assert registry.get("exemplo_slide_antes") is not None          # existe internamente
    car = registry.get("exemplo_carrossel")
    assert isinstance(car, Carousel) and [p.label for p in car.photos] == ["Foto ANTES", "Foto DEPOIS"]
    assert len(car.slides) == 3


def test_carousel_generates_three_slides_in_order(registry):
    car = registry.get("exemplo_carrossel")
    imgs = ic.compose_item(car, registry, {"antes": solid((255, 0, 0)), "depois": solid((0, 0, 255))}, {"servico": "Corte"})
    assert len(imgs) == 3 and all(i.size == (1080, 1350) for i in imgs)
    c = (540, 700)
    r, g, b = imgs[0].convert("RGB").getpixel(c)
    assert r > 200 and b < 60                      # slide 1 = ANTES (vermelho)
    r, g, b = imgs[1].convert("RGB").getpixel(c)
    assert b > 200 and r < 60                      # slide 2 = DEPOIS (azul)
    assert imgs[2].tobytes() == Image.open(car.directory / "cta.png").convert("RGBA").tobytes()  # slide 3 fixo


def test_carousel_missing_inputs(registry):
    car = registry.get("exemplo_carrossel")
    with pytest.raises(ic.MissingFieldError, match="DEPOIS"):
        ic.compose_item(car, registry, {"antes": solid((1, 1, 1))}, {"servico": "Corte"})
    with pytest.raises(ic.MissingFieldError, match="serviço"):
        ic.compose_item(car, registry, {"antes": solid((1, 1, 1)), "depois": solid((1, 1, 1))}, {})
    with pytest.raises(ic.CompositionError, match="longo"):
        ic.compose_item(car, registry, {"antes": solid((1, 1, 1)), "depois": solid((1, 1, 1))}, {"servico": "x" * 50})


def test_single_template_through_compose_item(registry):
    t = registry.get("exemplo_servico")
    assert len(ic.compose_item(t, registry, {"foto": solid((9, 9, 9))}, {"titulo": "Escova"})) == 1


def base_cfg():
    return {"type": "carousel", "id": "c", "name": "C", "photos": [{"id": "a", "label": "A"}],
            "texts": [], "slides": [{"template": "exemplo_servico", "photos": {"foto": "a"}, "texts": {"titulo": "t"}}]}


@pytest.mark.parametrize("mutate,msg", [
    (lambda d: d.update(slides=[]), "slides"),
    (lambda d: d["slides"][0].update(static="x.png"), "OU"),
    (lambda d: d["slides"][0].update(template=None, static="../x.png", photos={}, texts={}), "nome do arquivo"),
    (lambda d: d["slides"][0].update(photos={"foto": "inexistente"}), "inexistente"),
    (lambda d: d.update(id="Id Ruim"), "id inválido"),
])
def test_carousel_config_errors(tmp_path, mutate, msg):
    d = copy.deepcopy(base_cfg()); mutate(d)
    with pytest.raises(TemplateError, match=msg):
        parse_carousel(d, tmp_path)


def test_registry_validates_carousel_references(tmp_path, registry):
    root = tmp_path / "templates"; root.mkdir()
    (root / "c").mkdir()
    cfg = base_cfg(); cfg["texts"] = [{"id": "t", "label": "T"}]
    (root / "c" / "template.json").write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(TemplateError, match="não existe"):          # modelo referenciado ausente
        TemplateRegistry(root).load()


def test_cli_carousel_writes_three_files(tmp_path):
    a, d = tmp_path / "a.jpg", tmp_path / "d.jpg"
    a.write_bytes(make_photo_bytes(size=(1200, 1600))); d.write_bytes(make_photo_bytes(size=(1200, 1600)))
    out = tmp_path / "carrossel.png"
    assert cli.main(["--templates", str(EXAMPLES_DIR), "-t", "exemplo_carrossel", "-f", f"antes={a}", "-f", f"depois={d}", "-x", "servico=Corte", "-o", str(out)]) == 0
    assert sorted(p.name for p in tmp_path.glob("carrossel_*.png")) == ["carrossel_1.png", "carrossel_2.png", "carrossel_3.png"]
