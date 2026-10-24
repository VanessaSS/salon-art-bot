"""Teste local pelo terminal, sem Telegram (usa o mesmo motor do bot).

    python -m app.cli --listar
    python -m app.cli                      # modo guiado: pergunta modelo, fotos e textos
    python -m app.cli -t feed_antes_depois -f antes=a.jpg -f depois=d.jpg -x servico=Corte   # carrossel: 3 arquivos
    python -m app.cli -t story_servico_preco -f foto=minha.jpg -x titulo="Escova blindada" -x preco="R$ 70"
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from app.config import resolve_templates_dir
from app.models.template_schema import Carousel, Template, TemplateError
from app.services import image_composer as ic
from app.services.template_service import TemplateRegistry
from app.utils.image_processing import InvalidImageError, load_photo

ROOT = Path(__file__).resolve().parents[1]


def _pairs(items: list[str], what: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"Use o formato id=valor em {what} (recebi: {item!r}).")
        k, v = item.split("=", 1)
        out[k.strip()] = v
    return out


def _choose(templates: list[Template | Carousel]) -> Template | Carousel:
    for i, t in enumerate(templates, 1):
        print(f"  {i}. {t.name}  [{t.id}]" + (f"  → {len(t.slides)} imagens" if t.kind == "carousel" else ""))
    while True:
        raw = input("Escolha o número do modelo: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(templates):
            return templates[int(raw) - 1]
        print("Número inválido.")


def _read_photo(label: str) -> object:
    while True:
        path = Path(input(f"{label} – caminho da foto: ").strip().strip("'\""))
        try:
            return load_photo(path.read_bytes())
        except OSError:
            print("Não encontrei esse arquivo.")
        except InvalidImageError as e:
            print(e)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Gera uma arte do Toque da Fé pelo terminal.")
    ap.add_argument("--listar", action="store_true", help="lista os modelos e sai")
    ap.add_argument("-t", "--template", help="id do modelo")
    ap.add_argument("-f", "--foto", action="append", default=[], metavar="ID=ARQUIVO")
    ap.add_argument("-x", "--texto", action="append", default=[], metavar="ID=TEXTO")
    ap.add_argument("-o", "--saida", help="arquivo PNG de saída (padrão: output/<modelo>_<data>.png)")
    ap.add_argument("--templates", help="pasta com os modelos (padrão: templates/, ou os exemplos se estiver vazia)")
    ap.add_argument("--incluir-exemplo", action="store_true", help="mostra também o modelo de exemplo")
    a = ap.parse_args(argv)

    try:
        reg = TemplateRegistry(resolve_templates_dir(Path(a.templates) if a.templates else ROOT / "templates")).load()
    except TemplateError as e:
        print(f"Erro na configuração dos modelos: {e}")
        return 2
    templates = reg.all() + ([reg.get("exemplo_demo")] if a.incluir_exemplo and reg.get("exemplo_demo") else [])

    if a.listar:
        for t in templates:
            print(f"{t.id}: {t.name}" + (f"  (carrossel: {len(t.slides)} imagens)" if t.kind == "carousel" else ""))
            for p in t.photos:
                print(f"   foto  {p.id}: {p.label}")
            for x in t.texts:
                print(f"   texto {x.id}: {x.label}{'' if x.required else ' (opcional)'}")
        return 0

    interactive = a.template is None
    tpl = _choose(templates) if interactive else reg.get(a.template)
    if tpl is None:
        print(f"Modelo desconhecido: {a.template}. Use --listar.")
        return 2

    photos, texts = {}, _pairs(a.texto, "--texto")
    given = _pairs(a.foto, "--foto")
    try:
        for p in tpl.photos:
            if p.id in given:
                photos[p.id] = load_photo(Path(given[p.id]).read_bytes())
            elif interactive:
                photos[p.id] = _read_photo(p.label)
        for t in tpl.texts:
            if t.id not in texts and interactive:
                texts[t.id] = input(f"{t.label}: ")
        images = ic.compose_item(tpl, reg, photos, texts)
    except (InvalidImageError, ic.CompositionError) as e:
        print(f"Não deu certo: {e}")
        return 1
    except OSError as e:
        print(f"Não consegui ler o arquivo: {e.filename}")
        return 1

    base = Path(a.saida) if a.saida else ROOT / "output" / f"{tpl.id}_{datetime.now():%Y%m%d_%H%M%S}.png"
    base.parent.mkdir(parents=True, exist_ok=True)
    for i, img in enumerate(images, 1):
        out = base if len(images) == 1 else base.with_name(f"{base.stem}_{i}{base.suffix}")
        out.write_bytes(ic.to_png_bytes(img))
        print(f"Arte gerada: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
