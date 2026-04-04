import base64
import os
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

from tg_summary_core.report.gpt import (
    _get_client,
    _to_data_url,
    _ensure_valid_image,
    generate_gpt_parts_by_group_messages,
    resolve_message_media,
    generate_gpt_response_by_gpt_parts,
)


class TestGetClient:
    @patch("tg_summary_core.report.gpt.OpenAI")
    def test_singleton(self, mock_openai_cls):
        client1 = _get_client()
        client2 = _get_client()
        assert client1 is client2
        mock_openai_cls.assert_called_once()

    @patch("tg_summary_core.report.gpt.OpenAI")
    def test_uses_api_key(self, mock_openai_cls):
        _get_client()
        mock_openai_cls.assert_called_once_with(api_key="fake-openai-key")


class TestToDataUrl:
    def test_png(self, tmp_path):
        # Create a minimal 1x1 PNG
        img_path = str(tmp_path / "test.png")
        img = Image.new("RGB", (1, 1), color="red")
        img.save(img_path, format="PNG")

        result = _to_data_url(img_path)
        assert result.startswith("data:image/png;base64,")
        # Verify base64 is valid
        b64_part = result.split(",", 1)[1]
        decoded = base64.b64decode(b64_part)
        assert len(decoded) > 0

    def test_jpeg_mime(self, tmp_path):
        img_path = str(tmp_path / "test.jpg")
        img = Image.new("RGB", (1, 1), color="blue")
        img.save(img_path, format="JPEG")

        result = _to_data_url(img_path)
        assert result.startswith("data:image/jpeg;base64,")


class TestEnsureValidImage:
    def test_valid_image(self, tmp_path):
        img_path = str(tmp_path / "valid.png")
        img = Image.new("RGB", (1, 1))
        img.save(img_path)
        _ensure_valid_image(img_path)  # Should not raise

    def test_invalid_image(self, tmp_path):
        bad_path = str(tmp_path / "bad.png")
        with open(bad_path, "wb") as f:
            f.write(b"not an image at all")
        with pytest.raises(Exception):
            _ensure_valid_image(bad_path)


class TestResolveMessageMedia:
    def test_image_url_passthrough(self):
        media = {"mediaType": "image_url", "presignedUrl": "https://example.com/img.jpg"}
        result = resolve_message_media(media)
        assert result == {"type": "input_image", "image_url": "https://example.com/img.jpg"}

    @patch("tg_summary_core.report.gpt._to_data_url", return_value="data:image/png;base64,abc")
    @patch("tg_summary_core.report.gpt._ensure_valid_image")
    @patch("tg_summary_core.report.gpt.download_file", return_value=True)
    def test_photo_download(self, mock_download, mock_valid, mock_data_url):
        media = {"mediaType": "photo", "presignedUrl": "https://s3.example.com/path/photo.jpg"}
        result = resolve_message_media(media)
        assert result["type"] == "input_image"
        assert result["image_url"] == "data:image/png;base64,abc"

    @patch("tg_summary_core.report.gpt.download_file", return_value=False)
    def test_download_failure(self, mock_download):
        media = {"mediaType": "photo", "presignedUrl": "https://s3.example.com/path/photo.jpg"}
        result = resolve_message_media(media)
        assert result is None


class TestGenerateGptPartsByGroupMessages:
    @patch("tg_summary_core.report.gpt.clean_files")
    @patch("tg_summary_core.report.gpt.resolve_message_media")
    @patch("tg_summary_core.report.gpt.convert_item_to_json_text")
    def test_text_only(self, mock_convert, mock_resolve, mock_clean):
        mock_convert.return_value = '{"text": "hello"}'
        messages = [{"text": "hello"}]
        result = generate_gpt_parts_by_group_messages(messages)
        assert len(result) == 1
        assert result[0] == {"type": "input_text", "text": '{"text": "hello"}'}

    @patch("tg_summary_core.report.gpt.clean_files")
    @patch("tg_summary_core.report.gpt.resolve_message_media")
    @patch("tg_summary_core.report.gpt.convert_item_to_json_text")
    def test_with_media(self, mock_convert, mock_resolve, mock_clean):
        mock_convert.return_value = '{"text": "hello"}'
        mock_resolve.return_value = {"type": "input_image", "image_url": "data:..."}
        messages = [{"text": "hello", "media": {"mediaType": "photo", "presignedUrl": "url"}}]
        result = generate_gpt_parts_by_group_messages(messages)
        assert len(result) == 2
        assert result[1]["type"] == "input_image"


class TestGenerateGptResponseByGptParts:
    @patch("tg_summary_core.report.gpt._get_client")
    def test_text_parts(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_text = "Summary result"
        mock_client.responses.create.return_value = mock_response

        parts = [{"type": "input_text", "text": "hello"}]
        result = generate_gpt_response_by_gpt_parts(parts, "Summarize this")
        assert result == "Summary result"

    @patch("tg_summary_core.report.gpt._get_client")
    def test_image_parts(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_text = "Image analysis"
        mock_client.responses.create.return_value = mock_response

        parts = [{"type": "input_image", "image_url": "data:image/png;base64,abc"}]
        result = generate_gpt_response_by_gpt_parts(parts, "Analyze")
        assert result == "Image analysis"
        # Verify the content passed to API
        call_args = mock_client.responses.create.call_args
        content = call_args[1]["input"][0]["content"]
        assert any(c["type"] == "input_image" for c in content)

    @patch("tg_summary_core.report.gpt._get_client")
    def test_legacy_image_base64(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_text = "result"
        mock_client.responses.create.return_value = mock_response

        parts = [{"type": "image_base64", "image_data": "abc123"}]
        result = generate_gpt_response_by_gpt_parts(parts, "test")
        call_args = mock_client.responses.create.call_args
        content = call_args[1]["input"][0]["content"]
        image_parts = [c for c in content if c["type"] == "input_image"]
        assert len(image_parts) == 1
        assert "data:image/png;base64,abc123" in image_parts[0]["image_url"]

    @patch("tg_summary_core.report.gpt._get_client")
    def test_empty_parts(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_text = "empty"
        mock_client.responses.create.return_value = mock_response

        result = generate_gpt_response_by_gpt_parts([], "prompt")
        assert result == "empty"
        # Should have at least the prompt as input_text
        call_args = mock_client.responses.create.call_args
        content = call_args[1]["input"][0]["content"]
        assert any(c.get("text") == "prompt" for c in content)

    @patch("tg_summary_core.report.gpt._get_client")
    def test_legacy_text_type(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_text = "ok"
        mock_client.responses.create.return_value = mock_response

        parts = [{"type": "text", "text": "hello"}]
        result = generate_gpt_response_by_gpt_parts(parts, "")
        call_args = mock_client.responses.create.call_args
        content = call_args[1]["input"][0]["content"]
        text_parts = [c for c in content if c["type"] == "input_text"]
        assert any(c["text"] == "hello" for c in text_parts)
