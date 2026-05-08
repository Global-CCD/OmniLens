"""
OmniLens v3.0 - Main FastAPI Application
Complete API with database persistence, CORS, rate limiting, webhook verification,
pagination, and comprehensive error handling.
"""

import os
import hmac
import hashlib
import asyncio
from datetime import datetime
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import settings
from database import init_db, get_db, Photo, SyncLog
from providers import get_provider, get_configured_providers, PhotoMetadata
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# --- Rate Limiter ---
limiter = Limiter(key_func=get_remote_address)

# --- Pydantic Models ---
class PhotoResponse(BaseModel):
    id: int
    filename: str
    source: str
    size_mb: Optional[float]
    width: Optional[int]
    height: Optional[int]
    camera: Optional[str]
    focal_length: Optional[float]
    iso: Optional[int]
    gps: Optional[dict]
    taken_at: Optional[str]
    last_modified: Optional[str]

    class Config:
        from_attributes = True

class ScanRequest(BaseModel):
    provider: str = Field(default="all", pattern="^(all|google|s3)$")

class WebhookResponse(BaseModel):
    status: str
    message: str
    scan_triggered: bool

class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    database: str
    providers: List[str]
    total_photos: int
    uptime: str

# --- Application State ---
_app_start_time = datetime.utcnow()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - init DB on startup."""
    print("[OmniLens] Initializing database...")
    await init_db()
    print("[OmniLens] Database ready.")
    yield
    print("[OmniLens] Shutting down...")

# --- FastAPI App ---
app = FastAPI(
    title=settings.app_name,
    description="Unified API to process and retrieve photo metadata across multiple clouds.",
    version=settings.app_version,
    lifespan=lifespan
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if hasattr(settings.cors_origins, '__iter__') else [settings.cors_origins],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --- Helper Functions ---
async def sync_provider(provider_name: str, db: AsyncSession):
    """Sync a single provider and persist results to database."""
    provider = get_provider(provider_name)
    if not provider:
        raise ValueError(f"Provider '{provider_name}' not found")

    if not provider.is_configured():
        raise ValueError(f"Provider '{provider_name}' is not configured")

    # Create sync log entry
    sync_log = SyncLog(
        provider=provider_name,
        status="started",
        started_at=datetime.utcnow()
    )
    db.add(sync_log)
    await db.commit()

    try:
        print(f"[Sync] Scanning {provider.display_name}...")
        photos = await provider.scan()

        added_count = 0
        updated_count = 0

        for photo_meta in photos:
            # Check for existing photo by source + source_id
            result = await db.execute(
                select(Photo).where(
                    Photo.source == photo_meta.source,
                    Photo.source_id == photo_meta.source_id
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing
                existing.size_mb = photo_meta.size_mb
                existing.width = photo_meta.width
                existing.height = photo_meta.height
                existing.camera_make = photo_meta.camera_make
                existing.camera_model = photo_meta.camera_model
                existing.focal_length = photo_meta.focal_length
                existing.iso = photo_meta.iso
                existing.aperture = photo_meta.aperture
                existing.shutter_speed = photo_meta.shutter_speed
                existing.gps_lat = photo_meta.gps_lat
                existing.gps_lon = photo_meta.gps_lon
                existing.gps_alt = photo_meta.gps_alt
                existing.taken_at = photo_meta.taken_at
                existing.last_modified = photo_meta.last_modified
                existing.updated_at = datetime.utcnow()
                updated_count += 1
            else:
                # Create new
                new_photo = Photo(
                    filename=photo_meta.filename,
                    source=photo_meta.source,
                    source_id=photo_meta.source_id,
                    mime_type=photo_meta.mime_type,
                    size_mb=photo_meta.size_mb,
                    width=photo_meta.width,
                    height=photo_meta.height,
                    format=photo_meta.format,
                    camera_make=photo_meta.camera_make,
                    camera_model=photo_meta.camera_model,
                    focal_length=photo_meta.focal_length,
                    iso=photo_meta.iso,
                    aperture=photo_meta.aperture,
                    shutter_speed=photo_meta.shutter_speed,
                    gps_lat=photo_meta.gps_lat,
                    gps_lon=photo_meta.gps_lon,
                    gps_alt=photo_meta.gps_alt,
                    taken_at=photo_meta.taken_at,
                    last_modified=photo_meta.last_modified
                )
                db.add(new_photo)
                added_count += 1

        await db.commit()

        # Update sync log
        sync_log.status = "completed"
        sync_log.photos_found = len(photos)
        sync_log.photos_added = added_count
        sync_log.photos_updated = updated_count
        sync_log.completed_at = datetime.utcnow()
        await db.commit()

        print(f"[Sync] {provider.display_name}: {len(photos)} found, {added_count} added, {updated_count} updated")
        return len(photos), added_count, updated_count

    except Exception as e:
        sync_log.status = "failed"
        sync_log.error_message = str(e)[:1024]
        sync_log.completed_at = datetime.utcnow()
        await db.commit()
        raise

async def sync_all_providers(db: AsyncSession):
    """Sync all configured providers."""
    providers = get_configured_providers()
    total_found = 0
    total_added = 0
    total_updated = 0

    for name, provider in providers.items():
        try:
            found, added, updated = await sync_provider(name, db)
            total_found += found
            total_added += added
            total_updated += updated
        except Exception as e:
            print(f"[Sync] Error syncing {name}: {e}")
            continue

    return total_found, total_added, total_updated

# --- API Endpoints ---

@app.get("/", response_model=HealthResponse)
@limiter.limit("60/minute")
async def read_root(request: Request, db: AsyncSession = Depends(get_db)):
    """Health check and application status."""
    result = await db.execute(select(func.count(Photo.id)))
    total_photos = result.scalar()

    providers = list(get_configured_providers().keys())
    uptime = datetime.utcnow() - _app_start_time

    return HealthResponse(
        status="online",
        app=settings.app_name,
        version=settings.app_version,
        database="connected" if total_photos is not None else "error",
        providers=providers,
        total_photos=total_photos or 0,
        uptime=str(uptime).split(".")[0]
    )

@app.get("/photos", response_model=dict)
@limiter.limit("60/minute")
async def get_all_photos(
    request: Request,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Max records to return"),
    source: Optional[str] = Query(None, description="Filter by source (google_drive, s3_r2, s3_b2)"),
    search: Optional[str] = Query(None, description="Search in filename")
):
    """
    Get paginated list of all photos with optional filtering.
    """
    query = select(Photo)

    if source:
        query = query.where(Photo.source == source)

    if search:
        query = query.where(Photo.filename.ilike(f"%{search}%"))

    # Get total count
    count_query = select(func.count(Photo.id))
    if source:
        count_query = count_query.where(Photo.source == source)
    if search:
        count_query = count_query.where(Photo.filename.ilike(f"%{search}%"))

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Get paginated results
    query = query.order_by(Photo.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    photos = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "count": len(photos),
        "data": [photo.to_dict() for photo in photos]
    }

@app.get("/photos/{photo_id}", response_model=dict)
@limiter.limit("60/minute")
async def get_photo(
    photo_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Get a single photo by ID."""
    result = await db.execute(select(Photo).where(Photo.id == photo_id))
    photo = result.scalar_one_or_none()

    if not photo:
        raise HTTPException(status_code=404, detail=f"Photo {photo_id} not found")

    return photo.to_dict()

