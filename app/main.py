"""Ponto de entrada: python -m app.main"""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import EXAMPLES_DIR, Settings, SettingsError, load_settings
from app.handlers import fallback, image_creation, start, templates
from app.middlewares import AccessMiddleware
from app.models.template_schema import TemplateError
from app.services.flow import SessionStore
from app.services.template_service import TemplateRegistry

log = logging.getLogger("toque_da_fe")


def build_dispatcher(
    settings: Settings, registry: TemplateRegistry, store: SessionStore, busy: set[int] | None = None
) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage(), registry=registry, store=store, busy=busy if busy is not None else set())
    access = AccessMiddleware(settings.allowed_user_ids)
    dp.message.outer_middleware(access)
    dp.callback_query.outer_middleware(access)
    dp.include_routers(
        start.make_router(), templates.make_router(), image_creation.make_router(), fallback.make_router()
    )
    return dp


async def _sweeper(store: SessionStore) -> None:
    while True:
        await asyncio.sleep(300)
        if n := store.sweep():
            log.info("Sessões expiradas removidas: %d", n)


async def run() -> None:
    settings = load_settings()
    registry = TemplateRegistry(settings.templates_dir).load()  # falha cedo se algum modelo estiver errado
    if not registry.all():
        raise SystemExit("Nenhum modelo encontrado em templates/.")
    if settings.templates_dir == EXAMPLES_DIR:
        log.warning("Usando os modelos de EXEMPLO (examples/templates). Coloque seus modelos em templates/ para usar a sua marca.")
    if not settings.allowed_user_ids:
        log.warning("ALLOWED_USER_IDS vazio: qualquer pessoa que achar o bot poderá usá-lo.")
    store = SessionStore(settings.session_ttl_minutes)
    bot = Bot(settings.token)
    dp = build_dispatcher(settings, registry, store)
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Criar uma arte"),
            BotCommand(command="cancelar", description="Cancelar"),
            BotCommand(command="meuid", description="Ver meu ID"),
        ]
    )
    sweeper = asyncio.create_task(_sweeper(store))
    log.info("Bot iniciado com %d modelos.", len(registry.all()))
    try:
        await dp.start_polling(bot)
    finally:
        sweeper.cancel()
        await bot.session.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    try:
        asyncio.run(run())
    except (SettingsError, TemplateError) as e:
        sys.exit(f"Erro de configuração: {e}")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
