import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from tg_summary_core.config import settings

logger = logging.getLogger(__name__)


def _load_prompt_config() -> dict | None:
    """Load prompt configuration from conf/prompt.yaml.

    Returns the parsed YAML dict if the file exists and is valid, or None otherwise.
    Expected keys: prompt_template, additional_prompt, declaration, media_instruction.
    """
    prompt_yaml_path = Path(settings.prompt_yaml_path)
    if not prompt_yaml_path.exists():
        return None
    try:
        with open(prompt_yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            return data
        logger.warning("conf/prompt.yaml has invalid structure, using defaults")
        return None
    except Exception as e:
        logger.warning("Failed to load conf/prompt.yaml: %s, using defaults", e)
        return None


def get_beijing_date_str(day_change: int = 0, from_timestamp: int = None) -> str:
    beijing_tz = timezone(timedelta(hours=8))
    if from_timestamp is not None:
        dt = datetime.fromtimestamp(from_timestamp-86400, tz=beijing_tz)
    else:
        dt = datetime.now(beijing_tz) - timedelta(days=day_change)
    beijing_date = f"{dt.year}年{dt.month}月{dt.day}日"
    return beijing_date


DEFAULT_MEDIA_INSTRUCTION_ANALYZE = "包含在 media 字段中的内容需作为重要上下文分析。"
DEFAULT_MEDIA_INSTRUCTION_REFERENCE = "media 字段仅作参考（如\u201c发送了图片\u201d），无需深入分析媒体内容，除非文本中有上下文提及。"


def generate_telegram_message_daily_summary_prompt(
        chat_name: str,
        declaration: str = "",
        additional_prompt: str = "",
        analyze_media: bool = False,
        end_timestamp: int = None
) -> str:
    today = get_beijing_date_str(day_change=1 if end_timestamp is None else 0, from_timestamp=end_timestamp)

    media_instruction = (
        DEFAULT_MEDIA_INSTRUCTION_ANALYZE if analyze_media else DEFAULT_MEDIA_INSTRUCTION_REFERENCE
    )

    config = _load_prompt_config()
    if config is not None:
        # YAML values override function parameters; parameters serve as fallback
        if "media_instruction" in config:
            mi = config["media_instruction"]
            if isinstance(mi, dict):
                media_instruction = mi.get("analyze" if analyze_media else "reference_only", media_instruction)
            elif isinstance(mi, str):
                media_instruction = mi

        effective_declaration = config.get("declaration", declaration)
        effective_additional_prompt = config.get("additional_prompt", additional_prompt)

        if "prompt_template" in config:
            return config["prompt_template"].format(
                chat_name=chat_name,
                date=today,
                declaration=effective_declaration,
                additional_prompt=effective_additional_prompt,
                media_instruction=media_instruction,
            )
        # If YAML has no prompt_template, fall through to hardcoded default
        # but still use the YAML declaration/additional_prompt
        declaration = effective_declaration
        additional_prompt = effective_additional_prompt

    return (
        f"你是一位专业的舆情分析师和简报编辑。我将提供一份 JSON 格式的 Telegram 聊天记录，请你将其整理为一份高质量的**日报简报**。\n\n"

        f"### 数据说明\n"
        f"数据是标准的 Telegram 消息对象列表。关键字段：user (发送者), text (内容), replyTo (回复关系), media (媒体文件)。\n"
        f"请忽略 isBot=true 的机器人消息。\n"
        f"{media_instruction}\n\n"

        f"### 分析要求\n"
        f"1. **话题聚类**：将碎片化的聊天内容按主题归类，选取热度最高或价值最高的 5-8 个话题。\n"
        f"2. **深度挖掘**：对于时政、新闻、行业类话题，需结合 reply 上下文，分析群友的观点倾向、补充的背景信息或对新闻的独特解读。如果涉及不确定的新闻事实，请务必利用工具联网搜索确认。\n"
        f"3. **去噪**：过滤掉纯粹的闲聊（如打招呼、表情包刷屏），除非它们构成了某种群体性情绪。\n\n"

        f"### 输出格式（严格遵守 HTML）\n"
        f"请输出一段可以直接通过 Telegram 发送的 HTML 文本。不要使用 Markdown 代码块。格式规范如下：\n\n"

        f"第一行标题：<b>{chat_name} {today} 聊天记录总结报告</b>\n\n"

        f"对于每个话题，请严格按以下结构输出（注意空行和加粗）：\n"
        f"1. **话题标题**：必须包含超链接。HTML格式：<a href=\"https://t.me/c/{{chatId}}/{{messageId}}\"><b>{{标题}}</b></a>\n"
        f"   （链接指向该话题的第一条或最具代表性的消息 messageId）\n"
        f"2. **核心内容**：可以总结成一段文字，也可以根据内容中的子论点或次要内容使用类似\u201c\u2022\u201d的项目符号，分 2-4 点陈述。格式类似于：\n"
        f"   • <b>{{子标题/关键点}}</b>：具体内容的简练描述。\n"

        f"### 示例风格\n"
        f"（参考以下风格，但保持 HTML 标签）\n"
        f"<a href=\"...\"><b>某某政策引发讨论</b></a>\n"
        f"• <b>核心变化</b>：群友分享了新规，指出相比旧版主要变化在于...\n"
        f"• <b>主要争议</b>：部分群友认为这将导致...，而另一方则认为...\n\n"


        f"### 补充指令\n"
        f"{additional_prompt}\n"
        f"请在结尾另起一行添加：{declaration}\n\n"
        f"现在，请开始分析以下数据："
    )


def fix_telegram_text(original_text: str) -> str:
    return (
        f"你是一名专业的文本格式校对员，特别精通 Telegram Bot API 的 HTML 消息格式规范。\n"
        f"我将给你一段需要通过 Telegram API 发送的 HTML 格式文本。你的任务是：\n"
        f"1. ** 仔细校对 ** 这段文本，确保其完全符合 Telegram Bot API 对 HTML 消息格式的要求。\n"
        f"2. ** 不要改变任何内容的原始含义。 ** 你的工作仅限于格式规范检查和修正。\n"
        f"3. ** 直接输出校对后的文本。 ** 不要包含任何解释性文字、分析或额外信息，只提供修正后的最终 HTML 字符串。\n"
        f"以下是需要校对的原始文本：\n"
        f"{original_text}"
    )
