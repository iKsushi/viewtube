from functools import lru_cache

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings


@lru_cache
def s3():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(
            signature_version="s3v4",
            connect_timeout=5,
            read_timeout=60,
            retries={"max_attempts": 3},
            s3={"addressing_style": "path"},
        ),
    )


def ensure_bucket():
    bucket = get_settings().s3_bucket
    try:
        s3().head_bucket(Bucket=bucket)
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
            raise
        s3().create_bucket(Bucket=bucket)


def upload(path, key, content_type):
    s3().upload_file(
        str(path),
        get_settings().s3_bucket,
        key,
        ExtraArgs={"ContentType": content_type},
        Config=TransferConfig(max_concurrency=2),
    )


def remove(key):
    s3().delete_object(Bucket=get_settings().s3_bucket, Key=key)
