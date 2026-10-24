"""Configuração por variáveis de ambiente (.env). Nunca registre o token em logs."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv é opcional
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[1]


EXAMPLES_DIR = ROOT / "examples" / "templates"


def has_templates(path: Path) -> bool:
    return path.is_dir() and any((d / "template.json").is_file() for d in path.iterdir() if d.is_dir())


def resolve_templates_dir(path: Path) -> Path:
    """Usa `path` se tiver modelos; senão cai nos modelos de exemplo do repositório (para rodar/testar sem artes privadas)."""
    return path if has_templates(path) else EXAMPLES_DIR


class SettingsError(RuntimeError):
    """Configuração ausente ou inválida (mensagem segura, sem segredos)."""


@dataclass(frozen=True)
class Settings:
    token: str = ""
    templates_dir: Path = ROOT / "templates"
    allowed_user_ids: frozenset[int] = frozenset()   # vazio = qualquer pessoa pode usar o bot
    session_ttl_minutes: int = 60                    # fotos/textos em memória expiram após esse tempo

    def __repr__(self) -> str:  # evita vazar o token em logs/tracebacks
        return f"Settings(templates_dir={self.templates_dir}, allowed={len(self.allowed_user_ids)} usuários)"


def load_settings(env: dict[str, str] | None = None) -> Settings:
    if env is None:
        if load_dotenv:
            load_dotenv(ROOT / ".env")
        env = dict(os.environ)
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    if ":" not in token:
        raise SettingsError("TELEGRAM_BOT_TOKEN ausente ou inválido. Copie .env.example para .env e preencha o token do @BotFather.")
    raw_ids = [x.strip() for x in env.get("ALLOWED_USER_IDS", "").split(",") if x.strip()]
    if not all(x.isdigit() for x in raw_ids):
        raise SettingsError("ALLOWED_USER_IDS deve ter só números separados por vírgula (use /meuid no bot para descobrir o seu).")
    tdir = Path(env.get("TEMPLATES_DIR", "templates"))
    return Settings(
        token=token,
        templates_dir=resolve_templates_dir(tdir if tdir.is_absolute() else ROOT / tdir),
        allowed_user_ids=frozenset(int(x) for x in raw_ids),
        session_ttl_minutes=int(env.get("SESSION_TTL_MINUTES", "60")),
    )
