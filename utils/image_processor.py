from PIL import Image, ExifTags
from io import BytesIO

def extract_metadata_from_bytes(image_bytes: bytes) -> dict:
    """
    Reads a chunk of image bytes and extracts basic metadata and EXIF.
    """
    try:
        # Load the byte stream into Pillow
        img = Image.open(BytesIO(image_bytes))
        width, height = img.size
        
        # Extract basic EXIF if available
        exif_data = img.getexif()
        camera_make = exif_data.get(0x010F) if exif_data else "Unknown" # 0x010F is standard Make tag
        camera_model = exif_data.get(0x0110) if exif_data else "Unknown"
        
        return {
            "width": width,
            "height": height,
            "format": img.format,
            "camera": f"{camera_make} {camera_model}".strip()
        }
    except Exception as e:
        print(f"Failed to process image chunk: {e}")
        return {"width": None, "height": None, "format": "Unknown", "camera": "Unknown"}
