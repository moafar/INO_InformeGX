"""Small valid PNG fixtures containing synthetic pixels only."""

from __future__ import annotations

import struct
import zlib


def synthetic_png(red: int = 0) -> bytes:
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + chunk_type
            + data
            + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    scanline = bytes((0, red, 0, 0, 255))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(
        b"IDAT", zlib.compress(scanline)
    ) + chunk(b"IEND", b"")
