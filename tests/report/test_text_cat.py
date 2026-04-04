import json
from decimal import Decimal

from tg_summary_core.report.text_cat import (
    convert_decimal,
    convert_items_to_json_text,
    convert_item_to_json_text,
    KEY_ORDER,
)


class TestConvertDecimal:
    def test_int(self):
        assert convert_decimal(Decimal("42")) == 42
        assert isinstance(convert_decimal(Decimal("42")), int)

    def test_float(self):
        assert convert_decimal(Decimal("3.14")) == 3.14
        assert isinstance(convert_decimal(Decimal("3.14")), float)

    def test_nested_dict(self):
        result = convert_decimal({"a": Decimal("1"), "b": Decimal("2.5")})
        assert result == {"a": 1, "b": 2.5}

    def test_nested_list(self):
        result = convert_decimal([Decimal("1"), Decimal("2.5")])
        assert result == [1, 2.5]

    def test_passthrough_string(self):
        assert convert_decimal("hello") == "hello"

    def test_passthrough_int(self):
        assert convert_decimal(42) == 42

    def test_deeply_nested(self):
        data = {"a": [{"b": Decimal("10")}]}
        result = convert_decimal(data)
        assert result == {"a": [{"b": 10}]}


class TestConvertItemsToJsonText:
    def test_key_ordering(self):
        item = {"text": "hello", "chatId": 123, "user": "Alice", "timestamp": 100}
        result = convert_items_to_json_text([item])
        parsed = json.loads(result)
        keys = list(parsed[0].keys())
        # Keys should appear in KEY_ORDER sequence
        expected_order = [k for k in KEY_ORDER if k in keys]
        assert keys == expected_order

    def test_missing_keys_omitted(self):
        item = {"chatId": 123, "text": "hello"}
        result = convert_items_to_json_text([item])
        parsed = json.loads(result)
        assert "user" not in parsed[0]
        assert parsed[0]["chatId"] == 123

    def test_unicode(self):
        item = {"chatId": 1, "text": "你好世界"}
        result = convert_items_to_json_text([item])
        assert "你好世界" in result

    def test_with_decimals(self):
        item = {"chatId": Decimal("123"), "timestamp": Decimal("1700000000")}
        result = convert_items_to_json_text([item])
        parsed = json.loads(result)
        assert parsed[0]["chatId"] == 123
        assert parsed[0]["timestamp"] == 1700000000


class TestConvertItemToJsonText:
    def test_single_item(self):
        item = {"chatId": 1, "messageId": 2, "text": "test"}
        result = convert_item_to_json_text(item)
        parsed = json.loads(result)
        assert parsed["chatId"] == 1
        assert parsed["messageId"] == 2
        assert parsed["text"] == "test"

    def test_key_ordering(self):
        item = {"text": "hello", "chatId": 123, "user": "Alice"}
        result = convert_item_to_json_text(item)
        parsed = json.loads(result)
        keys = list(parsed.keys())
        expected_order = [k for k in KEY_ORDER if k in keys]
        assert keys == expected_order
