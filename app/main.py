import os
import time

import requests

from app.report.prompt import generate_telegram_message_daily_summary_prompt, fix_telegram_text
from app.report.text_cat import convert_items_to_json_text
from app.report.gpt import generate_gpt_response_by_gpt_parts, generate_gpt_parts_by_group_messages
from app.report.gemini import generate_gemini_response, generate_gemini_parts_by_group_messages, \
    generate_gemini_response_multiple_times, DEFAULT_GEMINI_FAST_MODEL
from app.utils.aws import AWSClient, AWSConfig
from app.utils.common import get_logger, save_json_to_file, load_json_from_file, save_html_to_file

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", None)
SUMMARY_CHAT_ID = int(os.getenv("SUMMARY_CHAT_ID", None))
SUMMARY_CHAT_NAME = os.getenv("SUMMARY_CHAT_NAME", None)
TARGET_CHAT_ID = "-100" + os.getenv("TARGET_CHAT_ID", None)
DECLARATION = os.getenv("DECLARATION", "")
logger = get_logger("main")
ADDITIONAL_PROMPT = os.getenv("ADDITIONAL_PROMPT", "")
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "gemini-3-flash-preview")

# temp test
TEST_MODEL_1 = "gemini-3-pro-preview"
TEST_MODEL_2 = "gemini-2.5-pro"

test_list = [
    TEST_MODEL_1,
    TEST_MODEL_2
]


def test_get_daily_report(method: str = 'gpt', temperature: float = 0.5):
    aws_config = AWSConfig()
    aws_client = AWSClient(aws_config)
    prompt = generate_telegram_message_daily_summary_prompt(SUMMARY_CHAT_NAME, DECLARATION, ADDITIONAL_PROMPT)
    # prompt = generate_telegram_message_weekly_summary_prompt(SUMMARY_CHAT_NAME)
    logger.info("message history fetching...")
    items = aws_client.get_recent_group_messages_by_day(
        chat_id=SUMMARY_CHAT_ID,
        recent_day=1,
        full_replied_message=True
    )
    if not items:
        print("没有找到今日聊天记录。")
        return
    logger.info("message history fetched.")
    json_text = convert_items_to_json_text(items)
    summary_html_text = ""
    logger.info("AI summarization...")
    if method == 'gpt':
        summary_html_text = generate_gpt_response_by_gpt_parts(json_text, prompt, temperature=temperature)
    elif method == 'gemini':
        prompt = prompt + '\n' + json_text
        summary_html_text = generate_gemini_response(prompt)
    logger.info("AI summarization finished.")
    logger.info("sending to telegram...")
    print(summary_html_text)
    telegram_message_response = requests.post(
        f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
        data={'chat_id': TARGET_CHAT_ID, 'text': summary_html_text, 'parse_mode': 'HTML'}
    )
    print(telegram_message_response.json())


def get_daily_group_chat(timestamp: int = None) -> list[dict]:
    # get AWS config from env
    aws_config = AWSConfig()
    aws_client = AWSClient(aws_config)
    print("message history fetching...")
    # get group messages by day
    items = aws_client.get_recent_group_messages_by_day(
        chat_id=SUMMARY_CHAT_ID,
        recent_day=1,
        full_replied_message=True,
        full_media_url=True,
        end_timestamp=timestamp
    )
    items.reverse()
    return items


def get_prompt(timestamp: int = None) -> str:
    # generate prompt
    prompt = generate_telegram_message_daily_summary_prompt(
        SUMMARY_CHAT_NAME,
        DECLARATION,
        ADDITIONAL_PROMPT,
        analyze_media=True,
        end_timestamp=timestamp
    )
    print("prompt generated", prompt)
    return prompt


def generate_llm_response(prompt: str, items: list[dict], method: str = 'gemini', model: str = None,
                          num_calls: int = 1) -> list[str]:
    summary_html_text_list = []
    # generate summary by model
    if method == 'gpt':
        gpt_parts = generate_gpt_parts_by_group_messages(items)
        summary_html_text_list.append(generate_gpt_response_by_gpt_parts(gpt_parts, prompt))
    elif method == 'gemini':
        gemini_parts = generate_gemini_parts_by_group_messages(items)
        gemini_parts.append(prompt)
        gemini_response_list = generate_gemini_response_multiple_times(gemini_parts, model=model, num_calls=num_calls,
                                                                       temperature=0.5)
        for gemini_response in gemini_response_list:
            summary_html_text_list.append(generate_gemini_response(fix_telegram_text(gemini_response), model=DEFAULT_GEMINI_FAST_MODEL))
            print(summary_html_text_list[-1])
    return summary_html_text_list


def send_to_telegram(summary_html_text: str, model: str = None):
    try_time = 0
    while try_time < 5:
        try:
            time.sleep(5)
            try_time += 1
            telegram_message_response = requests.post(
                f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
                data={'chat_id': TARGET_CHAT_ID, 'text': summary_html_text, 'parse_mode': 'HTML'},
                timeout=20
            )
            response_dict = telegram_message_response.json()
            if response_dict:
                if not response_dict['ok']:
                    summary_html_text = generate_gemini_response(fix_telegram_text(summary_html_text), model=DEFAULT_GEMINI_FAST_MODEL)
                    continue
                break
        except Exception as e:
            print(e)
            continue


def generate_llm_response_and_send_to_telegram(prompt: str, items: list[dict], method: str = 'gemini',
                                               model: str = None, num_calls: int = 1) -> None:
    summary_html_text_list = generate_llm_response(prompt, items, method, model, num_calls)
    for summary_html_text in summary_html_text_list:
        send_to_telegram(summary_html_text, model=model)


def test_get_daily_report_multimodal(method: str = 'gemini', timestamp: int = None, test_mode: bool = False,
                                     model:str = None, num_calls: int = 1):
    items = get_daily_group_chat(timestamp)
    prompt = get_prompt(timestamp)
    # test mode
    if test_mode:
        for test_model in test_list:
            generate_llm_response_and_send_to_telegram(prompt, items, method, test_model, num_calls)
    else:
        generate_llm_response_and_send_to_telegram(prompt, items, method, model, num_calls=num_calls)


if __name__ == "__main__":
    # test_get_daily_report('gpt', 0.2)
    # test_get_daily_report('gemini')
    test_get_daily_report_multimodal('gemini', model=SUMMARY_MODEL, num_calls=5)
    # test_get_daily_report_multimodal('gemini', 1773018000, False, num_calls=5)
    # test_get_daily_report_multimodal('gemini', test_mode=True, num_calls=5)
