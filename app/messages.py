"""Textos do bot (um lugar só, fácil de ajustar o tom)."""
WELCOME = "Olá! Bem-vinda ao Criador de Artes do Toque da Fé. Escolha o tipo de arte que deseja criar."
NO_TEMPLATES = "Ainda não há modelos de arte disponíveis."
PREPARING = "Preparando sua arte… ✨"
CANCELLED = "Tudo bem, cancelei. Quando quiser criar uma arte, é só enviar /start."
EXPIRED = "Essa conversa expirou. Envie /start para começar de novo."
USE_BUTTONS = "Use os botões abaixo ou envie /start para criar outra arte."
BUSY = "Ainda estou preparando sua arte, só um instante. ✨"
RESTRICTED = "Este bot é de uso restrito. Peça para liberarem o seu acesso (seu ID: {uid})."
STALE_BUTTON = "Esse botão não está mais disponível. Envie /start para recomeçar."
DOWNLOAD_FAILED = "Não consegui baixar essa foto. Tente enviar de novo."
GENERIC_ERROR = "Ops, algo deu errado ao montar a arte. Tente novamente em instantes."
RESULT_READY = "Sua arte está pronta! 💗"
SENDING_FILES = "Enviando em alta qualidade…"


def ask_photo(label: str, n: int, total: int) -> str:
    return f"📸 Passo {n} de {total}: envie a foto — {label}."


def ask_text(label: str, n: int, total: int, optional: bool) -> str:
    return f"✍️ Passo {n} de {total}: {label}" + ("\n(opcional — você pode pular)" if optional else "")


def expected_photo(label: str) -> str:
    return f"Preciso de uma foto aqui: {label}. Envie a imagem (pode ser como arquivo também)."


def expected_text(label: str) -> str:
    return f"Agora preciso de um texto: {label}."


def text_too_long(limit: int) -> str:
    return f"Esse texto está grande demais (máximo de {limit} caracteres). Pode encurtar?"
