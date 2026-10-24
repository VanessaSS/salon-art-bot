"""Descoberta e cache dos modelos em templates/."""
from __future__ import annotations

import logging
from pathlib import Path

from app.models.template_schema import Carousel, Template, TemplateError, load_template_file

log = logging.getLogger(__name__)


class TemplateRegistry:
    def __init__(self, root: Path):
        self.root = root
        self._templates: dict[str, Template | Carousel] = {}

    def load(self, strict: bool = True) -> "TemplateRegistry":
        """Carrega todos os modelos. strict=True falha no primeiro erro (use ao iniciar o bot)."""
        found: dict[str, Template | Carousel] = {}
        for d in sorted(p for p in self.root.iterdir() if p.is_dir() and not p.name.startswith(".")):
            try:
                t = load_template_file(d)
            except TemplateError as e:
                if strict:
                    raise
                log.error("Modelo ignorado: %s", e)
                continue
            if t.id in found:
                raise TemplateError(f"id de modelo duplicado: {t.id}")
            found[t.id] = t
        self._validate_carousels(found)
        self._templates = found
        return self

    @staticmethod
    def _validate_carousels(found: dict[str, Template | Carousel]) -> None:
        for car in (x for x in found.values() if isinstance(x, Carousel)):
            for i, sl in enumerate(car.slides, 1):
                if sl.template_id is None:
                    continue
                sub = found.get(sl.template_id)
                if not isinstance(sub, Template):
                    raise TemplateError(f"carrossel '{car.id}' slide {i}: modelo '{sl.template_id}' não existe")
                if not set(sl.photos) <= {p.id for p in sub.photos} or not set(sl.texts) <= {t.id for t in sub.texts}:
                    raise TemplateError(f"carrossel '{car.id}' slide {i}: mapeamento usa slot que o modelo não tem")
                if {p.id for p in sub.photos} - set(sl.photos):
                    raise TemplateError(f"carrossel '{car.id}' slide {i}: falta mapear fotos do modelo '{sub.id}'")
                if {t.id for t in sub.texts if t.required} - set(sl.texts):
                    raise TemplateError(f"carrossel '{car.id}' slide {i}: falta mapear textos obrigatórios de '{sub.id}'")

    def all(self, include_hidden: bool = False) -> list[Template | Carousel]:
        """Itens do menu (sem os modelos internos de carrosséis, a menos que include_hidden)."""
        return [t for t in self._templates.values() if include_hidden or not t.hidden]

    def get(self, template_id: str) -> Template | Carousel | None:
        return self._templates.get(template_id)
