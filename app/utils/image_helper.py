from __future__ import annotations

import base64
import re
import struct


SUPPORTED_IMAGE_FORMATS_MESSAGE = "Unsupported image format. Only JPG, JPEG, PNG, WEBP, GIF, BMP, SVG, and ICO are allowed"


def get_png_dimensions(content: bytes) -> tuple[int, int] | None:
    if len(content) < 24 or content[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    width = int.from_bytes(content[16:20], "big")
    height = int.from_bytes(content[20:24], "big")
    return width, height


def get_jpeg_dimensions(content: bytes) -> tuple[int, int] | None:
    if len(content) < 4 or content[0:2] != b"\xff\xd8":
        return None

    index = 2
    while index + 9 < len(content):
        if content[index] != 0xFF:
            index += 1
            continue

        marker = content[index + 1]
        index += 2

        if marker in {0xD8, 0xD9}:
            continue
        if marker == 0xDA:
            break
        if index + 2 > len(content):
            return None

        segment_length = struct.unpack(">H", content[index:index + 2])[0]
        if segment_length < 2 or index + segment_length > len(content):
            return None

        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if index + 7 > len(content):
                return None
            height = struct.unpack(">H", content[index + 3:index + 5])[0]
            width = struct.unpack(">H", content[index + 5:index + 7])[0]
            return width, height

        index += segment_length

    return None


def get_gif_dimensions(content: bytes) -> tuple[int, int] | None:
    if len(content) < 10 or content[:6] not in {b"GIF87a", b"GIF89a"}:
        return None
    width = int.from_bytes(content[6:8], "little")
    height = int.from_bytes(content[8:10], "little")
    return width, height


def get_webp_dimensions(content: bytes) -> tuple[int, int] | None:
    if len(content) < 30 or content[:4] != b"RIFF" or content[8:12] != b"WEBP":
        return None

    chunk_type = content[12:16]

    if chunk_type == b"VP8 ":
        if len(content) < 30:
            return None
        if content[23:26] != b"\x9d\x01\x2a":
            return None
        width = struct.unpack("<H", content[26:28])[0] & 0x3FFF
        height = struct.unpack("<H", content[28:30])[0] & 0x3FFF
        return width, height

    if chunk_type == b"VP8L":
        if len(content) < 25:
            return None
        if content[20] != 0x2F:
            return None
        bits = int.from_bytes(content[21:25], "little")
        width = (bits & 0x3FFF) + 1
        height = ((bits >> 14) & 0x3FFF) + 1
        return width, height

    if chunk_type == b"VP8X":
        if len(content) < 30:
            return None
        width = 1 + int.from_bytes(content[24:27], "little")
        height = 1 + int.from_bytes(content[27:30], "little")
        return width, height

    return None


def get_bmp_dimensions(content: bytes) -> tuple[int, int] | None:
    if len(content) < 26 or content[:2] != b"BM":
        return None
    dib_header_size = int.from_bytes(content[14:18], "little")
    if dib_header_size < 12:
        return None
    if dib_header_size >= 40:
        width = int.from_bytes(content[18:22], "little", signed=True)
        height = int.from_bytes(content[22:26], "little", signed=True)
        return abs(width), abs(height)
    width = int.from_bytes(content[18:20], "little")
    height = int.from_bytes(content[20:22], "little")
    return width, height


def _parse_svg_length_to_int(value: str | None) -> int | None:
    if value is None:
        return None
    match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)", value)
    if not match:
        return None
    try:
        number = float(match.group(1))
    except ValueError:
        return None
    if number <= 0:
        return None
    return int(round(number))


def get_svg_dimensions(content: bytes) -> tuple[int, int] | None:
    try:
        head = content[:4096].decode("utf-8", errors="ignore")
    except Exception:
        return None
    if "<svg" not in head.lower():
        return None

    width_match = re.search(r'\bwidth\s*=\s*"([^"]+)"', head, re.IGNORECASE)
    height_match = re.search(r'\bheight\s*=\s*"([^"]+)"', head, re.IGNORECASE)
    width = _parse_svg_length_to_int(width_match.group(1) if width_match else None)
    height = _parse_svg_length_to_int(height_match.group(1) if height_match else None)
    if width is not None and height is not None:
        return width, height

    view_box_match = re.search(r'\bviewBox\s*=\s*"([^"]+)"', head, re.IGNORECASE)
    if not view_box_match:
        return None
    try:
        parts = [float(part) for part in re.split(r"[\s,]+", view_box_match.group(1).strip()) if part]
    except ValueError:
        return None
    if len(parts) != 4:
        return None
    if parts[2] <= 0 or parts[3] <= 0:
        return None
    return int(round(parts[2])), int(round(parts[3]))


def get_ico_dimensions(content: bytes) -> tuple[int, int] | None:
    if len(content) < 14:
        return None
    reserved = int.from_bytes(content[0:2], "little")
    image_type = int.from_bytes(content[2:4], "little")
    image_count = int.from_bytes(content[4:6], "little")
    if reserved != 0 or image_type != 1 or image_count < 1:
        return None
    width = content[6] or 256
    height = content[7] or 256
    return int(width), int(height)


def detect_image_info(content: bytes) -> tuple[str, int, int]:
    png = get_png_dimensions(content)
    if png is not None:
        return "image/png", png[0], png[1]

    jpeg = get_jpeg_dimensions(content)
    if jpeg is not None:
        return "image/jpeg", jpeg[0], jpeg[1]

    gif = get_gif_dimensions(content)
    if gif is not None:
        return "image/gif", gif[0], gif[1]

    webp = get_webp_dimensions(content)
    if webp is not None:
        return "image/webp", webp[0], webp[1]

    bmp = get_bmp_dimensions(content)
    if bmp is not None:
        return "image/bmp", bmp[0], bmp[1]

    svg = get_svg_dimensions(content)
    if svg is not None:
        return "image/svg+xml", svg[0], svg[1]

    ico = get_ico_dimensions(content)
    if ico is not None:
        return "image/x-icon", ico[0], ico[1]

    raise ValueError(SUPPORTED_IMAGE_FORMATS_MESSAGE)


def build_data_url(*, mime_type: str, image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"
