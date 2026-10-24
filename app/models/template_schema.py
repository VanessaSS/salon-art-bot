"""Schema dos modelos gráficos (templates/<id>/template.json).

Ordem de composição (de trás para frente):
    background -> photos (na ordem do JSON) -> overlay -> texts

Elementos FIXOS ficam em background.png / overlay.png.
Elementos VARIÁVEIS são os slots de `photos` e `texts`.
Todas as coordenadas são em pixels do canvas (origem no canto superior esquerdo).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
SLUG = re.compile(r"^[a-z0-9_]+$")
Fit = Literal["cover", "contain"]
Mask = Literal["none", "circle", "rounded"]
Align = Literal["left", "center", "right"]
VAlign = Literal["top", "middle", "bottom"]


class TemplateError(ValueError):
    """Configuração de modelo inválida."""


@dataclass(frozen=True)
class PhotoSlot:
    id: str
    label: str
    x: int
    y: int
    width: int
    height: int
    fit: Fit = "cover"
    mask: Mask = "none"
    radius: int = 0  # usado quando mask == "rounded"
    focus_x: float = 0.5  # 0..1: ponto de foco horizontal do recorte (cover)
    focus_y: float = 0.5  # 0..1: ponto de foco vertical do recorte (cover)


@dataclass(frozen=True)
class TextSlot:
    id: str
    label: str
    x: int
    y: int
    width: int
    height: int
    max_font_size: int
    min_font_size: int
    color: str = "#39232F"
    font: str = "Poppins-Regular.ttf"  # arquivo dentro de fonts/
    font_variation: str | None = None  # fontes variáveis, ex.: "Bold"
    align: Align = "center"
    valign: VAlign = "middle"
    max_lines: int = 1
    line_spacing: float = 1.15
    required: bool = True
    max_chars: int = 120


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    description: str
    width: int
    height: int
    directory: Path
    background: str
    overlay: str | None = None
    preview: str | None = None
    photos: tuple[PhotoSlot, ...] = field(default_factory=tuple)
    texts: tuple[TextSlot, ...] = field(default_factory=tuple)
    hidden: bool = False  # True: não aparece no menu (usado só dentro de carrosséis)
    kind: str = "single"

    @property
    def background_path(self) -> Path:
        return self.directory / self.background

    @property
    def overlay_path(self) -> Path | None:
        return self.directory / self.overlay if self.overlay else None

    @property
    def preview_path(self) -> Path | None:
        return self.directory / self.preview if self.preview else None


@dataclass(frozen=True)
class InputPhoto:
    id: str
    label: str


@dataclass(frozen=True)
class InputText:
    id: str
    label: str
    required: bool = True
    max_chars: int = 120


@dataclass(frozen=True)
class SlideRef:
    """Um slide do carrossel: um modelo existente (com mapeamento de entradas) ou uma imagem estática."""
    template_id: str | None = None
    static: str | None = None
    photos: dict[str, str] = field(default_factory=dict)  # id da foto no modelo -> id da entrada do carrossel
    texts: dict[str, str] = field(default_factory=dict)   # id do texto no modelo -> id da entrada do carrossel


@dataclass(frozen=True)
class Carousel:
    """Uma opção do menu que gera VÁRIAS imagens a partir das mesmas fotos/textos."""
    id: str
    name: str
    description: str
    directory: Path
    photos: tuple[InputPhoto, ...]
    texts: tuple[InputText, ...]
    slides: tuple[SlideRef, ...]
    hidden: bool = False
    preview: str | None = None
    kind: str = "carousel"

    @property
    def preview_path(self) -> Path | None:
        return self.directory / self.preview if self.preview else None


def _req(d: dict[str, Any], key: str, typ: type | tuple, where: str) -> Any:
    if key not in d:
        raise TemplateError(f"{where}: campo obrigatório ausente: '{key}'")
    v = d[key]
    if isinstance(v, bool) or not isinstance(v, typ):
        raise TemplateError(f"{where}: '{key}' com tipo inválido")
    return v


def _rect(d: dict[str, Any], where: str, canvas: tuple[int, int]) -> tuple[int, int, int, int]:
    x, y, w, h = (_req(d, k, int, where) for k in ("x", "y", "width", "height"))
    if w <= 0 or h <= 0:
        raise TemplateError(f"{where}: width/height devem ser > 0")
    if x < 0 or y < 0 or x + w > canvas[0] or y + h > canvas[1]:
        raise TemplateError(f"{where}: área fora do canvas {canvas[0]}x{canvas[1]}")
    return x, y, w, h


def _choice(d: dict[str, Any], key: str, default: str, options: tuple[str, ...], where: str) -> str:
    v = d.get(key, default)
    if v not in options:
        raise TemplateError(f"{where}: '{key}' deve ser um de {options}")
    return v


def _parse_photo(d: dict[str, Any], canvas: tuple[int, int], where: str) -> PhotoSlot:
    pid = _req(d, "id", str, where)
    if not SLUG.match(pid):
        raise TemplateError(f"{where}: id inválido (use a-z, 0-9, _)")
    where = f"{where}[{pid}]"
    x, y, w, h = _rect(d, where, canvas)
    focus = [float(d.get(k, 0.5)) for k in ("focus_x", "focus_y")]
    if not all(0.0 <= f <= 1.0 for f in focus):
        raise TemplateError(f"{where}: focus_x/focus_y devem estar entre 0 e 1")
    mask = _choice(d, "mask", "none", ("none", "circle", "rounded"), where)
    radius = int(d.get("radius", 0))
    if mask == "rounded" and radius <= 0:
        raise TemplateError(f"{where}: mask 'rounded' exige radius > 0")
    return PhotoSlot(
        id=pid, label=_req(d, "label", str, where), x=x, y=y, width=w, height=h,
        fit=_choice(d, "fit", "cover", ("cover", "contain"), where),  # type: ignore[arg-type]
        mask=mask, radius=radius, focus_x=focus[0], focus_y=focus[1],  # type: ignore[arg-type]
    )


def _parse_text(d: dict[str, Any], canvas: tuple[int, int], where: str) -> TextSlot:
    tid = _req(d, "id", str, where)
    if not SLUG.match(tid):
        raise TemplateError(f"{where}: id inválido (use a-z, 0-9, _)")
    where = f"{where}[{tid}]"
    x, y, w, h = _rect(d, where, canvas)
    mx, mn = _req(d, "max_font_size", int, where), _req(d, "min_font_size", int, where)
    if not 0 < mn <= mx:
        raise TemplateError(f"{where}: exige 0 < min_font_size <= max_font_size")
    color = d.get("color", "#39232F")
    if not HEX_COLOR.match(str(color)):
        raise TemplateError(f"{where}: cor inválida (use #RRGGBB)")
    font = d.get("font", "Poppins-Regular.ttf")
    if "/" in font or "\\" in font or ".." in font:
        raise TemplateError(f"{where}: 'font' deve ser só o nome do arquivo em fonts/")
    max_lines = int(d.get("max_lines", 1))
    if max_lines < 1:
        raise TemplateError(f"{where}: max_lines deve ser >= 1")
    return TextSlot(
        id=tid, label=_req(d, "label", str, where), x=x, y=y, width=w, height=h,
        max_font_size=mx, min_font_size=mn, color=color, font=font,
        font_variation=d.get("font_variation"),
        align=_choice(d, "align", "center", ("left", "center", "right"), where),  # type: ignore[arg-type]
        valign=_choice(d, "valign", "middle", ("top", "middle", "bottom"), where),  # type: ignore[arg-type]
        max_lines=max_lines, line_spacing=float(d.get("line_spacing", 1.15)),
        required=bool(d.get("required", True)), max_chars=int(d.get("max_chars", 120)),
    )


def parse_template(data: dict[str, Any], directory: Path) -> Template:
    where = f"template '{directory.name}'"
    if not isinstance(data, dict):
        raise TemplateError(f"{where}: JSON deve ser um objeto")
    tid = _req(data, "id", str, where)
    if not SLUG.match(tid):
        raise TemplateError(f"{where}: id inválido (use a-z, 0-9, _)")
    canvas = _req(data, "canvas", dict, where)
    cw, ch = _req(canvas, "width", int, where), _req(canvas, "height", int, where)
    if cw <= 0 or ch <= 0:
        raise TemplateError(f"{where}: canvas inválido")
    photos = tuple(_parse_photo(p, (cw, ch), f"{where}.photos") for p in data.get("photos", []))
    texts = tuple(_parse_text(t, (cw, ch), f"{where}.texts") for t in data.get("texts", []))
    ids = [p.id for p in photos] + [t.id for t in texts]
    if len(ids) != len(set(ids)):
        raise TemplateError(f"{where}: ids de slots duplicados")
    for rel in ("background", "overlay", "preview"):
        name = data.get(rel)
        if name is not None and (("/" in name) or ("\\" in name) or (".." in name)):
            raise TemplateError(f"{where}: '{rel}' deve ser só o nome do arquivo")
    if not photos and not texts:
        raise TemplateError(f"{where}: o modelo precisa de ao menos uma foto ou texto")
    return Template(
        id=tid, name=_req(data, "name", str, where), description=data.get("description", ""),
        width=cw, height=ch, directory=directory,
        background=_req(data, "background", str, where),
        overlay=data.get("overlay"), preview=data.get("preview"),
        photos=photos, texts=texts, hidden=bool(data.get("hidden", False)),
    )


def _safe_name(value: str, where: str) -> str:
    if "/" in value or "\\" in value or ".." in value:
        raise TemplateError(f"{where}: use só o nome do arquivo")
    return value


def parse_carousel(data: dict[str, Any], directory: Path) -> Carousel:
    where = f"carrossel '{directory.name}'"
    cid = _req(data, "id", str, where)
    if not SLUG.match(cid):
        raise TemplateError(f"{where}: id inválido (use a-z, 0-9, _)")
    photos = tuple(InputPhoto(_req(p, "id", str, where), _req(p, "label", str, where)) for p in data.get("photos", []))
    texts = tuple(InputText(_req(t, "id", str, where), _req(t, "label", str, where), bool(t.get("required", True)),
                            int(t.get("max_chars", 120))) for t in data.get("texts", []))
    ids = [x.id for x in photos] + [x.id for x in texts]
    if len(ids) != len(set(ids)) or not all(SLUG.match(i) for i in ids):
        raise TemplateError(f"{where}: ids de entradas duplicados ou inválidos")
    raw = data.get("slides")
    if not isinstance(raw, list) or not raw:
        raise TemplateError(f"{where}: 'slides' deve ser uma lista com ao menos um slide")
    slides = []
    for i, sl in enumerate(raw, 1):
        w = f"{where}.slides[{i}]"
        tid, static = sl.get("template"), sl.get("static")
        if (tid is None) == (static is None):
            raise TemplateError(f"{w}: informe 'template' OU 'static'")
        pm, tm = dict(sl.get("photos", {})), dict(sl.get("texts", {}))
        if not set(pm.values()) <= {p.id for p in photos} or not set(tm.values()) <= {t.id for t in texts}:
            raise TemplateError(f"{w}: mapeamento aponta para entrada inexistente")
        slides.append(SlideRef(tid, _safe_name(static, w) if static else None, pm, tm))
    if not photos and not texts:
        raise TemplateError(f"{where}: o carrossel precisa de ao menos uma foto ou texto")
    return Carousel(id=cid, name=_req(data, "name", str, where), description=data.get("description", ""),
                    directory=directory, photos=photos, texts=texts, slides=tuple(slides),
                    hidden=bool(data.get("hidden", False)), preview=data.get("preview"))


def load_template_file(directory: Path) -> Template | Carousel:
    path = directory / "template.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise TemplateError(f"template.json não encontrado em {directory.name}") from e
    except json.JSONDecodeError as e:
        raise TemplateError(f"JSON inválido em {directory.name}/template.json: {e}") from e
    if isinstance(data, dict) and data.get("type") == "carousel":
        car = parse_carousel(data, directory)
        for sl in car.slides:
            if sl.static and not (directory / sl.static).is_file():
                raise TemplateError(f"{directory.name}: arquivo não encontrado: {sl.static}")
        return car
    t = parse_template(data, directory)
    for rel in (t.background_path, t.overlay_path):
        if rel is not None and not rel.is_file():
            raise TemplateError(f"{directory.name}: arquivo não encontrado: {rel.name}")
    return t
