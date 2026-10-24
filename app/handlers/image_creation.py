"""Coleta de fotos/textos, geração da arte e botões do resultado."""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import messages as msg
from app.handlers.start import show_menu
from app.handlers.states import Flow
from app.handlers.templates import begin, prompt_for
from app.services import image_composer as ic
from app.services.flow import Session, SessionStore
from app.services.telegram_service import (
    fetch_image_bytes,
    result_keyboard,
    send_documents,
    send_previews,
    step_keyboard,
)
from app.services.template_service import TemplateRegistry
from app.utils.image_processing import InvalidImageError, load_photo

log = logging.getLogger(__name__)


async def ask_current(m: Message, session: Session) -> None:
    await m.answer(prompt_for(session), reply_markup=step_keyboard(session.current))


async def _expired(m: Message, state: FSMContext) -> None:
    await state.clear()
    await m.answer(msg.EXPIRED)


def _render(item, registry, photo_bytes: dict[str, bytes], texts: dict[str, str]):
    """Roda em thread: decodifica fotos, compõe e codifica (não bloqueia o bot)."""
    photos = {k: load_photo(v) for k, v in photo_bytes.items()}
    images = ic.compose_item(item, registry, photos, texts)
    return [ic.to_jpeg_bytes(i) for i in images], [ic.to_png_bytes(i) for i in images]


def _input_id_for(item, slot_id: str) -> str:
    """Id da entrada do usuário que alimenta o slot de texto (no carrossel passa pelo mapeamento)."""
    for ref in getattr(item, "slides", ()):
        if slot_id in ref.texts:
            return ref.texts[slot_id]
    return slot_id


async def generate(
    m: Message, state: FSMContext, session: Session, registry: TemplateRegistry, busy: set[int], uid: int
) -> None:
    item = registry.get(session.item_id)
    busy.add(uid)
    status = await m.answer(msg.PREPARING)
    try:
        jpgs, pngs = await asyncio.to_thread(_render, item, registry, dict(session.photos), dict(session.texts))
    except ic.TextTooLongError as e:
        session.go_to(_input_id_for(item, e.slot.id))
        await m.answer(str(e))
        await ask_current(m, session)
        return
    except (ic.CompositionError, InvalidImageError) as e:
        session.back()
        await m.answer(str(e))
        await ask_current(m, session)
        return
    except Exception:  # noqa: BLE001 - nunca derruba o bot; o traceback não contém textos do cliente
        log.exception("Falha inesperada ao gerar arte (modelo=%s)", session.item_id)
        session.back()
        await m.answer(msg.GENERIC_ERROR)
        await ask_current(m, session)
        return
    finally:
        busy.discard(uid)
        with contextlib.suppress(Exception):
            await status.delete()
    session.results_png = pngs
    await state.set_state(Flow.finished)
    await send_previews(m, jpgs)
    await m.answer(msg.RESULT_READY, reply_markup=result_keyboard())
    log.info("Arte entregue (modelo=%s, imagens=%d)", session.item_id, len(pngs))


async def advance(
    m: Message, state: FSMContext, session: Session, registry: TemplateRegistry, busy: set[int], uid: int
) -> None:
    if session.done:
        await generate(m, state, session, registry, busy, uid)
    else:
        await ask_current(m, session)


async def _session_cb(cb: CallbackQuery, state: FSMContext, store: SessionStore) -> Session | None:
    session = store.get(cb.from_user.id)
    await cb.answer()
    if session is None or cb.message is None:
        await state.clear()
        if cb.message:
            await cb.message.answer(msg.EXPIRED)
        return None
    return session


