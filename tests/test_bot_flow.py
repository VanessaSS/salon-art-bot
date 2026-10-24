"""Fluxo completo do bot passando pelo Dispatcher do aiogram, com uma API do Telegram simulada."""
from datetime import datetime

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import SendMediaGroup
from aiogram.types import Chat, File, Message

from app import messages as msg
from app.config import Settings
from app.main import build_dispatcher
from app.services.flow import SessionStore
from tests.conftest import make_photo_bytes

UID = 1


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.file_bytes = make_photo_bytes(size=(1200, 1600))

    async def close(self): ...

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        name = type(method).__name__
        mk = lambda i=0: Message(message_id=len(self.calls) + i, date=datetime.now(), chat=Chat(id=UID, type="private"))
        if name == "GetFile":
            return File(file_id=method.file_id, file_unique_id="u", file_path="x/y.jpg")
        if name in ("SendMessage", "SendPhoto", "SendDocument"):
            return mk()
        if isinstance(method, SendMediaGroup):
            return [mk(i) for i in range(len(method.media))]
        return True

    async def stream_content(self, url, **kwargs):
        yield self.file_bytes


class Harness:
    def __init__(self, registry, allowed=frozenset(), ttl=60):
        self.net = FakeSession()
        self.bot = Bot("123456:TEST-TOKEN", session=self.net)
        self.store = SessionStore(ttl)
        self.dp = build_dispatcher(Settings(token="123456:TEST-TOKEN", allowed_user_ids=allowed), registry, self.store)
        self.busy = self.dp.workflow_data["busy"]
        self.n = 0

    def _msg(self, **extra):
        self.n += 1
        return {"message_id": self.n, "date": 0, "chat": {"id": UID, "type": "private"},
                "from": {"id": UID, "is_bot": False, "first_name": "Teste"}, **extra}

    async def _feed(self, **kw):
        self.n += 1
        await self.dp.feed_raw_update(self.bot, {"update_id": self.n, **kw})

    async def text(self, t):
        await self._feed(message=self._msg(text=t))

    async def photo(self, size=1000):
        await self._feed(message=self._msg(photo=[{"file_id": "f1", "file_unique_id": "u1", "width": 9, "height": 9, "file_size": size}]))

    async def document(self, mime="image/jpeg"):
        await self._feed(message=self._msg(document={"file_id": "d1", "file_unique_id": "u2", "mime_type": mime, "file_size": 1000}))

    async def click(self, data):
        self.n += 1
        await self._feed(callback_query={"id": str(self.n), "chat_instance": "c", "data": data,
                                         "from": {"id": UID, "is_bot": False, "first_name": "Teste"},
                                         "message": self._msg(text="x")})

    def kinds(self):
        return [type(c).__name__ for c in self.net.calls]

    def texts(self):
        return [c.text for c in self.net.calls if type(c).__name__ == "SendMessage"]

    def last_buttons(self):
        for c in reversed(self.net.calls):
            if type(c).__name__ == "SendMessage" and c.reply_markup:
                return [b.text for row in c.reply_markup.inline_keyboard for b in row]
        return []

    def count(self, name):
        return self.kinds().count(name)


@pytest.fixture
def h(registry):
    return Harness(registry)


async def test_start_lists_models_without_internal_ones(h):
    await h.text("/start")
    assert h.texts()[0] == msg.WELCOME
    btns = h.last_buttons()
    assert "Exemplo – Carrossel antes e depois" in btns and "Exemplo – Serviço com preço" in btns
    assert not any("demonstrativo" in b or b.startswith("Exemplo – Slide") for b in btns)


async def test_single_template_full_flow(h):
    await h.text("/start")
    await h.click("tpl:exemplo_servico")
    assert "Passo 1 de 2" in h.texts()[-1] and "envie a foto" in h.texts()[-1]
    await h.photo()
    assert "Passo 2 de 2" in h.texts()[-1]
    await h.text("Escova blindada\ne modelada")
    assert h.count("SendPhoto") == 1
    assert msg.RESULT_READY in h.texts()
    assert "🎨 Criar outra arte" in h.last_buttons() and "📎 Receber em alta qualidade" in h.last_buttons()
    assert h.busy == set()


async def test_carousel_asks_before_and_after_then_sends_album(h):
    await h.click("tpl:exemplo_carrossel")
    assert "Foto ANTES" in h.texts()[-1]
    await h.photo()
    assert "Foto DEPOIS" in h.texts()[-1]
    await h.photo()
    assert "serviço" in h.texts()[-1]
    await h.text("Corte")
    album = [c for c in h.net.calls if isinstance(c, SendMediaGroup)]
    assert len(album) == 1 and len(album[0].media) == 3
    await h.click("res:hq")
    assert h.count("SendDocument") == 3


async def test_photo_sent_as_file_is_accepted(h):
    await h.click("tpl:exemplo_servico")
    await h.document("image/png")
    assert "Passo 2 de 2" in h.texts()[-1]
    await h.click("nav:back")
    await h.document("application/pdf")
    assert "Envie uma foto" in h.texts()[-1]


