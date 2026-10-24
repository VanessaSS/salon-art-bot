"""Último recurso: mensagens e botões que não pertencem a nenhum fluxo ativo."""

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from app import messages as msg


def make_router() -> Router:
    router = Router(name="fallback")

    @router.message()
    async def any_message(message: Message) -> None:
        await message.answer(msg.USE_BUTTONS)

    @router.callback_query()
    async def any_callback(cb: CallbackQuery) -> None:
        await cb.answer(msg.STALE_BUTTON, show_alert=True)

    return router
