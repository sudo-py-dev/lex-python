import os

import pytest
from PIL import Image

from src.utils.media import apply_watermark


@pytest.fixture
def test_images(tmp_path):
    """Create temporary images for testing."""
    src_path = tmp_path / "source.png"
    wm_path = tmp_path / "watermark.png"
    out_path = tmp_path / "output.png"

    # Create a 1000x1000 base image (blue background)
    Image.new("RGB", (1000, 1000), (0, 0, 255)).save(src_path)
    # Create a 200x200 watermark image (semi-transparent white)
    Image.new("RGBA", (200, 200), (255, 255, 255, 128)).save(wm_path)

    return str(src_path), str(wm_path), str(out_path)


def test_apply_text_watermark(test_images):
    src, _, out = test_images
    result = apply_watermark(
        src,
        text="@TestChannel",
        output_path=out,
        color="white",
        style="soft_shadow",
        position="bottom_right",
    )
    assert result is True
    assert os.path.exists(out)

    # Verify we can open the result
    with Image.open(out) as img:
        assert img.size == (1000, 1000)


def test_apply_image_watermark(test_images):
    src, wm, out = test_images
    result = apply_watermark(
        src, text="", output_path=out, image_wm_path=wm, position="top_left", opacity=0.5, scale=20
    )
    assert result is True
    assert os.path.exists(out)

    with Image.open(out) as img:
        assert img.size == (1000, 1000)


def test_apply_combined_watermark(test_images):
    src, wm, out = test_images
    result = apply_watermark(
        src,
        text="@Combined",
        output_path=out,
        image_wm_path=wm,
        position="center",
        opacity=0.8,
        scale=15,
    )
    assert result is True
    assert os.path.exists(out)


def test_watermark_positions(test_images):
    src, _, out = test_images
    positions = ["top_left", "top_right", "bottom_left", "bottom_right", "center"]
    for pos in positions:
        result = apply_watermark(src, "POS TEST", out, position=pos)
        assert result is True
        assert os.path.exists(out)


def test_watermark_styles_and_colors(test_images):
    src, _, out = test_images
    # Test a few combinations of colors and styles
    combinations = [
        ("red", "outline"),
        ("gold", "clean"),
        ("blue", "pattern_grid"),
        ("black", "pattern_diagonal"),
    ]
    for color, style in combinations:
        result = apply_watermark(src, "STYLE TEST", out, color=color, style=style)
        assert result is True
        assert os.path.exists(out)


def test_invalid_source_path(tmp_path):
    src = tmp_path / "non_existent.png"
    out = tmp_path / "output.png"
    result = apply_watermark(str(src), "FAIL", str(out))
    assert result is False


def test_image_watermark_scaling(test_images):
    src, wm, out = test_images
    # Test very small and very large scale
    for scale in [5, 50]:
        result = apply_watermark(src, "", out, image_wm_path=wm, scale=scale)
        assert result is True
        assert os.path.exists(out)
