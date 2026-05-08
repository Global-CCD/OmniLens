"""
OmniLens v3.0 - Google Drive Provider
Full implementation with pagination, OAuth token refresh, retry logic,
and comprehensive EXIF metadata extraction via imageMediaMetadata.
"""

import os
import asyncio
from typing import List, Optional
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from providers import CloudProvider, PhotoMetadata, register_provider
from config import settings
from utils.retry import with_retry


class GoogleDriveProvider(CloudProvider):
    """Google Drive cloud provider implementation."""

    name = "google"
    display_name = "Google Drive"

    # Supported image formats via Google Drive mime types
    _supported_mimes = [
        "image/jpeg", "image/png", "image/webp", "image/gif",
        "image/tiff", "image/bmp", "image/heic", "image/heif"
    ]

    def __init__(self):
        self._service = None
        self._credentials = None

    def _get_credentials(self) -> Optional[Credentials]:
        """
        Load or refresh OAuth2 credentials.
        Handles token refresh automatically when expired.
        """
        creds = None
        token_path = settings.google_token_file
        secrets_path = settings.google_client_secrets_file

        # Load existing token
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(
                token_path, 
                settings.google_scopes_list
            )

        # Refresh if expired
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Save refreshed token
                with open(token_path, "w") as token_file:
                    token_file.write(creds.to_json())
            except Exception as e:
                print(f"[GoogleDrive] Token refresh failed: {e}")
                creds = None

        # Initiate new OAuth flow if no valid credentials
        if not creds or not creds.valid:
            if not os.path.exists(secrets_path):
                print(f"[GoogleDrive] Missing {secrets_path}. Run OAuth setup.")
                return None

            flow = InstalledAppFlow.from_client_secrets_file(
                secrets_path,
                settings.google_scopes_list
            )
            creds = flow.run_local_server(port=0)

            # Save token for future runs
            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())

        self._credentials = creds
        return creds

    def _get_service(self):
        """Get or create the Google Drive API service."""
        if self._service is None:
            creds = self._get_credentials()
            if creds is None:
                raise RuntimeError("Google Drive credentials not available")
            self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def is_configured(self) -> bool:
        """Check if Google Drive is configured."""
        return (
            os.path.exists(settings.google_client_secrets_file) or
            os.path.exists(settings.google_token_file)
        )

    @property
    def supported_formats(self) -> List[str]:
        return [".jpg", ".jpeg", ".png", ".webp", ".gif", ".tiff", ".bmp", ".heic", ".heif"]

    @with_retry(max_attempts=3, backoff_factor=2.0, exceptions=(HttpError,))
    async def scan(self, **kwargs) -> List[PhotoMetadata]:
        """
        Scan Google Drive for photos with full pagination.
        Handles rate limits with exponential backoff.
        """
        service = self._get_service()
        photos: List[PhotoMetadata] = []

        # Build mime type query
        mime_query = " or ".join([f"mimeType='{m}'" for m in self._supported_mimes])
        query = f"({mime_query}) and trashed = false"

        # Request comprehensive metadata fields
        fields = (
            "nextPageToken, "
            "files(id, name, mimeType, size, modifiedTime, "
            "imageMediaMetadata(width, height, rotation, location, "
            "time, cameraMake, cameraModel, aperture, focalLength, "
            "isoSpeed, exposureTime, sensor, lens))"
        )

        page_token = None
        page_count = 0

        try:
            while True:
                page_count += 1
                print(f"[GoogleDrive] Fetching page {page_count}...")

                # Run blocking API call in thread pool
                results = await asyncio.to_thread(
                    service.files().list(
                        q=query,
                        spaces="drive",
                        fields=fields,
                        pageSize=100,
                        pageToken=page_token,
                        orderBy="modifiedTime desc"
                    ).execute
                )

                items = results.get("files", [])

                for item in items:
                    photo = self._normalize_item(item)
                    if photo:
                        photos.append(photo)

                page_token = results.get("nextPageToken")
                if not page_token:
                    break

                # Brief pause between pages to respect rate limits
                await asyncio.sleep(0.5)

            print(f"[GoogleDrive] Scan complete: {len(photos)} photos found across {page_count} pages")
            return photos

        except HttpError as e:
            if e.resp.status == 429:
                print("[GoogleDrive] Rate limit exceeded. Backing off...")
                raise  # Let retry decorator handle it
            elif e.resp.status in (401, 403):
                print(f"[GoogleDrive] Auth error: {e}")
                self._service = None  # Force re-auth on next attempt
                raise
            else:
                print(f"[GoogleDrive] API error: {e}")
                raise

    def _normalize_item(self, item: dict) -> Optional[PhotoMetadata]:
        """Normalize a Google Drive file item to PhotoMetadata."""
        try:
            img_meta = item.get("imageMediaMetadata", {})

            # Parse location
            location = img_meta.get("location", {})
            gps_lat = location.get("latitude")
            gps_lon = location.get("longitude")
            gps_alt = location.get("altitude")

            # Parse timestamp
            taken_at = None
            time_str = img_meta.get("time")
            if time_str:
                try:
                    taken_at = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                except ValueError:
                    pass

            # Parse last modified
            last_modified = None
            mod_str = item.get("modifiedTime")
            if mod_str:
                try:
                    last_modified = datetime.fromisoformat(mod_str.replace("Z", "+00:00"))
                except ValueError:
                    pass

            # Parse exposure time (shutter speed)
            exposure = img_meta.get("exposureTime")
            shutter_speed = None
            if exposure:
                shutter_speed = f"{exposure}s"

            return PhotoMetadata(
                filename=item.get("name", "unknown"),
                source="google_drive",
                source_id=item.get("id"),
                mime_type=item.get("mimeType"),
                size_bytes=int(item.get("size", 0)) if item.get("size") else None,
                width=img_meta.get("width"),
                height=img_meta.get("height"),
                format=self._mime_to_format(item.get("mimeType")),
                camera_make=img_meta.get("cameraMake"),
                camera_model=img_meta.get("cameraModel"),
                focal_length=img_meta.get("focalLength"),
                iso=img_meta.get("isoSpeed"),
                aperture=img_meta.get("aperture"),
                shutter_speed=shutter_speed,
                gps_lat=gps_lat,
                gps_lon=gps_lon,
                gps_alt=gps_alt,
                taken_at=taken_at,
                last_modified=last_modified,
                raw_metadata={
                    "rotation": img_meta.get("rotation"),
                    "sensor": img_meta.get("sensor"),
                    "lens": img_meta.get("lens"),
                    "drive_id": item.get("id")
                }
            )

        except Exception as e:
            print(f"[GoogleDrive] Failed to normalize item {item.get('id')}: {e}")
            return None

    def _mime_to_format(self, mime_type: Optional[str]) -> Optional[str]:
        """Convert MIME type to image format string."""
        mapping = {
            "image/jpeg": "JPEG",
            "image/png": "PNG",
            "image/webp": "WEBP",
            "image/gif": "GIF",
            "image/tiff": "TIFF",
            "image/bmp": "BMP",
            "image/heic": "HEIC",
            "image/heif": "HEIF"
        }
        return mapping.get(mime_type)

    async def get_file_bytes(self, source_id: str, **kwargs) -> bytes:
        """Download file bytes from Google Drive."""
        service = self._get_service()

        def _download():
            request = service.files().get_media(fileId=source_id)
            return request.execute()

        return await asyncio.to_thread(_download)


# Register provider
register_provider(GoogleDriveProvider())
