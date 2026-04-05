import json
from collections import OrderedDict
from decimal import Decimal

KEY_ORDER = [
    "chatId",
    "messageId",
    "timestamp",
    "user",
    "text",
    "media",
    "replyTo",
    "replyMessage",
    "isForward",
    "fwdFrom",
]


def convert_decimal(obj):
    if isinstance(obj, list):
        return [convert_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    else:
        return obj


def convert_items_to_json_text(
    items: list[dict],
) -> str:
    ordered_items = [OrderedDict((key, d[key]) for key in KEY_ORDER if key in d) for d in items]

    json_text = json.dumps(ordered_items, indent=2, ensure_ascii=False, default=convert_decimal)
    print("json text length:", len(json_text))
    return json_text


def convert_item_to_json_text(item: dict) -> str:
    ordered_item = OrderedDict((key, item[key]) for key in KEY_ORDER if key in item)
    json_text = json.dumps(ordered_item, indent=2, ensure_ascii=False, default=convert_decimal)
    print("json text length:", len(json_text))
    return json_text
