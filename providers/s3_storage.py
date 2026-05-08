"""
OmniLens v3.0 - S3-Compatible Storage Provider
Supports Cloudflare R2, Backblaze B2, AWS S3, and any S3-compatible API.
Includes pagination, range requests, retry logic, and async operations.
"""

import os
import asyncio
import hashlib
from typing import List, Optional
from datetime import datetime
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from botocore.config import Config

from providers import CloudProvider, PhotoMetadata, register_provider
from config import settings
from utils.image_processor import extract_metadata_from_bytes
from utils.retry import with_retry


class S3Provider(CloudProvider):
    """S3-compatible cloud provider (R2, B2, AWS S3)."""

    name = "s3"
    display_name = "S3-Compatible Storage"

    # Supported image formats (case-insensitive)
    _supported_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tiff", ".bmp", ".heic", ".heif", ".raw", ".cr2", ".nef", ".arw"}

    def __init__(self):
        self._client = None
        self._bucket_name = None

    def _get_client(self):
        """Get or create boto3 S3 client."""
        if self._client is None:
            # Configure boto3 with retries and timeouts
            botocore_config = Config(
                retries={"max_attempts": 3, "mode": "adaptive"},
                connect_timeout=10,
                read_timeout=30,
                max_pool_connections=25
            )

            self._client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                region_name=settings.s3_region,
                config=botocore_config
            )
            self._bucket_name = settings.s3_bucket_name

        return self._client

    def is_configured(self) -> bool:
        """Check if S3 credentials are fully configured."""
        return settings.is_s3_configured

    @property
    def supported_formats(self) -> List[str]:
        return list(self._supported_extensions)

    @with_retry(max_attempts=3, backoff_factor=2.0, exceptions=(ClientError, BotoCoreError))
    async def scan(self, **kwargs) -> List[PhotoMetadata]:
        """
        Scan S3 bucket for photos with full pagination.
        Uses range requests to minimize bandwidth.
        """
        client = self._get_client()
        bucket = self._bucket_name
        photos: List[PhotoMetadata] = []

        # Use paginator for automatic pagination
        paginator = client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=bucket, PaginationConfig={"PageSize": 1000})

        page_count = 0

        try:
            for page in page_iterator:
                page_count += 1
                print(f"[S3] Processing page {page_count}...")

                contents = page.get("Contents", [])

                for obj in contents:
                    photo = await self._process_object(obj, client, bucket)
                    if photo:
                        photos.append(photo)

                # Brief pause between pages
                await asyncio.sleep(0.1)

            print(f"[S3] Scan complete: {len(photos)} photos found across {page_count} pages")
            return photos

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("NoSuchBucket", "AccessDenied", "InvalidAccessKeyId"):
                print(f"[S3] Critical error: {error_code} - {e.response['Error']['Message']}")
                raise
            elif error_code == "SlowDown":
                print("[S3] Rate limit (SlowDown). Backing off...")
                raise  # Let retry decorator handle
            else:
                print(f"[S3] Client error: {error_code}")
                raise

    async def _process_object(self, obj: dict, client, bucket: str) -> Optional[PhotoMetadata]:
        """Process a single S3 object into PhotoMetadata."""
        filename = obj["Key"]

        # Check if file is an image (case-insensitive)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self._supported_extensions:
            return None

        size_bytes = obj["Size"]

        # Parse last modified
        last_modified = obj.get("LastModified")
        if isinstance(last_modified, datetime):
            last_modified = last_modified.replace(tzinfo=None)

        # Extract metadata via range request (first 2MB for safety)
        metadata = await self._extract_metadata_with_range(client, bucket, filename)

        return PhotoMetadata(
            filename=filename,
            source="s3_r2" if "r2" in (settings.s3_endpoint_url or "") else "s3_b2",
            source_id=filename,  # S3 uses key as ID
            mime_type=self._ext_to_mime(ext),
            size_bytes=size_bytes,
            width=metadata.get("width"),
            height=metadata.get("height"),
            format=metadata.get("format"),
            camera_make=metadata.get("camera_make"),
            camera_model=metadata.get("camera_model"),
            focal_length=metadata.get("focal_length"),
            iso=metadata.get("iso"),
            aperture=metadata.get("aperture"),
            shutter_speed=metadata.get("shutter_speed"),
            gps_lat=metadata.get("gps_lat"),
            gps_lon=metadata.get("gps_lon"),
            gps_alt=metadata.get("gps_alt"),
            taken_at=metadata.get("taken_at"),
            last_modified=last_modified,
            raw_metadata={
                "etag": obj.get("ETag"),
                "storage_class": obj.get("StorageClass"),
                "bucket": bucket
            }
        )

    async def _extract_metadata_with_range(self, client, bucket: str, key: str) -> dict:
        """
        Download only the first 2MB of an image to extract metadata.
        Falls back to full download if range request fails.
        """
        try:
            # Try range request first (saves bandwidth)
            def _get_range():
                return client.get_object(
                    Bucket=bucket,
                    Key=key,
                    Range="bytes=0-2097151"  # 2MB
                )

            response = await asyncio.to_thread(_get_range)
            image_chunk = response["Body"].read()

            metadata = extract_metadata_from_bytes(image_chunk)

            # If EXIF extraction failed, try full download for small files (<5MB)
            if metadata.get("width") is None and response["ContentLength"] < 5242880:
                print(f"[S3] Range request insufficient for {key}, trying full download...")
                def _get_full():
                    return client.get_object(Bucket=bucket, Key=key)

                full_response = await asyncio.to_thread(_get_full)
                full_bytes = full_response["Body"].read()
                metadata = extract_metadata_from_bytes(full_bytes)

            return metadata

        except ClientError as e:
            if e.response["Error"]["Code"] == "InvalidRange":
                # File is smaller than range, try full download
                try:
                    def _get_full():
                        return client.get_object(Bucket=bucket, Key=key)

                    response = await asyncio.to_thread(_get_full)
                    image_bytes = response["Body"].read()
                    return extract_metadata_from_bytes(image_bytes)
                except Exception as e2:
                    print(f"[S3] Full download failed for {key}: {e2}")
                    return {}
            else:
                print(f"[S3] Range request failed for {key}: {e}")
                return {}
        except Exception as e:
            print(f"[S3] Metadata extraction failed for {key}: {e}")
            return {}

    def _ext_to_mime(self, ext: str) -> Optional[str]:
        """Convert file extension to MIME type."""
        mapping = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".tiff": "image/tiff",
            ".bmp": "image/bmp",
            ".heic": "image/heic",
            ".heif": "image/heif",
            ".raw": "image/x-raw",
            ".cr2": "image/x-canon-cr2",
            ".nef": "image/x-nikon-nef",
            ".arw": "image/x-sony-arw"
        }
        return mapping.get(ext.lower())

    async def get_file_bytes(self, source_id: str, **kwargs) -> bytes:
        """Download full file bytes from S3."""
        client = self._get_client()
        bucket = self._bucket_name

        def _download():
            response = client.get_object(Bucket=bucket, Key=source_id)
            return response["Body"].read()

        return await asyncio.to_thread(_download)


# Register provider
register_provider(S3Provider())
