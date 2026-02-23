"""
assembly.py — Module 4: Video Assembly with Ken Burns Effect + Dynamic Captions
=================================================================================
Assembles the final YouTube Short (1080×1920, 9:16) from:
  - Audio: output/narration.mp3
  - Images: output/image_0.png ... image_N.png
  - Timestamps: output/timestamps.json

Features:
  - Ken Burns effect (slow zoom/pan) on every image
  - Image swap every 8-12 seconds with crossfade
  - Word-level dynamic captions burned into video center
  - White text with thick black stroke (anti-slop style)
  - Final render: output/final_video.mp4 (H.264, AAC audio)
"""

import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
)
from moviepy.video.fx.all import fadein, fadeout

# ── Configuration ─────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("output")
AUDIO_FILE = OUTPUT_DIR / "narration.mp3"
TIMESTAMPS_FILE = OUTPUT_DIR / "timestamps.json"
FINAL_VIDEO = OUTPUT_DIR / "final_video.mp4"

# Video specs — YouTube Shorts standard
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_FPS = 30

# Ken Burns settings
ZOOM_FACTOR = 1.12        # Max zoom level (12% zoom-in)
PAN_RANGE_X = 40          # Max horizontal pan in pixels
PAN_RANGE_Y = 25          # Max vertical pan in pixels

# Image display timing
MIN_IMAGE_DURATION = 8.0   # seconds
MAX_IMAGE_DURATION = 12.0  # seconds
CROSSFADE_DURATION = 0.6   # seconds

# Caption styling
CAPTION_FONT_SIZE = 72
CAPTION_Y_POSITION = 0.62  # 62% from top (center-lower area)
CAPTION_STROKE_WIDTH = 6
CAPTION_COLOR = (255, 255, 255)       # White
CAPTION_STROKE_COLOR = (0, 0, 0)      # Black
CAPTION_BG_ALPHA = 140                # Semi-transparent background (0-255)
CAPTION_BG_PADDING = 20              # Pixels of padding around text


# ── Font Loading ──────────────────────────────────────────────────────────────

