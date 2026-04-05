from unittest.mock import MagicMock, patch

import pytest
from google.genai import types

from tg_summary_core.report.gemini import (
    _get_client,
    count_token_and_remove,
    generate_gemini_parts_by_group_messages,
    generate_gemini_response,
    generate_gemini_response_by_gemini_parts,
    generate_gemini_response_multiple_seeds,
    generate_gemini_response_multiple_times,
    resolve_message_media,
    upload_video_to_gemini,
    wait_until_all_parts_active,
)


class TestGetClient:
    @patch("tg_summary_core.report.gemini.genai.Client")
    def test_singleton(self, mock_client_cls):
        client1 = _get_client()
        client2 = _get_client()
        assert client1 is client2
        mock_client_cls.assert_called_once()

    @patch("tg_summary_core.report.gemini.genai.Client")
    def test_uses_api_key(self, mock_client_cls):
        _get_client()
        mock_client_cls.assert_called_once_with(api_key="fake-google-key")


class TestResolveMessageMedia:
    @patch("tg_summary_core.report.gemini.Image.open")
    @patch("tg_summary_core.report.gemini.download_file", return_value=True)
    def test_photo(self, mock_download, mock_open):
        mock_image = MagicMock()
        mock_open.return_value = mock_image
        media = {"mediaType": "photo", "presignedUrl": "https://s3.example.com/path/photo.jpg"}
        result = resolve_message_media(media)
        assert result is mock_image
        mock_download.assert_called_once()

    @patch("tg_summary_core.report.gemini.upload_video_to_gemini")
    @patch("tg_summary_core.report.gemini.download_file", return_value=True)
    def test_video(self, mock_download, mock_upload):
        mock_file = MagicMock(spec=types.File)
        mock_upload.return_value = mock_file
        media = {"mediaType": "video", "presignedUrl": "https://s3.example.com/path/video.mp4"}
        result = resolve_message_media(media)
        assert result is mock_file

    @patch("tg_summary_core.report.gemini.download_file", return_value=False)
    def test_download_failure(self, mock_download):
        media = {"mediaType": "photo", "presignedUrl": "https://s3.example.com/path/photo.jpg"}
        result = resolve_message_media(media)
        assert result is None


