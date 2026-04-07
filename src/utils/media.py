import os
import json

from PIL import Image, ImageDraw, ImageFont


def parse_watermark_config(raw_value: str | None) -> dict[str, str]:
    """Parse legacy/plain watermark text or JSON config."""
    default = {"text": raw_value or "", "type": "text", "color": "white", "style": "shadow"}
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
            }
    except Exception:
        pass
    return default


def build_watermark_config(
    text: str, wm_type: str = "text", color: str = "white", style: str = "shadow"
) -> str:
    return json.dumps({"text": text, "type": wm_type, "color": color, "style": style})


def apply_watermark(
    image_path: str,
    text: str,
    output_path: str,
    color: str = "white",
    style: str = "shadow",
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

            # Try to load a font, fallback to default
            try:
                # Common linux fonts paths
                font_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                    "arial.ttf",
                ]
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

            # Position: Bottom-Right with margin
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