def make_router() -> Router:
    router = Router(name="image_creation")

    # ---------- mensagens durante a coleta ----------
    @router.message(Flow.collecting, F.photo | F.document)
    async def on_photo(
        message: Message, bot: Bot, state: FSMContext, store: SessionStore, registry: TemplateRegistry, busy: set[int]
    ) -> None:
        uid = message.from_user.id
        session = store.get(uid)
        if session is None:
            return await _expired(message, state)
        if uid in busy:
            return await message.answer(msg.BUSY)
        step = session.current
        if step is None or step.kind != "photo":
            return await message.answer(msg.expected_text(step.label) if step else msg.USE_BUTTONS)
        try:
            data = await fetch_image_bytes(bot, message)
            await asyncio.to_thread(load_photo, data)  # valida formato, tamanho e resolução
        except InvalidImageError as e:
            return await message.answer(str(e))
        session.add_photo(data)
        await advance(message, state, session, registry, busy, uid)

    @router.message(Flow.collecting, F.text)
    async def on_text(
        message: Message, state: FSMContext, store: SessionStore, registry: TemplateRegistry, busy: set[int]
    ) -> None:
        uid = message.from_user.id
        session = store.get(uid)
        if session is None:
            return await _expired(message, state)
        if uid in busy:
            return await message.answer(msg.BUSY)
        step = session.current
        if step is None:
            return await message.answer(msg.USE_BUTTONS)
        if step.kind == "photo":
            return await message.answer(msg.expected_photo(step.label))
        value = message.text.strip()
        if value.startswith("/"):
            return await message.answer("Não conheço esse comando. Use /start para recomeçar ou /cancelar para sair.")
        if step.max_chars and len(value) > step.max_chars:
            return await message.answer(msg.text_too_long(step.max_chars))
        session.add_text(value)
        await advance(message, state, session, registry, busy, uid)

    @router.message(Flow.collecting)
    async def on_other(message: Message, store: SessionStore) -> None:
        session = store.get(message.from_user.id)
        step = session.current if session else None
        if step is None:
            return await message.answer(msg.USE_BUTTONS)
        await message.answer(msg.expected_photo(step.label) if step.kind == "photo" else msg.expected_text(step.label))

    # ---------- botões de navegação ----------
    @router.callback_query(Flow.collecting, F.data == "nav:back")
    async def nav_back(cb: CallbackQuery, state: FSMContext, store: SessionStore, registry: TemplateRegistry) -> None:
        if (session := await _session_cb(cb, state, store)) is None:
            return
        if not session.back():  # já estava no primeiro passo: volta ao menu
            await state.clear()
            store.drop(cb.from_user.id)
            return await show_menu(cb.message, registry)
        await ask_current(cb.message, session)

    @router.callback_query(Flow.collecting, F.data == "nav:skip")
    async def nav_skip(
        cb: CallbackQuery, state: FSMContext, store: SessionStore, registry: TemplateRegistry, busy: set[int]
    ) -> None:
        if (session := await _session_cb(cb, state, store)) is None:
            return
        if not session.skip():
            return await cb.message.answer("Esse passo é obrigatório.")
        await advance(cb.message, state, session, registry, busy, cb.from_user.id)

    @router.callback_query(Flow.collecting, F.data == "nav:restart")
    async def nav_restart(cb: CallbackQuery, state: FSMContext, store: SessionStore) -> None:
        if (session := await _session_cb(cb, state, store)) is None:
            return
        session.restart()
        await ask_current(cb.message, session)

    # ---------- botões do resultado ----------
    @router.callback_query(Flow.finished, F.data == "res:again")
    async def res_again(cb: CallbackQuery, state: FSMContext, store: SessionStore, registry: TemplateRegistry) -> None:
        session = store.get(cb.from_user.id)
        if session is None or cb.message is None:
            await cb.answer()
            return await _expired(cb.message, state) if cb.message else None
        await begin(cb, state, store, registry, session.item_id)

    @router.callback_query(Flow.finished, F.data == "res:other")
    async def res_other(cb: CallbackQuery, state: FSMContext, store: SessionStore, registry: TemplateRegistry) -> None:
        await cb.answer()
        await state.clear()
        store.drop(cb.from_user.id)
        if cb.message:
            await show_menu(cb.message, registry)

    @router.callback_query(Flow.finished, F.data == "res:hq")
    async def res_hq(cb: CallbackQuery, state: FSMContext, store: SessionStore) -> None:
        if (session := await _session_cb(cb, state, store)) is None:
            return
        await send_documents(cb.message, session.results_png)

    @router.callback_query(Flow.finished, F.data == "res:fix")
    async def res_fix(cb: CallbackQuery, state: FSMContext, store: SessionStore) -> None:
        if (session := await _session_cb(cb, state, store)) is None:
            return
        session.back()
        await state.set_state(Flow.collecting)
        await ask_current(cb.message, session)

    return router
