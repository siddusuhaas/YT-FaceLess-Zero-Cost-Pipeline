"""
vision.py — Module 3: Image Generation
=======================================
Supports three configurable backends via IMAGE_BACKEND:

  "local"  → Draw Things only (FLUX.1 Schnell via HTTP API on port 7888)
  "gemini" → Google Gemini Nano Banana only
  "both"   → Runs BOTH in parallel; saves image_N_local.png + image_N_gemini.png
              so you can compare side-by-side and pick the winner

─────────────────────────────────────────────────────────────────
QUICK SETUP FOR GEMINI:
  1. Go to https://aistudio.google.com/app/apikey
  2. Create an API key (free tier available via AI Studio)
  3. Set GEMINI_API_KEY below (or export GEMINI_API_KEY=... in terminal)
  4. Run: pip install google-genai
─────────────────────────────────────────────────────────────────

GEMINI MODEL OPTIONS + PRICING (per image):
  "gemini-2.5-flash-image-preview"  ← Nano Banana — ~$0.04/img ✅ DEFAULT
  "gemini-3.1-flash-image-preview"  ← Nano Banana 2 — faster, ~$0.05/img
  "gemini-3-pro-image-preview"      ← Nano Banana Pro — best quality, ~$0.12/img
  "imagen-3.0-fast-generate-001"    ← Imagen 3 Flash — FREE tier (limited), lower quality

NOTE: Gemini native image gen uses generate_content() with IMAGE modality,
NOT generate_images() — that's a different API for Imagen models only.
"""

import base64
import concurrent.futures
import io
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

# ══════════════════════════════════════════════════════════════════════════════
# ██  CONFIGURATION — EDIT THESE  ████████████████████████████████████████████
# ══════════════════════════════════════════════════════════════════════════════

# ── Which backend to use ─────────────────────────────────────────────────────
#   "local"  → Draw Things only
#   "gemini" → Gemini Nano Banana only
#   "both"   → Both in parallel (for comparison)
IMAGE_BACKEND = "gemini"

# ── Gemini settings ───────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")

# Nano Banana — ~$0.04/image, best balance of quality/cost
# GEMINI_MODEL = "gemini-2.5-flash-image-preview"

# Alternatives (uncomment to switch):
GEMINI_MODEL = "gemini-3.1-flash-image-preview"      # Nano Banana 2 — faster
# GEMINI_MODEL = "gemini-3-pro-image-preview"           # Nano Banana Pro — highest quality
# GEMINI_MODEL = "imagen-3.0-fast-generate-001"         # Imagen 3 Flash — free tier, uses generate_images() API

# ── Local Draw Things settings ────────────────────────────────────────────────
DRAW_THINGS_URL = "http://localhost:7888"
TXT2IMG_ENDPOINT = f"{DRAW_THINGS_URL}/sdapi/v1/txt2img"

IMAGE_WIDTH = 768
IMAGE_HEIGHT = 1344   # 9:16 portrait

LOCAL_PARAMS = {
    "width": IMAGE_WIDTH,
    "height": IMAGE_HEIGHT,
    "steps": 8,
    "cfg_scale": 1.0,
    "sampler_name": "Euler A Trailing",
    "shift": 3.17,
    "n_iter": 1,
    "batch_size": 1,
}

NEGATIVE_PROMPT = (
    "text, letters, words, title, caption, watermark, signature, logo, label, "
    "any writing, english text, hindi text, "
    "photorealistic, photograph, 3d render, 3d cgi, "
    "western comic, marvel style, dc style, manga, anime, "
    "blurry, low quality, deformed, extra limbs, bad anatomy, "
    "distorted face, disfigured, dark background"
)

API_TIMEOUT = 600
OUTPUT_DIR = Path("output")

# ══════════════════════════════════════════════════════════════════════════════


# ── Gemini Client (lazy init) ─────────────────────────────────────────────────

_gemini_client = None

