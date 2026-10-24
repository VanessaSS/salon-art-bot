from PIL import Image

from app import cli
from app.config import EXAMPLES_DIR
from tests.conftest import make_photo_bytes

EX = str(EXAMPLES_DIR)


def test_cli_generates_png(tmp_path, capsys):
    foto = tmp_path / "f.jpg"
    foto.write_bytes(make_photo_bytes(size=(1200, 1600)))
    out = tmp_path / "arte.png"
    code = cli.main(["--templates", EX, "-t", "exemplo_servico", "-f", f"foto={foto}", "-x", "titulo=Escova blindada", "-o", str(out)])
    assert code == 0 and Image.open(out).size == (1080, 1920)


def test_cli_errors_are_friendly(tmp_path, capsys):
    assert cli.main(["--templates", EX, "-t", "nao_existe"]) == 2
    assert cli.main(["--templates", EX, "-t", "exemplo_servico", "-f", "foto=/nao/existe.jpg", "-x", "titulo=x"]) == 1
    foto = tmp_path / "f.jpg"
    foto.write_bytes(make_photo_bytes(size=(1200, 1600)))
    assert cli.main(["--templates", EX, "-t", "exemplo_servico_preco", "-f", f"foto={foto}", "-x", "titulo=x"]) == 1
    assert "Preço" in capsys.readouterr().out
