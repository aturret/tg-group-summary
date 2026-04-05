import boto3
import pytest
from moto import mock_aws

from tg_summary_core.utils.aws import AWSClient


@pytest.fixture
def dynamo_table():
    """Set up moto-mocked DynamoDB table matching the real schema."""
    with mock_aws():
        session = boto3.Session(region_name="us-east-1")
        dynamodb = session.resource("dynamodb")
        table = dynamodb.create_table(
            TableName="tg-searcher-prod",
            KeySchema=[
                {"AttributeName": "chatId", "KeyType": "HASH"},
                {"AttributeName": "messageId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "chatId", "AttributeType": "N"},
                {"AttributeName": "messageId", "AttributeType": "N"},
                {"AttributeName": "timestamp", "AttributeType": "N"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "chatId-timestamp-index",
                    "KeySchema": [
                        {"AttributeName": "chatId", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(TableName="tg-searcher-prod")
        yield table


@pytest.fixture
def s3_bucket():
    """Set up moto-mocked S3 bucket."""
    with mock_aws():
        session = boto3.Session(region_name="us-east-1")
        s3 = session.client("s3")
        s3.create_bucket(Bucket="tg-searcher-prod")
        yield s3


def _seed_messages(table, chat_id, messages):
    """Helper to put items into DynamoDB."""
    for msg in messages:
        msg["chatId"] = chat_id
        table.put_item(Item=msg)


class TestGetRecentGroupMessagesByDay:
    @mock_aws
    def test_basic_query(self):
        # Setup
        session = boto3.Session(region_name="us-east-1")
        dynamodb = session.resource("dynamodb")
        table = dynamodb.create_table(
            TableName="tg-searcher-prod",
            KeySchema=[
                {"AttributeName": "chatId", "KeyType": "HASH"},
                {"AttributeName": "messageId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "chatId", "AttributeType": "N"},
                {"AttributeName": "messageId", "AttributeType": "N"},
                {"AttributeName": "timestamp", "AttributeType": "N"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "chatId-timestamp-index",
                    "KeySchema": [
                        {"AttributeName": "chatId", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.meta.client.get_waiter("table_exists").wait(TableName="tg-searcher-prod")

        now = 1700100000
        _seed_messages(
            table,
            12345,
            [
                {"messageId": 1, "timestamp": now - 3600, "user": "Alice", "text": "Hello"},
                {"messageId": 2, "timestamp": now - 1800, "user": "Bob", "text": "World"},
                {"messageId": 3, "timestamp": now - 200000, "user": "Old", "text": "Too old"},
            ],
        )

        client = AWSClient()
        result = client.get_recent_group_messages_by_day(chat_id=12345, recent_day=1, end_timestamp=now)
        # Should get messages 1 and 2 (within 1 day), not message 3
        message_ids = [int(m["messageId"]) for m in result]
        assert 1 in message_ids
        assert 2 in message_ids
        assert 3 not in message_ids

    @mock_aws
    def test_empty_result(self):
        session = boto3.Session(region_name="us-east-1")
        dynamodb = session.resource("dynamodb")
        dynamodb.create_table(
            TableName="tg-searcher-prod",
            KeySchema=[
                {"AttributeName": "chatId", "KeyType": "HASH"},
                {"AttributeName": "messageId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "chatId", "AttributeType": "N"},
                {"AttributeName": "messageId", "AttributeType": "N"},
                {"AttributeName": "timestamp", "AttributeType": "N"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "chatId-timestamp-index",
                    "KeySchema": [
                        {"AttributeName": "chatId", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        client = AWSClient()
        result = client.get_recent_group_messages_by_day(chat_id=99999, recent_day=1, end_timestamp=1700000000)
        assert result == []


class TestGetDynamoItemByKey:
    @mock_aws
    def test_found(self):
        session = boto3.Session(region_name="us-east-1")
        dynamodb = session.resource("dynamodb")
        table = dynamodb.create_table(
            TableName="tg-searcher-prod",
            KeySchema=[
                {"AttributeName": "chatId", "KeyType": "HASH"},
                {"AttributeName": "messageId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "chatId", "AttributeType": "N"},
                {"AttributeName": "messageId", "AttributeType": "N"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.put_item(Item={"chatId": 1, "messageId": 10, "text": "hello"})

        client = AWSClient()
        result = client._get_dynamo_item_by_key({"chatId": 1, "messageId": 10})
        assert result["text"] == "hello"

    @mock_aws
    def test_not_found(self):
        session = boto3.Session(region_name="us-east-1")
        dynamodb = session.resource("dynamodb")
        dynamodb.create_table(
            TableName="tg-searcher-prod",
            KeySchema=[
                {"AttributeName": "chatId", "KeyType": "HASH"},
                {"AttributeName": "messageId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "chatId", "AttributeType": "N"},
                {"AttributeName": "messageId", "AttributeType": "N"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        client = AWSClient()
        result = client._get_dynamo_item_by_key({"chatId": 1, "messageId": 999})
        assert result is None


class TestGetS3PresignedUrl:
    @mock_aws
    def test_returns_url(self):
        session = boto3.Session(region_name="us-east-1")
        s3 = session.client("s3")
        s3.create_bucket(Bucket="tg-searcher-prod")
        s3.put_object(Bucket="tg-searcher-prod", Key="media/photo.jpg", Body=b"data")

        client = AWSClient()
        url = client._get_s3_presigned_url("media/photo.jpg")
        assert url is not None
        assert "photo.jpg" in url


class TestResolveFullRepliedMessage:
    @mock_aws
    def test_reply_chain(self):
        session = boto3.Session(region_name="us-east-1")
        dynamodb = session.resource("dynamodb")
        table = dynamodb.create_table(
            TableName="tg-searcher-prod",
            KeySchema=[
                {"AttributeName": "chatId", "KeyType": "HASH"},
                {"AttributeName": "messageId", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "chatId", "AttributeType": "N"},
                {"AttributeName": "messageId", "AttributeType": "N"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.put_item(Item={"chatId": 1, "messageId": 1, "text": "original"})

        client = AWSClient()
        messages = [{"chatId": 1, "messageId": 2, "replyTo": 1, "text": "reply"}]
        result = client._resolve_full_replied_message(messages)
        assert result[0]["repliedMessage"]["text"] == "original"


class TestGetPresignedUrlForAllMessages:
    @mock_aws
    def test_adds_presigned_url(self):
        session = boto3.Session(region_name="us-east-1")
        s3 = session.client("s3")
        s3.create_bucket(Bucket="tg-searcher-prod")
        s3.put_object(Bucket="tg-searcher-prod", Key="path/photo.jpg", Body=b"img")

        client = AWSClient()
        messages = [
            {
                "media": {"mediaKey": "bucket/path/photo.jpg"},
            }
        ]
        result = client._get_presigned_url_for_all_messages(messages)
        assert "presignedUrl" in result[0]["media"]
        assert "photo.jpg" in result[0]["media"]["presignedUrl"]

    @mock_aws
    def test_replied_message_media(self):
        session = boto3.Session(region_name="us-east-1")
        s3 = session.client("s3")
        s3.create_bucket(Bucket="tg-searcher-prod")
        s3.put_object(Bucket="tg-searcher-prod", Key="media/reply.jpg", Body=b"img")

        client = AWSClient()
        messages = [
            {
                "repliedMessage": {
                    "media": {"mediaKey": "media/reply.jpg"},
                }
            }
        ]
        result = client._get_presigned_url_for_all_messages(messages)
        assert "presignedUrl" in result[0]["repliedMessage"]["media"]