def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        try:
            from google import genai
            _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        except ImportError:
            raise ImportError(
                "google-genai package not installed.\n"
                "Run: pip install google-genai"
            )
    return _gemini_client


# ── Local: Draw Things ────────────────────────────────────────────────────────

def _check_draw_things(verbose: bool = True) -> bool:
    try:
        response = requests.get(DRAW_THINGS_URL, timeout=5)
        if response.status_code == 200:
            if verbose:
                print(f"   ✅ Draw Things running at {DRAW_THINGS_URL}")
            return True
        return False
    except Exception:
        if verbose:
            print(f"   ❌ Draw Things not reachable at {DRAW_THINGS_URL}")
        return False


def _generate_local(prompt: str, output_path: Path, verbose: bool = True) -> Optional[Path]:
    """Generate one image via local Draw Things API."""
    payload = {
        **LOCAL_PARAMS,
        "prompt": prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "seed": -1,
    }
    try:
        if verbose:
            short = prompt[:80] + "..." if len(prompt) > 80 else prompt
            print(f"      [LOCAL] 🎨 {short}")

        t = time.time()
        resp = requests.post(TXT2IMG_ENDPOINT, json=payload, timeout=API_TIMEOUT)
        elapsed = time.time() - t

        if resp.status_code != 200:
            print(f"      [LOCAL] ❌ HTTP {resp.status_code}: {resp.text[:100]}")
            return None

        images = resp.json().get("images", [])
        if not images:
            print(f"      [LOCAL] ❌ No images in response")
            return None

        img = Image.open(io.BytesIO(base64.b64decode(images[0])))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), "PNG")

        if verbose:
            print(f"      [LOCAL] ✅ {output_path.name} ({img.width}×{img.height}, {elapsed:.1f}s)")
        return output_path

    except Exception as e:
        print(f"      [LOCAL] ❌ Failed: {e}")
        return None


# ── Gemini: Nano Banana ───────────────────────────────────────────────────────

def _generate_gemini(prompt: str, output_path: Path, verbose: bool = True) -> Optional[Path]:
    """
    Generate one image via Gemini Nano Banana API.

    IMPORTANT: Nano Banana (gemini-*-image-*) uses generate_content() with
    response_modalities=[Modality.IMAGE] — NOT generate_images() which is
    the Imagen-only API and will throw a 404 for these models.
    """
    try:
        from google.genai import types
        from google.genai.types import GenerateContentConfig, Modality

        client = _get_gemini_client()

        if verbose:
            short = prompt[:80] + "..." if len(prompt) > 80 else prompt
            print(f"      [GEMINI] 🎨 {short}")

        t = time.time()

        # generate_content() has no negative_prompt or aspect_ratio params,
        # so we inject both constraints directly into the prompt text.
        portrait_prompt = (
            f"{prompt}. "
            "IMPORTANT RULES: "
            "1. Generate as a tall vertical portrait image, 9:16 aspect ratio, taller than wide, for mobile phone screen. "
            "2. NO text, NO speech bubbles, NO dialogue boxes, NO captions, NO labels, NO letters, NO words, NO Hindi text, NO English text anywhere in the image. "
            "3. Pure illustration only, zero text elements."
        )

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=portrait_prompt,
            config=GenerateContentConfig(
                response_modalities=[Modality.IMAGE],
            )
        )

        elapsed = time.time() - t

        # Extract image from response parts
        img_data = None
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                img_data = part.inline_data.data
                break

        if img_data is None:
            print(f"      [GEMINI] ❌ No image in response (may have been filtered)")
            return None

        img = Image.open(io.BytesIO(img_data))

        # Safety net: if Gemini still returned landscape, force-crop to portrait
        w, h = img.size
        if w > h:
            # Crop centre square then resize to 9:16
            side = min(w, h)
            left = (w - side) // 2
            img = img.crop((left, 0, left + side, side))
            img = img.resize((IMAGE_WIDTH, IMAGE_HEIGHT), Image.LANCZOS)
            if verbose:
                print(f"      [GEMINI] ⚠️  Landscape detected ({w}×{h}) — auto-cropped to portrait")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), "PNG")

        if verbose:
            print(f"      [GEMINI] ✅ {output_path.name} ({img.width}×{img.height}, {elapsed:.1f}s)")
        return output_path

    except Exception as e:
        err = str(e)
        if "API_KEY" in err or "api key" in err.lower() or "credentials" in err.lower():
            print(f"      [GEMINI] ❌ Invalid API key. Get yours: https://aistudio.google.com/app/apikey")
        elif "quota" in err.lower() or "429" in err:
            print(f"      [GEMINI] ⚠️  Rate limit hit. Waiting 15s...")
            time.sleep(15)
        elif "not found" in err.lower() or "404" in err:
            print(f"      [GEMINI] ❌ Model '{GEMINI_MODEL}' not found. Check GEMINI_MODEL in vision.py")
        elif "billing" in err.lower() or "payment" in err.lower():
            print(f"      [GEMINI] ❌ Billing required for this model. Enable at: https://aistudio.google.com")
        else:
            print(f"      [GEMINI] ❌ Failed: {e}")
        return None