@app.post("/scan", response_model=dict)
@limiter.limit("10/minute")
async def trigger_manual_scan(
    request: Request,
    scan_req: ScanRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger a scan for a specific provider or all providers.
    Uses BackgroundTasks for non-blocking response.
    """
    provider = scan_req.provider

    if provider == "all":
        background_tasks.add_task(sync_all_providers, db)
        return {
            "message": "Full scan initiated for all configured providers",
            "providers": list(get_configured_providers().keys()),
            "status": "running_in_background"
        }
    else:
        prov = get_provider(provider)
        if not prov:
            raise HTTPException(status_code=400, detail=f"Provider '{provider}' not found")
        if not prov.is_configured():
            raise HTTPException(status_code=400, detail=f"Provider '{provider}' is not configured")

        background_tasks.add_task(sync_provider, provider, db)
        return {
            "message": f"Scan initiated for {prov.display_name}",
            "provider": provider,
            "status": "running_in_background"
        }

@app.get("/sync-history", response_model=dict)
@limiter.limit("30/minute")
async def get_sync_history(
    request: Request,
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    """Get history of sync operations."""
    query = select(SyncLog).order_by(SyncLog.started_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "count": len(logs),
        "data": [
            {
                "id": log.id,
                "provider": log.provider,
                "status": log.status,
                "photos_found": log.photos_found,
                "photos_added": log.photos_added,
                "photos_updated": log.photos_updated,
                "error_message": log.error_message,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None
            }
            for log in logs
        ]
    }

# --- Webhook Endpoints ---

@app.post("/webhook/google", response_model=WebhookResponse)
@limiter.limit("120/minute")
async def google_drive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint for Google Drive Push Notifications.
    Verifies channel token before processing.
    """
    # Verify Google webhook token
    channel_token = request.headers.get("X-Goog-Channel-Token")
    expected_token = settings.google_webhook_token

    if expected_token and channel_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    # Verify channel ID consistency (optional but recommended)
    channel_id = request.headers.get("X-Goog-Channel-Id")
    if not channel_id:
        raise HTTPException(status_code=400, detail="Missing channel ID")

    # Trigger sync
    provider = get_provider("google")
    if provider and provider.is_configured():
        background_tasks.add_task(sync_provider, "google", db)
        return WebhookResponse(
            status="success",
            message="Webhook verified and accepted",
            scan_triggered=True
        )
    else:
        return WebhookResponse(
            status="ignored",
            message="Google Drive provider not configured",
            scan_triggered=False
        )

@app.post("/webhook/s3", response_model=WebhookResponse)
@limiter.limit("120/minute")
async def s3_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Endpoint for S3-compatible Event Notifications.
    Verifies HMAC signature if configured.
    """
    body = await request.body()

    # Verify HMAC signature if secret is configured
    expected_secret = settings.s3_webhook_secret
    if expected_secret:
        signature = request.headers.get("X-Signature") or request.headers.get("X-Hub-Signature-256")

        if not signature:
            raise HTTPException(status_code=401, detail="Missing webhook signature")

        # Compute expected signature
        expected_sig = hmac.new(
            expected_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        # Compare signatures (constant-time)
        provided_sig = signature.replace("sha256=", "") if signature.startswith("sha256=") else signature
        if not hmac.compare_digest(expected_sig, provided_sig):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Trigger sync
    provider = get_provider("s3")
    if provider and provider.is_configured():
        background_tasks.add_task(sync_provider, "s3", db)
        return WebhookResponse(
            status="success",
            message="Webhook verified and accepted",
            scan_triggered=True
        )
    else:
        return WebhookResponse(
            status="ignored",
            message="S3 provider not configured",
            scan_triggered=False
        )

# --- Error Handlers ---

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    print(f"[Error] Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__}
    )

# --- Run Command ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
