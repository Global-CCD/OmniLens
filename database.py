"""
OmniLens v3.0 - Async Database Layer
SQLAlchemy 2.0+ with async SQLite support.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import String, Float, Integer, DateTime, func, Index
from datetime import datetime
from typing import Optional

from config import settings

# --- Engine & Session ---
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

Base = declarative_base()


# --- Models ---
class Photo(Base):
    """Unified photo metadata from all cloud providers."""

    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # --- Identification ---
    filename: Mapped[str] = mapped_column(String(512), index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)  # 'google_drive', 's3_r2', 's3_b2'
    source_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # --- File Info ---
    size_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # --- Dimensions ---
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    format: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # --- Camera EXIF ---
    camera_make: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    camera_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    focal_length: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    iso: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    aperture: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    shutter_speed: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # --- GPS ---
    gps_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_alt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # --- Timestamps ---
    taken_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_modified: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # --- System ---
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=func.now(), 
        onupdate=func.now()
    )

    # --- Indexes for common queries ---
    __table_args__ = (
        Index("idx_photos_source_filename", "source", "filename"),
        Index("idx_photos_gps", "gps_lat", "gps_lon"),
        Index("idx_photos_taken", "taken_at"),
    )

    def to_dict(self) -> dict:
        """Serialize to dictionary for API responses."""
        return {
            "id": self.id,
            "filename": self.filename,
            "source": self.source,
            "source_id": self.source_id,
            "size_mb": self.size_mb,
            "file_hash": self.file_hash,
            "mime_type": self.mime_type,
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "camera": f"{self.camera_make or ''} {self.camera_model or ''}".strip() or None,
            "camera_make": self.camera_make,
            "camera_model": self.camera_model,
            "focal_length": self.focal_length,
            "iso": self.iso,
            "aperture": self.aperture,
            "shutter_speed": self.shutter_speed,
            "gps": {
                "lat": self.gps_lat,
                "lon": self.gps_lon,
                "alt": self.gps_alt
            } if any([self.gps_lat, self.gps_lon]) else None,
            "taken_at": self.taken_at.isoformat() if self.taken_at else None,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SyncLog(Base):
    """Track sync operations for audit and debugging."""

    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))  # 'started', 'completed', 'failed'
    photos_found: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    photos_added: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    photos_updated: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# --- Database Operations ---
async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Dependency for FastAPI to get database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
