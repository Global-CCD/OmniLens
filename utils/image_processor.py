"""
OmniLens v3.0 - Enhanced Image Metadata Extractor
Extracts comprehensive EXIF data including GPS, camera settings, timestamps.
Supports JPEG, PNG, WebP, HEIC, and basic RAW formats.
"""

from PIL import Image, ExifTags
from PIL.ExifTags import GPSTAGS
from io import BytesIO
from typing import Optional, Dict, Any
from datetime import datetime
import struct

# Try to import HEIC support
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORT = True
except ImportError:
    HEIC_SUPPORT = False

# Try to import RAW support
try:
    import rawpy
    RAW_SUPPORT = True
except ImportError:
    RAW_SUPPORT = False


# EXIF tag mappings
EXIF_TAG_MAP = {
    "Make": 0x010F,
    "Model": 0x0110,
    "DateTimeOriginal": 0x9003,
    "DateTimeDigitized": 0x9004,
    "ExposureTime": 0x829A,
    "FNumber": 0x829D,
    "ISOSpeedRatings": 0x8827,
    "FocalLength": 0x920A,
    "LensModel": 0xA434,
    "LensSpecification": 0xA432,
    "Orientation": 0x0112,
    "Software": 0x0131,
}

GPS_TAG_MAP = {
    "GPSLatitudeRef": 1,
    "GPSLatitude": 2,
    "GPSLongitudeRef": 3,
    "GPSLongitude": 4,
    "GPSAltitudeRef": 5,
    "GPSAltitude": 6,
    "GPSTimeStamp": 7,
    "GPSDateStamp": 29,
}


def extract_metadata_from_bytes(image_bytes: bytes) -> Dict[str, Any]:
    """
    Extract comprehensive metadata from image bytes.

    Args:
        image_bytes: Raw image file bytes (can be partial for some formats)

    Returns:
        Dictionary with width, height, format, camera info, GPS, timestamps
    """
    result = {
        "width": None,
        "height": None,
        "format": None,
        "camera_make": None,
        "camera_model": None,
        "lens_model": None,
        "focal_length": None,
        "iso": None,
        "aperture": None,
        "shutter_speed": None,
        "orientation": None,
        "gps_lat": None,
        "gps_lon": None,
        "gps_alt": None,
        "taken_at": None,
        "software": None,
    }

    if not image_bytes or len(image_bytes) < 100:
        return result

    try:
        img = Image.open(BytesIO(image_bytes))
        result["width"] = img.width
        result["height"] = img.height
        result["format"] = img.format

        # Extract EXIF
        exif = img.getexif()
        if exif:
            result.update(_extract_exif_data(exif))

            # Extract GPS from EXIF
            gps_info = exif.get_ifd(ExifTags.IFD.GPSInfo)
            if gps_info:
                result.update(_extract_gps_data(gps_info))

        # Try to get more detailed EXIF via img.info for some formats
        if "exif" in img.info:
            # Already handled above
            pass

        img.close()

    except Exception as e:
        # Log but don't fail - partial bytes might still give dimensions
        print(f"[ImageProcessor] Processing error: {e}")
        # Try to get at least dimensions from header
        try:
            dims = _get_dimensions_from_header(image_bytes)
            if dims:
                result["width"], result["height"] = dims
        except:
            pass

    return result


def _extract_exif_data(exif) -> Dict[str, Any]:
    """Extract standard EXIF tags."""
    data = {}

    # Camera make/model
    make = exif.get(EXIF_TAG_MAP["Make"])
    model = exif.get(EXIF_TAG_MAP["Model"])
    data["camera_make"] = make.strip() if make else None
    data["camera_model"] = model.strip() if model else None

    # Lens
    lens = exif.get(EXIF_TAG_MAP["LensModel"])
    data["lens_model"] = lens.strip() if lens else None

    # Camera settings
    focal = exif.get(EXIF_TAG_MAP["FocalLength"])
    if focal:
        data["focal_length"] = float(focal) if isinstance(focal, (int, float)) else None

    iso = exif.get(EXIF_TAG_MAP["ISOSpeedRatings"])
    if iso:
        data["iso"] = int(iso) if isinstance(iso, (int, float)) else None

    aperture = exif.get(EXIF_TAG_MAP["FNumber"])
    if aperture:
        data["aperture"] = float(aperture) if isinstance(aperture, (int, float)) else None

    exposure = exif.get(EXIF_TAG_MAP["ExposureTime"])
    if exposure:
        if isinstance(exposure, tuple) and len(exposure) == 2:
            num, den = exposure
            if den == 1:
                data["shutter_speed"] = f"{num}s"
            else:
                data["shutter_speed"] = f"{num}/{den}s"
        elif isinstance(exposure, (int, float)):
            data["shutter_speed"] = f"{exposure}s"

    # Orientation
    orient = exif.get(EXIF_TAG_MAP["Orientation"])
    if orient:
        data["orientation"] = int(orient)

    # Software
    software = exif.get(EXIF_TAG_MAP["Software"])
    if software:
        data["software"] = software.strip()

    # Timestamp
    dt_str = exif.get(EXIF_TAG_MAP["DateTimeOriginal"])
    if not dt_str:
        dt_str = exif.get(EXIF_TAG_MAP["DateTimeDigitized"])

    if dt_str:
        try:
            # EXIF datetime format: "2024:01:15 14:30:00"
            data["taken_at"] = datetime.strptime(str(dt_str), "%Y:%m:%d %H:%M:%S")
        except ValueError:
            pass

    return data


