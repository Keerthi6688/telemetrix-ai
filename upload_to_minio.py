import os
from datetime import datetime

import pandas as pd
from minio import Minio
from minio.error import S3Error

MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
BUCKET_NAME = "telemetry-raw"


def get_client():
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )


def ensure_bucket(client, bucket_name=BUCKET_NAME):
    """Layer 3: make sure the historical-storage bucket exists."""
    try:
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
            print(f"Bucket created: {bucket_name}")
        else:
            print(f"Bucket exists: {bucket_name}")
        return True
    except S3Error as e:
        print(f"Error ensuring bucket: {e}")
        return False


def upload_partitioned(client, df, bucket_name=BUCKET_NAME, date=None):
    """Write one Parquet file per component, partitioned by component/date
    as required by the RFP storage schema, so data is queryable by
    component and time range without scanning the whole bucket.
    """
    date = date or datetime.now().strftime("%Y-%m-%d")
    os.makedirs("data/_partitions", exist_ok=True)
    uploaded = []

    for component, group in df.groupby("component"):
        local_path = f"data/_partitions/{component}_{date}.parquet"
        group.to_parquet(local_path, index=False, engine="pyarrow")

        object_name = f"{component}/{date}/metrics.parquet"
        file_size = os.path.getsize(local_path)

        with open(local_path, "rb") as f:
            client.put_object(bucket_name, object_name, f, length=file_size)

        print(f"Uploaded: {object_name} ({file_size} bytes, {len(group)} records)")
        uploaded.append(object_name)

    return uploaded


def upload_to_minio(csv_path="data/metrics.csv"):
    """Layer 3 entry point: load the unified dataset and archive it to MinIO,
    partitioned by component/date.
    """
    client = get_client()

    if not ensure_bucket(client):
        return False

    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return False

    df = pd.read_csv(csv_path)
    if df.empty:
        print("No records to upload")
        return False

    upload_partitioned(client, df)
    return True


if __name__ == "__main__":
    upload_to_minio()
