# -*- coding: utf-8 -*-
import os
import base64
import mimetypes
from typing import Union, List, Dict, Any
from urllib.parse import urlparse, unquote
from pathlib import Path

from PIL import Image

from openai import OpenAI
from tg_summary_core.config import settings
from tg_summary_core.report.text_cat import convert_item_to_json_text
from tg_summary_core.utils.common import download_file, clean_files

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client

current_directory = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DOWNLOAD_DIR = os.path.join(current_directory, "..", "..", "download")
os.makedirs(DEFAULT_DOWNLOAD_DIR, exist_ok=True)

# 收尾清理
_remove_file_path_list: List[str] = []


# ---------- 工具函数 ----------
def _to_data_url(file_path: str) -> str:
    """把本地图片转为 data URL（base64）以满足 Responses API 的 input_image 规范。"""
    mime = mimetypes.guess_type(file_path)[0] or "image/png"
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _ensure_valid_image(file_path: str) -> None:
    """用 PIL 验证图片能打开；打不开会抛异常。"""
    with Image.open(file_path) as im:
        im.verify()


# ---------- 你的对外函数 ----------
def generate_gpt_parts_by_group_messages(group_messages: List[dict]) -> List[dict]:
    """
    把 DynamoDB 聊天记录转换为 Responses API 可识别的多模态 parts 列表。
    - 文本段: {"type":"input_text","text": "..."}
    - 图片段: {"type":"input_image","image_url": "http(s)://... 或 data:..."}
    """
    gpt_parts: List[dict] = []

    for message in group_messages:
        # 文本部分（老数据若产出 "type": "text"，这里一并映射为 input_text）
        message_json_text = convert_item_to_json_text(message)
        gpt_parts.append({"type": "input_text", "text": message_json_text})

        # 媒体部分
        media = message.get("media")
        if media:
            valid_media = resolve_message_media(media)
            if valid_media:
                gpt_parts.append(valid_media)

    # 清理临时下载
    if _remove_file_path_list:
        clean_files(_remove_file_path_list)
        _remove_file_path_list.clear()

    return gpt_parts


def resolve_message_media(media: dict) -> Union[dict, None]:
    """
    下载媒体并转为 Responses API 的 input_image 段。
    支持：
      - {"mediaType": "photo", "presignedUrl": "..."}  # 远端图，先下本地再转 data URL
      - {"mediaType": "image_url", "presignedUrl": "..."}  # 直接用 URL
    """
    result: Union[dict, None] = None

    # 统一从 presignedUrl 解析文件名
    urlparser = urlparse(media["presignedUrl"])
    filename = os.path.basename(unquote(urlparser.path)) or "image"
    file_path = os.path.join(DEFAULT_DOWNLOAD_DIR, filename)

    # 远端直链（不下载）：直接作为 image_url 使用
    if media.get("mediaType") == "image_url":
        return {"type": "input_image", "image_url": media["presignedUrl"]}

    # 需要下载的图片（例如 "photo"）
    if media.get("mediaType") == "photo":
        if download_file(media["presignedUrl"], file_path):
            try:
                _ensure_valid_image(file_path)
                data_url = _to_data_url(file_path)
                result = {"type": "input_image", "image_url": data_url}
            except Exception as e:
                print(f"[resolve_message_media] Error processing image {file_path}: {e}")
            finally:
                if os.path.exists(file_path):
                    _remove_file_path_list.append(file_path)

    return result


def generate_gpt_response_by_gpt_parts(
    gpt_parts: List[dict],
    prompt: str,
    model: str = None,
    *,
    temperature: float = 1.0,
    reasoning_effort: str = "medium",  # "minimal" | "medium" | "high"
) -> str:
    """
    把 parts + prompt 组织成一个 user message，调用 Responses API，返回 output_text。
    兼容你的旧数据键名：
      - "text" -> "input_text"
      - "image_url" -> input_image.image_url
      - "image_base64" -> 包装成 data URL 后放到 image_url
    """
    if model is None:
        model = settings.openai_gpt_model

    content_list: List[Dict[str, Any]] = []

    for part in gpt_parts or []:
        ptype = part.get("type")

        # 文本
        if ptype in ("input_text", "text"):
            txt = part.get("text", "")
            if txt:
                content_list.append({"type": "input_text", "text": txt})
            continue

        # 规范的 input_image（透传）
        if ptype == "input_image":
            # 要求是 {"image_url": "..."}；此处直接透传
            if "image_url" in part:
                content_list.append({"type": "input_image", "image_url": part["image_url"]})
            continue

        # 旧的 image_url
        if ptype == "image_url":
            content_list.append({"type": "input_image", "image_url": part["image_url"]})
            continue

        # 旧的 image_base64（自定义字段名），改成 data URL
        if ptype == "image_base64" or "image_data" in part:
            b64 = part.get("image_data") or part.get("b64") or ""
            if b64:
                # 缺 MIME 就用 png
                data_url = f"data:image/png;base64,{b64}"
                content_list.append({"type": "input_image", "image_url": data_url})
            continue

        # 其它类型忽略
        # print(f"[generate_gpt_response_by_gpt_parts] skip unknown part: {part}")

    # 附加最终的自然语言 prompt
    if prompt:
        content_list.append({"type": "input_text", "text": prompt})

    # 如果 content 为空，至少给一个空提示，避免 400
    if not content_list:
        content_list.append({"type": "input_text", "text": ""})

    response = _get_client().responses.create(
        model=model,
        input=[{"role": "user", "content": content_list}],
        reasoning={"effort": reasoning_effort},
        temperature=temperature,
    )

    return response.output_text
