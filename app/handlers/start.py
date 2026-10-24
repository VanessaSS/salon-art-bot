from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app import messages as msg
from app.services.flow import SessionStore
from app.services.telegram_service import menu_keyboard
from app.services.template_service import TemplateRegistry


async def show_menu(message: Message, registry: TemplateRegistry) -> None:
    items = registry.all()
    if not items:
        await message.answer(msg.NO_TEMPLATES)
        return
    await message.answer(msg.WELCOME, reply_markup=menu_keyboard(items))


def make_router() -> Router:
    router = Router(name="start")

    @router.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext, store: SessionStore, registry: TemplateRegistry) -> None:
        await state.clear()
        store.drop(message.from_user.id)
        await show_menu(message, registry)

    @router.message(Command("cancelar"))
    async def cmd_cancel(message: Message, state: FSMContext, store: SessionStore) -> None:
        await state.clear()
        store.drop(message.from_user.id)
        await message.answer(msg.CANCELLED)

    @router.message(Command("meuid"))
    async def cmd_my_id(message: Message) -> None:
        await message.answer(f"Seu ID do Telegram é: {message.from_user.id}")

    @router.callback_query(F.data == "nav:cancel")
    async def cb_cancel(cb: CallbackQuery, state: FSMContext, store: SessionStore) -> None:
        await state.clear()
        store.drop(cb.from_user.id)
        await cb.answer()
        if cb.message:
            await cb.message.answer(msg.CANCELLED)

    return router
