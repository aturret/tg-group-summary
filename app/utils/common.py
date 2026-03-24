import logging
import json
import os

import pathlib

import requests


def get_logger(name: str):
    _logger = logging.getLogger(name)
    return _logger


def save_json_to_file(data: list[dict], filename: str) -> None:
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_json_from_file(filename: str) -> list[dict]:
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_html_to_file(html_text: str, filename: str) -> None:
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_text)


def download_file(url: str, dest_path: str):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded: {url} to {dest_path}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return False


def clean_files(file_path_list: list):
    for file_path in file_path_list:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError as e:
            print(f"Error deleting {file_path}: {e}")
            return
