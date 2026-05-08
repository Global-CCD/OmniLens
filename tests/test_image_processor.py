"""
OmniLens v3.0 - Image Processor Tests
Tests for EXIF extraction, GPS parsing, and format detection.
"""

import pytest
from datetime import datetime
from utils.image_processor import (
    extract_metadata_from_bytes,
    compute_file_hash,
    _get_dimensions_from_header
)


class TestExtractMetadata:
    def test_empty_bytes(self):
        result = extract_metadata_from_bytes(b"")
        assert result["width"] is None
        assert result["height"] is None

    def test_invalid_bytes(self):
        result = extract_metadata_from_bytes(b"not an image")
        assert result["width"] is None
        assert result["height"] is None

    def test_compute_hash(self):
        data = b"test image data"
        hash1 = compute_file_hash(data)
        hash2 = compute_file_hash(data)
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length


class TestHeaderParsing:
    def test_jpeg_header(self):
        # Minimal JPEG header: SOI + APP0 marker
        jpeg_header = bytes([
            0xFF, 0xD8,  # SOI
            0xFF, 0xE0,  # APP0
            0x00, 0x10,  # Length
            0x4A, 0x46, 0x49, 0x46, 0x00,  # JFIF
            0x01, 0x01,  # Version
            0x00,        # Units
            0x00, 0x01,  # X density
            0x00, 0x01,  # Y density
            0x00, 0x00,  # Thumbnail
            0xFF, 0xC0,  # SOF0
            0x00, 0x0B,  # Length
            0x08,        # Precision
            0x00, 0x10,  # Height (16)
            0x00, 0x20,  # Width (32)
        ])
        dims = _get_dimensions_from_header(jpeg_header)
        assert dims == (32, 16)

    def test_png_header(self):
        png_header = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D,  # IHDR length
            0x49, 0x48, 0x44, 0x52,  # IHDR
            0x00, 0x00, 0x01, 0x00,  # Width (256)
            0x00, 0x00, 0x00, 0x80,  # Height (128)
        ])
        dims = _get_dimensions_from_header(png_header)
        assert dims == (256, 128)