class TestWaitUntilAllPartsActive:
    def test_no_files(self):
        # Only strings in the list, no types.File objects
        wait_until_all_parts_active(["text part", "another text"])

    @patch("tg_summary_core.report.gemini._get_client")
    def test_immediate_active(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_file = MagicMock(spec=types.File)
        mock_file.name = "file1"

        file_status = MagicMock()
        file_status.state = types.FileState.ACTIVE
        file_status.display_name = "file1"
        file_status.name = "file1"
        mock_client.files.get.return_value = file_status

        wait_until_all_parts_active([mock_file])

    @patch("tg_summary_core.report.gemini.time.sleep")
    @patch("tg_summary_core.report.gemini.time.time")
    @patch("tg_summary_core.report.gemini._get_client")
    def test_polling_then_active(self, mock_get_client, mock_time, mock_sleep):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_file = MagicMock(spec=types.File)
        mock_file.name = "file1"

        processing = MagicMock()
        processing.state = types.FileState.PROCESSING
        processing.display_name = "file1"
        processing.name = "file1"

        active = MagicMock()
        active.state = types.FileState.ACTIVE
        active.display_name = "file1"
        active.name = "file1"

        mock_client.files.get.side_effect = [processing, active]
        mock_time.side_effect = [0, 5, 10]  # start_time, first check, second check

        wait_until_all_parts_active([mock_file], timeout_seconds=600, poll_interval_seconds=1)
        mock_sleep.assert_called_once_with(1)

    @patch("tg_summary_core.report.gemini.time.sleep")
    @patch("tg_summary_core.report.gemini.time.time")
    @patch("tg_summary_core.report.gemini._get_client")
    def test_timeout(self, mock_get_client, mock_time, mock_sleep):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_file = MagicMock(spec=types.File)
        mock_file.name = "file1"

        processing = MagicMock()
        processing.state = types.FileState.PROCESSING
        processing.display_name = "file1"
        processing.name = "file1"

        mock_client.files.get.return_value = processing
        mock_time.side_effect = [0, 601]  # start_time, then past timeout

        with pytest.raises(TimeoutError):
            wait_until_all_parts_active([mock_file], timeout_seconds=600)

    @patch("tg_summary_core.report.gemini._get_client")
    def test_failed_file(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_file = MagicMock(spec=types.File)
        mock_file.name = "file1"

        failed = MagicMock()
        failed.state = types.FileState.FAILED
        failed.display_name = "file1"
        failed.name = "file1"
        mock_client.files.get.return_value = failed

        with pytest.raises(Exception, match="failed to process"):
            wait_until_all_parts_active([mock_file])


class TestCountTokenAndRemove:
    @patch("tg_summary_core.report.gemini._get_client")
    def test_under_threshold(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        count_resp = MagicMock()
        count_resp.total_tokens = 1000
        mock_client.models.count_tokens.return_value = count_resp

        result = count_token_and_remove(["part1", "part2"], "model")
        assert result == ["part1", "part2"]

    @patch("tg_summary_core.report.gemini._get_client")
    def test_over_threshold(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        count_under = MagicMock()
        count_under.total_tokens = 1000
        count_over = MagicMock()
        count_over.total_tokens = 300000
        mock_client.models.count_tokens.side_effect = [count_under, count_over]

        result = count_token_and_remove(["keep", "remove"], "model")
        assert result == ["keep"]

    @patch("tg_summary_core.report.gemini._get_client")
    def test_error_keeps_item(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.models.count_tokens.side_effect = Exception("API error")

        result = count_token_and_remove(["part1"], "model")
        assert result == ["part1"]

    @patch("tg_summary_core.report.gemini._get_client")
    def test_empty_content_skipped(self, mock_get_client):
        result = count_token_and_remove(["valid", "", None], "model")
        # Only "valid" should be processed; empty/None skipped
        assert "valid" in result


class TestGenerateGeminiResponse:
    @patch("tg_summary_core.report.gemini._get_client")
    def test_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = "Generated summary"
        mock_client.models.generate_content.return_value = mock_response

        result = generate_gemini_response("test prompt")
        assert result == "Generated summary"

    @patch("tg_summary_core.report.gemini._get_client")
    def test_empty_response(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.text = ""
        mock_candidate = MagicMock()
        mock_candidate.finish_reason = "SAFETY"
        mock_response.candidates = [mock_candidate]
        mock_client.models.generate_content.return_value = mock_response

        result = generate_gemini_response("test prompt")
        assert "blocked" in result or "SAFETY" in result

    @patch("tg_summary_core.report.gemini._get_client")
    def test_exception(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("API down")

        result = generate_gemini_response("test prompt")
        assert "error" in result.lower()


class TestGenerateGeminiResponseByParts:
    @patch("tg_summary_core.report.gemini.count_token_and_remove")
    @patch("tg_summary_core.report.gemini._get_client")
    def test_success(self, mock_get_client, mock_count):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_count.return_value = ["part1"]
        mock_response = MagicMock()
        mock_response.text = "Response text"
        mock_client.models.generate_content.return_value = mock_response

        result = generate_gemini_response_by_gemini_parts(["part1"], model="test-model")
        assert result == "Response text"

    @patch("tg_summary_core.report.gemini.count_token_and_remove")
    @patch("tg_summary_core.report.gemini._get_client")
    def test_exception(self, mock_get_client, mock_count):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_count.return_value = ["part1"]
        mock_client.models.generate_content.side_effect = Exception("fail")

        result = generate_gemini_response_by_gemini_parts(["part1"])
        assert "Error" in result


class TestMultipleTimes:
    @patch("tg_summary_core.report.gemini.generate_gemini_response_by_gemini_parts")
    def test_correct_seed_count(self, mock_gen):
        mock_gen.return_value = "response"
        results = generate_gemini_response_multiple_times(["parts"], num_calls=3)
        assert len(results) == 3
        assert mock_gen.call_count == 3

    @patch("tg_summary_core.report.gemini.generate_gemini_response_by_gemini_parts")
    def test_seeds_default(self, mock_gen):
        mock_gen.return_value = "r"
        generate_gemini_response_multiple_times(["parts"], num_calls=3)
        # The seeds should be passed via generate_gemini_response_multiple_seeds
        assert mock_gen.call_count == 3

    @patch("tg_summary_core.report.gemini.generate_gemini_response_by_gemini_parts")
    def test_base_seed(self, mock_gen):
        mock_gen.return_value = "r"
        generate_gemini_response_multiple_times(["parts"], num_calls=2, base_seed=10)
        assert mock_gen.call_count == 2


class TestMultipleSeeds:
    @patch("tg_summary_core.report.gemini.generate_gemini_response_by_gemini_parts")
    def test_generates_per_seed(self, mock_gen):
        mock_gen.return_value = "resp"
        results = generate_gemini_response_multiple_seeds(["parts"], seeds=[1, 2, 3])
        assert len(results) == 3

    @patch("tg_summary_core.report.gemini.generate_gemini_response_by_gemini_parts")
    def test_error_handling(self, mock_gen):
        mock_gen.side_effect = Exception("fail")
        results = generate_gemini_response_multiple_seeds(["parts"], seeds=[1])
        assert len(results) == 1
        assert "Error" in results[0]


class TestUploadVideoToGemini:
    @patch("tg_summary_core.report.gemini._get_client")
    def test_success(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_file = MagicMock()
        mock_file.display_name = "video.mp4"
        mock_file.name = "files/123"
        mock_client.files.upload.return_value = mock_file

        result = upload_video_to_gemini("/path/to/video.mp4")
        assert result is mock_file

    @patch("tg_summary_core.report.gemini._get_client")
    def test_failure(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.files.upload.side_effect = Exception("upload failed")

        result = upload_video_to_gemini("/path/to/video.mp4")
        assert result is None


class TestGenerateGeminiPartsByGroupMessages:
    @patch("tg_summary_core.report.gemini.clean_files")
    @patch("tg_summary_core.report.gemini.wait_until_all_parts_active")
    @patch("tg_summary_core.report.gemini.resolve_message_media")
    @patch("tg_summary_core.report.gemini.convert_item_to_json_text")
    def test_text_only(self, mock_convert, mock_resolve, mock_wait, mock_clean):
        mock_convert.return_value = '{"text": "hello"}'
        messages = [{"text": "hello"}]
        result = generate_gemini_parts_by_group_messages(messages)
        assert len(result) == 1
        assert result[0] == '{"text": "hello"}'

    @patch("tg_summary_core.report.gemini.clean_files")
    @patch("tg_summary_core.report.gemini.wait_until_all_parts_active")
    @patch("tg_summary_core.report.gemini.resolve_message_media")
    @patch("tg_summary_core.report.gemini.convert_item_to_json_text")
    def test_with_media(self, mock_convert, mock_resolve, mock_wait, mock_clean):
        mock_convert.return_value = '{"text": "hello"}'
        mock_image = MagicMock()
        mock_resolve.return_value = mock_image
        messages = [{"text": "hello", "media": {"mediaType": "photo", "presignedUrl": "url"}}]
        result = generate_gemini_parts_by_group_messages(messages)
        assert len(result) == 2  # text + image