def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a bold font, falling back through common system fonts."""
    font_candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "/System/Library/Fonts/SFNSDisplay-Bold.otf",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    for font_path in font_candidates:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                continue
    # Ultimate fallback: PIL default (no stroke, but won't crash)
    return ImageFont.load_default()


# ── Image Preprocessing ───────────────────────────────────────────────────────

def _prepare_image(image_path: Path) -> np.ndarray:
    """
    Load and resize image to fill the video canvas (cover mode).
    Returns numpy array of shape (VIDEO_HEIGHT, VIDEO_WIDTH, 3).
    """
    img = Image.open(str(image_path)).convert("RGB")
    orig_w, orig_h = img.size

    # Scale to cover the canvas (maintain aspect ratio, crop excess)
    # Add extra margin for Ken Burns zoom headroom
    target_w = int(VIDEO_WIDTH * ZOOM_FACTOR) + PAN_RANGE_X * 2
    target_h = int(VIDEO_HEIGHT * ZOOM_FACTOR) + PAN_RANGE_Y * 2

    scale = max(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Center crop to target size
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))

    return np.array(img)


# ── Ken Burns Effect ──────────────────────────────────────────────────────────

def _make_ken_burns_clip(
    image_path: Path,
    duration: float,
    direction: int = 0,
) -> ImageClip:
    """
    Create a Ken Burns (slow zoom + pan) video clip from a single image.

    Args:
        image_path: Path to the source image
        duration: Duration of the clip in seconds
        direction: 0-3 for different zoom/pan directions (variety)

    Returns:
        MoviePy ImageClip with Ken Burns animation
    """
    img_array = _prepare_image(image_path)
    src_h, src_w = img_array.shape[:2]

    # Define start/end zoom and pan based on direction
    directions = [
        # (start_zoom, end_zoom, start_pan_x, end_pan_x, start_pan_y, end_pan_y)
        (1.0, ZOOM_FACTOR, 0, PAN_RANGE_X, 0, PAN_RANGE_Y),          # zoom in, pan right-down
        (ZOOM_FACTOR, 1.0, PAN_RANGE_X, 0, PAN_RANGE_Y, 0),          # zoom out, pan left-up
        (1.0, ZOOM_FACTOR, PAN_RANGE_X, 0, 0, PAN_RANGE_Y),          # zoom in, pan left-down
        (ZOOM_FACTOR, 1.0, 0, PAN_RANGE_X, PAN_RANGE_Y, 0),          # zoom out, pan right-up
    ]
    start_z, end_z, spx, epx, spy, epy = directions[direction % 4]

    def make_frame(t: float) -> np.ndarray:
        """Generate a single frame at time t with Ken Burns transform."""
        progress = t / duration  # 0.0 → 1.0

        # Interpolate zoom and pan
        zoom = start_z + (end_z - start_z) * progress
        pan_x = int(spx + (epx - spx) * progress)
        pan_y = int(spy + (epy - spy) * progress)

        # Calculate crop dimensions at current zoom level
        crop_w = int(VIDEO_WIDTH / zoom)
        crop_h = int(VIDEO_HEIGHT / zoom)

        # Center of the source image
        center_x = src_w // 2 + pan_x
        center_y = src_h // 2 + pan_y

        # Crop coordinates
        x1 = max(0, center_x - crop_w // 2)
        y1 = max(0, center_y - crop_h // 2)
        x2 = min(src_w, x1 + crop_w)
        y2 = min(src_h, y1 + crop_h)

        # Adjust if we hit boundaries
        if x2 - x1 < crop_w:
            x1 = max(0, x2 - crop_w)
        if y2 - y1 < crop_h:
            y1 = max(0, y2 - crop_h)

        # Crop and resize to video dimensions
        cropped = img_array[y1:y2, x1:x2]
        frame_img = Image.fromarray(cropped).resize(
            (VIDEO_WIDTH, VIDEO_HEIGHT), Image.BILINEAR
        )
        return np.array(frame_img)

    clip = ImageClip(make_frame=make_frame, duration=duration)
    clip = clip.set_fps(VIDEO_FPS)
    return clip


# ── Caption Frame Renderer ────────────────────────────────────────────────────

def _render_caption_frame(
    text: str,
    frame_size: tuple = (VIDEO_WIDTH, VIDEO_HEIGHT),
) -> np.ndarray:
    """
    Render a single caption frame as a transparent RGBA numpy array.
    White text with thick black stroke on a semi-transparent dark background.

    Returns:
        RGBA numpy array of shape (VIDEO_HEIGHT, VIDEO_WIDTH, 4)
    """
    font = _get_font(CAPTION_FONT_SIZE)

    # Create transparent canvas
    canvas = Image.new("RGBA", frame_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # Measure text dimensions
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    # Center horizontally, position at CAPTION_Y_POSITION vertically
    x = (frame_size[0] - text_w) // 2
    y = int(frame_size[1] * CAPTION_Y_POSITION) - text_h // 2

    # Draw semi-transparent background pill
    bg_x1 = x - CAPTION_BG_PADDING
    bg_y1 = y - CAPTION_BG_PADDING
    bg_x2 = x + text_w + CAPTION_BG_PADDING
    bg_y2 = y + text_h + CAPTION_BG_PADDING
    draw.rounded_rectangle(
        [bg_x1, bg_y1, bg_x2, bg_y2],
        radius=15,
        fill=(0, 0, 0, CAPTION_BG_ALPHA)
    )

    # Draw black stroke (outline) by drawing text offset in 8 directions
    stroke_offsets = [
        (-CAPTION_STROKE_WIDTH, -CAPTION_STROKE_WIDTH),
        (0, -CAPTION_STROKE_WIDTH),
        (CAPTION_STROKE_WIDTH, -CAPTION_STROKE_WIDTH),
        (-CAPTION_STROKE_WIDTH, 0),
        (CAPTION_STROKE_WIDTH, 0),
        (-CAPTION_STROKE_WIDTH, CAPTION_STROKE_WIDTH),
        (0, CAPTION_STROKE_WIDTH),
        (CAPTION_STROKE_WIDTH, CAPTION_STROKE_WIDTH),
    ]
    for ox, oy in stroke_offsets:
        draw.text(
            (x + ox, y + oy),
            text,
            font=font,
            fill=(*CAPTION_STROKE_COLOR, 255)
        )

    # Draw white text on top
    draw.text((x, y), text, font=font, fill=(*CAPTION_COLOR, 255))

    return np.array(canvas)


# ── Caption Clip Builder ──────────────────────────────────────────────────────

def _build_caption_clips(
    caption_chunks: list,
    total_duration: float,
) -> list:
    """
    Build a list of MoviePy ImageClips for each caption chunk.

    Args:
        caption_chunks: List of {"text": str, "start": float, "end": float}
        total_duration: Total video duration in seconds

    Returns:
        List of positioned ImageClips with correct start/end times
    """
    caption_clips = []

    for chunk in caption_chunks:
        text = chunk["text"].strip()
        start = chunk["start"]
        end = min(chunk["end"], total_duration)
        duration = end - start

        if duration <= 0 or not text:
            continue

        # Render caption frame as RGBA
        frame_rgba = _render_caption_frame(text)

        # Convert RGBA to RGB + mask
        frame_rgb = frame_rgba[:, :, :3]
        frame_alpha = frame_rgba[:, :, 3] / 255.0

        # Create ImageClip from the caption frame
        caption_clip = (
            ImageClip(frame_rgb, ismask=False)
            .set_start(start)
            .set_duration(duration)
            .set_opacity(1.0)
        )

        # Apply alpha mask
        mask_clip = ImageClip(frame_alpha, ismask=True).set_duration(duration)
        caption_clip = caption_clip.set_mask(mask_clip).set_start(start)

        caption_clips.append(caption_clip)

    return caption_clips


# ── Main Assembly Function ────────────────────────────────────────────────────

def assemble_video(
    image_paths: list,
    audio_path: Path,
    caption_chunks: list,
    output_path: Path = FINAL_VIDEO,
    verbose: bool = True,
) -> Optional[Path]:
    """
    Assemble the final YouTube Short video.

    Args:
        image_paths: List of Paths to generated images
        audio_path: Path to narration MP3
        caption_chunks: List of {"text", "start", "end"} dicts
        output_path: Where to save the final MP4
        verbose: Whether to print progress

    Returns:
        Path to final video, or None on failure
    """
    if verbose:
        print(f"\n🎬 [assembly.py] Assembling final video...")
        print(f"   Canvas: {VIDEO_WIDTH}×{VIDEO_HEIGHT} @ {VIDEO_FPS}fps")
        print(f"   Images: {len(image_paths)}")
        print(f"   Captions: {len(caption_chunks)} chunks")

    OUTPUT_DIR.mkdir(exist_ok=True)

    # ── Load Audio ────────────────────────────────────────────────────────────
    if verbose:
        print(f"\n   📻 Loading audio: {audio_path}")
    try:
        audio_clip = AudioFileClip(str(audio_path))
        total_duration = audio_clip.duration
        if verbose:
            print(f"   ✅ Audio duration: {total_duration:.1f}s")
    except Exception as e:
        print(f"   ❌ Failed to load audio: {e}")
        return None

    # ── Distribute Images Across Timeline ─────────────────────────────────────
    if not image_paths:
        print("   ❌ No images provided for assembly.")
        return None

    num_images = len(image_paths)
    # Distribute duration evenly, clamped to min/max
    base_duration = total_duration / num_images
    image_duration = max(MIN_IMAGE_DURATION, min(MAX_IMAGE_DURATION, base_duration))

    if verbose:
        print(f"\n   🖼️  Building {num_images} Ken Burns clips ({image_duration:.1f}s each)...")

    # ── Build Ken Burns Clips ─────────────────────────────────────────────────
    kb_clips = []
    current_time = 0.0

    for i, img_path in enumerate(image_paths):
        # Last image fills remaining duration
        if i == num_images - 1:
            clip_duration = max(MIN_IMAGE_DURATION, total_duration - current_time + CROSSFADE_DURATION)
        else:
            clip_duration = image_duration + CROSSFADE_DURATION  # overlap for crossfade

        if verbose:
            print(f"   [{i+1}/{num_images}] Ken Burns on {img_path.name} ({clip_duration:.1f}s)...")

        try:
            kb_clip = _make_ken_burns_clip(
                image_path=img_path,
                duration=clip_duration,
                direction=i,  # Alternate directions for variety
            )

            # Apply fade in/out for crossfade effect
            if i > 0:
                kb_clip = fadein(kb_clip, CROSSFADE_DURATION)
            if i < num_images - 1:
                kb_clip = fadeout(kb_clip, CROSSFADE_DURATION)

            kb_clip = kb_clip.set_start(current_time)
            kb_clips.append(kb_clip)

        except Exception as e:
            print(f"   ⚠️  Ken Burns failed for image {i+1}: {e}")
            # Fallback: static image clip
            try:
                img_array = _prepare_image(img_path)
                static_clip = (
                    ImageClip(img_array[:VIDEO_HEIGHT, :VIDEO_WIDTH])
                    .set_duration(clip_duration)
                    .set_start(current_time)
                )
                kb_clips.append(static_clip)
            except Exception as e2:
                print(f"   ❌ Static fallback also failed: {e2}")

        current_time += image_duration  # Advance by base duration (not clip_duration)

    if not kb_clips:
        print("   ❌ No video clips could be created.")
        return None

    # ── Composite Background ──────────────────────────────────────────────────
    if verbose:
        print(f"\n   🎞️  Compositing background clips...")

    background = CompositeVideoClip(kb_clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    background = background.set_duration(total_duration)

    # ── Build Caption Overlay ─────────────────────────────────────────────────
    if verbose:
        print(f"   💬 Building {len(caption_chunks)} caption overlays...")

    caption_clips = _build_caption_clips(caption_chunks, total_duration)

    if verbose:
        print(f"   ✅ {len(caption_clips)} caption clips created")

    # ── Final Composite ───────────────────────────────────────────────────────
    all_clips = [background] + caption_clips
    final_video = CompositeVideoClip(all_clips, size=(VIDEO_WIDTH, VIDEO_HEIGHT))
    final_video = final_video.set_audio(audio_clip)
    final_video = final_video.set_duration(total_duration)

    # ── Render to File ────────────────────────────────────────────────────────
    if verbose:
        print(f"\n   🔄 Rendering final video to {output_path}...")
        print(f"   ⏳ This may take 2-5 minutes depending on video length...")

    render_start = time.time()
    try:
        final_video.write_videofile(
            str(output_path),
            fps=VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            ffmpeg_params=[
                "-crf", "18",          # High quality (lower = better, 18 is near-lossless)
                "-preset", "medium",   # Encoding speed/quality balance
                "-pix_fmt", "yuv420p", # Maximum compatibility
                "-movflags", "+faststart",  # Web-optimized (metadata at start)
            ],
            threads=4,                 # Use multiple CPU cores
            logger=None if not verbose else "bar",
        )

        render_elapsed = time.time() - render_start

        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            if verbose:
                print(f"\n   ✅ Video rendered in {render_elapsed:.1f}s")
                print(f"   📁 Output: {output_path} ({size_mb:.1f} MB)")
                print(f"   📐 Specs: {VIDEO_WIDTH}×{VIDEO_HEIGHT}, {VIDEO_FPS}fps, {total_duration:.1f}s")
            return output_path
        else:
            print("   ❌ Output file was not created.")
            return None

    except Exception as e:
        print(f"   ❌ Video rendering failed: {e}")
        import traceback
        traceback.print_exc()
        return None

    finally:
        # Clean up MoviePy resources
        try:
            audio_clip.close()
            final_video.close()
        except Exception:
            pass


# ── CLI Entry Point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Load existing output files for testing
    print("🎬 assembly.py — Testing with existing output files...")

    # Check required files
    missing = []
    if not AUDIO_FILE.exists():
        missing.append(str(AUDIO_FILE))
    if not TIMESTAMPS_FILE.exists():
        missing.append(str(TIMESTAMPS_FILE))

    image_files = sorted(OUTPUT_DIR.glob("image_*.png")) if OUTPUT_DIR.exists() else []
    if not image_files:
        missing.append("output/image_*.png")

    if missing:
        print(f"❌ Missing required files: {', '.join(missing)}")
        print("   Run voice.py and vision.py first, or use main.py for the full pipeline.")
        sys.exit(1)

    # Load timestamps
    with open(TIMESTAMPS_FILE, "r") as f:
        chunks = json.load(f)

    print(f"   Found {len(image_files)} images, {len(chunks)} caption chunks")

    result = assemble_video(
        image_paths=image_files,
        audio_path=AUDIO_FILE,
        caption_chunks=chunks,
    )

    if result:
        print(f"\n✅ Video ready: {result}")
    else:
        print("❌ Assembly failed.")
        sys.exit(1)
