"""Regras do fluxo de criação (sem Telegram): passos, sessão e expiração. Fácil de testar."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class Step:
    kind: Literal["photo", "text"]
    id: str
    label: str
    required: bool = True
    max_chars: int | None = None


def steps_for(item) -> list[Step]:
    """Fotos primeiro, depois textos — vale para modelo simples e carrossel."""
    steps = [Step("photo", p.id, p.label) for p in item.photos]
    steps += [Step("text", t.id, t.label, t.required, t.max_chars) for t in item.texts]
    return steps


@dataclass
class Session:
    item_id: str
    steps: list[Step]
    index: int = 0
    photos: dict[str, bytes] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)
    results_png: list[bytes] = field(default_factory=list)
    touched: float = field(default_factory=time.monotonic)

    @property
    def current(self) -> Step | None:
        return self.steps[self.index] if self.index < len(self.steps) else None

    @property
    def done(self) -> bool:
        return self.index >= len(self.steps)

    @property
    def position(self) -> tuple[int, int]:
        return min(self.index + 1, len(self.steps)), len(self.steps)

    def _touch(self) -> None:
        self.touched = time.monotonic()

    def add_photo(self, data: bytes) -> None:
        step = self.current
        assert step and step.kind == "photo"
        self.photos[step.id] = data
        self.index += 1
        self._touch()

    def add_text(self, value: str) -> None:
        step = self.current
        assert step and step.kind == "text"
        self.texts[step.id] = value
        self.index += 1
        self._touch()

    def skip(self) -> bool:
        step = self.current
        if not step or step.required:
            return False
        self.index += 1
        self._touch()
        return True

    def back(self) -> bool:
        """Volta um passo mantendo o que já foi preenchido antes dele. False se já está no primeiro."""
        if self.index == 0:
            return False
        self.index -= 1
        prev = self.steps[self.index]
        (self.photos if prev.kind == "photo" else self.texts).pop(prev.id, None)
        self.results_png = []
        self._touch()
        return True

    def go_to(self, step_id: str) -> None:
        """Reabre um passo (ex.: texto longo demais), descartando-o e os seguintes."""
        for i, s in enumerate(self.steps):
            if s.id == step_id:
                while self.index > i:
                    self.back()
                self.index = i
                (self.photos if s.kind == "photo" else self.texts).pop(s.id, None)
                return

    def restart(self) -> None:
        self.index, self.photos, self.texts, self.results_png = 0, {}, {}, []
        self._touch()


class SessionStore:
    """Sessões em memória por usuário, com expiração. Nada de fotos de clientes vai para o disco."""

    def __init__(self, ttl_minutes: int = 60):
        self.ttl = ttl_minutes * 60
        self._data: dict[int, Session] = {}

    def start(self, user_id: int, item) -> Session:
        s = Session(item.id, steps_for(item))
        self._data[user_id] = s
        return s

    def get(self, user_id: int) -> Session | None:
        s = self._data.get(user_id)
        if s and time.monotonic() - s.touched > self.ttl:
            self._data.pop(user_id, None)
            return None
        return s

    def drop(self, user_id: int) -> None:
        self._data.pop(user_id, None)

    def sweep(self) -> int:
        now = time.monotonic()
        old = [u for u, s in self._data.items() if now - s.touched > self.ttl]
        for u in old:
            del self._data[u]
        return len(old)
