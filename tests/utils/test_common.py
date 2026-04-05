import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

from tg_summary_core.utils.common import (
    clean_files,
    download_file,
    get_logger,
    load_json_from_file,
    save_html_to_file,
    save_json_to_file,
)


class TestGetLogger:
    def test_returns_logger(self):
        logger = get_logger("test_name")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_name"


class TestJsonFileIO:
    def test_round_trip(self, tmp_path):
        data = [{"key": "value", "num": 42}]
        filepath = str(tmp_path / "test.json")
        save_json_to_file(data, filepath)
        loaded = load_json_from_file(filepath)
        assert loaded == data

    def test_unicode(self, tmp_path):
        data = [{"text": "你好世界"}]
        filepath = str(tmp_path / "unicode.json")
        save_json_to_file(data, filepath)
        # Verify the file contains actual unicode, not escaped
        raw = (tmp_path / "unicode.json").read_text(encoding="utf-8")
        assert "你好世界" in raw
        loaded = load_json_from_file(filepath)
        assert loaded[0]["text"] == "你好世界"

    def test_load_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_json_from_file("/nonexistent/file.json")


class TestSaveHtmlToFile:
    def test_write_and_read(self, tmp_path):
        html = "<h1>Hello</h1><p>World</p>"
        filepath = str(tmp_path / "test.html")
        save_html_to_file(html, filepath)
        content = (tmp_path / "test.html").read_text(encoding="utf-8")
        assert content == html


class TestDownloadFile:
    @patch("tg_summary_core.utils.common.requests.get")
    def test_success(self, mock_get, tmp_path):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
        mock_get.return_value = mock_response

        dest = str(tmp_path / "downloaded.bin")
        result = download_file("https://example.com/file", dest)
        assert result is True
        assert (tmp_path / "downloaded.bin").read_bytes() == b"chunk1chunk2"

    @patch("tg_summary_core.utils.common.requests.get")
    def test_http_error(self, mock_get, tmp_path):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404")
        mock_get.return_value = mock_response

        dest = str(tmp_path / "fail.bin")
        result = download_file("https://example.com/missing", dest)
        assert result is False

    @patch("tg_summary_core.utils.common.requests.get")
    def test_connection_error(self, mock_get, tmp_path):
        mock_get.side_effect = requests.exceptions.ConnectionError("refused")
        dest = str(tmp_path / "fail.bin")
        result = download_file("https://example.com/down", dest)
        assert result is False


class TestCleanFiles:
    def test_removes_existing_files(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("a")
        f2.write_text("b")
        clean_files([str(f1), str(f2)])
        assert not f1.exists()
        assert not f2.exists()

    def test_nonexistent_files_no_crash(self, tmp_path):
        clean_files([str(tmp_path / "nope.txt")])
