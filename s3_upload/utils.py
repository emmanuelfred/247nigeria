import boto3, uuid
from django.conf import settings

s3 = boto3.client(
    "s3",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)

BUCKET = settings.AWS_STORAGE_BUCKET_NAME
REGION = settings.AWS_S3_REGION_NAME


def generate_key(folder: str, filename: str):
    ext = filename.split('.')[-1]
    unique_name = f"{uuid.uuid4()}.{ext}"
    return f"{folder}/{unique_name}"


def upload_file_to_s3(file_obj, folder="uploads", content_type=None):
    file_key = generate_key(folder, file_obj.name)

    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type

    s3.upload_fileobj(
        file_obj,
        BUCKET,
        file_key,
        ExtraArgs=extra_args
    )

    file_url = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{file_key}"
    return file_url, file_key


def delete_file_from_s3(file_key):
    s3.delete_object(Bucket=BUCKET, Key=file_key)
    return True
