import boto3
import os
from utils.image_processor import extract_metadata_from_bytes

def get_s3_client():
    return boto3.client('s3',
        endpoint_url=os.getenv('S3_ENDPOINT_URL'), # e.g., https://<account_id>.r2.cloudflarestorage.com
        aws_access_key_id=os.getenv('S3_ACCESS_KEY'),
        aws_secret_access_key=os.getenv('S3_SECRET_KEY')
    )

def scan_r2_bucket(bucket_name: str) -> list:
    s3 = get_s3_client()
    normalized_photos =[]
    
    # List files in the bucket
    response = s3.list_objects_v2(Bucket=bucket_name)
    
    if 'Contents' not in response:
        return normalized_photos

    for obj in response['Contents']:
        filename = obj['Key']
        
        # Skip non-images
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            continue
            
        size_mb = obj['Size'] / (1024 * 1024)
        
        # Smart Download: Only grab the first 1MB to get EXIF headers, saving egress bandwidth
        try:
            partial_obj = s3.get_object(Bucket=bucket_name, Key=filename, Range='bytes=0-1048576')
            image_chunk = partial_obj['Body'].read()
            metadata = extract_metadata_from_bytes(image_chunk)
        except Exception as e:
            metadata = {"width": None, "height": None}

        normalized_photos.append({
            "filename": filename,
            "source": f"S3 Bucket ({bucket_name})",
            "size_mb": round(size_mb, 2),
            "width": metadata['width'],
            "height": metadata['height'],
            "last_modified": str(obj['LastModified'])
        })
        
    return normalized_photos
