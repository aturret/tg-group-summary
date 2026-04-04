import pytest


@pytest.fixture(autouse=True)
def _clean_settings(monkeypatch):
    """Set minimal env vars so Settings() never fails, then reload the singleton.

    Because each module does `from tg_summary_core.config import settings`,
    we must patch the `settings` attribute in every module that imports it.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token-123")
    monkeypatch.setenv("SUMMARY_CHAT_ID", "12345")
    monkeypatch.setenv("SUMMARY_CHAT_NAME", "TestChat")
    monkeypatch.setenv("TARGET_CHAT_ID", "67890")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-google-key")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
    # Point prompt yaml to nonexistent path so tests don't read real config
    monkeypatch.setenv("PROMPT_YAML_PATH", "/nonexistent/prompt.yaml")

    import tg_summary_core.config as config_mod
    new_settings = config_mod.Settings()
    config_mod.settings = new_settings

    # Patch settings in every module that does `from tg_summary_core.config import settings`
    import tg_summary_core.report.gemini as gemini_mod
    import tg_summary_core.report.gpt as gpt_mod
    import tg_summary_core.report.prompt as prompt_mod
    import tg_summary_core.report.report_generate as report_mod
    import tg_summary_core.utils.aws as aws_mod

    monkeypatch.setattr(gemini_mod, "settings", new_settings)
    monkeypatch.setattr(gpt_mod, "settings", new_settings)
    monkeypatch.setattr(prompt_mod, "settings", new_settings)
    monkeypatch.setattr(report_mod, "settings", new_settings)
    monkeypatch.setattr(aws_mod, "settings", new_settings)
    yield


@pytest.fixture
def sample_messages():
    """Standard set of DynamoDB-shaped messages for reuse across test files."""
    return [
        {
            "chatId": 12345,
            "messageId": 1,
            "timestamp": 1700000000,
            "user": "Alice",
            "text": "Hello world",
        },
        {
            "chatId": 12345,
            "messageId": 2,
            "timestamp": 1700000060,
            "user": "Bob",
            "text": "Reply here",
            "replyTo": 1,
            "media": {
                "mediaType": "photo",
                "mediaKey": "bucket/path/photo.jpg",
                "presignedUrl": "https://s3.example.com/photo.jpg",
            },
        },
    ]