def _extract_gps_data(gps_ifd) -> Dict[str, Any]:
    """Extract GPS coordinates from GPSInfo IFD."""
    data = {}

    def _convert_dms(dms):
        """Convert DMS tuple to decimal degrees."""
        if not dms or len(dms) != 3:
            return None
        degrees = float(dms[0])
        minutes = float(dms[1])
        seconds = float(dms[2])
        return degrees + minutes / 60 + seconds / 3600

    # Latitude
    lat_ref = gps_ifd.get(GPS_TAG_MAP["GPSLatitudeRef"])
    lat_dms = gps_ifd.get(GPS_TAG_MAP["GPSLatitude"])
    if lat_dms:
        lat = _convert_dms(lat_dms)
        if lat is not None and lat_ref == "S":
            lat = -lat
        data["gps_lat"] = round(lat, 6) if lat is not None else None

    # Longitude
    lon_ref = gps_ifd.get(GPS_TAG_MAP["GPSLongitudeRef"])
    lon_dms = gps_ifd.get(GPS_TAG_MAP["GPSLongitude"])
    if lon_dms:
        lon = _convert_dms(lon_dms)
        if lon is not None and lon_ref == "W":
            lon = -lon
        data["gps_lon"] = round(lon, 6) if lon is not None else None

    # Altitude
    alt_ref = gps_ifd.get(GPS_TAG_MAP["GPSAltitudeRef"], 0)
    alt = gps_ifd.get(GPS_TAG_MAP["GPSAltitude"])
    if alt is not None:
        data["gps_alt"] = float(alt) if alt_ref == 0 else -float(alt)

    # GPS timestamp (supplement to regular timestamp)
    gps_time = gps_ifd.get(GPS_TAG_MAP["GPSTimeStamp"])
    gps_date = gps_ifd.get(GPS_TAG_MAP["GPSDateStamp"])
    if gps_time and gps_date:
        try:
            # GPS date format: "2024:01:15"
            # GPS time: (hour, minute, second) tuple
            if isinstance(gps_time, tuple) and len(gps_time) == 3:
                hour, minute, second = [float(t) for t in gps_time]
                dt = datetime.strptime(str(gps_date), "%Y:%m:%d")
                dt = dt.replace(hour=int(hour), minute=int(minute), second=int(second))
                data["taken_at"] = dt
        except (ValueError, TypeError):
            pass

    return data


def _get_dimensions_from_header(image_bytes: bytes) -> Optional[tuple]:
    """
    Try to get image dimensions from file header without full parsing.
    Supports JPEG, PNG, GIF, WebP.
    """
    if len(image_bytes) < 24:
        return None

    # JPEG
    if image_bytes[:2] == b'\xff\xd8':
        return _get_jpeg_dimensions(image_bytes)

    # PNG
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        width = struct.unpack(">I", image_bytes[16:20])[0]
        height = struct.unpack(">I", image_bytes[20:24])[0]
        return (width, height)

    # GIF
    if image_bytes[:6] in (b'GIF87a', b'GIF89a'):
        width = struct.unpack("<H", image_bytes[6:8])[0]
        height = struct.unpack("<H", image_bytes[8:10])[0]
        return (width, height)

    # WebP
    if image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        return _get_webp_dimensions(image_bytes)

    return None


def _get_jpeg_dimensions(image_bytes: bytes) -> Optional[tuple]:
    """Extract dimensions from JPEG SOF markers."""
    offset = 2
    while offset < len(image_bytes):
        if image_bytes[offset] != 0xFF:
            offset += 1
            continue

        marker = image_bytes[offset + 1]

        # Skip padding
        if marker == 0xFF:
            offset += 1
            continue

        # SOF markers (0xC0-0xCF except 0xC4, 0xC8, 0xCC)
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            if offset + 9 < len(image_bytes):
                height = struct.unpack(">H", image_bytes[offset + 5:offset + 7])[0]
                width = struct.unpack(">H", image_bytes[offset + 7:offset + 9])[0]
                return (width, height)

        # Skip marker segment
        if marker == 0xD9:  # EOI
            break

        if marker == 0xD8:  # SOI
            offset += 2
            continue

        if offset + 3 < len(image_bytes):
            length = struct.unpack(">H", image_bytes[offset + 2:offset + 4])[0]
            offset += 2 + length
        else:
            break

    return None


def _get_webp_dimensions(image_bytes: bytes) -> Optional[tuple]:
    """Extract dimensions from WebP VP8 chunk."""
    if len(image_bytes) < 30:
        return None

    chunk_type = image_bytes[12:16]

    if chunk_type == b'VP8 ':
        # Simple lossy
        if len(image_bytes) >= 30:
            bits = struct.unpack("<I", image_bytes[26:30])[0]
            width = bits & 0x3FFF
            height = (bits >> 16) & 0x3FFF
            return (width, height)

    elif chunk_type == b'VP8L':
        # Lossless
        if len(image_bytes) >= 30:
            bits = struct.unpack("<I", image_bytes[25:29])[0]
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return (width, height)

    elif chunk_type == b'VP8X':
        # Extended
        if len(image_bytes) >= 30:
            width = struct.unpack("<I", image_bytes[24:27] + b'\x00')[0] + 1
            height = struct.unpack("<I", image_bytes[27:30] + b'\x00')[0] + 1
            return (width, height)

    return None


def compute_file_hash(image_bytes: bytes) -> str:
    """Compute SHA-256 hash of image bytes for deduplication."""
    return hashlib.sha256(image_bytes).hexdigest()
