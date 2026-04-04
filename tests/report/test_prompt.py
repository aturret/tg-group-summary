import pytest
from freezegun import freeze_time

from tg_summary_core.report.prompt import (
    get_beijing_date_str,
    _load_prompt_config,
    generate_telegram_message_daily_summary_prompt,
    fix_telegram_text,
    DEFAULT_MEDIA_INSTRUCTION_ANALYZE,
    DEFAULT_MEDIA_INSTRUCTION_REFERENCE,
)
import tg_summary_core.report.prompt as prompt_mod


class TestGetBeijingDateStr:
    @freeze_time("2026-01-15 02:00:00")  # UTC; Beijing = 10:00
    def test_today(self):
        result = get_beijing_date_str(day_change=0)
        assert result == "2026年1月15日"

    @freeze_time("2026-01-15 02:00:00")
    def test_day_change(self):
        result = get_beijing_date_str(day_change=1)
        assert result == "2026年1月14日"

    def test_from_timestamp(self):
        # 1700000000 = 2023-11-14 22:13:20 UTC = 2023-11-15 06:13:20 Beijing
        # But the code subtracts 86400 first, so: 2023-11-14 06:13:20 Beijing
        result = get_beijing_date_str(from_timestamp=1700000000)
        assert result == "2023年11月14日"

    def test_from_timestamp_another(self):
        # 1700100000 - 86400 = 1700013600
        # 1700013600 = 2023-11-15 02:00:00 UTC = 2023-11-15 10:00:00 Beijing
        result = get_beijing_date_str(from_timestamp=1700100000)
        assert result == "2023年11月15日"


class TestLoadPromptConfig:
    def test_file_exists(self, tmp_path, monkeypatch):
        yaml_file = tmp_path / "prompt.yaml"
        yaml_file.write_text("declaration: test\nadditional_prompt: extra\n", encoding="utf-8")
        monkeypatch.setattr(prompt_mod.settings, "prompt_yaml_path", str(yaml_file))
        result = _load_prompt_config()
        assert result == {"declaration": "test", "additional_prompt": "extra"}

    def test_file_missing(self):
        # Default conftest sets path to /nonexistent/prompt.yaml
        result = _load_prompt_config()
        assert result is None

    def test_invalid_yaml_list(self, tmp_path, monkeypatch):
        yaml_file = tmp_path / "prompt.yaml"
        yaml_file.write_text("- item1\n- item2\n", encoding="utf-8")
        monkeypatch.setattr(prompt_mod.settings, "prompt_yaml_path", str(yaml_file))
        result = _load_prompt_config()
        assert result is None


class TestGenerateSummaryPrompt:
    def test_default_contains_chat_name(self):
        result = generate_telegram_message_daily_summary_prompt("MyGroup")
        assert "MyGroup" in result

    def test_default_contains_declaration(self):
        result = generate_telegram_message_daily_summary_prompt("G", declaration="footer text")
        assert "footer text" in result

    def test_default_contains_additional_prompt(self):
        result = generate_telegram_message_daily_summary_prompt("G", additional_prompt="extra instructions")
        assert "extra instructions" in result

    def test_media_instruction_analyze(self):
        result = generate_telegram_message_daily_summary_prompt("G", analyze_media=True)
        assert DEFAULT_MEDIA_INSTRUCTION_ANALYZE in result

    def test_media_instruction_reference(self):
        result = generate_telegram_message_daily_summary_prompt("G", analyze_media=False)
        assert DEFAULT_MEDIA_INSTRUCTION_REFERENCE in result

    def test_yaml_template_override(self, tmp_path, monkeypatch):
        yaml_file = tmp_path / "prompt.yaml"
        yaml_file.write_text(
            'prompt_template: "Custom: {chat_name} {date} {declaration} {additional_prompt} {media_instruction}"\n',
            encoding="utf-8",
        )
        monkeypatch.setattr(prompt_mod.settings, "prompt_yaml_path", str(yaml_file))
        result = generate_telegram_message_daily_summary_prompt("TestGroup", declaration="decl", additional_prompt="add")
        assert result.startswith("Custom: TestGroup")
        assert "decl" in result
        assert "add" in result

    def test_yaml_media_dict(self, tmp_path, monkeypatch):
        yaml_file = tmp_path / "prompt.yaml"
        yaml_file.write_text(
            "media_instruction:\n  analyze: Custom analyze\n  reference_only: Custom ref\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(prompt_mod.settings, "prompt_yaml_path", str(yaml_file))
        result = generate_telegram_message_daily_summary_prompt("G", analyze_media=True)
        assert "Custom analyze" in result

    def test_contains_date(self):
        result = generate_telegram_message_daily_summary_prompt("G")
        assert "年" in result and "月" in result and "日" in result


class TestFixTelegramText:
    def test_contains_original_text(self):
        result = fix_telegram_text("<b>Hello</b>")
        assert "<b>Hello</b>" in result

    def test_contains_instruction(self):
        result = fix_telegram_text("test")
        assert "Telegram" in result
        assert "HTML" in result
