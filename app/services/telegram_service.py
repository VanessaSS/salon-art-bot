"""Tudo que fala com a API do Telegram: teclados, download de fotos e envio das artes."""
from __future__ import annotations

import io
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile, InlineKeyboardMarkup, InputMediaPhoto, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app import messages as msg
from app.services.flow import Step
from app.utils.image_processing import MAX_BYTES, InvalidImageError

log = logging.getLogger(__name__)


# ---------- teclados ----------
def menu_keyboard(items) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t in items:
        kb.button(text=t.name, callback_data=f"tpl:{t.id}")
    kb.adjust(1)
    return kb.as_markup()


def step_keyboard(step: Step) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if not step.required:
        kb.button(text="⏭ Pular", callback_data="nav:skip")
    kb.button(text="⬅️ Voltar", callback_data="nav:back")
    kb.button(text="🔄 Recomeçar", callback_data="nav:restart")
    kb.button(text="✖️ Cancelar", callback_data="nav:cancel")
    kb.adjust(*([1, 3] if not step.required else [3]))
    return kb.as_markup()


def result_keyboard() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎨 Criar outra arte", callback_data="res:again")
    kb.button(text="🗂 Escolher outro modelo", callback_data="res:other")
    kb.button(text="📎 Receber em alta qualidade", callback_data="res:hq")
    kb.button(text="⬅️ Corrigir o último passo", callback_data="res:fix")
    kb.button(text="✖️ Cancelar", callback_data="nav:cancel")
    kb.adjust(1)
    return kb.as_markup()


# ---------- download ----------
async def fetch_image_bytes(bot: Bot, message: Message) -> bytes:
    """Baixa a foto enviada (comprimida ou como arquivo). Levanta InvalidImageError com texto seguro."""
    if message.photo:
        file_id, size = message.photo[-1].file_id, message.photo[-1].file_size
    elif message.document and (message.document.mime_type or "").startswith("image/"):
        file_id, size = message.document.file_id, message.document.file_size
    else:
        raise InvalidImageError("Envie uma foto (JPG, PNG ou WEBP).")
    if size and size > MAX_BYTES:
        raise InvalidImageError("A foto é muito grande. Envie uma de até 15 MB.")
    try:
        buf = await bot.download(file_id, destination=io.BytesIO())
    except TelegramAPIError as e:
        log.warning("Falha ao baixar foto (%s)", type(e).__name__)
        raise InvalidImageError(msg.DOWNLOAD_FAILED) from e
    data = buf.getvalue() if buf else b""
    if not data:
        raise InvalidImageError(msg.DOWNLOAD_FAILED)
    return data


# ---------- envio ----------
async def send_previews(message: Message, jpegs: list[bytes]) -> None:
    files = [BufferedInputFile(b, filename=f"arte_{i}.jpg") for i, b in enumerate(jpegs, 1)]
    if len(files) == 1:
        await message.answer_photo(files[0])
    else:
        await message.answer_media_group([InputMediaPhoto(media=f) for f in files])


async def send_documents(message: Message, pngs: list[bytes]) -> None:
    for i, b in enumerate(pngs, 1):
        await message.answer_document(BufferedInputFile(b, filename=f"toque-da-fe_{i}.png"))
