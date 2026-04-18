import contextlib
import os
import random
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from src.utils.i18n import at, t

P = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
F = os.path.join(P, "assets", "fonts")


@lru_cache(maxsize=4)
def get_font(n, s):
    path = os.path.join(F, n)
    with contextlib.suppress(Exception):
        return ImageFont.truetype(path, s) if os.path.exists(path) else None


def generate_math_captcha():
    a, b = random.randint(1, 20), random.randint(1, 20)
    mx, mn = max(a, b), min(a, b)
    op, res = random.choice([("+", a + b), ("-", mx - mn)])
    return (f"{mx} - {mn} = ?" if op == "-" else f"{a} + {b} = ?"), str(res)


async def generate_poll_captcha(c_id):
    a, b = random.randint(1, 10), random.randint(1, 10)
    cor = a + b
    opts = [str(cor), str(cor + random.randint(1, 3)), str(cor - random.randint(1, 3))]
    random.shuffle(opts)
    return await at(c_id, "captcha.what_is", a=a, b=b), opts, opts.index(str(cor))


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
    "butterfly": "🦋",
    "pizza": "🍕",
    "cactus": "🌵",
    "umbrella": "☂️",
    "diamond": "💎",
    "duck": "🦆",
    "fire": "🔥",
    "cloud": "☁️",
    "rocket": "🚀",
    "crown": "👑",
    "key": "🔑",
    "bell": "🔔",
    "cupcake": "🧁",
    "heart": "❤️",
    "ghost": "👻",
    "alien": "👽",
    "mushroom": "🍄",
    "snowflake": "❄️",
    "balloon": "🎈",
    "gift": "🎁",
}


def generate_image_captcha(lang="en"):
    w, h = 400, 150
    img = Image.new("RGB", (w, h), (random.randint(230, 255),) * 3)
    draw, tx_f, em_f = (
        ImageDraw.Draw(img),
        get_font("DejaVuSans.ttf", 80),
        get_font("NotoColorEmoji.ttf", 109),
    )
    names = list(CAPTCHA_OBJECTS.keys())
    sel = random.sample(names, 3)
    tar = random.choice(sel)
    pos = [(20, 15), (145, 15), (270, 15)]
    random.shuffle(pos)
    t_pos = None

    for n, p in zip(sel, pos, strict=True):
        fp = (p[0] + random.randint(-5, 5), p[1] + random.randint(-5, 5))
        if em_f:
            draw.text(fp, CAPTCHA_OBJECTS[n], font=em_f, embedded_color=True)
        else:
            draw.text(fp, t(lang, f"captcha.object.{n}").upper(), font=tx_f, fill=(0, 0, 0))
        if n == tar:
            t_pos = fp

    if t_pos:
        cx, cy, r = t_pos[0] + 55, t_pos[1] + 60, 65
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline="red", width=5)

    for _ in range(random.randint(8, 12)):
        draw.line(
            [
                random.randint(0, w),
                random.randint(0, h),
                random.randint(0, w),
                random.randint(0, h),
            ],
            fill=(random.randint(100, 200),) * 3,
            width=random.randint(1, 3),
        )

    for _ in range(random.randint(500, 1000)):
        draw.point(
            [random.randint(0, w), random.randint(0, h)], fill=(random.randint(150, 220),) * 3
        )

    b_io = BytesIO()
    img.filter(ImageFilter.SMOOTH).save(b_io, "PNG")
    b_io.seek(0)

    opts = set(sel)
    while len(opts) < 4:
        opts.add(random.choice(names))
    return b_io, tar, sorted(list(opts), key=lambda _: random.random())
