import os
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from app.core.config import settings

s3_client = boto3.client(
    "s3",
    endpoint_url=settings.S3_ENDPOINT,
    aws_access_key_id=settings.S3_ACCESS_KEY,
    aws_secret_access_key=settings.S3_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)


def ensure_bucket_exists():
    try:
        s3_client.head_bucket(Bucket=settings.S3_BUCKET)
    except ClientError:
        s3_client.create_bucket(Bucket=settings.S3_BUCKET)


def list_s3_keys(prefix: str) -> list[str]:
    paginator = s3_client.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=settings.S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])
    return keys


def download_s3_object(key: str, local_path: str):
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    s3_client.download_file(settings.S3_BUCKET, key, local_path)


def upload_file_to_s3(local_path: str, s3_key: str):
    s3_client.upload_file(local_path, settings.S3_BUCKET, s3_key)


def upload_bytes_to_s3(file_obj, s3_key: str):
    s3_client.upload_fileobj(file_obj, settings.S3_BUCKET, s3_key)
