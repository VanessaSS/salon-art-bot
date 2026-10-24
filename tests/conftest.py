import io
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.template_service import TemplateRegistry  # noqa: E402


def make_photo_bytes(size=(1600, 900), color=(200, 30, 30), fmt="JPEG", exif_orientation=None) -> bytes:
    """Foto sintética: metade esquerda `color`, metade direita azul (para checar recortes)."""
    img = Image.new("RGB", size, color)
    img.paste((20, 20, 200), (size[0] // 2, 0, size[0], size[1]))
    buf = io.BytesIO()
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation
        img.save(buf, format=fmt, exif=exif)
    else:
        img.save(buf, format=fmt)
    return buf.getvalue()


@pytest.fixture(scope="session")
def registry():
    """Modelos de EXEMPLO versionados no repositório: os testes não dependem de arquivos privados."""
    import subprocess
    examples = ROOT / "examples" / "templates"
    if not (examples / "exemplo_demo" / "template.json").exists():
        subprocess.run([sys.executable, str(ROOT / "tools" / "make_example_templates.py")], check=True)
    return TemplateRegistry(examples).load()


@pytest.fixture(scope="session")
def real_registry():
    """Modelos reais (pasta templates/, privada). Os testes que os usam são pulados se ela não existir."""
    if not (ROOT / "templates" / "story_servico" / "template.json").exists():
        pytest.skip("modelos reais (templates/) não estão neste checkout")
    return TemplateRegistry(ROOT / "templates").load()


@pytest.fixture
def demo(registry):
    return registry.get("exemplo_demo")