# ── Single Image Dispatcher ───────────────────────────────────────────────────

def generate_single_image(
    prompt: str,
    output_path: Path,
    verbose: bool = True,
) -> Optional[Path]:
    """
    Route to the correct backend based on IMAGE_BACKEND setting.

    "both" mode: saves image_N_local.png + image_N_gemini.png in parallel.
    Returns local result as primary (so the rest of the pipeline works normally).
    """
    if IMAGE_BACKEND == "local":
        return _generate_local(prompt, output_path, verbose)

    elif IMAGE_BACKEND == "gemini":
        return _generate_gemini(prompt, output_path, verbose)

    elif IMAGE_BACKEND == "both":
        stem = output_path.stem       # "image_0"
        parent = output_path.parent
        local_path = parent / f"{stem}_local.png"
        gemini_path = parent / f"{stem}_gemini.png"

        # Run both backends in parallel threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_local = executor.submit(_generate_local, prompt, local_path, verbose)
            future_gemini = executor.submit(_generate_gemini, prompt, gemini_path, verbose)
            local_result = future_local.result()
            gemini_result = future_gemini.result()

        # Return whichever succeeded — prefer local as primary
        return local_result or gemini_result

    else:
        print(f"   ❌ Unknown IMAGE_BACKEND: '{IMAGE_BACKEND}'. Use 'local', 'gemini', or 'both'.")
        return None


# ── Batch Generation ──────────────────────────────────────────────────────────

