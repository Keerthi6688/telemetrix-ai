from minio import Minio
from minio.error import S3Error
import os

def upload_to_minio():
    """Upload Parquet to MinIO (Layer 3 - Historical Storage)"""
    
    # MinIO client
    client = Minio(
        "localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False
    )
    
    # Ensure bucket exists
    try:
        if not client.bucket_exists("telemetry-raw"):
            client.make_bucket("telemetry-raw")
            print("✓ Bucket created: telemetry-raw")
        else:
            print("✓ Bucket exists: telemetry-raw")
    except S3Error as e:
        print(f"Error: {e}")
        return False
    
    # Upload Parquet file
    try:
        parquet_file = "data/metrics.parquet"
        
        if os.path.exists(parquet_file):
            file_size = os.path.getsize(parquet_file)
            
            with open(parquet_file, 'rb') as file:
                client.put_object(
                    "telemetry-raw",
                    "checkoutservice/2026-01-01/metrics.parquet",
                    file,
                    length=file_size
                )
            
            print(f"✓ Uploaded: {parquet_file} to MinIO")
            print(f"  Size: {file_size} bytes")
            return True
        else:
            print(f"✗ File not found: {parquet_file}")
            return False
    
    except S3Error as e:
        print(f"Error uploading: {e}")
        return False

if __name__ == "__main__":
    upload_to_minio()
