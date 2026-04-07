import os
import json

from PIL import Image, ImageDraw, ImageFont


def _detect_script(text: str) -> str:
    for ch in text:
        code = ord(ch)
        if 0x0600 <= code <= 0x06FF or 0x0750 <= code <= 0x077F or 0x08A0 <= code <= 0x08FF:
            return "arabic"
        if 0x0590 <= code <= 0x05FF:
            return "hebrew"
        if 0x0900 <= code <= 0x097F:
            return "devanagari"
        if (
            0x3040 <= code <= 0x30FF  # Japanese kana
            or 0x4E00 <= code <= 0x9FFF  # CJK unified ideographs
            or 0xAC00 <= code <= 0xD7AF  # Hangul
        ):
            return "cjk"
    return "latin"


def _font_candidates(script: str) -> list[str]:
    project_fonts = {
        "arabic": [
            os.path.join("assets", "fonts", "NotoSansArabic-Bold.ttf"),
            os.path.join("assets", "fonts", "NotoSansArabic-Regular.ttf"),
        ],
        "hebrew": [
            os.path.join("assets", "fonts", "NotoSansHebrew-Bold.ttf"),
            os.path.join("assets", "fonts", "NotoSansHebrew-Regular.ttf"),
        ],
        "devanagari": [
            os.path.join("assets", "fonts", "NotoSansDevanagari-Bold.ttf"),
            os.path.join("assets", "fonts", "NotoSansDevanagari-Regular.ttf"),
        ],
        "cjk": [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ],
        "latin": [
            os.path.join("assets", "fonts", "DejaVuSans-Bold.ttf"),
            os.path.join("assets", "fonts", "LiberationSans-Bold.ttf"),
            os.path.join("assets", "fonts", "DejaVuSans.ttf"),
        ],
    }
    common_fallbacks = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "arial.ttf",
    ]
    return project_fonts.get(script, []) + project_fonts["latin"] + common_fallbacks


def parse_watermark_config(raw_value: str | None) -> dict[str, str]:
    """Parse legacy/plain watermark text or JSON config."""
    default = {
        "text": raw_value or "",
        "type": "text",
        "color": "white",
        "style": "shadow",
        "location": "bottom_right",
    }
    if not raw_value:
        return default
    try:
        if str(raw_value).lstrip().startswith("{"):
            payload = json.loads(str(raw_value))
            return {
                "text": str(payload.get("text", "")),
                "type": str(payload.get("type", "text")),
                "color": str(payload.get("color", "white")),
                "style": str(payload.get("style", "shadow")),
                "location": str(payload.get("location", "bottom_right")),
            }
    except Exception:
        pass
    return default


def build_watermark_config(
    text: str,
    wm_type: str = "text",
    color: str = "white",
    style: str = "shadow",
    location: str = "bottom_right",
) -> str:
    return json.dumps(
        {"text": text, "type": wm_type, "color": color, "style": style, "location": location}
    )


def apply_watermark(
    image_path: str,
    text: str,
    output_path: str,
    color: str = "white",
    style: str = "shadow",
    location: str = "bottom_right",
) -> bool:
    """
    Apply a text watermark to an image.
    :param image_path: Path to the source image.
    :param text: Watermark text (e.g., '@MyChannel').
    :param output_path: Path to save the watermarked image.
    :return: True if successful, False otherwise.
    """
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (e.g. RGBA or Palette)
            if img.mode != "RGB":
                img = img.convert("RGB")

            draw = ImageDraw.Draw(img)
            width, height = img.size

            # Adaptive font size (3% of image width)
            font_size = max(20, int(width * 0.04))

            # Prefer project-managed fonts, then system fallback.
            try:
                script = _detect_script(text)
                font_paths = _font_candidates(script)
                font = None
                for path in font_paths:
                    if os.path.exists(path):
                        font = ImageFont.truetype(path, font_size)
                        break
                if not font:
                    font = ImageFont.load_default()
            except Exception:
                font = ImageFont.load_default()

            # Measure text size using textbbox (Pillow 9.2.0+)
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            text_width = right - left
            text_height = bottom - top

            margin = int(width * 0.02)
            positions = {
                "top_left": (margin, margin),
                "top_center": ((width - text_width) // 2, margin),
                "top_right": (width - text_width - margin, margin),
                "center": ((width - text_width) // 2, (height - text_height) // 2),
                "bottom_left": (margin, height - text_height - margin),
                "bottom_center": ((width - text_width) // 2, height - text_height - margin),
                "bottom_right": (width - text_width - margin, height - text_height - margin),
            }
            x, y = positions.get(location, positions["bottom_right"])

            palette = {
                "white": (255, 255, 255),
                "black": (0, 0, 0),
                "red": (255, 60, 60),
                "blue": (80, 160, 255),
                "gold": (255, 200, 60),
            }
            fill_color = palette.get(color, palette["white"])
            shadow_offset = max(1, int(font_size * 0.05))
            if style in ("shadow", "outline"):
                draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(0, 0, 0))
            if style == "outline":
                draw.text((x - shadow_offset, y), text, font=font, fill=(0, 0, 0))
                draw.text((x + shadow_offset, y), text, font=font, fill=(0, 0, 0))
                draw.text((x, y - shadow_offset), text, font=font, fill=(0, 0, 0))
                draw.text((x, y + shadow_offset), text, font=font, fill=(0, 0, 0))

            # Draw main text
            draw.text((x, y), text, font=font, fill=fill_color)

            img.save(output_path, "JPEG", quality=90)
            return True
    except Exception as e:
        print(f"Error applying watermark: {e}")
        return False
