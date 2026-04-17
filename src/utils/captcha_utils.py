import contextlib
import os
import random
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from src.utils.i18n import at, t


def generate_math_captcha():
    """Generates a simple math problem and its answer."""
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    ops = [("+", a + b), ("-", max(a, b) - min(a, b))]
    op_char, result = random.choice(ops)
    problem = f"{max(a, b)} - {min(a, b)} = ?" if op_char == "-" else f"{a} + {b} = ?"
    return problem, str(result)


async def generate_poll_captcha(chat_id: int):
    """Generates a simple poll question for captcha."""
    a = random.randint(1, 10)
    b = random.randint(1, 10)
    correct = a + b
    options = [
        str(correct),
        str(correct + random.randint(1, 3)),
        str(correct - random.randint(1, 3)),
    ]
    random.shuffle(options)
    correct_index = options.index(str(correct))
    question = await at(chat_id, "captcha.what_is", a=a, b=b)
    return question, options, correct_index


CAPTCHA_OBJECTS = {
    "apple": "🍎",
    "car": "🚗",
    "dog": "🐶",
    "cat": "🐱",
    "banana": "🍌",
    "soccer": "⚽",
    "guitar": "🎸",
    "robot": "🤖",
    "plane": "✈️",
    "tree": "🌳",
    "house": "🏠",
    "sun": "☀️",
}


def generate_image_captcha(lang: str = "en"):
    """Generates a Multi-Modal Logic Challenge CAPTCHA image with random emojis and a target marker."""
    width, height = 400, 150
    bg_color = (random.randint(230, 255), random.randint(230, 255), random.randint(230, 255))
    image = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(image)

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assets_dir = os.path.join(base_dir, "assets")
    text_font_path = os.path.join(assets_dir, "fonts", "DejaVuSans.ttf")

    text_font = None

    if os.path.exists(text_font_path):
        with contextlib.suppress(Exception):
            text_font = ImageFont.truetype(text_font_path, 80)

    all_names = list(CAPTCHA_OBJECTS.keys())
    selected_names = random.sample(all_names, 3)
    target_name = random.choice(selected_names)

    positions = [(40, 20), (160, 20), (280, 20)]
    random.shuffle(positions)

    target_pos = None

    for name, pos in zip(selected_names, positions, strict=True):
        final_pos = (pos[0] + random.randint(-10, 10), pos[1] + random.randint(-5, 5))

        localized_name = t(lang, f"captcha.object.{name}")
        # Always use text labels - PIL doesn't support color emoji fonts
        draw.text(final_pos, localized_name.upper(), font=text_font, fill=(0, 0, 0))

        if name == target_name:
            target_pos = final_pos

    if target_pos:
        r = 55
        cx, cy = target_pos[0] + 50, target_pos[1] + 55
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline="red", width=5)

    for _ in range(random.randint(8, 12)):
        line_color = (random.randint(100, 200), random.randint(100, 200), random.randint(100, 200))
        draw.line(
            [
                random.randint(0, width),
                random.randint(0, height),
                random.randint(0, width),
                random.randint(0, height),
            ],
            fill=line_color,
            width=random.randint(1, 3),
        )

    for _ in range(random.randint(500, 1000)):
        dot_color = (random.randint(150, 220), random.randint(150, 220), random.randint(150, 220))
        draw.point([random.randint(0, width), random.randint(0, height)], fill=dot_color)

    image = image.filter(ImageFilter.SMOOTH)

    byte_io = BytesIO()
    image.save(byte_io, "PNG")
    byte_io.seek(0)

    options = set(selected_names)
    while len(options) < 4:
        options.add(random.choice(all_names))

    all_options = list(options)
    random.shuffle(all_options)

    return byte_io, target_name, all_options
