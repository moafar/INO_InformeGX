"""Session-backed presentation data for the authenticated user's PDF signature."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import struct
from typing import Protocol
import zlib

from flask import session


SIGNATURE_PROFILE_SESSION_KEY = "_pdf_signature_profile"
PNG_MIME_TYPE = "image/png"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_SIGNATURE_IMAGE_BYTES = 1024 * 1024
MAX_DECOMPRESSED_SIGNATURE_BYTES = 64 * 1024 * 1024


class SignatureImageValidationError(ValueError):
    pass


class _SignatureUser(Protocol):
    full_name: str
    signature_name: str | None
    profession_specialty: str | None
    professional_registration: str | None
    institutional_line: str | None


@dataclass(frozen=True, slots=True)
class SignatureProfile:
    """Trusted signature footer values loaded from the authentication source."""

    name: str
    profession_specialty: str = ""
    professional_registration: str = ""
    institutional_line: str = ""


def _invalid_png() -> SignatureImageValidationError:
    return SignatureImageValidationError("El archivo debe ser un PNG válido.")


def _png_row_lengths(width: int, height: int, bits_per_pixel: int, interlace: int) -> list[int]:
    if interlace == 0:
        return [(width * bits_per_pixel + 7) // 8] * height
    rows: list[int] = []
    for x_start, y_start, x_step, y_step in (
        (0, 0, 8, 8),
        (4, 0, 8, 8),
        (0, 4, 4, 8),
        (2, 0, 4, 4),
        (0, 2, 2, 4),
        (1, 0, 2, 2),
        (0, 1, 1, 2),
    ):
        pass_width = max(0, (width - x_start + x_step - 1) // x_step)
        pass_height = max(0, (height - y_start + y_step - 1) // y_step)
        if pass_width:
            rows.extend([(pass_width * bits_per_pixel + 7) // 8] * pass_height)
    return rows


def validate_signature_png(content: bytes) -> bytes:
    """Validate PNG structure, checksums and compressed scanlines."""
    if not content:
        raise SignatureImageValidationError("Seleccione un archivo PNG.")
    if len(content) > MAX_SIGNATURE_IMAGE_BYTES:
        raise SignatureImageValidationError("La firma manuscrita no puede superar 1 MB.")
    if not content.startswith(PNG_SIGNATURE):
        raise _invalid_png()

    position = len(PNG_SIGNATURE)
    ihdr: tuple[int, int, int, int, int] | None = None
    compressed = bytearray()
    saw_iend = False
    saw_plte = False
    saw_idat = False
    idat_ended = False
    chunk_index = 0
    while position < len(content):
        if position + 12 > len(content):
            raise _invalid_png()
        length = struct.unpack(">I", content[position : position + 4])[0]
        chunk_type = content[position + 4 : position + 8]
        data_start = position + 8
        data_end = data_start + length
        chunk_end = data_end + 4
        if chunk_end > len(content):
            raise _invalid_png()
        chunk_data = content[data_start:data_end]
        stored_crc = struct.unpack(">I", content[data_end:chunk_end])[0]
        if zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF != stored_crc:
            raise _invalid_png()
        if chunk_index == 0 and chunk_type != b"IHDR":
            raise _invalid_png()
        if chunk_type not in {b"IHDR", b"PLTE", b"IDAT", b"IEND"} and not (
            chunk_type[0] & 0x20
        ):
            raise _invalid_png()
        if chunk_type == b"IHDR":
            if ihdr is not None or length != 13:
                raise _invalid_png()
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", chunk_data
            )
            valid_depths = {
                0: {1, 2, 4, 8, 16},
                2: {8, 16},
                3: {1, 2, 4, 8},
                4: {8, 16},
                6: {8, 16},
            }
            if (
                width == 0
                or height == 0
                or bit_depth not in valid_depths.get(color_type, set())
                or compression != 0
                or filtering != 0
                or interlace not in {0, 1}
            ):
                raise _invalid_png()
            ihdr = (width, height, bit_depth, color_type, interlace)
        elif chunk_type == b"PLTE":
            if (
                ihdr is None
                or saw_plte
                or saw_idat
                or length == 0
                or length > 768
                or length % 3
                or ihdr[3] in {0, 4}
                or (ihdr[3] == 3 and length // 3 > 2 ** ihdr[2])
            ):
                raise _invalid_png()
            saw_plte = True
        elif chunk_type == b"IDAT":
            if (
                ihdr is None
                or saw_iend
                or idat_ended
                or (ihdr[3] == 3 and not saw_plte)
            ):
                raise _invalid_png()
            saw_idat = True
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            if length != 0 or saw_iend:
                raise _invalid_png()
            saw_iend = True
            position = chunk_end
            if position != len(content):
                raise _invalid_png()
            break
        elif saw_idat:
            idat_ended = True
        position = chunk_end
        chunk_index += 1

    if ihdr is None or not compressed or not saw_iend:
        raise _invalid_png()
    width, height, bit_depth, color_type, interlace = ihdr
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_lengths = _png_row_lengths(width, height, bit_depth * channels, interlace)
    expected_size = sum(row_length + 1 for row_length in row_lengths)
    if expected_size > MAX_DECOMPRESSED_SIGNATURE_BYTES:
        raise _invalid_png()
    try:
        decompressor = zlib.decompressobj()
        decoded = decompressor.decompress(bytes(compressed), expected_size + 1)
        decoded += decompressor.flush()
    except zlib.error as error:
        raise _invalid_png() from error
    if (
        not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
        or len(decoded) != expected_size
    ):
        raise _invalid_png()
    offset = 0
    for row_length in row_lengths:
        if decoded[offset] > 4:
            raise _invalid_png()
        offset += row_length + 1
    return content


def _clean(value: object, *, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def signature_profile_for_user(user: _SignatureUser) -> SignatureProfile:
    """Build the database-backed profile, falling back only to full_name."""
    fallback_name = _clean(user.full_name, limit=200) or "Profesional responsable"
    return SignatureProfile(
        name=_clean(user.signature_name, limit=200) or fallback_name,
        profession_specialty=_clean(user.profession_specialty, limit=200),
        professional_registration=_clean(user.professional_registration, limit=120),
        institutional_line=_clean(user.institutional_line, limit=300),
    )


def store_signature_profile_in_session(user: _SignatureUser) -> None:
    """Store a trusted, bounded profile when authentication is established."""
    session[SIGNATURE_PROFILE_SESSION_KEY] = asdict(signature_profile_for_user(user))


def signature_profile_from_session(user: _SignatureUser) -> SignatureProfile:
    """Read the authenticated session profile without consulting clinical input."""
    stored = session.get(SIGNATURE_PROFILE_SESSION_KEY)
    if not isinstance(stored, dict):
        profile = signature_profile_for_user(user)
        session[SIGNATURE_PROFILE_SESSION_KEY] = asdict(profile)
        return profile

    fallback = signature_profile_for_user(user)
    return SignatureProfile(
        name=_clean(stored.get("name"), limit=200) or fallback.name,
        profession_specialty=_clean(
            stored.get("profession_specialty"),
            limit=200,
        ),
        professional_registration=_clean(
            stored.get("professional_registration"),
            limit=120,
        ),
        institutional_line=_clean(stored.get("institutional_line"), limit=300),
    )


def clear_signature_profile_from_session() -> None:
    session.pop(SIGNATURE_PROFILE_SESSION_KEY, None)
