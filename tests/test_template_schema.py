import copy
import json

import pytest

from app.models.template_schema import TemplateError, load_template_file, parse_template
from app.services.template_service import TemplateRegistry


def valid(tmp_path):
    return {
        "id": "t1", "name": "T", "canvas": {"width": 1000, "height": 1000}, "background": "b.png",
        "photos": [{"id": "f1", "label": "F", "x": 0, "y": 0, "width": 500, "height": 500}],
        "texts": [{"id": "x1", "label": "X", "x": 0, "y": 600, "width": 500, "height": 100,
                   "max_font_size": 40, "min_font_size": 20}],
    }


def test_demo_loads(demo):
    assert demo.id == "exemplo_demo" and len(demo.photos) == 1 and len(demo.texts) == 3


def test_valid_parses(tmp_path):
    t = parse_template(valid(tmp_path), tmp_path)
    assert t.photos[0].fit == "cover" and t.texts[0].align == "center"


@pytest.mark.parametrize("mutate,msg", [
    (lambda d: d.pop("name"), "name"),
    (lambda d: d.update(id="Id Inválido"), "id inválido"),
    (lambda d: d["photos"][0].update(width=5000), "fora do canvas"),
    (lambda d: d["photos"][0].update(fit="stretch"), "fit"),
    (lambda d: d["photos"][0].update(mask="rounded"), "radius"),
    (lambda d: d["texts"][0].update(min_font_size=99), "min_font_size"),
    (lambda d: d["texts"][0].update(color="rosa"), "cor"),
    (lambda d: d["texts"][0].update(font="../../etc/passwd"), "font"),
    (lambda d: d["texts"][0].update(id="f1"), "duplicados"),
    (lambda d: d.update(background="../x.png"), "background"),
    (lambda d: d.update(photos=[], texts=[]), "ao menos"),
    (lambda d: d["canvas"].update(width="1080"), "tipo"),
])
def test_invalid_configs(tmp_path, mutate, msg):
    d = copy.deepcopy(valid(tmp_path))
    mutate(d)
    with pytest.raises(TemplateError, match=msg):
        parse_template(d, tmp_path)


def test_bad_json_and_missing_files(tmp_path):
    (tmp_path / "template.json").write_text("{nao é json", encoding="utf-8")
    with pytest.raises(TemplateError, match="JSON inválido"):
        load_template_file(tmp_path)
    (tmp_path / "template.json").write_text(json.dumps(valid(tmp_path)), encoding="utf-8")
    with pytest.raises(TemplateError, match="não encontrado"):
        load_template_file(tmp_path)


def test_registry_strict_vs_lenient(tmp_path):
    bad = tmp_path / "ruim"
    bad.mkdir()
    (bad / "template.json").write_text("{}", encoding="utf-8")
    with pytest.raises(TemplateError):
        TemplateRegistry(tmp_path).load(strict=True)
    assert TemplateRegistry(tmp_path).load(strict=False).all() == []
