from aiogram.fsm.state import State, StatesGroup


class Flow(StatesGroup):
    collecting = State()  # recebendo fotos e textos
    finished = State()  # arte entregue; aguardando botões
