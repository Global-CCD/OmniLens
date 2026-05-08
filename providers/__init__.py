"""
OmniLens v3.0 - Cloud Provider Interface
Abstract base class and registry for all cloud storage providers.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class PhotoMetadata:
    """Unified metadata schema for photos from any provider."""

    # Required
    filename: str
    source: str  # e.g., 'google_drive', 's3_r2', 's3_b2'

    # Identification
    source_id: Optional[str] = None
    file_hash: Optional[str] = None
    mime_type: Optional[str] = None

    # File Info
    size_bytes: Optional[int] = None
    size_mb: Optional[float] = None

    # Dimensions
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None

    # Camera EXIF
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    focal_length: Optional[float] = None
    iso: Optional[int] = None
    aperture: Optional[float] = None
    shutter_speed: Optional[str] = None

    # GPS
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    gps_alt: Optional[float] = None

    # Timestamps
    taken_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None

    # Raw metadata (provider-specific extras)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Auto-calculate size_mb from size_bytes."""
        if self.size_bytes is not None and self.size_mb is None:
            self.size_mb = round(self.size_bytes / (1024 * 1024), 2)


class CloudProvider(ABC):
    """Abstract base class for all cloud storage providers."""

    name: str = "base"
    display_name: str = "Base Provider"

    @abstractmethod
    async def scan(self, **kwargs) -> List[PhotoMetadata]:
        """
        Scan the provider for photos and return normalized metadata.
        Must handle pagination internally.
        """
        pass

    @abstractmethod
    async def get_file_bytes(self, source_id: str, **kwargs) -> bytes:
        """
        Download file bytes for a given photo.
        Used for hash calculation, thumbnail generation, etc.
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if this provider has valid configuration."""
        pass

    @property
    @abstractmethod
    def supported_formats(self) -> List[str]:
        """List of file extensions this provider supports."""
        pass


# Provider registry
_provider_registry: Dict[str, CloudProvider] = {}


def register_provider(provider: CloudProvider):
    """Register a provider instance."""
    _provider_registry[provider.name] = provider


def get_provider(name: str) -> Optional[CloudProvider]:
    """Get a registered provider by name."""
    return _provider_registry.get(name)


def get_all_providers() -> Dict[str, CloudProvider]:
    """Get all registered providers."""
    return _provider_registry.copy()


def get_configured_providers() -> Dict[str, CloudProvider]:
    """Get only providers that are properly configured."""
    return {
        name: provider 
        for name, provider in _provider_registry.items() 
        if provider.is_configured()
    }
