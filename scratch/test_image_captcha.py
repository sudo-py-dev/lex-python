"""Test script for image CAPTCHA generation with emojis."""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.captcha_utils import CAPTCHA_OBJECTS, generate_image_captcha


async def main():
    """Generate a test image captcha and save it."""
    print("Testing image CAPTCHA generation...")
    print(f"Available emoji objects: {CAPTCHA_OBJECTS}")
    print()

    # Generate captcha with English locale
    img_bytes, target, options = generate_image_captcha(lang="en")

    print(f"Target (circled): {target}")
    print(f"Target emoji: {CAPTCHA_OBJECTS.get(target, 'N/A')}")
    print(f"Button options: {options}")
    print(f"Button emojis: {[CAPTCHA_OBJECTS.get(o, '?') for o in options]}")
    print()

    # Save the image
    output_path = os.path.join(os.path.dirname(__file__), "test_captcha_output.png")
    with open(output_path, "wb") as f:
        f.write(img_bytes.getvalue())

    print(f"✅ Test image saved to: {output_path}")
    print()

    # Verify file exists and has content
    if os.path.exists(output_path):
        size = os.path.getsize(output_path)
        print(f"✅ File exists with size: {size} bytes")
        if size > 1000:
            print("✅ Image appears to be valid (size > 1KB)")
        else:
            print("⚠️ Warning: Image seems too small, may be invalid")
    else:
        print("❌ Error: File was not created")

    return output_path


if __name__ == "__main__":
    result = asyncio.run(main())
    print(f"\nDone! Check the image at: {result}")
