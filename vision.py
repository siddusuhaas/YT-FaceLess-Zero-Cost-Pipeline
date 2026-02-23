"""
vision.py — Module 3: Image Generation via Draw Things HTTP API
================================================================
Sends image prompts to the Draw Things app running locally on port 7888.
Draw Things must be running with its HTTP API server enabled.

How to enable Draw Things API:
  1. Open Draw Things app
  2. Go to Settings → API Server
  3. Enable "HTTP API Server" on port 7888

Output files:
    output/image_0.png ... output/image_N.png

Draw Things API Reference:
  POST http://localhost:7888/sdapi/v1/txt2img
  Body: { "prompt": str, "width": int, "height": int, ... }
  Response: { "images": [base64_string, ...] }
"""

import base64
import json
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from PIL import Image
import io

# ── Configuration ─────────────────────────────────────────────────────────────
DRAW_THINGS_URL = "http://localhost:7888"
TXT2IMG_ENDPOINT = f"{DRAW_THINGS_URL}/sdapi/v1/txt2img"
API_TIMEOUT = 300  # 5 minutes per image (generous for complex prompts)

# Output canvas: 1080×1920 (9:16 vertical for YouTube Shorts)
# Draw Things generates square images; we'll crop/pad in assembly.py
# Requesting portrait directly for best results
IMAGE_WIDTH = 768
IMAGE_HEIGHT = 1344   # ~9:16 ratio at 768 width

OUTPUT_DIR = Path("output")

# ── Default Generation Parameters ─────────────────────────────────────────────
DEFAULT_PARAMS = {
    "width": IMAGE_WIDTH,
    "height": IMAGE_HEIGHT,
    "steps": 25,                    # Good quality/speed balance
    "cfg_scale": 7.5,               # Prompt adherence
    "sampler_name": "DPM++ 2M Karras",
    "negative_prompt": (
        "ugly, blurry, low quality, distorted, deformed, modern clothing, "
        "western art style, cartoon, anime, text, watermark, signature, "
        "nsfw, violence, gore, modern buildings, cars, technology"
    ),
    "restore_faces": False,
    "tiling": False,
    "n_iter": 1,
    "batch_size": 1,
}


# ── API Health Check ──────────────────────────────────────────────────────────

