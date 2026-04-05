import time

import boto3
from boto3.dynamodb.conditions import Key

from tg_summary_core.config import settings
from tg_summary_core.utils.common import get_logger


class AWSClient:
    def __init__(self):
        self._logger = get_logger("aws-client")
        self._session = boto3.Session(region_name=settings.region_name)

    def get_recent_group_messages_by_day(
        self,
        chat_id: int,
        recent_day: int,
        end_timestamp: int,
        full_replied_message: bool = False,
        full_media_url: bool = False,
    ) -> list[dict]:
        timestamp_diff = recent_day * 24 * 60 * 60
        if not end_timestamp:
            end_timestamp = int(time.time())
        group_messages = self._get_dynamo_items_by_timestamp_range(
            chat_id=chat_id,
            start_timestamp=end_timestamp - timestamp_diff,
            end_timestamp=end_timestamp,
        )
        if full_replied_message:
            group_messages = self._resolve_full_replied_message(group_messages)
        if full_media_url:
            group_messages = self._get_presigned_url_for_all_messages(group_messages)
        return group_messages

    def _get_dynamo_item_by_key(self, key: dict, table_name: str = None) -> dict:
        if table_name is None:
            table_name = settings.dynamo_table_name
        dynamodb = self._session.resource("dynamodb")
        table = dynamodb.Table(table_name)
        response = table.get_item(Key=key)
        return response.get("Item", None)

    def _get_s3_presigned_url(
        self,
        s3_key: str,
        bucket_name: str = None,
        expires_in: int = 600,
    ) -> str:
        if bucket_name is None:
            bucket_name = settings.s3_bucket_name
        s3_client = self._session.client("s3")
        try:
            presigned_url = s3_client.generate_presigned_url(
                ClientMethod="get_object", Params={"Bucket": bucket_name, "Key": s3_key}, ExpiresIn=expires_in
            )
            return presigned_url
        except Exception as e:
            self._logger.error(e)

    def _get_dynamo_items_by_timestamp_range(
        self, chat_id: int, start_timestamp: int, end_timestamp: int, table_name: str = None
    ) -> list[dict]:
        if table_name is None:
            table_name = settings.dynamo_table_name
        dynamodb = self._session.resource("dynamodb")
        table = dynamodb.Table(table_name)
        response = table.query(
            IndexName="chatId-timestamp-index",
            KeyConditionExpression=Key("chatId").eq(chat_id) & Key("timestamp").between(start_timestamp, end_timestamp),
            ScanIndexForward=False,
        )
        return response.get("Items", [])

    def _resolve_full_replied_message(self, group_messages: list) -> list:
        for message in group_messages:
            if message.get("replyTo"):
                replied_message = self._get_dynamo_item_by_key(
                    key={
                        "chatId": message["chatId"],
                        "messageId": message["replyTo"],
                    }
                )
                message["repliedMessage"] = replied_message
        return group_messages

    def _get_presigned_url_for_all_messages(self, group_messages: list) -> list:
        for message in group_messages:
            if message.get("media"):
                s3_key = message["media"]["mediaKey"].split("/")[1] + "/" + message["media"]["mediaKey"].split("/")[2]
                presigned_url = self._get_s3_presigned_url(s3_key=s3_key)
                message["media"]["presignedUrl"] = presigned_url
            if message.get("repliedMessage") and message["repliedMessage"].get("media"):
                presigned_url = self._get_s3_presigned_url(
                    s3_key=message["repliedMessage"]["media"]["mediaKey"],
                )
                message["repliedMessage"]["media"]["presignedUrl"] = presigned_url
        return group_messages
