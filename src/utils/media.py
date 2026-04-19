import base64
import io
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
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
SUPPORTED_VIDEO_WATERMARK_QUALITIES = {"high", "medium", "low"}
DEFAULT_VIDEO_WATERMARK_QUALITY = "medium"
SUPPORTED_VIDEO_WATERMARK_MOTIONS = {"static", "float", "scroll_lr", "scroll_rl"}
DEFAULT_VIDEO_WATERMARK_MOTION = "static"


def encode_image_to_base64(bio: io.BytesIO) -> str:
    """Encode an in-memory image buffer to Base64."""
    bio.seek(0)
    return base64.b64encode(bio.read()).decode("utf-8")


@dataclass(slots=True)
class WatermarkConfig:
    text: str = ""
    color: str = DEFAULT_WATERMARK_COLOR
    style: str = DEFAULT_WATERMARK_STYLE
    video_enabled: bool = False
    image_enabled: bool = True
    video_quality: str = DEFAULT_VIDEO_WATERMARK_QUALITY
    video_motion: str = DEFAULT_VIDEO_WATERMARK_MOTION


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
            Path("assets/fonts/NotoSansArabic-Bold.ttf"),
            Path("assets/fonts/NotoSansArabic-Regular.ttf"),
        ],
        "hebrew": [
            Path("assets/fonts/NotoSansHebrew-Bold.ttf"),
            Path("assets/fonts/NotoSansHebrew-Regular.ttf"),
        ],
        "devanagari": [
            Path("assets/fonts/NotoSansDevanagari-Bold.ttf"),
            Path("assets/fonts/NotoSansDevanagari-Regular.ttf"),
        ],
        "cjk": [
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        ],
        "latin": [
            Path("assets/fonts/DejaVuSans-Bold.ttf"),
            Path("assets/fonts/LiberationSans-Bold.ttf"),
            Path("assets/fonts/DejaVuSans.ttf"),
        ],
    }
    common_fallbacks = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("arial.ttf"),
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
    raw_vq = str(payload.get("video_quality", DEFAULT_VIDEO_WATERMARK_QUALITY))
    raw_vm = str(payload.get("video_motion", DEFAULT_VIDEO_WATERMARK_MOTION))

    return WatermarkConfig(
        text=str(payload.get("text", "")),
        color=color if color in SUPPORTED_WATERMARK_COLORS else DEFAULT_WATERMARK_COLOR,
        style=style if style in SUPPORTED_WATERMARK_STYLES else DEFAULT_WATERMARK_STYLE,
        video_enabled=bool(payload.get("video_enabled", False)),
        image_enabled=bool(payload.get("image_enabled", True)),
        video_quality=raw_vq
        if raw_vq in SUPPORTED_VIDEO_WATERMARK_QUALITIES
        else DEFAULT_VIDEO_WATERMARK_QUALITY,
        video_motion=raw_vm
        if raw_vm in SUPPORTED_VIDEO_WATERMARK_MOTIONS
        else DEFAULT_VIDEO_WATERMARK_MOTION,
    )


def build_watermark_config(
    text: str,
    color: str = DEFAULT_WATERMARK_COLOR,
    style: str = DEFAULT_WATERMARK_STYLE,
    video_enabled: bool = False,
    image_enabled: bool = True,
    video_quality: str = DEFAULT_VIDEO_WATERMARK_QUALITY,
    video_motion: str = DEFAULT_VIDEO_WATERMARK_MOTION,
) -> str:
    payload = {
        "text": text,
        "color": color,
        "style": style,
        "video_enabled": bool(video_enabled),
        "image_enabled": bool(image_enabled),
        "video_quality": (
            video_quality
            if video_quality in SUPPORTED_VIDEO_WATERMARK_QUALITIES
            else DEFAULT_VIDEO_WATERMARK_QUALITY
        ),
        "video_motion": (
            video_motion
            if video_motion in SUPPORTED_VIDEO_WATERMARK_MOTIONS
            else DEFAULT_VIDEO_WATERMARK_MOTION
        ),
    }
    return json.dumps(payload)