def generate_images(
    image_prompts: list,
    output_dir: Path = OUTPUT_DIR,
    verbose: bool = True,
) -> list[Path]:
    """Generate all images for a video."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"\n🖼️  [vision.py] Generating {len(image_prompts)} images...")
        print(f"   Backend: {IMAGE_BACKEND.upper()}")
        if IMAGE_BACKEND in ("local", "both"):
            print(f"   Local:   Draw Things @ {DRAW_THINGS_URL} ({LOCAL_PARAMS['steps']} steps)")
        if IMAGE_BACKEND in ("gemini", "both"):
            print(f"   Gemini:  {GEMINI_MODEL}")
        if IMAGE_BACKEND == "both":
            print(f"   ℹ️  Saves image_N_local.png + image_N_gemini.png — compare and choose!")

    # Pre-flight checks
    local_ok = True
    gemini_ok = True

    if IMAGE_BACKEND in ("local", "both"):
        local_ok = _check_draw_things(verbose)
        if not local_ok and IMAGE_BACKEND == "local":
            print("   ❌ Draw Things not running. Use --no-images or set IMAGE_BACKEND='gemini'")
            return []

    if IMAGE_BACKEND in ("gemini", "both"):
        if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
            print("   ❌ GEMINI_API_KEY not set in vision.py")
            print("      Get free key at: https://aistudio.google.com/app/apikey")
            gemini_ok = False
            if IMAGE_BACKEND == "gemini":
                return []

    generated_paths = []

    for i, prompt in enumerate(image_prompts):
        output_path = output_dir / f"image_{i}.png"

        if verbose:
            print(f"\n   [{i+1}/{len(image_prompts)}] Image {i+1}:")

        # Gentle rate limiting for Gemini-only mode (free tier: 10 req/min)
        if IMAGE_BACKEND == "gemini" and i > 0:
            time.sleep(6)

        path = generate_single_image(
            prompt=prompt,
            output_path=output_path,
            verbose=verbose,
        )

        if path:
            generated_paths.append(path)
        else:
            print(f"   ⚠️  Skipping image {i+1}")

    if verbose:
        print(f"\n   📊 Generated {len(generated_paths)}/{len(image_prompts)} images")
        if IMAGE_BACKEND == "both":
            local_count = len(list(output_dir.glob("image_*_local.png")))
            gemini_count = len(list(output_dir.glob("image_*_gemini.png")))
            print(f"   📁 Local:  {local_count} files (image_N_local.png)")
            print(f"   📁 Gemini: {gemini_count} files (image_N_gemini.png)")
            print(f"\n   👀 Open output folder and compare both sets!")
            print(f"      Then set IMAGE_BACKEND = 'local' or 'gemini' to pick your winner.")

    return generated_paths


# ── Placeholder Generator ─────────────────────────────────────────────────────

def generate_placeholder_images(count: int = 8, output_dir: Path = OUTPUT_DIR, verbose: bool = True) -> list[Path]:
    import numpy as np
    output_dir.mkdir(parents=True, exist_ok=True)
    if verbose:
        print(f"\n🖼️  [vision.py] Generating {count} placeholder images...")

    color_schemes = [
        ((139, 69, 19), (255, 215, 0)),
        ((25, 25, 112), (138, 43, 226)),
        ((0, 100, 0), (255, 165, 0)),
        ((128, 0, 0), (255, 215, 0)),
        ((0, 0, 139), (135, 206, 235)),
        ((80, 20, 120), (255, 200, 0)),
        ((20, 80, 40), (255, 140, 0)),
        ((100, 0, 50), (255, 220, 100)),
    ]

    paths = []
    for i in range(count):
        output_path = output_dir / f"image_{i}.png"
        c1, c2 = color_schemes[i % len(color_schemes)]
        arr = __import__("numpy").zeros((IMAGE_HEIGHT, IMAGE_WIDTH, 3), dtype=__import__("numpy").uint8)
        for y in range(IMAGE_HEIGHT):
            t = y / IMAGE_HEIGHT
            arr[y] = [int(c1[j] * (1 - t) + c2[j] * t) for j in range(3)]
        Image.fromarray(arr).save(str(output_path), "PNG")
        paths.append(output_path)
        if verbose:
            print(f"   ✅ Placeholder {i+1}: {output_path}")
    return paths


# ── CLI Entry Point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--placeholder" in sys.argv:
        paths = generate_placeholder_images(count=8)
    else:
        test_prompt = (
            "Amar Chitra Katha comic book panel, vibrant flat colors, bold black ink outlines, cel-shaded, "
            "blue-skinned slim young male Krishna, short curly black hair, peacock feather in golden crown, "
            "yellow silk dhoti, bare chest with tulsi bead necklace, "
            "placing hand on shoulder of brown-skinned muscular warrior Arjuna, "
            "long straight black hair, golden chest plate armor, white dhoti, "
            "wooden chariot, dust rising, golden sunset backlight"
        )
        print(f"🔧 Testing with IMAGE_BACKEND = '{IMAGE_BACKEND}'\n")
        paths = generate_images([test_prompt], output_dir=OUTPUT_DIR)

    if paths:
        print(f"\n✅ Done: {len(paths)} image(s) generated")
        for p in paths:
            print(f"   {p}")
    else:
        print("❌ No images generated.")
        sys.exit(1)