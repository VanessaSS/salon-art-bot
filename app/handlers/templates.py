from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery

from app import messages as msg
from app.handlers.states import Flow
from app.services.flow import SessionStore
from app.services.telegram_service import step_keyboard
from app.services.template_service import TemplateRegistry


def prompt_for(session) -> str:
    step, (n, total) = session.current, session.position
    return (
        msg.ask_photo(step.label, n, total)
        if step.kind == "photo"
        else msg.ask_text(step.label, n, total, not step.required)
    )


async def begin(
    cb: CallbackQuery, state: FSMContext, store: SessionStore, registry: TemplateRegistry, template_id: str
) -> None:
    item = registry.get(template_id)
    if item is None or item.hidden:
        await cb.answer(msg.STALE_BUTTON, show_alert=True)
        return
    session = store.start(cb.from_user.id, item)
    await state.set_state(Flow.collecting)
    await cb.answer()
    m = cb.message
    if item.preview_path and item.preview_path.is_file():
        await m.answer_photo(BufferedInputFile(item.preview_path.read_bytes(), filename="previa.jpg"))
    intro = f"{item.name}" + (f"\n{item.description}" if item.description else "")
    await m.answer(f"{intro}\n\n{prompt_for(session)}", reply_markup=step_keyboard(session.current))


def make_router() -> Router:
    router = Router(name="templates")

    @router.callback_query(F.data.startswith("tpl:"))
    async def choose_template(
        cb: CallbackQuery, state: FSMContext, store: SessionStore, registry: TemplateRegistry
    ) -> None:
        await begin(cb, state, store, registry, cb.data.split(":", 1)[1])

    return router