async def test_invalid_photo_keeps_same_step(h):
    h.net.file_bytes = b"isto nao e imagem"
    await h.click("tpl:exemplo_servico")
    await h.photo()
    assert "Não consegui abrir" in h.texts()[-1]
    assert h.store.get(UID).index == 0


async def test_oversized_photo_rejected_before_download(h):
    await h.click("tpl:exemplo_servico")
    await h.photo(size=50 * 1024 * 1024)
    assert "muito grande" in h.texts()[-1] and "GetFile" not in h.kinds()


async def test_wrong_input_type_gets_helpful_message(h):
    await h.click("tpl:exemplo_servico")
    await h.text("oi")
    assert "Preciso de uma foto" in h.texts()[-1]
    await h.photo()
    await h.photo()
    assert "preciso de um texto" in h.texts()[-1]


async def test_back_keeps_previous_data_and_restart_clears(h):
    await h.click("tpl:exemplo_carrossel")
    await h.photo(); await h.photo()
    await h.click("nav:back")
    s = h.store.get(UID)
    assert s.index == 1 and set(s.photos) == {"antes"} and "Foto DEPOIS" in h.texts()[-1]
    await h.click("nav:restart")
    assert s.index == 0 and not s.photos
    await h.click("nav:back")                      # no primeiro passo, voltar = menu
    assert h.texts()[-1] == msg.WELCOME and h.store.get(UID) is None


async def test_cancel_clears_everything(h):
    await h.click("tpl:exemplo_servico"); await h.photo()
    await h.click("nav:cancel")
    assert h.texts()[-1] == msg.CANCELLED and h.store.get(UID) is None
    await h.text("/start"); await h.click("tpl:exemplo_servico"); await h.text("/cancelar")
    assert h.texts()[-1] == msg.CANCELLED


async def test_text_limits(h):
    await h.click("tpl:exemplo_servico"); await h.photo()
    await h.text("x" * 80)
    assert "grande demais" in h.texts()[-1] and h.store.get(UID).index == 1
    await h.text("/comando")
    assert "Não conheço" in h.texts()[-1]


async def test_text_that_does_not_fit_reopens_text_step(h):
    await h.click("tpl:exemplo_servico"); await h.photo()
    await h.text("W" * 40)                          # cabe em max_chars, mas não na largura
    assert "longo demais" in " ".join(h.texts())
    assert h.store.get(UID).current.id == "titulo" and h.count("SendPhoto") == 0
    await h.text("Corte")                           # corrige e conclui
    assert h.count("SendPhoto") == 1


async def test_price_template_asks_price(h):
    await h.click("tpl:exemplo_servico_preco"); await h.photo()
    await h.text("Escova blindada")
    assert "Preço" in h.texts()[-1]
    await h.text("R$ 70")
    assert h.count("SendPhoto") == 1


async def test_result_buttons(h):
    await h.click("tpl:exemplo_servico"); await h.photo(); await h.text("Corte")
    await h.click("res:fix")
    assert h.store.get(UID).current.id == "titulo"
    await h.text("Escova"); assert h.count("SendPhoto") == 2
    await h.click("res:again")
    assert h.store.get(UID).index == 0 and not h.store.get(UID).photos
    await h.photo(); await h.text("Outra"); await h.click("res:other")
    assert h.texts()[-1] == msg.WELCOME and h.store.get(UID) is None


async def test_duplicate_messages_do_not_generate_twice(h):
    await h.click("tpl:exemplo_servico"); await h.photo()
    h.busy.add(UID)
    await h.text("Corte")
    assert h.texts()[-1] == msg.BUSY and h.count("SendPhoto") == 0
    h.busy.discard(UID)


async def test_expired_session(registry):
    h = Harness(registry, ttl=0)
    await h.click("tpl:exemplo_servico")
    await h.photo()
    assert h.texts()[-1] == msg.EXPIRED


async def test_stale_buttons_and_stray_messages(h):
    await h.click("res:hq")
    assert "AnswerCallbackQuery" in h.kinds()
    await h.text("oi do nada")
    assert h.texts()[-1] == msg.USE_BUTTONS
    await h.click("tpl:nao_existe")
    assert h.kinds().count("AnswerCallbackQuery") >= 2


async def test_hidden_template_cannot_be_opened_directly(h):
    await h.click("tpl:exemplo_slide_antes")
    assert h.store.get(UID) is None


async def test_access_control(registry):
    h = Harness(registry, allowed=frozenset({999}))
    await h.text("/start")
    assert "uso restrito" in h.texts()[-1] and msg.WELCOME not in h.texts()
    await h.text("/meuid")
    assert h.texts()[-1] == f"Seu ID do Telegram é: {UID}"
    await h.click("tpl:exemplo_servico")
    assert h.store.get(UID) is None
    ok = Harness(registry, allowed=frozenset({UID}))
    await ok.text("/start")
    assert ok.texts()[0] == msg.WELCOME