def check_draw_things_running(verbose: bool = True) -> bool:
    """
    Check if Draw Things HTTP API is accessible.

    Returns:
        True if API is reachable, False otherwise
    """
    try:
        response = requests.get(f"{DRAW_THINGS_URL}/sdapi/v1/sd-models", timeout=5)
        if response.status_code == 200:
            if verbose:
                print(f"   ✅ Draw Things API is running at {DRAW_THINGS_URL}")
            return True
        else:
            if verbose:
                print(f"   ⚠️  Draw Things API returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        if verbose:
            print(f"   ❌ Cannot connect to Draw Things at {DRAW_THINGS_URL}")
            print(f"   ℹ️  Please open Draw Things app and enable:")
            print(f"       Settings → API Server → Enable HTTP API (port 7888)")
        return False
    except Exception as e:
        if verbose:
            print(f"   ❌ Draw Things check failed: {e}")
        return False


# ── Single Image Generation ───────────────────────────────────────────────────

def generate_single_image(
    prompt: str,
    output_path: Path,
    seed: int = -1,
    verbose: bool = True
) -> Optional[Path]:
    """
    Generate a single image via Draw Things API.

    Args:
        prompt: The image generation prompt
        output_path: Where to save the PNG file
        seed: Random seed (-1 for random)
        verbose: Whether to print progress

    Returns:
        Path to saved image, or None on failure
    """
    payload = {
        **DEFAULT_PARAMS,
        "prompt": prompt,
        "seed": seed,
    }

    try:
        if verbose:
            # Show truncated prompt
            short_prompt = prompt[:80] + "..." if len(prompt) > 80 else prompt
            print(f"   🎨 Generating: \"{short_prompt}\"")

        start_time = time.time()
        response = requests.post(
            TXT2IMG_ENDPOINT,
            json=payload,
            timeout=API_TIMEOUT
        )
        elapsed = time.time() - start_time

        if response.status_code != 200:
            print(f"   ❌ API error {response.status_code}: {response.text[:200]}")
            return None

        data = response.json()

        # Extract base64 image
        images = data.get("images", [])
        if not images:
            print(f"   ❌ No images in API response")
            return None

        # Decode and save
        img_data = base64.b64decode(images[0])
        img = Image.open(io.BytesIO(img_data))

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save as PNG
        img.save(str(output_path), "PNG")

        if verbose:
            w, h = img.size
            print(f"   ✅ Saved: {output_path} ({w}×{h}, {elapsed:.1f}s)")

        return output_path

    except requests.exceptions.Timeout:
        print(f"   ❌ Request timed out after {API_TIMEOUT}s")
        return None
    except requests.exceptions.ConnectionError:
        print(f"   ❌ Lost connection to Draw Things API")
        return None
    except Exception as e:
        print(f"   ❌ Image generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


# ── Batch Image Generation ────────────────────────────────────────────────────

def generate_images(
    image_prompts: list,
    verbose: bool = True
) -> list[Path]:
    """
    Generate all images for the video from a list of prompts.

    Args:
        image_prompts: List of prompt strings (5-6 items)
        verbose: Whether to print progress

    Returns:
        List of Paths to generated images (may be shorter than input if some fail)
    """
    OUTPUT_DIR.mkdir(exist_ok=True)

    if verbose:
        print(f"\n🖼️  [vision.py] Generating {len(image_prompts)} images via Draw Things...")
        print(f"   Resolution: {IMAGE_WIDTH}×{IMAGE_HEIGHT} (portrait 9:16)")
        print(f"   API: {DRAW_THINGS_URL}")

    # Check API availability
    if not check_draw_things_running(verbose=verbose):
        print("\n   ❌ Draw Things is not running. Cannot generate images.")
        print("   ℹ️  Tip: You can still test the pipeline with placeholder images.")
        print("   ℹ️  Run: python main.py --no-images \"<topic>\"")
        return []

    generated_paths = []

    for i, prompt in enumerate(image_prompts):
        output_path = OUTPUT_DIR / f"image_{i}.png"

        if verbose:
            print(f"\n   [{i+1}/{len(image_prompts)}] Image {i+1}:")

        path = generate_single_image(
            prompt=prompt,
            output_path=output_path,
            seed=-1,  # Random seed for variety
            verbose=verbose
        )

        if path:
            generated_paths.append(path)
        else:
            print(f"   ⚠️  Skipping image {i+1} due to generation failure")

    if verbose:
        print(f"\n   📊 Generated {len(generated_paths)}/{len(image_prompts)} images successfully")

    return generated_paths


# ── Placeholder Image Generator (for --no-images mode) ───────────────────────

def generate_placeholder_images(count: int = 5, verbose: bool = True) -> list[Path]:
    """
    Generate simple gradient placeholder images for testing without Draw Things.
    Creates visually distinct colored gradient images at full resolution.

    Args:
        count: Number of placeholder images to create
        verbose: Whether to print progress

    Returns:
        List of Paths to placeholder images
    """
    import numpy as np

    OUTPUT_DIR.mkdir(exist_ok=True)

    if verbose:
        print(f"\n🖼️  [vision.py] Generating {count} placeholder images (no Draw Things)...")

    # Rich color palettes inspired by Indian art
    color_schemes = [
        ((139, 69, 19), (255, 215, 0)),    # Saffron/Gold — sacred fire
        ((25, 25, 112), (138, 43, 226)),    # Midnight blue/Purple — cosmic
        ((0, 100, 0), (255, 165, 0)),       # Forest green/Orange — nature
        ((128, 0, 0), (255, 215, 0)),       # Deep red/Gold — royalty
        ((0, 0, 139), (135, 206, 235)),     # Deep blue/Sky — divine
    ]

    paths = []
    for i in range(count):
        output_path = OUTPUT_DIR / f"image_{i}.png"
        color1, color2 = color_schemes[i % len(color_schemes)]

        # Create gradient image
        img_array = np.zeros((IMAGE_HEIGHT, IMAGE_WIDTH, 3), dtype=np.uint8)
        for y in range(IMAGE_HEIGHT):
            t = y / IMAGE_HEIGHT
            r = int(color1[0] * (1 - t) + color2[0] * t)
            g = int(color1[1] * (1 - t) + color2[1] * t)
            b = int(color1[2] * (1 - t) + color2[2] * t)
            img_array[y, :] = [r, g, b]

        img = Image.fromarray(img_array)
        img.save(str(output_path), "PNG")
        paths.append(output_path)

        if verbose:
            print(f"   ✅ Placeholder {i+1}: {output_path}")

    return paths


# ── CLI Entry Point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_prompts = [
        (
            "Lord Krishna standing on the battlefield of Kurukshetra, holding a divine conch shell, "
            "golden divine aura surrounding him, Arjuna kneeling before him in despair, "
            "thousands of warriors in the background, dramatic sunset sky with orange and purple clouds, "
            "epic oil painting, ancient Indian art style, dramatic golden hour lighting, "
            "Mughal miniature meets photorealism, rich jewel tones, cinematic composition, "
            "8K resolution, hyper-detailed, no text, no watermarks"
        ),
        (
            "Ancient Sanskrit manuscript open on a stone altar, glowing golden text, "
            "lotus flowers surrounding it, soft divine light rays from above, "
            "ancient Indian temple interior, incense smoke, peaceful atmosphere, "
            "epic oil painting, ancient Indian art style, dramatic golden hour lighting, "
            "8K resolution, hyper-detailed"
        ),
    ]

    if "--placeholder" in sys.argv:
        paths = generate_placeholder_images(count=5)
    else:
        paths = generate_images(test_prompts)

    if paths:
        print(f"\n✅ Generated {len(paths)} images:")
        for p in paths:
            print(f"   {p}")
    else:
        print("❌ No images generated.")
        sys.exit(1)
