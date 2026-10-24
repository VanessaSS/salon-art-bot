"""Controle de acesso: só IDs autorizados usam o bot (se ALLOWED_USER_IDS estiver preenchido)."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app import messages as msg


class AccessMiddleware(BaseMiddleware):
    def __init__(self, allowed: frozenset[int]):
        self.allowed = allowed

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: dict[str, Any]) -> Any:
        user = getattr(event, "from_user", None)
        if not self.allowed or user is None or user.id in self.allowed:
            return await handler(event, data)
        if isinstance(event, Message) and (event.text or "").split("@")[0].strip() == "/meuid":
            return await handler(event, data)  # deixa a pessoa descobrir o ID para pedir liberação
        text = msg.RESTRICTED.format(uid=user.id)
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        elif isinstance(event, Message):
            await event.answer(text)
        return None
