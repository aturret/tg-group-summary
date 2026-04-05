from unittest.mock import MagicMock, patch

from tg_summary_core.report.report_generate import (
    generate_llm_response,
    generate_llm_response_and_send_to_telegram,
    get_daily_group_chat,
    get_prompt,
    send_to_telegram,
)
from tg_summary_core.report.report_generate import test_get_daily_report_multimodal as _multimodal_fn


class TestGetDailyGroupChat:
    @patch("tg_summary_core.report.report_generate.AWSClient")
    def test_items_reversed(self, mock_aws_cls):
        mock_client = MagicMock()
        mock_aws_cls.return_value = mock_client
        mock_client.get_recent_group_messages_by_day.return_value = [
            {"messageId": 1},
            {"messageId": 2},
            {"messageId": 3},
        ]
        result = get_daily_group_chat()
        assert result == [{"messageId": 3}, {"messageId": 2}, {"messageId": 1}]

    @patch("tg_summary_core.report.report_generate.AWSClient")
    def test_empty(self, mock_aws_cls):
        mock_client = MagicMock()
        mock_aws_cls.return_value = mock_client
        mock_client.get_recent_group_messages_by_day.return_value = []
        result = get_daily_group_chat()
        assert result == []

    @patch("tg_summary_core.report.report_generate.AWSClient")
    def test_with_timestamp(self, mock_aws_cls):
        mock_client = MagicMock()
        mock_aws_cls.return_value = mock_client
        mock_client.get_recent_group_messages_by_day.return_value = []
        get_daily_group_chat(timestamp=1700000000)
        mock_client.get_recent_group_messages_by_day.assert_called_once_with(
            chat_id=12345,
            recent_day=1,
            full_replied_message=True,
            full_media_url=True,
            end_timestamp=1700000000,
        )


class TestGetPrompt:
    @patch("tg_summary_core.report.report_generate.generate_telegram_message_daily_summary_prompt")
    def test_calls_with_settings(self, mock_gen):
        mock_gen.return_value = "prompt text"
        result = get_prompt()
        mock_gen.assert_called_once_with("TestChat", "", "", analyze_media=True, end_timestamp=None)
        assert result == "prompt text"


class TestGenerateLlmResponse:
    @patch("tg_summary_core.report.report_generate.generate_gpt_response_by_gpt_parts")
    @patch("tg_summary_core.report.report_generate.generate_gpt_parts_by_group_messages")
    def test_gpt_routing(self, mock_parts, mock_response):
        mock_parts.return_value = [{"type": "input_text", "text": "data"}]
        mock_response.return_value = "<b>Summary</b>"
        result = generate_llm_response("prompt", [{"text": "msg"}], method="gpt")
        assert result == ["<b>Summary</b>"]
        mock_parts.assert_called_once()

    @patch("tg_summary_core.report.report_generate.generate_gemini_response")
    @patch("tg_summary_core.report.report_generate.fix_telegram_text")
    @patch("tg_summary_core.report.report_generate.generate_gemini_response_multiple_times")
    @patch("tg_summary_core.report.report_generate.generate_gemini_parts_by_group_messages")
    def test_gemini_routing(self, mock_parts, mock_multi, mock_fix, mock_gen_resp):
        mock_parts.return_value = ["part1"]
        mock_multi.return_value = ["raw response"]
        mock_fix.return_value = "fix prompt"
        mock_gen_resp.return_value = "<b>Fixed</b>"

        result = generate_llm_response("prompt", [{"text": "msg"}], method="gemini", num_calls=1)
        assert result == ["<b>Fixed</b>"]
        mock_fix.assert_called_once_with("raw response")


class TestSendToTelegram:
    @patch("tg_summary_core.report.report_generate.time.sleep")
    @patch("tg_summary_core.report.report_generate.requests.post")
    def test_success_first_try(self, mock_post, mock_sleep):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_post.return_value = mock_response

        send_to_telegram("<b>Summary</b>")
        assert mock_post.call_count == 1

    @patch("tg_summary_core.report.report_generate.generate_gemini_response")
    @patch("tg_summary_core.report.report_generate.fix_telegram_text")
    @patch("tg_summary_core.report.report_generate.time.sleep")
    @patch("tg_summary_core.report.report_generate.requests.post")
    def test_retry_on_failure(self, mock_post, mock_sleep, mock_fix, mock_gen):
        fail_resp = MagicMock()
        fail_resp.json.return_value = {"ok": False, "description": "bad format"}
        ok_resp = MagicMock()
        ok_resp.json.return_value = {"ok": True}
        mock_post.side_effect = [fail_resp, ok_resp]
        mock_fix.return_value = "fix prompt"
        mock_gen.return_value = "<b>Fixed</b>"

        send_to_telegram("<b>Bad</b>")
        assert mock_post.call_count == 2

    @patch("tg_summary_core.report.report_generate.time.sleep")
    @patch("tg_summary_core.report.report_generate.requests.post")
    def test_max_retries(self, mock_post, mock_sleep):
        fail_resp = MagicMock()
        fail_resp.json.return_value = {"ok": False}
        mock_post.return_value = fail_resp

        with (
            patch("tg_summary_core.report.report_generate.generate_gemini_response", return_value="fixed"),
            patch("tg_summary_core.report.report_generate.fix_telegram_text", return_value="fix"),
        ):
            send_to_telegram("<b>Always fails</b>")
        assert mock_post.call_count == 5

    @patch("tg_summary_core.report.report_generate.time.sleep")
    @patch("tg_summary_core.report.report_generate.requests.post")
    def test_exception_handling(self, mock_post, mock_sleep):
        mock_post.side_effect = [Exception("network"), MagicMock(json=MagicMock(return_value={"ok": True}))]
        send_to_telegram("<b>Test</b>")
        assert mock_post.call_count == 2


class TestGenerateLlmResponseAndSendToTelegram:
    @patch("tg_summary_core.report.report_generate.send_to_telegram")
    @patch("tg_summary_core.report.report_generate.generate_llm_response")
    def test_sends_each_response(self, mock_gen, mock_send):
        mock_gen.return_value = ["resp1", "resp2"]
        generate_llm_response_and_send_to_telegram("prompt", [{"text": "msg"}])
        assert mock_send.call_count == 2
        mock_send.assert_any_call("resp1", model=None)
        mock_send.assert_any_call("resp2", model=None)


class TestGetDailyReportMultimodal:
    @patch("tg_summary_core.report.report_generate.generate_llm_response_and_send_to_telegram")
    @patch("tg_summary_core.report.report_generate.get_prompt")
    @patch("tg_summary_core.report.report_generate.get_daily_group_chat")
    def test_normal_mode(self, mock_chat, mock_prompt, mock_send):
        mock_chat.return_value = [{"text": "msg"}]
        mock_prompt.return_value = "prompt"
        _multimodal_fn(method="gemini", model="test-model", num_calls=2)
        mock_send.assert_called_once_with("prompt", [{"text": "msg"}], "gemini", "test-model", num_calls=2)

    @patch("tg_summary_core.report.report_generate.generate_llm_response_and_send_to_telegram")
    @patch("tg_summary_core.report.report_generate.get_prompt")
    @patch("tg_summary_core.report.report_generate.get_daily_group_chat")
    def test_test_mode(self, mock_chat, mock_prompt, mock_send):
        mock_chat.return_value = [{"text": "msg"}]
        mock_prompt.return_value = "prompt"
        _multimodal_fn(test_mode=True)
        # Should call for each model in test_list (2 models)
        assert mock_send.call_count == 2
