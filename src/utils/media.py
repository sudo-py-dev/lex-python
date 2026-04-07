import json
import os
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

DEFAULT_WATERMARK_COLOR = "white"
DEFAULT_WATERMARK_STYLE = "soft_shadow"
SUPPORTED_WATERMARK_COLORS = {"white", "black", "red", "blue", "gold"}
SUPPORTED_WATERMARK_STYLES = {
    "soft_shadow",
    "outline",
    "clean",
    "pattern_grid",
    "pattern_diagonal",
}


@dataclass(slots=True)
class WatermarkConfig:
    text: str = ""
    color: str = DEFAULT_WATERMARK_COLOR
    style: str = DEFAULT_WATERMARK_STYLE


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


def parse_watermark_config(raw_value: str | None) -> WatermarkConfig:
    """Parse strict JSON watermark config into typed fields."""
    if not raw_value:
        return WatermarkConfig()

    try:
        payload = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return WatermarkConfig()

    if not isinstance(payload, dict):
        return WatermarkConfig()

    color = str(payload.get("color", DEFAULT_WATERMARK_COLOR))
    style = str(payload.get("style", DEFAULT_WATERMARK_STYLE))
    return WatermarkConfig(
        text=str(payload.get("text", "")),
        color=color if color in SUPPORTED_WATERMARK_COLORS else DEFAULT_WATERMARK_COLOR,
        style=style if style in SUPPORTED_WATERMARK_STYLES else DEFAULT_WATERMARK_STYLE,
    )


def build_watermark_config(
    text: str,
    color: str = DEFAULT_WATERMARK_COLOR,
    style: str = DEFAULT_WATERMARK_STYLE,
) -> str:
    payload = {"text": text, "color": color, "style": style}
    return json.dumps(payload)


def apply_watermark(
    image_path: str,
    text: str,
    output_path: str,
    color: str = DEFAULT_WATERMARK_COLOR,
    style: str = DEFAULT_WATERMARK_STYLE,
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
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            width, height = img.size

            font_size = max(20, int(width * 0.04))

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

            measure_draw = ImageDraw.Draw(img)
            left, top, right, bottom = measure_draw.textbbox((0, 0), text, font=font)
            text_width = max(1, right - left)
            text_height = max(1, bottom - top)

            margin = int(width * 0.02)
            x = width - text_width - margin
            y = height - text_height - margin

            palette = {
                "white": (255, 255, 255),
                "black": (0, 0, 0),
                "red": (255, 60, 60),
                "blue": (80, 160, 255),
                "gold": (255, 200, 60),
            }
            fill_color = palette.get(color, palette["white"])
            shadow_offset = max(1, int(font_size * 0.05))
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            main_fill = (*fill_color, 190)
            shadow_fill = (0, 0, 0, 145)

            def draw_text_effect(target_draw: ImageDraw.ImageDraw, px: int, py: int, st: str) -> None:
                if st in ("soft_shadow", "pattern_grid", "pattern_diagonal", "outline"):
                    target_draw.text((px + shadow_offset, py + shadow_offset), text, font=font, fill=shadow_fill)
                if st == "outline":
                    target_draw.text((px - shadow_offset, py), text, font=font, fill=shadow_fill)
                    target_draw.text((px + shadow_offset, py), text, font=font, fill=shadow_fill)
                    target_draw.text((px, py - shadow_offset), text, font=font, fill=shadow_fill)
                    target_draw.text((px, py + shadow_offset), text, font=font, fill=shadow_fill)
                target_draw.text((px, py), text, font=font, fill=main_fill)

            if style in ("pattern_grid", "pattern_diagonal"):
                step_x = max(text_width + margin * 2, int(width * 0.2))
                step_y = max(text_height + margin * 2, int(height * 0.15))
                offset = step_x // 2 if style == "pattern_diagonal" else 0
                yy = -step_y
                row = 0
                while yy < height + step_y:
                    xx = -step_x + (offset if row % 2 else 0)
                    while xx < width + step_x:
                        draw_text_effect(draw, xx, yy, style)
                        xx += step_x
                    yy += step_y
                    row += 1
            else:
                draw_text_effect(
                    draw,
                    x,
                    y,
                    style if style in ("soft_shadow", "outline", "clean") else "soft_shadow",
                )

            out = Image.alpha_composite(img, overlay).convert("RGB")
            out.save(output_path, "JPEG", quality=90)
            return True
    except Exception as e:
        print(f"Error applying watermark: {e}")
        return False