def _escape_ffmpeg_drawtext(value: str) -> str:
    return (
        value.replace("\\", r"\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace("%", r"\%")
        .replace(",", r"\,")
        .replace("[", r"\[")
        .replace("]", r"\]")
    )


def apply_video_watermark(
    video_path: str,
    text: str,
    output_path: str,
    color: str = DEFAULT_WATERMARK_COLOR,
    style: str = DEFAULT_WATERMARK_STYLE,
    quality: str = DEFAULT_VIDEO_WATERMARK_QUALITY,
    motion: str = DEFAULT_VIDEO_WATERMARK_MOTION,
) -> bool:
    """Apply a drawtext watermark to a video using ffmpeg."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return False

    palette = {
        "white": "white",
        "black": "black",
        "red": "0xff3c3c",
        "blue": "0x50a0ff",
        "gold": "0xffc83c",
    }
    font_color = palette.get(color, "white")
    shadow = "1" if style in ("soft_shadow", "outline", "pattern_grid", "pattern_diagonal") else "0"
    border = "2" if style == "outline" else "0"
    q = (
        quality
        if quality in SUPPORTED_VIDEO_WATERMARK_QUALITIES
        else DEFAULT_VIDEO_WATERMARK_QUALITY
    )
    m = motion if motion in SUPPORTED_VIDEO_WATERMARK_MOTIONS else DEFAULT_VIDEO_WATERMARK_MOTION
    quality_map = {
        "high": ("22", "medium"),
        "medium": ("28", "veryfast"),
        "low": ("33", "superfast"),
    }
    crf, preset = quality_map[q]

    script = _detect_script(text)
    fontfile = next((str(p) for p in _font_candidates(script) if p.exists()), "")
    text_escaped = _escape_ffmpeg_drawtext(text)
    if m == "float":
        x_expr = "(w-tw)/2+(w/3)*sin(t*0.7)"
        y_expr = "(h-th)/2+(h/4)*cos(t*0.9)"
    elif m == "scroll_lr":
        x_expr = "mod(t*140,w+tw)-tw"
        y_expr = "h-th-20"
    elif m == "scroll_rl":
        x_expr = "w-mod(t*140,w+tw)"
        y_expr = "h-th-20"
    else:
        x_expr = "w-tw-20"
        y_expr = "h-th-20"

    drawtext_parts = [
        f"text='{text_escaped}'",
        f"x={x_expr}",
        f"y={y_expr}",
        "fontsize=h/24",
        f"fontcolor={font_color}",
        "alpha=0.85",
    ]
    if fontfile:
        drawtext_parts.append(f"fontfile='{_escape_ffmpeg_drawtext(fontfile)}'")
    if shadow == "1":
        drawtext_parts.extend(["shadowx=2", "shadowy=2", "shadowcolor=black"])
    if border == "2":
        drawtext_parts.extend(["borderw=2", "bordercolor=black@0.7"])
    vf = "drawtext=" + ":".join(drawtext_parts)

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        video_path,
        "-vf",
        vf,
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        crf,
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        stderr_tail = (e.stderr or "").strip().splitlines()[-8:]
        logger.error(
            "[media] ffmpeg video watermark failed (code={}): {}",
            e.returncode,
            " | ".join(stderr_tail) if stderr_tail else "no stderr",
        )
        logger.debug("[media] ffmpeg command: {}", " ".join(cmd))
        return False
    except Exception as e:
        logger.error(f"[media] Unexpected video watermark error: {e}")
        return False


def apply_watermark(
    image_path: str,
    text: str,
    output_path: str,
    color: str = DEFAULT_WATERMARK_COLOR,
    style: str = DEFAULT_WATERMARK_STYLE,
    image_wm_path: str | None = None,
    position: str = "bottom_right",
    opacity: float = 0.7,
    scale: int = 10,
) -> bool:
    """
    Apply a text or image watermark to an image.
    :param image_path: Path to the source image.
    :param text: Watermark text (e.g., '@MyChannel').
    :param output_path: Path to save the watermarked image.
    :param color: Text color.
    :param style: Text style.
    :param image_wm_path: Path to the watermark image (optional).
    :param position: Watermark position.
    :param opacity: Watermark opacity (0.0 to 1.0).
    :param scale: Watermark size as percentage of source image width.
    :return: True if successful, False otherwise.
    """
    try:
        with Image.open(image_path) as img:
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            width, height = img.size
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)

            # --- Handle Image Watermark ---
            if image_wm_path and os.path.exists(image_wm_path):
                try:
                    with Image.open(image_wm_path) as wm_img:
                        if wm_img.mode != "RGBA":
                            wm_img = wm_img.convert("RGBA")

                        # Resize watermark based on scale percentage
                        wm_width = int(width * (scale / 100))
                        aspect_ratio = wm_img.height / wm_img.width
                        wm_height = int(wm_width * aspect_ratio)
                        wm_img = wm_img.resize((wm_width, wm_height), Image.Resampling.LANCZOS)

                        # Apply opacity
                        if opacity < 1.0:
                            alpha = wm_img.split()[3]
                            alpha = alpha.point(lambda p: int(p * opacity))
                            wm_img.putalpha(alpha)

                        # Calculate position
                        margin = int(width * 0.02)
                        if position == "top_left":
                            pos = (margin, margin)
                        elif position == "top_right":
                            pos = (width - wm_width - margin, margin)
                        elif position == "bottom_left":
                            pos = (margin, height - wm_height - margin)
                        elif position == "center":
                            pos = ((width - wm_width) // 2, (height - wm_height) // 2)
                        else:  # bottom_right
                            pos = (width - wm_width - margin, height - wm_height - margin)

                        overlay.paste(wm_img, pos, wm_img)
                except Exception as e:
                    logger.error(f"[media] Failed to apply image watermark: {e}")

            # --- Handle Text Watermark ---
            if text:
                font_size = (
                    max(20, int(width * (scale / 100) * 0.4))
                    if not image_wm_path
                    else max(20, int(width * 0.04))
                )

                try:
                    script = _detect_script(text)
                    font_paths = _font_candidates(script)
                    font = None
                    for path in font_paths:
                        if path.exists():
                            font = ImageFont.truetype(str(path), font_size)
                            break
                    if not font:
                        font = ImageFont.load_default()
                except Exception:
                    font = ImageFont.load_default()

                left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
                text_width = max(1, right - left)
                text_height = max(1, bottom - top)

                margin = int(width * 0.02)

                # If image watermark is present, we might want to place text below it or just skip
                # For now, let's just place text in its own position or default bottom_right
                if position == "top_left":
                    x, y = margin, margin
                elif position == "top_right":
                    x, y = width - text_width - margin, margin
                elif position == "bottom_left":
                    x, y = margin, height - text_height - margin
                elif position == "center":
                    x, y = (width - text_width) // 2, (height - text_height) // 2
                else:  # bottom_right
                    x, y = width - text_width - margin, height - text_height - margin

                # If both are present and in same position, offset text
                if image_wm_path and position != "center":
                    y += int(height * (scale / 100)) + 5

                palette = {
                    "white": (255, 255, 255),
                    "black": (0, 0, 0),
                    "red": (255, 60, 60),
                    "blue": (80, 160, 255),
                    "gold": (255, 200, 60),
                }
                fill_color = palette.get(color, palette["white"])
                shadow_offset = max(1, int(font_size * 0.05))

                alpha_val = int(opacity * 255)
                main_fill = (*fill_color, alpha_val)
                shadow_fill = (0, 0, 0, int(alpha_val * 0.75))

                def draw_text_effect(
                    target_draw: ImageDraw.ImageDraw, px: int, py: int, st: str
                ) -> None:
                    if st in ("soft_shadow", "pattern_grid", "pattern_diagonal", "outline"):
                        target_draw.text(
                            (px + shadow_offset, py + shadow_offset),
                            text,
                            font=font,
                            fill=shadow_fill,
                        )
                    if st == "outline":
                        target_draw.text(
                            (px - shadow_offset, py), text, font=font, fill=shadow_fill
                        )
                        target_draw.text(
                            (px + shadow_offset, py), text, font=font, fill=shadow_fill
                        )
                        target_draw.text(
                            (px, py - shadow_offset), text, font=font, fill=shadow_fill
                        )
                        target_draw.text(
                            (px, py + shadow_offset), text, font=font, fill=shadow_fill
                        )
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

            out = Image.alpha_composite(img, overlay)

            ext = Path(output_path).suffix.lower()
            if ext in (".webp", ".png"):
                out.save(output_path, quality=90 if ext == ".webp" else None)
            else:
                out.convert("RGB").save(output_path, "JPEG", quality=90)

            return True
    except Exception:
        logger.exception(f"Error applying watermark to {image_path}")
        return False
