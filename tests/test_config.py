import pytest

from app.config import EXAMPLES_DIR, SettingsError, load_settings, resolve_templates_dir

TOKEN = "123456:ABC-test"


def test_valid_settings_and_id_parsing():
    s = load_settings({"TELEGRAM_BOT_TOKEN": TOKEN, "ALLOWED_USER_IDS": "111, 222"})
    assert s.allowed_user_ids == {111, 222} and s.session_ttl_minutes == 60


def test_missing_or_bad_token_and_ids_are_clear_errors():
    with pytest.raises(SettingsError, match="TELEGRAM_BOT_TOKEN"):
        load_settings({})
    with pytest.raises(SettingsError, match="ALLOWED_USER_IDS"):
        load_settings({"TELEGRAM_BOT_TOKEN": TOKEN, "ALLOWED_USER_IDS": "abc"})


def test_token_never_appears_in_repr():
    assert TOKEN not in repr(load_settings({"TELEGRAM_BOT_TOKEN": TOKEN}))


def test_falls_back_to_examples_when_templates_dir_is_empty(tmp_path):
    assert resolve_templates_dir(tmp_path / "nao_existe") == EXAMPLES_DIR
    assert resolve_templates_dir(tmp_path) == EXAMPLES_DIR
    assert resolve_templates_dir(EXAMPLES_DIR) == EXAMPLES_DIR
