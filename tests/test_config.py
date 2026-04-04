import pytest

from tg_summary_core.config import Settings


class TestSettings:
    def test_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "my-token")
        monkeypatch.setenv("SUMMARY_CHAT_ID", "999")
        monkeypatch.setenv("SUMMARY_CHAT_NAME", "MyChat")
        monkeypatch.setenv("TARGET_CHAT_ID", "111")
        s = Settings()
        assert s.telegram_bot_token == "my-token"
        assert s.summary_chat_id == 999
        assert s.summary_chat_name == "MyChat"
        assert s.target_chat_id == "111"

    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PROMPT_YAML_PATH", raising=False)
        s = Settings()
        assert s.openai_gpt_model == "gpt-5"
        assert s.region_name == "us-east-1"
        assert s.s3_bucket_name == "tg-searcher-prod"
        assert s.dynamo_table_name == "tg-searcher-prod"
        assert s.summary_model == "gemini-3-flash-preview"
        assert s.prompt_yaml_path == "conf/prompt.yaml"

    def test_optional_api_keys_default_none(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        s = Settings()
        assert s.google_api_key is None
        assert s.openai_api_key is None

    def test_target_chat_id_full_prepends_100(self, monkeypatch):
        monkeypatch.setenv("TARGET_CHAT_ID", "67890")
        s = Settings()
        assert s.target_chat_id_full == "-10067890"

    def test_target_chat_id_full_already_prefixed(self, monkeypatch):
        monkeypatch.setenv("TARGET_CHAT_ID", "-10067890")
        s = Settings()
        assert s.target_chat_id_full == "-10067890"

    def test_extra_fields_ignored(self, monkeypatch):
        monkeypatch.setenv("SOME_RANDOM_EXTRA_FIELD", "should_not_fail")
        s = Settings()
        assert not hasattr(s, "some_random_extra_field")
